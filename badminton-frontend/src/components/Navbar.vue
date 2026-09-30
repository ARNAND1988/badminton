<template>
  <nav class="arena-navbar sticky top-0 z-40 w-full px-3 sm:px-8" aria-label="Primary navigation">
    <div class="mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-3 py-2">
      <router-link to="/availability" class="arena-brand">
        <img :src="logoUrl" class="rounded-full" alt="Nieuwegein Badminton" width="48" height="48" />
        <span class="arena-brand-name">Nieuwegein<br />Badminton</span>
      </router-link>
      <div class="hidden md:block">
        <ul class="flex items-center gap-1">
          <li v-for="link in pageLinks" :key="link.label">
            <router-link :to="link.to" :class="navTextClass(link.to)">{{ link.label }}</router-link>
          </li>
          <li v-if="adminLinks.length" class="relative">
            <button type="button" :class="adminMenuButtonClass" :aria-expanded="isAdminMenuOpen" @click.stop="toggleAdminMenu">
              <AdminIcon class="h-5 w-5" /> Admin <span aria-hidden="true">▾</span>
            </button>
            <div v-if="isAdminMenuOpen" class="arena-menu absolute right-0 mt-3 w-64">
              <router-link v-for="link in adminLinks" :key="link.label" :to="link.to" :class="navTextClass(link.to)" @click="isAdminMenuOpen = false">
                <component :is="link.icon" class="h-5 w-5" />{{ link.label }}
              </router-link>
            </div>
          </li>
        </ul>
      </div>
      <div class="relative" ref="accountMenuRef">
        <button v-if="isLoggedIn" type="button" class="arena-account" :aria-expanded="isAccountMenuOpen" aria-label="Open account menu" @click="toggleAccountMenu">{{ userInitial }}</button>
        <router-link v-else to="/login" class="btn-primary"><ArenaIcon name="profile" class="h-5 w-5" />Login</router-link>
        <div v-if="isLoggedIn && isAccountMenuOpen" class="arena-menu absolute right-0 mt-3 w-56">
          <div class="border-b border-slate-100 px-3 py-2">
            <p class="text-xs font-medium uppercase tracking-wide text-slate-500">Signed in as</p>
            <p class="truncate text-sm font-semibold text-slate-900">{{ userDisplayName }}</p>
          </div>
          <button type="button" class="mt-2 flex min-h-11 w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-rose-700 transition hover:bg-rose-50" @click="logout">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M9 4H4v16h5m4-12 4 4-4 4m-5-4h13" /></svg>Logout
          </button>
        </div>
      </div>
    </div>
  </nav>
  <nav class="arena-bottom-nav fixed inset-x-0 bottom-0 z-40 border-t px-2 pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_20px_rgba(16,36,59,0.05)] md:hidden" aria-label="Mobile primary navigation">
    <div v-if="isAdminMenuOpen && adminLinks.length" class="arena-menu mx-auto mb-2 max-h-[60dvh] max-w-lg overflow-y-auto">
      <p class="px-2 pb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Admin menu</p>
      <div class="grid grid-cols-2 gap-2">
        <router-link v-for="link in adminLinks" :key="link.label" :to="link.to" :class="mobileAdminLinkClass(link.to)" @click="isAdminMenuOpen = false">
          <component :is="link.icon" class="h-5 w-5" /><span>{{ link.label }}</span>
        </router-link>
      </div>
    </div>
    <ul class="mx-auto grid max-w-lg items-stretch gap-1 py-2" :class="mobileNavGridClass">
      <li v-for="link in mobilePageLinks" :key="link.label" class="min-w-0">
        <router-link :to="link.to" :class="mobileNavClass(link.to)"><component :is="link.icon" class="h-6 w-6" /><span>{{ link.mobileLabel || link.label }}</span></router-link>
      </li>
      <li v-if="adminLinks.length" class="min-w-0">
        <button type="button" :class="mobileAdminButtonClass" :aria-expanded="isAdminMenuOpen" @click.stop="toggleAdminMenu"><AdminIcon class="h-6 w-6" /><span>Admin</span></button>
      </li>
    </ul>
  </nav>
</template>

<script>
import ArenaIcon from './ArenaIcon.vue'
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAuthSession, getAuthSessionVersion, getSessionValue, hasAuthSession, setSessionValue } from '../authSession'
import logoUrl from '../assets/nieuwegein-badminton-logo.svg'

function navIcon(name) {
  return { render() { return h(ArenaIcon, { name }) } }
}
const CalendarIcon = navIcon('calendar')
const ShuttleIcon = navIcon('participation')
const CostIcon = navIcon('invoice')
const AdminIcon = navIcon('admin')
const FamilyIcon = navIcon('family')
const BellIcon = navIcon('bell')

export default {
  name: 'Navbar',
  components: { ArenaIcon },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const isAccountMenuOpen = ref(false)
    const isAdminMenuOpen = ref(false)
    const accountMenuRef = ref(null)
    const sessionSnapshot = ref({
      email: getSessionValue('member_email') || '',
      name: getSessionValue('member_name') || '',
      role: getSessionValue('member_role') || 'member'
    })
    const isLoggedIn = computed(() => hasAuthSession())
    const userDisplayName = computed(() => {
      getAuthSessionVersion()
      return sessionSnapshot.value.name || sessionSnapshot.value.email || 'Member'
    })
    const userInitial = computed(() => userDisplayName.value.trim().charAt(0) || 'M')

    function logout() {
      isAccountMenuOpen.value = false
      clearAuthSession()
      refreshSessionSnapshot()
      router.replace('/login')
    }

    function toggleAccountMenu() {
      isAccountMenuOpen.value = !isAccountMenuOpen.value
      isAdminMenuOpen.value = false
    }

    function toggleAdminMenu() {
      isAdminMenuOpen.value = !isAdminMenuOpen.value
      isAccountMenuOpen.value = false
    }

    function closeAccountMenu(event) {
      if (!accountMenuRef.value?.contains(event.target)) {
        isAccountMenuOpen.value = false
      }
      isAdminMenuOpen.value = false
    }

    function rememberSession() {
      return Boolean(localStorage.getItem('auth_token'))
    }

    function refreshSessionSnapshot() {
      sessionSnapshot.value = {
        email: getSessionValue('member_email') || '',
        name: getSessionValue('member_name') || '',
        role: getSessionValue('member_role') || 'member'
      }
    }

    async function refreshCurrentUser() {
      const token = getSessionValue('auth_token')
      refreshSessionSnapshot()
      if (!token) return
      try {
        const response = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (!response.ok) return
        const data = await response.json()
        const user = data.user || {}
        const remember = rememberSession()
        setSessionValue('member_name', user.name || '', remember)
        setSessionValue('member_email', user.email || '', remember)
        setSessionValue('member_phone', user.phone || '', remember)
        setSessionValue('member_role', user.role || 'member', remember)
        refreshSessionSnapshot()
      } catch (err) {
        refreshSessionSnapshot()
      }
    }

    function handleAuthChanged() {
      refreshCurrentUser()
    }

    onMounted(() => {
      document.addEventListener('click', closeAccountMenu)
      window.addEventListener('badminton-auth-changed', handleAuthChanged)
      refreshCurrentUser()
    })
    onBeforeUnmount(() => {
      document.removeEventListener('click', closeAccountMenu)
      window.removeEventListener('badminton-auth-changed', handleAuthChanged)
    })

    const pageLinks = computed(() => {
      const links = [
        { label: 'Play Availability', mobileLabel: 'Play', to: '/availability', icon: ShuttleIcon },
        { label: 'Bookings', mobileLabel: 'Booking', to: '/bookings', icon: CalendarIcon },
      ]
      getAuthSessionVersion()
      if (isLoggedIn.value) {
        links.push({ label: 'My Invoices', mobileLabel: 'Invoices', to: '/costs', icon: CostIcon })
      }
      return links
    })

    const adminLinks = computed(() => {
      getAuthSessionVersion()
      if (!isLoggedIn.value || !['admin', 'super_admin'].includes(sessionSnapshot.value.role)) return []
      return [
        { label: 'Manage Bookings', mobileLabel: 'Bookings+', to: '/admin/bookings', icon: CalendarIcon },
        { label: 'Courts', mobileLabel: 'Courts', to: '/admin/courts', icon: ShuttleIcon },
        { label: 'Members', mobileLabel: 'Members', to: '/admin/members', icon: FamilyIcon },
        { label: 'Invoices & Payments', mobileLabel: 'Invoices', to: '/admin/costs', icon: CostIcon },
        ...(sessionSnapshot.value.role === 'super_admin' ? [{ label: 'Payment Settings', mobileLabel: 'Pay cfg', to: '/admin/payment-settings', icon: AdminIcon }] : []),
        { label: 'Diagnostics', mobileLabel: 'Checks', to: '/admin/system-checks', icon: AdminIcon },
        { label: 'Audit Logs', mobileLabel: 'Logs', to: '/admin/audit-logs', icon: AdminIcon },
        { label: 'WhatsApp', mobileLabel: 'WhatsApp', to: '/admin/notifications', icon: BellIcon }
      ]
    })

    const mobilePageLinks = computed(() => pageLinks.value)
    const mobileNavGridClass = computed(() => {
      if (adminLinks.value.length) return 'grid-cols-4'
      return pageLinks.value.length >= 3 ? 'grid-cols-3' : 'grid-cols-2'
    })

    function navTextClass(path) {
      return `arena-nav-link ${route.path === path ? 'arena-nav-link-active' : ''}`
    }
    const adminMenuButtonClass = computed(() => `arena-nav-link ${route.path.startsWith('/admin') ? 'arena-nav-link-active' : ''}`)
    function mobileNavClass(path) {
      const base = 'flex h-full min-h-14 flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-[0.68rem] font-semibold leading-tight transition sm:text-xs [&>span]:max-w-full [&>span]:truncate'
      return `${base} ${route.path === path ? 'arena-bottom-link-active' : 'arena-bottom-link'}`
    }
    function mobileAdminLinkClass(path) {
      const base = 'flex min-h-11 items-center gap-2 rounded-xl px-3 py-3 text-sm font-bold transition'
      return `${base} ${route.path === path ? 'arena-bottom-link-active' : 'arena-bottom-link'}`
    }
    const mobileAdminButtonClass = computed(() => {
      const base = 'flex h-full min-h-14 w-full flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-[0.68rem] font-semibold leading-tight transition sm:text-xs'
      return `${base} ${route.path.startsWith('/admin') || isAdminMenuOpen.value ? 'arena-bottom-link-active' : 'arena-bottom-link'}`
    })

    return { accountMenuRef, AdminIcon, adminLinks, adminMenuButtonClass, isAccountMenuOpen, isAdminMenuOpen, isLoggedIn, logoUrl, logout, mobileAdminButtonClass, mobileAdminLinkClass, mobileNavClass, mobileNavGridClass, mobilePageLinks, navTextClass, pageLinks, route, toggleAccountMenu, toggleAdminMenu, userDisplayName, userInitial }
  }
}
</script>
