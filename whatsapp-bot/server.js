const express = require('express')
const fs = require('fs')
const path = require('path')
const qrcode = require('qrcode-terminal')
const { Client, LocalAuth } = require('whatsapp-web.js')

const app = express()
app.use(express.json({ limit: '1mb' }))

let ready = false
const defaultRecipient = process.env.WHATSAPP_GROUP_ID || ''
const sessionPath = process.env.WHATSAPP_SESSION_PATH || '/data/session'
const botToken = process.env.WHATSAPP_BOT_TOKEN || ''

function clearChromiumProfileLocks(rootPath) {
  if (!fs.existsSync(rootPath)) return
  for (const entry of fs.readdirSync(rootPath, { withFileTypes: true })) {
    const entryPath = path.join(rootPath, entry.name)
    if (entry.isDirectory()) {
      clearChromiumProfileLocks(entryPath)
      continue
    }
    if (entry.name.startsWith('Singleton')) {
      fs.rmSync(entryPath, { force: true })
    }
  }
}

clearChromiumProfileLocks(sessionPath)

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: sessionPath }),
  puppeteer: {
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  }
})

client.on('qr', (qr) => qrcode.generate(qr, { small: true }))
client.on('ready', () => { ready = true; console.log('WhatsApp bot is ready') })
client.on('disconnected', (reason) => { ready = false; console.log('WhatsApp bot disconnected:', reason) })
client.initialize()

function requireBotToken(req, res, next) {
  if (!botToken) return next()
  const suppliedToken = req.get('X-Bot-Token') || ''
  if (suppliedToken !== botToken) return res.status(403).json({ error: 'bot_token_required' })
  return next()
}

app.get('/health', (_, res) => res.json({ status: 'ok', ready }))
app.get('/groups', requireBotToken, async (_, res) => {
  if (!ready) return res.status(503).json({ error: 'whatsapp_not_ready' })
  const chats = await client.getChats()
  const groups = chats
    .filter((chat) => chat.isGroup)
    .map((chat) => ({
      id: chat.id?._serialized || '',
      name: chat.name || chat.formattedTitle || chat.id?._serialized || 'Unnamed group',
      participants_count: Array.isArray(chat.participants) ? chat.participants.length : null
    }))
    .sort((left, right) => left.name.localeCompare(right.name))
  res.json({ groups })
})

app.post('/send', requireBotToken, async (req, res) => {
  if (!ready) return res.status(503).json({ error: 'whatsapp_not_ready' })
  const message = (req.body.message || '').trim()
  const recipient = (req.body.recipient || defaultRecipient || '').trim()
  if (!message) return res.status(400).json({ error: 'message required' })
  if (!recipient) return res.status(400).json({ error: 'recipient required' })
  const result = await client.sendMessage(recipient, message)
  res.json({ status: 'sent', id: result.id?._serialized || null })
})

app.listen(process.env.PORT || 3000, () => console.log(`WhatsApp bot listening`))
