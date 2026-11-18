// The adapters supply only verified inbound metadata and send Flask's reply
// back to the originating chat.
function createMemberMessageForwarder({ backendUrl, botToken, provider }) {
  if (!backendUrl || !botToken || botToken === 'dev-whatsapp-bot-token') return null
  const url = `${backendUrl.replace(/\/$/, '')}/internal/whatsapp/member-message`

  return async ({ id, sender, text, sendReply, trace }) => {
    try {
      const response = await fetch(url, {
        method: 'POST',
        signal: AbortSignal.timeout(10000),
        headers: { 'Content-Type': 'application/json', 'X-Bot-Token': botToken },
        body: JSON.stringify({ provider, message_id: id, sender, text, private: true })
      })
      trace?.(`Flask returned HTTP ${response.status}`)
      if (!response.ok) {
        console.warn('WhatsApp member callback failed:', response.status)
        return
      }
      if (response.status === 204) return
      const { reply } = await response.json()
      if (reply) {
        await sendReply(reply)
        trace?.('reply submitted to WhatsApp')
      } else {
        trace?.('Flask returned no reply')
      }
    } catch {
      // Provider errors may contain message content or credentials.
      console.warn('WhatsApp member message processing failed')
    }
  }
}

module.exports = { createMemberMessageForwarder }
