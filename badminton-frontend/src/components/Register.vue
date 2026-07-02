<template>
  <div class="flex min-h-[calc(100vh-8rem)] items-center justify-center px-4 py-8">
    <div class="w-full max-w-md rounded-lg bg-white p-6 shadow-lg sm:p-8">
      <div class="mb-6">
        <div class="grid grid-cols-2 rounded-lg bg-slate-100 p-1">
          <button
            type="button"
            class="rounded-md px-4 py-2 text-sm font-semibold transition"
            :class="mode === 'login' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'"
            @click="setMode('login')"
          >
            Login
          </button>
          <button
            type="button"
            class="rounded-md px-4 py-2 text-sm font-semibold transition"
            :class="mode === 'register' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'"
            @click="setMode('register')"
          >
            Register
          </button>
        </div>
      </div>

      <h2 class="mb-2 text-center text-2xl font-bold text-slate-900">
        {{ mode === 'login' ? 'Welcome back' : 'Create your account' }}
      </h2>
      <p class="mb-6 text-center text-sm text-slate-600">
        {{ mode === 'login' ? 'Use your email and password to continue.' : 'Add WhatsApp now if you want future updates there.' }}
      </p>

      <form class="space-y-4" @submit.prevent="submitAuth">
        <div v-if="mode === 'register'">
          <label class="mb-1 block text-sm font-medium text-slate-700">Name</label>
          <input
            v-model="name"
            autocomplete="name"
            class="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            placeholder="Your name"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700">{{ mode === 'login' ? 'Name or email' : 'Email' }}</label>
          <input
            v-model="email"
            :type="mode === 'login' ? 'text' : 'email'"
            autocomplete="email"
            required
            class="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            :placeholder="mode === 'login' ? 'Your name or you@example.com' : 'you@example.com'"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium text-slate-700">Password</label>
          <input
            v-model="password"
            type="password"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
            required
            minlength="6"
            class="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            placeholder="At least 6 characters"
          />
        </div>

        <div v-if="mode === 'register'">
          <label class="mb-1 block text-sm font-medium text-slate-700">WhatsApp number <span class="font-normal text-slate-400">optional</span></label>
          <input
            v-model="whatsappNumber"
            autocomplete="tel"
            class="w-full rounded-lg border border-slate-300 px-4 py-2 text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
            placeholder="+31 6 12345678"
          />
        </div>

        <label class="flex items-center">
          <input v-model="rememberMe" type="checkbox" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
          <span class="ml-2 text-sm text-slate-600">Remember me</span>
        </label>

        <button
          class="w-full rounded-lg bg-indigo-600 py-2.5 font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-indigo-300"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? 'Please wait...' : mode === 'login' ? 'Login' : 'Create account' }}
        </button>
      </form>

      <div v-if="msg" class="mt-4 rounded-lg border p-3 text-sm leading-6" :class="messageClass">
        {{ msg }}
      </div>

      <div class="mt-6 text-center text-sm text-slate-600">
        {{ mode === 'login' ? 'Need a new account?' : 'Already registered?' }}
        <button type="button" class="font-medium text-indigo-600 hover:text-indigo-500" @click="toggleMode">
          {{ mode === 'login' ? 'Register' : 'Login' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { notifyAuthChanged, setSessionValue } from '../authSession'

export default {
  setup() {
    const mode = ref('login')
    const email = ref('')
    const password = ref('')
    const name = ref('')
    const whatsappNumber = ref('')
    const msg = ref('')
    const hasError = ref(false)
    const isSubmitting = ref(false)
    const rememberMe = ref(true)
    const router = useRouter()

    const messageClass = computed(() => {
      return hasError.value
        ? 'border-rose-200 bg-rose-50 text-rose-700'
        : 'border-emerald-200 bg-emerald-50 text-emerald-700'
    })

    function setMode(nextMode) {
      mode.value = nextMode
      msg.value = ''
      hasError.value = false
    }

    function toggleMode() {
      setMode(mode.value === 'login' ? 'register' : 'login')
    }

    function saveSession(data) {
      setSessionValue('auth_token', data.token, rememberMe.value)
      setSessionValue('member_phone', data.user?.phone || '', rememberMe.value)
      setSessionValue('member_name', data.user?.name || '', rememberMe.value)
      setSessionValue('member_email', data.user?.email || '', rememberMe.value)
      setSessionValue('member_role', data.user?.role || 'member', rememberMe.value)
      notifyAuthChanged()
    }

    async function submitAuth() {
      msg.value = ''
      hasError.value = false
      isSubmitting.value = true

      const isRegister = mode.value === 'register'
      const endpoint = isRegister ? '/api/auth/register' : '/api/auth/login'
      const payload = isRegister
        ? {
            email: email.value,
            password: password.value,
            name: name.value,
            whatsapp_number: whatsappNumber.value
          }
        : {
            email: email.value,
            username: email.value,
            password: password.value
          }

      try {
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        const data = await res.json()
        if (res.ok) {
          saveSession(data)
          msg.value = isRegister ? 'Account created.' : 'Logged in.'
          setTimeout(() => router.push('/dashboard'), 400)
        } else {
          hasError.value = true
          msg.value = readableError(data.error, isRegister)
        }
      } catch (err) {
        hasError.value = true
        msg.value = isRegister ? 'Error creating account.' : 'Error logging in.'
      } finally {
        isSubmitting.value = false
      }
    }

    function readableError(error, isRegister) {
      const messages = {
        valid_email_required: 'Please enter a valid email address.',
        password_too_short: 'Password must be at least 6 characters.',
        email_already_registered: 'That email is already registered. Try logging in.',
        whatsapp_already_registered: 'That WhatsApp number is already in use.',
        invalid_credentials: 'Email or password is incorrect.'
      }
      return messages[error] || (isRegister ? 'Registration failed.' : 'Login failed.')
    }

    return {
      mode,
      email,
      password,
      name,
      whatsappNumber,
      rememberMe,
      msg,
      messageClass,
      isSubmitting,
      setMode,
      toggleMode,
      submitAuth
    }
  }
}
</script>
