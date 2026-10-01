const crypto = require('crypto')
const express = require('express')

const app = express()
app.use(express.json({ limit: '1mb', verify: (req, _res, buffer) => { req.rawBody = buffer } }))

const accessToken = process.env.WHATSAPP_ACCESS_TOKEN || ''
const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID || ''
const verifyToken = process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN || ''
const appSecret = process.env.WHATSAPP_APP_SECRET || ''
const graphVersion = process.env.WHATSAPP_GRAPH_API_VERSION || 'v23.0'
const botToken = process.env.WHATSAPP_BOT_TOKEN || ''
const backendUrl = (process.env.BACKEND_URL || '').replace(/\/$/, '')

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
  return supplied.length === expected.length && crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))
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
        const selectedOption = message.interactive?.list_reply?.title || message.interactive?.button_reply?.title || message.text?.body || ''
        const pollMessageId = message.context?.id || ''
        if (!backendUrl || !selectedOption) continue
        try {
          const response = await fetch(`${backendUrl}/api/whatsapp/poll-vote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...(botToken ? { 'X-Bot-Token': botToken } : {}) },
            body: JSON.stringify({ poll_message_id: pollMessageId, voter: message.from, selected_option: selectedOption })
          })
          if (!response.ok) console.warn('WhatsApp response was not applied:', response.status, await response.text())
        } catch (error) {
          console.error('Failed to forward WhatsApp response:', error)
        }
      }
    }
  }
})

app.listen(process.env.PORT || 3000, () => console.log('Meta WhatsApp Cloud API adapter listening'))
