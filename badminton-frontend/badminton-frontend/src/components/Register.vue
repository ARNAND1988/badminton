<template>
  <div>
    <h2 class="text-2xl font-semibold mb-4">Register / Login via WhatsApp OTP</h2>
    <form @submit.prevent="sendOtp" class="space-y-4">
      <div>
        <label class="block text-sm font-medium">Phone (E.164, e.g. +1234567890)</label>
        <input v-model="phone" class="mt-1 block w-full rounded border-gray-300 p-2" />
      </div>
      <div>
        <label class="block text-sm font-medium">Name (optional)</label>
        <input v-model="name" class="mt-1 block w-full rounded border-gray-300 p-2" />
      </div>
      <div>
        <button class="px-4 py-2 bg-blue-600 text-white rounded">Send OTP</button>
      </div>
    </form>
    <div class="mt-4 text-sm text-gray-700" v-if="msg" v-html="msg"></div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

export default {
  setup() {
    const phone = ref('')
    const name = ref('')
    const msg = ref('')
    const router = useRouter()

    async function sendOtp() {
      msg.value = ''
      try {
        const res = await fetch('/api/auth/send-otp', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ phone: phone.value, name: name.value })
        })
        const data = await res.json()
        if (res.ok) {
          if (data.mock_otp) {
            localStorage.setItem('mock_otp', data.mock_otp)
            localStorage.setItem('mock_phone', phone.value)
            msg.value = `OTP (mock) sent: <strong>${data.mock_otp}</strong>. <a href="/verify">Verify</a>`
          } else {
            msg.value = 'OTP sent. <a href="/verify">Verify</a>'
          }
          // navigate to verify page automatically
          setTimeout(()=>router.push('/verify'), 600)
        } else {
          msg.value = data.error || JSON.stringify(data)
        }
      } catch (err) {
        msg.value = 'Error sending OTP.'
      }
    }

    return { phone, name, msg, sendOtp }
  }
}
</script>
