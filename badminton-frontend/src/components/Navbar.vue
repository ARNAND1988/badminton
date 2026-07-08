<template>
  <nav class="sticky top-0 z-40 w-full border-b border-sky-200/20 bg-slate-950/80 px-3 shadow-2xl shadow-sky-950/30 backdrop-blur-2xl sm:px-8">
    <div class="container mx-auto flex min-h-16 items-center justify-between gap-3 py-2 md:px-4">
      <router-link to="/availability" class="group flex min-w-0 items-center gap-3 text-sky-100">
        <span class="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-slate-950 p-1 shadow-[0_0_30px_rgba(56,189,248,0.35)] ring-1 ring-sky-300/50 transition duration-300 group-hover:scale-105 sm:h-14 sm:w-14">
          <span class="absolute inset-0 rounded-full bg-gradient-to-br from-sky-400/35 via-transparent to-emerald-300/30 blur-md"></span>
          <img
            :src="logoUrl"
            alt="Nieuwegein Badminton"
            class="relative h-full w-full rounded-full object-cover"
          >
        </span>
        <span class="min-w-0 leading-tight">
          <span class="block truncate text-sm font-black uppercase tracking-[0.24em] text-white sm:text-base">Nieuwegein</span>
          <span class="block truncate text-[0.65rem] font-semibold uppercase tracking-[0.32em] text-sky-200/80 sm:text-xs">Badminton</span>
        </span>
      </router-link>

      <div class="hidden text-gray-500 md:block">
        <ul class="flex items-center gap-1 font-semibold">
          <li v-for="link in pageLinks" :key="link.label">
            <router-link :to="link.to" :class="navTextClass(link.to)">
              {{ link.label }}
            </router-link>
          </li>
          <li v-if="adminLinks.length" class="relative">
            <button type="button" :class="adminMenuButtonClass" @click.stop="toggleAdminMenu">
              <AdminIcon class="h-4 w-4" />
              Admin
              <span aria-hidden="true">▾</span>
            </button>
            <div
              v-if="isAdminMenuOpen"
              class="absolute right-0 mt-3 w-56 rounded-2xl border border-sky-200/30 bg-slate-950/95 p-2 text-sky-50 shadow-2xl shadow-sky-950/40 backdrop-blur-xl"
            >
              <router-link
                v-for="link in adminLinks"
                :key="link.label"
                :to="link.to"
                class="block rounded-xl px-3 py-2 text-sm font-semibold text-sky-100/80 transition hover:bg-white/10 hover:text-white"
                :class="route.path === link.to ? 'bg-sky-400/15 text-white' : ''"
                @click="isAdminMenuOpen = false"
              >
                {{ link.label }}
              </router-link>
            </div>
          </li>
        </ul>
      </div>

      <div class="relative" ref="accountMenuRef">
        <button
          v-if="isLoggedIn"
          type="button"
          class="relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-full border border-sky-300/50 bg-slate-950 text-base font-black uppercase text-white shadow-[0_0_24px_rgba(14,165,233,0.45)] ring-2 ring-sky-400/20 transition hover:scale-105 hover:border-emerald-200 focus:outline-none focus:ring-4 focus:ring-sky-300/40"
          :aria-expanded="isAccountMenuOpen"
          aria-label="Open account menu"
          @click="toggleAccountMenu"
        >
          {{ userInitial }}
        </button>
        <router-link
          v-else
          to="/login"
          class="group relative inline-flex items-center gap-2 overflow-hidden rounded-2xl border border-sky-300/40 bg-slate-950 px-4 py-2 text-sm font-bold uppercase tracking-[0.18em] text-sky-50 shadow-[0_0_24px_rgba(14,165,233,0.35)] transition duration-300 hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-[0_0_34px_rgba(45,212,191,0.45)]"
        >
          <span class="absolute inset-0 bg-gradient-to-r from-sky-500/30 via-cyan-300/20 to-emerald-300/30 opacity-0 transition group-hover:opacity-100"></span>
          <svg xmlns="http://www.w3.org/2000/svg" class="relative h-5 w-5 drop-shadow-[0_0_8px_rgba(125,211,252,0.9)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M12 3.5a4.25 4.25 0 014.25 4.25c0 1.35-.63 2.56-1.61 3.34A7.25 7.25 0 0119.25 18v.75a1.75 1.75 0 01-1.75 1.75h-11a1.75 1.75 0 01-1.75-1.75V18a7.25 7.25 0 014.61-6.91 4.23 4.23 0 01-1.61-3.34A4.25 4.25 0 0112 3.5z" />
            <path d="M18.5 5.5l.55 1.2 1.2.55-1.2.55-.55 1.2-.55-1.2-1.2-.55 1.2-.55.55-1.2z" fill="currentColor" stroke="none" />
          </svg>
          <span class="relative">Login</span>
        </router-link>

        <div
          v-if="isLoggedIn && isAccountMenuOpen"
          class="absolute right-0 mt-3 w-56 rounded-2xl border border-sky-200/30 bg-slate-950/95 p-2 text-sky-50 shadow-2xl shadow-sky-950/40 backdrop-blur-xl"
        >
          <div class="border-b border-slate-100 px-3 py-2">
            <p class="text-xs font-medium uppercase tracking-wide text-slate-400">Signed in as</p>
            <p class="truncate text-sm font-semibold text-sky-50">{{ userDisplayName }}</p>
          </div>
          <button
            type="button"
            class="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-rose-600 transition hover:bg-rose-50"
            @click="logout"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M3 3a1 1 0 011 1v12a1 1 0 11-2 0V4a1 1 0 011-1zm10.293 3.293a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 01-1.414-1.414L14.586 11H7a1 1 0 110-2h7.586l-1.293-1.293a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
            Logout
          </button>
        </div>
      </div>
    </div>
  </nav>

  <nav class="fixed inset-x-0 bottom-0 z-40 border-t border-emerald-200/70 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] shadow-[0_-10px_30px_rgba(15,23,42,0.08)] backdrop-blur md:hidden" aria-label="Mobile primary navigation">
    <div
      v-if="isAdminMenuOpen && adminLinks.length"
      class="mx-auto mb-2 max-w-lg rounded-2xl border border-emerald-200 bg-white p-2 shadow-2xl shadow-slate-900/15"
    >
      <p class="px-2 pb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Admin menu</p>
      <div class="grid grid-cols-2 gap-2">
        <router-link
          v-for="link in adminLinks"
          :key="link.label"
          :to="link.to"
          :class="mobileAdminLinkClass(link.to)"
          @click="isAdminMenuOpen = false"
        >
          <component :is="link.icon" class="h-5 w-5" />
          <span>{{ link.label }}</span>
        </router-link>
      </div>
    </div>
    <ul class="mx-auto grid max-w-lg items-stretch gap-1 py-2" :class="mobileNavGridClass">
      <li v-for="link in mobilePageLinks" :key="link.label" class="min-w-0">
        <router-link :to="link.to" :class="mobileNavClass(link.to)">
          <component :is="link.icon" class="h-5 w-5" />
          <span>{{ link.mobileLabel }}</span>
        </router-link>
      </li>
      <li v-if="adminLinks.length" class="min-w-0">
        <button type="button" :class="mobileAdminButtonClass" :aria-expanded="isAdminMenuOpen" @click.stop="toggleAdminMenu">
          <AdminIcon class="h-5 w-5" />
          <span>Admin</span>
        </button>
      </li>
    </ul>
  </nav>
</template>

<script>
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAuthSession, getAuthSessionVersion, getSessionValue, hasAuthSession, setSessionValue } from '../authSession'
import logoUrl from '../assets/nieuwegein-badminton-logo.svg'

function navIcon(pathData) {
  return {
    render() {
      return h('svg', { xmlns: 'http://www.w3.org/2000/svg', viewBox: '0 0 20 20', fill: 'currentColor', 'aria-hidden': 'true' }, [
        h('path', { d: pathData })
      ])
    }
  }
}

const CalendarIcon = navIcon('M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zM18 9H2v7a2 2 0 002 2h12a2 2 0 002-2V9z')
const ShuttleIcon = navIcon('M10.7 2.3a1 1 0 00-1.4 0L3 8.6V15a2 2 0 002 2h3v-4h4v4h3a2 2 0 002-2V8.6l-6.3-6.3z')
const CostIcon = navIcon('M10 2a8 8 0 100 16 8 8 0 000-16zm1 4a1 1 0 10-2 0v.2a3 3 0 00-1.7.9 2.3 2.3 0 00-.6 1.7c0 1.5 1.1 2.2 2.8 2.6 1.1.3 1.5.5 1.5 1s-.5.9-1.2.9c-.8 0-1.5-.3-2.1-.8a1 1 0 10-1.3 1.5 5 5 0 002.6 1.2v.2a1 1 0 102 0v-.2c1.6-.4 2.6-1.5 2.6-2.9 0-1.7-1.2-2.4-3-2.8-1-.3-1.4-.5-1.4-.9s.4-.8 1.1-.8c.6 0 1.1.2 1.6.5a1 1 0 101.1-1.7A4.4 4.4 0 0011 6.2V6z')
const AdminIcon = navIcon('M10 2a3 3 0 00-3 3v1H5a2 2 0 00-2 2v7a2 2 0 002 2h10a2 2 0 002-2V8a2 2 0 00-2-2h-2V5a3 3 0 00-3-3zm-1 4V5a1 1 0 112 0v1H9z')

export default {
  name: 'Navbar',
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
        { label: 'Members', mobileLabel: 'Members', to: '/admin/members', icon: AdminIcon },
        { label: 'Split Costs', mobileLabel: 'Split', to: '/admin/costs', icon: CostIcon },
        { label: 'Payments', mobileLabel: 'Pay', to: '/admin/payments', icon: CostIcon },
        ...(sessionSnapshot.value.role === 'super_admin' ? [{ label: 'Payment Settings', mobileLabel: 'Pay cfg', to: '/admin/payment-settings', icon: AdminIcon }] : []),
        { label: 'Audit Logs', mobileLabel: 'Logs', to: '/admin/audit-logs', icon: AdminIcon },
        { label: 'WhatsApp', mobileLabel: 'WhatsApp', to: '/admin/notifications', icon: AdminIcon }
      ]
    })

    const mobilePageLinks = computed(() => pageLinks.value)
    const mobileNavGridClass = computed(() => {
      if (adminLinks.value.length) return 'grid-cols-4'
      return pageLinks.value.length >= 3 ? 'grid-cols-3' : 'grid-cols-2'
    })

    function navTextClass(path) {
      const base = 'block rounded-xl border border-transparent px-4 py-2 text-sm font-bold transition hover:border-sky-300/40 hover:bg-white/10 hover:text-sky-100'
      return route.path === path
        ? `${base} border-sky-300/50 bg-sky-400/15 text-white shadow-[0_0_18px_rgba(14,165,233,0.25)]`
        : `${base} text-sky-100/75`
    }

    const adminMenuButtonClass = computed(() => {
      const base = 'flex items-center gap-1 rounded-xl border border-transparent px-4 py-2 text-sm font-bold transition hover:border-sky-300/40 hover:bg-white/10 hover:text-sky-100'
      return route.path.startsWith('/admin')
        ? `${base} border-sky-300/50 bg-sky-400/15 text-white shadow-[0_0_18px_rgba(14,165,233,0.25)]`
        : `${base} text-sky-100/75`
    })

    function mobileNavClass(path) {
      const base = 'flex h-full min-h-14 flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-[0.68rem] font-semibold leading-tight transition sm:text-xs [&>span]:max-w-full [&>span]:truncate'
      return route.path === path
        ? `${base} bg-emerald-100 text-emerald-800 shadow-sm`
        : `${base} text-slate-500 hover:bg-emerald-50 hover:text-emerald-700`
    }

    function mobileAdminLinkClass(path) {
      const base = 'flex items-center gap-2 rounded-xl px-3 py-3 text-sm font-bold transition'
      return route.path === path
        ? `${base} bg-emerald-100 text-emerald-800 shadow-sm`
        : `${base} text-slate-600 hover:bg-emerald-50 hover:text-emerald-700`
    }

    const mobileAdminButtonClass = computed(() => {
      const base = 'flex h-full min-h-14 w-full flex-col items-center justify-center gap-1 rounded-xl px-1 py-2 text-[0.68rem] font-semibold leading-tight transition sm:text-xs'
      return route.path.startsWith('/admin') || isAdminMenuOpen.value
        ? `${base} bg-emerald-100 text-emerald-800 shadow-sm`
        : `${base} text-slate-500 hover:bg-emerald-50 hover:text-emerald-700`
    })

    return { accountMenuRef, AdminIcon, adminLinks, adminMenuButtonClass, isAccountMenuOpen, isAdminMenuOpen, isLoggedIn, logoUrl, logout, mobileAdminButtonClass, mobileAdminLinkClass, mobileNavClass, mobileNavGridClass, mobilePageLinks, navTextClass, pageLinks, route, toggleAccountMenu, toggleAdminMenu, userDisplayName, userInitial }
  }
}
</script>
