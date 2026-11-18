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

test('private QR chat forwards verified sender metadata and replies only to the original chat', async () => {
  const http = require('node:http')
  const callbacks = []
  const replies = []
  const backend = http.createServer(async (req, res) => {
    const chunks = []
    for await (const chunk of req) chunks.push(chunk)
    callbacks.push({ url: req.url, token: req.headers['x-bot-token'], body: JSON.parse(Buffer.concat(chunks)) })
    if (callbacks.length === 2) return res.writeHead(204).end()
    res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ reply: 'Member reply' }))
  })
  await new Promise((resolve) => backend.listen(0, '127.0.0.1', resolve))
  try {
    const { clients } = fixture({ backendUrl: `http://127.0.0.1:${backend.address().port}`, botToken: 'fixture-token' })
    const [client] = clients
    client.emit('ready')
    client.getContactLidAndPhone = async (ids) => {
      assert.deepEqual(ids, ['31600000000@c.us'])
      return [{ lid: '12345@lid' }]
    }
    client.sendMessage = async (...args) => replies.push(args)
    const [receive] = client.listeners('message')
    const message = { type: 'chat', body: '  balance  ', id: { _serialized: 'message-1' }, from: '31600000000@c.us' }
    await receive({ ...message, from: '111@g.us', author: '12345@lid' })
    await receive({ ...message, fromMe: true })
    await receive({ ...message, isStatus: true })
    assert.equal(callbacks.length, 0)

    await receive(message)
    await receive({ ...message, from: '12345@lid' })
    assert.deepEqual(callbacks, Array(2).fill({
      url: '/internal/whatsapp/member-message',
      token: 'fixture-token',
      body: { provider: 'whatsapp_web', message_id: 'message-1', sender: '12345@lid', text: '  balance  ', private: true }
    }))
    assert.deepEqual(replies, [['31600000000@c.us', 'Member reply', { linkPreview: false }]])
    client.getContactLidAndPhone = async () => []
    await receive({ ...message, body: 'MENU', id: { _serialized: 'unresolved' } })
    assert.equal(callbacks[2].body.sender, message.from)
    assert.deepEqual(replies[1], [message.from, 'Member reply', { linkPreview: false }])
  } finally {
    await new Promise((resolve) => backend.close(resolve))
  }
})

test('MENU continues to the verification reply when WhatsApp identity lookup stalls', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const callbacks = []
  t.mock.method(global, 'fetch', async (_url, options) => {
    callbacks.push(JSON.parse(options.body))
    return Response.json({ reply: 'Identity unavailable' })
  })
  const { clients } = fixture({ backendUrl: 'http://backend.invalid', botToken: 'fixture-token' })
  const [client] = clients
  const replies = []
  client.getContactLidAndPhone = () => new Promise(() => {})
  client.sendMessage = async (...args) => replies.push(args)
  client.emit('ready')
  const [receive] = client.listeners('message')
  const from = '31600000000@c.us'
  const handling = receive({ from, type: 'chat', body: 'MENU', id: { _serialized: 'menu-1' } })
  assert.equal(callbacks.length, 0)
  t.mock.timers.tick(5000)
  await handling
  assert.equal(callbacks[0].sender, from)
  assert.deepEqual(replies, [[from, 'Identity unavailable', { linkPreview: false }]])
})

test('accepts device-qualified private chat IDs and split message keys while rejecting group chats', async (t) => {
  const callbacks = []
  t.mock.method(global, 'fetch', async (_url, options) => {
    callbacks.push(JSON.parse(options.body))
    return Response.json({ reply: 'Member menu' })
  })
  const { clients } = fixture({ backendUrl: 'http://backend.invalid', botToken: 'fixture-token' })
  const [client] = clients
  const replies = []
  client.getContactLidAndPhone = async (ids) => {
    assert.deepEqual(ids, ['31600000000@c.us'])
    return [{ lid: '12345@lid' }]
  }
  client.sendMessage = async (...args) => replies.push(args)
  client.emit('ready')
  const [receive] = client.listeners('message')
  const message = { type: 'chat', body: 'MENU', from: '12345:12@lid' }

  await receive({ ...message, id: { remote: '12345:12@lid', id: 'ABC123' } })
  await receive({
    ...message,
    from: '31600000000:7@s.whatsapp.net',
    id: { remote: { _serialized: '31600000000:7@s.whatsapp.net' }, _serialized: 'phone-key' }
  })
  await receive({ ...message, id: { remote: '77@g.us', id: 'GROUP123' } })
  await receive({ ...message, from: '77@g.us', id: { remote: '12345@lid', id: 'GROUP456' } })
  await receive({ ...message, id: {} })

  assert.deepEqual(callbacks.map(({ sender, message_id }) => [sender, message_id]), [
    ['12345@lid', 'false_12345:12@lid_ABC123'],
    ['12345@lid', 'phone-key']
  ])
  assert.deepEqual(replies.map(([address]) => address), ['12345@lid', '31600000000@c.us'])
})
