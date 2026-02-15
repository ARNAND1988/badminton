<template>
  <div>
    <h2 class="text-2xl font-semibold mb-4">Verify OTP</h2>
    <form @submit.prevent="verify" class="space-y-4">
      <div>
        <label class="block text-sm font-medium">Phone</label>
        <input v-model="phone" class="mt-1 block w-full rounded border-gray-300 p-2" />
      </div>
      <div>
        <label class="block text-sm font-medium">OTP</label>
        <input v-model="otp" class="mt-1 block w-full rounded border-gray-300 p-2" />
      </div>
      <div>
        <button class="px-4 py-2 bg-green-600 text-white rounded">Verify</button>
      </div>
    </form>
    <div class="mt-4 text-sm text-gray-700">{{ msg }}</div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'

export default {
  setup() {
    const phone = ref('')
    const otp = ref('')
    const msg = ref('')

    onMounted(()=>{
      const mockPhone = localStorage.getItem('mock_phone')
      const mockOtp = localStorage.getItem('mock_otp')
      if (mockPhone) phone.value = mockPhone
      if (mockOtp) otp.value = mockOtp
    })

    async function verify() {
      msg.value = ''
      try {
        const res = await fetch('/api/auth/verify', {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ phone: phone.value, otp: otp.value })
        })
        const data = await res.json()
        if (res.ok) {
          localStorage.setItem('auth_token', data.token)
          localStorage.removeItem('mock_otp')
          localStorage.removeItem('mock_phone')
          msg.value = 'Verified. Loading profile...'
          // fetch profile
          const meRes = await fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + data.token } })
          const meData = await meRes.json()
          if (meRes.ok) {
            const u = meData.user
            msg.value = `Welcome, ${u.name || u.phone} — phone: ${u.phone}`
          } else {
            msg.value = 'Verified, but failed to load profile.'
          }
        } else {
          msg.value = data.error || JSON.stringify(data)
        }
      } catch (err) {
        msg.value = 'Error verifying OTP.'
      }
    }

    return { phone, otp, msg, verify }
  }
}
</script>
