const provider = process.env.WHATSAPP_PROVIDER || 'whatsapp_web'
if (provider === 'meta_cloud_api') {
  require('./meta-server')
} else if (provider === 'whatsapp_web') {
  const { Client, LocalAuth, Poll, MessageMedia } = require('whatsapp-web.js')
  const qrcode = require('qrcode')
  const terminalQr = require('qrcode-terminal')
  const { createSession } = require('./session')
  const { createWebApp } = require('./web-app')
  const session = createSession({
    createClient: () => new Client({
      authStrategy: new LocalAuth({ dataPath: process.env.WHATSAPP_SESSION_PATH || '/data/session' }),
      puppeteer: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
      }
    }),
    renderQr: async (qr) => {
      terminalQr.generate(qr, { small: true })
      return qrcode.toDataURL(qr, { margin: 2, width: 320 })
    },
    backendUrl: process.env.BACKEND_URL,
    botToken: process.env.WHATSAPP_BOT_TOKEN
  })
  createWebApp({ session, Poll, MessageMedia }).listen(process.env.PORT || 3000, () => {
    console.log('QR-linked WhatsApp bot listening')
    session.start()
  })
} else {
  throw new Error(`Unknown WHATSAPP_PROVIDER: ${provider}`)
}
