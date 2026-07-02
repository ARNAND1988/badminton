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
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('badminton-auth-changed'))
  }
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

export function getAuthSessionVersion() {
  return authChangeVersion.value
}

export function hasAuthSession() {
  getAuthSessionVersion()
  return Boolean(getSessionValue('auth_token'))
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

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === null || SESSION_KEYS.includes(event.key)) {
      emitAuthChanged()
    }
  })
}
