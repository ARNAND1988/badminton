const crypto = require('crypto')
const express = require('express')
const { createMemberMessageForwarder } = require('./member-messages')

const app = express()
app.use(express.json({ limit: '1mb', verify: (req, _res, buffer) => { req.rawBody = buffer } }))

const accessToken = process.env.WHATSAPP_ACCESS_TOKEN || ''
const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID || ''
const verifyToken = process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN || ''
const appSecret = process.env.WHATSAPP_APP_SECRET || ''
const graphVersion = process.env.WHATSAPP_GRAPH_API_VERSION || 'v23.0'
const botToken = process.env.WHATSAPP_BOT_TOKEN || ''
const backendUrl = (process.env.BACKEND_URL || '').replace(/\/$/, '')

// Keep legacy poll behavior while requiring a signed webhook for member data.
const forwardMemberMessage = appSecret && createMemberMessageForwarder({ backendUrl, botToken, provider: 'meta_cloud_api' })

const configured = () => Boolean(accessToken && phoneNumberId)
const digits = (value) => String(value || '').replace(/\D/g, '')

function requireBotToken(req, res, next) {
  if (!botToken || req.get('X-Bot-Token') === botToken) return next()
  return res.status(403).json({ error: 'bot_token_required' })
}

function validSignature(req) {
  if (!appSecret) return true
  const supplied = req.get('X-Hub-Signature-256') || ''
  const expected = `sha256=${crypto.createHmac('sha256', appSecret).update(req.rawBody || Buffer.from('')).digest('hex')}`
  return /^sha256=[a-f0-9]{64}$/.test(supplied) && crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))
}

async function graphMessage(payload) {
  if (!configured()) return { ok: false, status: 503, body: { error: 'meta_cloud_api_not_configured' } }
  const response = await fetch(`https://graph.facebook.com/${graphVersion}/${phoneNumberId}/messages`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ messaging_product: 'whatsapp', ...payload })
  })
  const body = await response.json().catch(() => ({ error: { message: 'Invalid Meta response' } }))
  return { ok: response.ok, status: response.status, body }
}

app.get('/health', (_req, res) => res.json({ status: 'ok', ready: configured(), provider: 'meta_cloud_api' }))
app.get('/', (_req, res) => res.json({ status: 'ok', provider: 'meta_cloud_api', endpoints: ['/health', '/send', '/poll', '/document', '/webhook'] }))
app.get('/groups', requireBotToken, (_req, res) => res.status(400).json({ error: 'groups_not_supported_by_meta_cloud_api' }))

app.post('/send', requireBotToken, async (req, res) => {
  const message = String(req.body.message || '').trim()
  const recipient = digits(req.body.recipient)
  if (!message || !recipient) return res.status(400).json({ error: 'message and recipient required' })
  const result = await graphMessage({ to: recipient, type: 'text', text: { preview_url: true, body: message } })
  return res.status(result.status).json(result.body)
})

app.post('/poll', requireBotToken, async (req, res) => {
  const question = String(req.body.question || '').trim()
  const recipient = digits(req.body.recipient)
  const options = Array.isArray(req.body.options) ? req.body.options.map(String).map((item) => item.trim()).filter(Boolean) : []
  if (!question || !recipient || options.length < 2) return res.status(400).json({ error: 'question, recipient and at least two options required' })
  if (options.length > 10) {
    const result = await graphMessage({
      to: recipient,
      type: 'text',
      text: { body: `${question}\n\n${options.join('\n')}\n\nReply with one or more names separated by commas.`.slice(0, 4096) }
    })
    return res.status(result.status).json(result.body)
  }
  const rows = options.map((title, index) => ({ id: `option_${index}`, title: title.slice(0, 24) }))
  const result = await graphMessage({
    to: recipient,
    type: 'interactive',
    interactive: {
      type: 'list',
      body: { text: question.slice(0, 1024) },
      action: { button: 'Choose players', sections: [{ title: 'Participants', rows }] }
    }
  })
  return res.status(result.status).json(result.body)
})

app.post('/document', requireBotToken, async (req, res) => {
  const recipient = digits(req.body.recipient)
  const link = String(req.body.link || '').trim()
  if (!recipient || !link) return res.status(400).json({ error: 'recipient and link required' })
  const result = await graphMessage({
    to: recipient,
    type: 'document',
    document: { link, filename: String(req.body.filename || 'invoice.pdf'), caption: String(req.body.caption || '') }
  })
  return res.status(result.status).json(result.body)
})

app.get('/webhook', (req, res) => {
  if (req.query['hub.mode'] === 'subscribe' && req.query['hub.verify_token'] === verifyToken) {
    return res.status(200).send(req.query['hub.challenge'])
  }
  return res.sendStatus(403)
})

app.post('/webhook', async (req, res) => {
  if (!validSignature(req)) return res.sendStatus(401)
  res.sendStatus(200)
  for (const entry of req.body.entry || []) {
    for (const change of entry.changes || []) {
      for (const message of change.value?.messages || []) {
        const button = message.interactive?.button_reply
        const actionId = message.type === 'interactive' && message.interactive?.type === 'button_reply' &&
          typeof button?.id === 'string' && button.id.startsWith('member:') ? button.id : null
        const selectedOption = message.interactive?.list_reply?.title || message.interactive?.button_reply?.title || message.text?.body || ''
        const pollMessageId = message.context?.id || ''
        if (!actionId && backendUrl && selectedOption && (pollMessageId || message.interactive)) {
          try {
            const response = await fetch(`${backendUrl}/api/whatsapp/poll-vote`, {
              method: 'POST',
              signal: AbortSignal.timeout(10000),
              headers: { 'Content-Type': 'application/json', ...(botToken ? { 'X-Bot-Token': botToken } : {}) },
              body: JSON.stringify({ poll_message_id: pollMessageId, voter: message.from, selected_option: selectedOption })
            })
            if (response.ok) continue
            if (response.status !== 404 || message.interactive) {
              console.warn('WhatsApp response was not applied:', response.status)
              continue
            }
          } catch {
            console.warn('Failed to forward WhatsApp poll response')
            continue
          }
        }
        if (!forwardMemberMessage || !phoneNumberId || change.field !== 'messages' ||
            change.value.metadata?.phone_number_id !== phoneNumberId ||
            message.group_id || !/^\d{1,32}$/.test(message.from || '') ||
            !message.id || (!actionId && (message.type !== 'text' || !message.text?.body))) continue
        await forwardMemberMessage({
          id: message.id, sender: message.from, text: actionId ? '' : message.text.body, actionId,
          sendReply: async (reply, buttons) => {
            const payload = buttons?.length
              ? {
                  type: 'interactive',
                  interactive: {
                    type: 'button', body: { text: reply },
                    action: { buttons: buttons.map((button) => ({ type: 'reply', reply: button })) }
                  }
                }
              : { type: 'text', text: { preview_url: false, body: reply } }
            const result = await graphMessage({ to: message.from, ...payload })
            if (!result.ok) console.warn('WhatsApp member reply failed:', result.status)
          }
        })
      }
    }
  }
})

module.exports = app
