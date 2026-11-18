const assert = require('node:assert/strict')
const { createHmac } = require('node:crypto')
const { test } = require('node:test')

test('Meta forwards signed private messages, preserves poll handling and sends replies to the verified sender', async () => {
  process.env.WHATSAPP_APP_SECRET = 'test-signing-secret'
  process.env.WHATSAPP_BOT_TOKEN = 'test-backend-token'
  process.env.WHATSAPP_ACCESS_TOKEN = 'test-access-token'
  process.env.WHATSAPP_PHONE_NUMBER_ID = 'test-phone-id'
  process.env.BACKEND_URL = 'https://backend.example'
  const calls = []
  const networkFetch = global.fetch
  let onReply
  global.fetch = async (url, options) => {
    calls.push({ url, headers: options.headers, body: JSON.parse(options.body) })
    if (url.endsWith('/member-message')) {
      if (JSON.parse(options.body).action_id) {
        return Response.json({ reply: 'Member reply', buttons: [{ id: 'member:menu', title: 'Open member menu' }] })
      }
      return Response.json({ reply: 'Member reply' })
    }
    if (url.startsWith('https://graph.facebook.com/')) onReply()
    return Response.json({})
  }

  const server = require('../meta-server').listen(0, '127.0.0.1')
  await new Promise((resolve) => server.once('listening', resolve))
  const url = `http://127.0.0.1:${server.address().port}/webhook`
  const message = { id: 'message-1', from: '31600000000', type: 'text', text: { body: 'BALANCE' } }
  const post = (messages, { signed = true, phone = 'test-phone-id' } = {}) => {
    const body = JSON.stringify({
      entry: [{ changes: [{ field: 'messages', value: { metadata: { phone_number_id: phone }, messages } }] }]
    })
    const signature = 'sha256=' + createHmac('sha256', process.env.WHATSAPP_APP_SECRET).update(body).digest('hex')
    return networkFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Hub-Signature-256': signed ? signature : 'invalid' },
      body
    })
  }

  try {
    assert.equal((await post([message], { signed: false })).status, 401)
    assert.equal((await post([message], { phone: 'other-phone' })).status, 200)
    assert.equal(calls.length, 0)

    const replied = new Promise((resolve) => { onReply = resolve })
    assert.equal((await post([
      { ...message, group_id: 'test-group' },
      { ...message, id: 'poll-1', context: { id: 'original-poll' }, type: 'interactive', interactive: { list_reply: { title: 'Everyone' } } },
      message
    ])).status, 200)
    await replied
    assert.equal(calls.length, 3)
    assert.equal(calls[0].url, 'https://backend.example/api/whatsapp/poll-vote')
    assert.equal(calls[0].body.selected_option, 'Everyone')
    assert.equal(calls[1].url, 'https://backend.example/internal/whatsapp/member-message')
    assert.equal(calls[1].headers['X-Bot-Token'], 'test-backend-token')
    assert.deepEqual(calls[1].body, {
      provider: 'meta_cloud_api', message_id: 'message-1', sender: '31600000000', text: 'BALANCE', private: true
    })
    assert.equal(calls[2].body.to, message.from)
    assert.equal(calls[2].body.text.body, 'Member reply')

    const menuTap = {
      id: 'tap-1', from: message.from, context: { id: 'original-menu' }, type: 'interactive',
      interactive: { type: 'button_reply', button_reply: { id: 'member:balance', title: 'Check balance' } }
    }
    assert.equal((await post([menuTap], { signed: false })).status, 401)
    const tapped = new Promise((resolve) => { onReply = resolve })
    assert.equal((await post([{ ...menuTap, group_id: 'test-group' }, menuTap])).status, 200)
    await tapped
    assert.equal(calls.length, 5)
    assert.equal(calls[3].url, 'https://backend.example/internal/whatsapp/member-message')
    assert.deepEqual(calls[3].body, {
      provider: 'meta_cloud_api', message_id: 'tap-1', sender: message.from, text: '', private: true, action_id: 'member:balance'
    })
    assert.equal(calls[4].body.to, message.from)
    assert.equal(calls[4].body.type, 'interactive')
    assert.deepEqual(calls[4].body.interactive, {
      type: 'button', body: { text: 'Member reply' },
      action: { buttons: [{ type: 'reply', reply: { id: 'member:menu', title: 'Open member menu' } }] }
    })
  } finally {
    global.fetch = networkFetch
    await new Promise((resolve) => server.close(resolve))
  }
})
