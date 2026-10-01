const fs = require('fs')
const path = require('path')

function clearProfileLocks(root) {
  if (!fs.existsSync(root)) return
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const file = path.join(root, entry.name)
    if (entry.isDirectory()) clearProfileLocks(file)
    else if (['SingletonLock', 'SingletonSocket', 'SingletonCookie'].includes(entry.name)) fs.rmSync(file, { force: true })
  }
}

function createSession({ createClient, renderQr, backendUrl = '', botToken = '', sessionPath = process.env.WHATSAPP_SESSION_PATH || '/data/session', reconnectDelay = 5000 }) {
  let client, qrImage = null, state = 'starting', lastError = null, restarting = false, reconnectTimer, qrVersion = 0
  const settledClients = new WeakSet()
  const info = () => ({ ready: state === 'ready', state, provider: 'whatsapp_web', message: {
    starting: 'WhatsApp is starting.', qr_required: 'Scan the QR code in WhatsApp → Linked devices → Link a device.',
    authenticated: 'WhatsApp is linked and loading.', ready: 'WhatsApp is connected.',
    disconnected: 'WhatsApp disconnected. Reconnecting…', error: 'WhatsApp could not connect. Try reconnecting or reset the session.'
  }[state], error: lastError, qr_image: qrImage })

  function scheduleReconnect() {
    if (restarting || reconnectTimer) return
    reconnectTimer = setTimeout(() => { reconnectTimer = null; restart(false).catch(console.error) }, reconnectDelay)
    reconnectTimer.unref?.()
  }

  function start() {
    clearProfileLocks(sessionPath)
    state = 'starting'; qrImage = null; lastError = null
    const current = createClient()
    client = current
    current.on('qr', async (qr) => {
      if (client !== current) return
      const version = ++qrVersion
      state = 'qr_required'; qrImage = null
      try {
        const image = await renderQr(qr)
        if (client === current && state === 'qr_required' && version === qrVersion) qrImage = image
      } catch (error) { lastError = error.message }
    })
    current.on('authenticated', () => { if (client === current) { state = 'authenticated'; qrImage = null } })
    current.on('ready', () => { if (client === current) { state = 'ready'; qrImage = null; lastError = null; console.log('WhatsApp bot is ready') } })
    current.on('auth_failure', (message) => { if (client === current) { state = 'error'; qrImage = null; lastError = String(message) } })
    current.on('disconnected', (reason) => {
      if (client !== current) return
      state = 'disconnected'; qrImage = null; lastError = String(reason)
      scheduleReconnect()
    })
    current.on('vote_update', async (vote) => {
      if (client !== current || !backendUrl) return
      try {
        const contact = await current.getContactById(vote.voter)
        const response = await fetch(`${backendUrl.replace(/\/$/, '')}/api/whatsapp/poll-vote`, {
          method: 'POST', signal: AbortSignal.timeout(10000),
          headers: { 'Content-Type': 'application/json', ...(botToken ? { 'X-Bot-Token': botToken } : {}) },
          body: JSON.stringify({ poll_message_id: vote.parentMessage?.id?._serialized || vote.parentMsgKey?._serialized || '', voter: contact?.number || vote.voter || '', selected_option: vote.selectedOptions?.[0]?.name || '' })
        })
        if (!response.ok) console.warn('WhatsApp vote was not applied:', response.status)
      } catch (error) { console.error('Failed to forward WhatsApp poll response:', error.message) }
    })
    Promise.resolve().then(() => current.initialize()).catch((error) => {
      if (client !== current) return
      state = 'error'; qrImage = null; lastError = error.message
      console.error('WhatsApp initialization failed:', error.message)
    }).finally(() => settledClients.add(current))
  }

  async function restart(reset) {
    if (restarting) throw new Error('WhatsApp is already reconnecting')
    restarting = true
    clearTimeout(reconnectTimer); reconnectTimer = null
    const previous = client
    client = null; state = 'starting'; qrImage = null
    try {
      if (previous) {
        // Initialization waits for pairing. Close its browser before launching
        // another client, so two clients cannot share one Chromium profile.
        for (let attempt = 0; !previous.pupBrowser && !settledClients.has(previous) && attempt < 50; attempt++) {
          await new Promise((resolve) => setTimeout(resolve, 100))
        }
        if (!previous.pupBrowser && !settledClients.has(previous)) throw new Error('Browser is still starting. Wait a moment and reconnect again.')
        if (previous.pupBrowser) await previous.destroy()
        if (reset) await previous.authStrategy.logout()
      }
      start()
    } catch (error) {
      client = previous; state = 'error'; lastError = error.message
      throw error
    } finally { restarting = false }
  }
  return { start, restart, info, getClient: () => client }
}

module.exports = { createSession, clearProfileLocks }
