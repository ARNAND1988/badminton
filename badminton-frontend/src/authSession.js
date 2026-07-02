const SESSION_KEYS = [
  'auth_token',
  'member_phone',
  'member_name',
  'member_email',
  'member_role'
]

export function clearAuthSession() {
  SESSION_KEYS.forEach((key) => {
    clearSessionValue(key)
  })
  window.dispatchEvent(new CustomEvent('badminton-auth-changed'))
}

export function notifyAuthChanged() {
  window.dispatchEvent(new CustomEvent('badminton-auth-changed'))
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
