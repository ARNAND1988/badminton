const express = require('express')

function createWebApp({ session, Poll, MessageMedia, botToken = process.env.WHATSAPP_BOT_TOKEN || '', defaultRecipient = process.env.WHATSAPP_GROUP_ID || '' }) {
  const app = express()
  app.use(express.json({ limit: '1mb' }))
  app.get('/health', (_req, res) => {
    const { qr_image, ...status } = session.info()
    res.json({ status: 'ok', ...status })
  })
  app.use((req, res, next) => {
    if (!botToken || req.get('X-Bot-Token') !== botToken) return res.status(403).json({ error: 'bot_token_required' })
    next()
  })
  app.get('/connection', (_req, res) => res.json(session.info()))
  app.post('/reconnect', async (req, res) => {
    if (req.body.reset_session !== undefined && typeof req.body.reset_session !== 'boolean') return res.status(400).json({ error: 'reset_session must be a boolean' })
    try {
      await session.restart(req.body.reset_session === true)
      res.json({ status: 'reconnecting' })
    } catch (error) { res.status(503).json({ error: error.message }) }
  })
  app.use((req, res, next) => {
    if (!session.info().ready) return res.status(503).json({ error: 'whatsapp_not_ready', message: session.info().message })
    next()
  })
  app.get('/groups', async (_req, res) => {
    try {
      const chats = await session.getClient().getChats()
      res.json({ groups: chats.filter((chat) => chat.isGroup).map((chat) => ({ id: chat.id?._serialized || '', name: chat.name || 'Unnamed group', participants_count: chat.participants?.length || 0 })).sort((a, b) => a.name.localeCompare(b.name)) })
    } catch (error) { res.status(502).json({ error: 'groups_failed', message: error.message }) }
  })
  function recipient(value) {
    const address = String(value || defaultRecipient).trim()
    if (/^\d+(?:-\d+)?@(?:c\.us|g\.us|lid)$/.test(address)) return address
    if (/^\+?[\d\s().-]+$/.test(address)) return `${address.replace(/\D/g, '')}@c.us`
    return null
  }
  for (const endpoint of ['send', 'poll', 'document']) {
    app.post(`/${endpoint}`, async (req, res) => {
      const to = recipient(req.body.recipient)
      if (!to) return res.status(400).json({ error: 'valid recipient required' })
      try {
        let content, options
        if (endpoint === 'send') {
          content = String(req.body.message || '').trim()
          if (!content) return res.status(400).json({ error: 'message required' })
        } else if (endpoint === 'poll') {
          const question = String(req.body.question || '').trim()
          const choices = Array.isArray(req.body.options) ? req.body.options.map(String).map((item) => item.trim()).filter(Boolean) : []
          if (!question || choices.length < 2) return res.status(400).json({ error: 'question and at least two options required' })
          content = new Poll(question, choices, { allowMultipleAnswers: false })
        } else {
          if (!req.body.link) return res.status(400).json({ error: 'link required' })
          content = await MessageMedia.fromUrl(String(req.body.link), { filename: String(req.body.filename || 'invoice.pdf') })
          options = { sendMediaAsDocument: true, caption: String(req.body.caption || '') }
        }
        const result = await session.getClient().sendMessage(to, content, options)
        res.json({ status: 'sent', id: result?.id?._serialized || null })
      } catch (error) { res.status(502).json({ error: 'send_failed', message: error.message }) }
    })
  }
  return app
}

module.exports = { createWebApp }
