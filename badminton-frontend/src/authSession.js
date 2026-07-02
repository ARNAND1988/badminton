import { ref } from 'vue'

const SESSION_KEYS = [
  'auth_token',
  'member_phone',
  'member_name',
  'member_email',
  'member_role'
]

export const authChangeVersion = ref(0)

function emitAuthChanged() {
  authChangeVersion.value += 1
  window.dispatchEvent(new CustomEvent('badminton-auth-changed'))
}

export function clearAuthSession() {
  SESSION_KEYS.forEach((key) => {
    clearSessionValue(key)
  })
  emitAuthChanged()
}

export function notifyAuthChanged() {
  emitAuthChanged()
}

export function getSessionValue(key) {
  return localStorage.getItem(key) || sessionStorage.getItem(key)
}

export function setSessionValue(key, value, remember = true) {
  const target = remember ? localStorage : sessionStorage
  const other = remember ? sessionStorage : localStorage
  other.removeItem(key)
  target.setItem(key, value)
}

export function clearSessionValue(key) {
  localStorage.removeItem(key)
  sessionStorage.removeItem(key)
}

window.addEventListener('storage', (event) => {
  if (SESSION_KEYS.includes(event.key)) {
    emitAuthChanged()
  }
})
