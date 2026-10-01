const { test } = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter } = require('node:events')
const { mkdtempSync, writeFileSync, existsSync, rmSync } = require('node:fs')
const { tmpdir } = require('node:os')
const path = require('node:path')
const { createSession, clearProfileLocks } = require('../session')
const { createWebApp } = require('../web-app')
const tick = () => new Promise((resolve) => setImmediate(resolve))

function fixture(overrides = {}) {
  const clients = []
  const session = createSession({
    sessionPath: '/tmp/nonexistent-whatsapp-test-session', renderQr: async (qr) => `image:${qr}`,
    createClient: () => {
      const client = new EventEmitter()
      client.pupBrowser = {}
      client.initialize = async () => {}
      client.destroy = async () => { client.destroyed = true }
      client.authStrategy = { logout: async () => { client.loggedOut = true } }
      clients.push(client)
      return client
    }, ...overrides
  })
  session.start()
  return { session, clients }
}

test('QR linking transitions through authentication and readiness without leaking stale QR', async () => {
  const { session, clients } = fixture()
  clients[0].emit('qr', 'first'); await tick()
  assert.equal(session.info().qr_image, 'image:first')
  assert.equal(session.info().ready, false)
  clients[0].emit('authenticated')
  assert.equal(session.info().qr_image, null)
  clients[0].emit('ready')
  assert.equal(session.info().ready, true)
  await session.restart(false)
  assert.equal(clients[0].destroyed, true)
  assert.equal(clients[0].loggedOut, undefined)
  clients[0].emit('ready')
  assert.equal(session.info().ready, false)
  await session.restart(true)
  assert.equal(clients[1].loggedOut, true)
  clients[2].emit('qr', 'new'); await tick()
  assert.equal(session.info().qr_image, 'image:new')
})

test('only the latest asynchronously rendered QR code can be displayed', async () => {
  const renders = []
  const { session, clients } = fixture({ renderQr: () => new Promise((resolve) => renders.push(resolve)) })
  clients[0].emit('qr', 'old'); clients[0].emit('qr', 'new')
  renders[1]('new-image'); await tick()
  renders[0]('old-image'); await tick()
  assert.equal(session.info().qr_image, 'new-image')
})

test('disconnection reconnects automatically without logging out the saved account', async () => {
  const { session, clients } = fixture({ reconnectDelay: 1 })
  clients[0].emit('ready')
  clients[0].emit('disconnected', 'network')
  assert.equal(session.info().ready, false)
  await new Promise((resolve) => setTimeout(resolve, 20))
  assert.equal(clients.length, 2)
  assert.equal(clients[0].loggedOut, undefined)
})

test('startup failure remains recoverable', async () => {
  let attempts = 0
  const { session } = fixture({ createClient: () => {
    const client = new EventEmitter()
    client.initialize = async () => { if (++attempts === 1) throw new Error('launch failed') }
    return client
  } })
  await tick()
  assert.equal(session.info().state, 'error')
  await session.restart(false); await tick()
  assert.equal(attempts, 2)
  assert.equal(session.info().state, 'starting')
})

test('startup removes Chromium locks while preserving session files', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'badminton-wa-'))
  try {
    writeFileSync(path.join(root, 'SingletonLock'), 'stale')
    writeFileSync(path.join(root, 'account'), 'keep')
    clearProfileLocks(root)
    assert.equal(existsSync(path.join(root, 'SingletonLock')), false)
    assert.equal(existsSync(path.join(root, 'account')), true)
  } finally { rmSync(root, { recursive: true, force: true }) }
})

test('bot HTTP contract protects QR/reset, gates sends, and supports group notifications and polls', async () => {
  const { session, clients } = fixture()
  const sent = []
  clients[0].sendMessage = async (...args) => { sent.push(args); return { id: { _serialized: 'message-1' } } }
  clients[0].getChats = async () => [{ isGroup: true, id: { _serialized: '123@g.us' }, name: 'Badminton', participants: [{}] }]
  class Poll { constructor(question, choices) { this.question = question; this.choices = choices } }
  const server = createWebApp({ session, Poll, botToken: 'test-secret' }).listen(0, '127.0.0.1')
  await new Promise((resolve) => server.once('listening', resolve))
  const url = `http://127.0.0.1:${server.address().port}`
  const call = (endpoint, body, auth = true) => fetch(url + endpoint, {
    method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json', ...(auth ? { 'X-Bot-Token': 'test-secret' } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body)
  })
  try {
    clients[0].emit('qr', 'private'); await tick()
    assert.equal((await call('/connection', undefined, false)).status, 403)
    assert.equal((await call('/reconnect', {}, false)).status, 403)
    assert.equal((await (await call('/health', undefined, false)).json()).qr_image, undefined)
    assert.equal((await (await call('/connection')).json()).qr_image, 'image:private')
    assert.equal((await call('/send', { recipient: '+31612345678', message: 'reset code' })).status, 503)
    clients[0].emit('ready')
    assert.equal((await call('/send', { recipient: '+31 6 12345678', message: 'reset code' })).status, 200)
    assert.equal(sent[0][0], '31612345678@c.us')
    assert.equal((await call('/send', { recipient: '123@g.us', message: 'booking' })).status, 200)
    assert.equal(sent[1][0], '123@g.us')
    assert.equal((await call('/poll', { recipient: '123@g.us', question: 'Players?', options: ['One', 'Two'] })).status, 200)
    assert.ok(sent[2][1] instanceof Poll)
    assert.equal((await (await call('/groups')).json()).groups[0].id, '123@g.us')
    assert.equal((await call('/reconnect', { reset_session: 'false' })).status, 400)
    clients[0].sendMessage = async () => { throw new Error('offline') }
    assert.equal((await call('/send', { recipient: '123@g.us', message: 'booking' })).status, 502)
    assert.equal((await call('/reconnect', { reset_session: true })).status, 200)
    assert.equal(clients[0].loggedOut, true)
  } finally { await new Promise((resolve) => server.close(resolve)) }
})
