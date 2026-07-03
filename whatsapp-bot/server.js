const express = require('express')
const qrcode = require('qrcode-terminal')
const { Client, LocalAuth } = require('whatsapp-web.js')

const app = express()
app.use(express.json({ limit: '1mb' }))

let ready = false
const defaultRecipient = process.env.WHATSAPP_GROUP_ID || ''
const client = new Client({
  authStrategy: new LocalAuth({ dataPath: process.env.WHATSAPP_SESSION_PATH || '/data/session' }),
  puppeteer: { executablePath: process.env.PUPPETEER_EXECUTABLE_PATH, args: ['--no-sandbox', '--disable-setuid-sandbox'] }
})

client.on('qr', (qr) => qrcode.generate(qr, { small: true }))
client.on('ready', () => { ready = true; console.log('WhatsApp bot is ready') })
client.on('disconnected', (reason) => { ready = false; console.log('WhatsApp bot disconnected:', reason) })
client.initialize()

app.get('/health', (_, res) => res.json({ status: 'ok', ready }))
app.post('/send', async (req, res) => {
  if (!ready) return res.status(503).json({ error: 'whatsapp_not_ready' })
  const message = (req.body.message || '').trim()
  const recipient = (req.body.recipient || defaultRecipient || '').trim()
  if (!message) return res.status(400).json({ error: 'message required' })
  if (!recipient) return res.status(400).json({ error: 'recipient required' })
  const result = await client.sendMessage(recipient, message)
  res.json({ status: 'sent', id: result.id?._serialized || null })
})

app.listen(process.env.PORT || 3000, () => console.log(`WhatsApp bot listening`))
