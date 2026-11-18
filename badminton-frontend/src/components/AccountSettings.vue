<template>
  <div class="space-y-5">
    <h1 class="text-2xl font-bold">Account settings</h1>
    <section class="panel-card space-y-4" aria-labelledby="whatsapp-settings">
      <h2 id="whatsapp-settings" class="text-xl font-semibold">WhatsApp</h2>
      <p class="section-copy">Link your account to check invoices and the next booking in a private chat with the club bot.</p>
      <p v-if="status" role="status">{{ status.linked ? 'Linked' : 'Not linked' }}</p>
      <p v-if="status && !status.available && !status.linked" class="section-copy">WhatsApp linking is currently unavailable.</p>
      <p v-if="error" class="text-red-700" role="alert">{{ error }}</p>
      <div v-if="pending" class="space-y-2 rounded-lg bg-slate-50 p-4">
        <p>Send this message to the club bot in a private chat within 10 minutes.</p>
        <p><code class="select-all font-semibold">{{ pending.message }}</code></p>
        <a v-if="pending.whatsapp_url" class="btn-primary inline-flex" :href="pending.whatsapp_url" target="_blank" rel="noopener noreferrer">Open WhatsApp</a>
      </div>
      <div class="flex flex-wrap gap-2">
        <button v-if="status?.available && !status.linked" class="btn-primary" :disabled="busy" @click="update('POST')">
          {{ pending ? 'Generate new code' : 'Link WhatsApp' }}
        </button>
        <button v-if="status?.linked || pending" class="btn-muted" :disabled="busy" @click="update('DELETE')">
          {{ status.linked ? 'Unlink' : 'Cancel code' }}
        </button>
        <button class="btn-muted" :disabled="busy" @click="update()">{{ busy ? 'Please wait…' : 'Refresh status' }}</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getSessionValue } from '../authSession'

const status = ref(null)
const pending = ref(null)
const busy = ref(false)
const error = ref('')
let expiryTimer

function clearPending() {
  clearTimeout(expiryTimer)
  pending.value = null
}

async function update(method = 'GET') {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    const response = await fetch('/api/account/whatsapp', {
      method,
      headers: { Authorization: `Bearer ${getSessionValue('auth_token')}` },
      cache: 'no-store'
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error === 'missing_authorization' ? 'Sign in again to manage WhatsApp.' : data.error)
    if (method === 'POST') {
      clearPending()
      pending.value = data
      expiryTimer = setTimeout(clearPending, Math.max(0, Date.parse(data.expires_at) - Date.now()))
    } else {
      status.value = { ...status.value, ...data }
      if (data.linked || method === 'DELETE') clearPending()
    }
  } catch (err) {
    error.value = err.message || 'Could not update WhatsApp settings.'
  } finally {
    busy.value = false
  }
}

const refreshOnFocus = () => update()
onMounted(() => {
  update()
  window.addEventListener('focus', refreshOnFocus)
})
onBeforeUnmount(() => {
  clearPending()
  window.removeEventListener('focus', refreshOnFocus)
})
</script>
