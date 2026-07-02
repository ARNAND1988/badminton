<template>
  <nav class="sticky top-0 z-40 w-full border-b border-slate-200 bg-white/95 px-4 shadow-sm backdrop-blur sm:px-8">
    <div class="container mx-auto flex h-16 items-center justify-between md:px-4">
      <router-link to="/availability" class="flex items-center gap-3 text-indigo-500">
        <img
          :src="logoUrl"
          alt="Nieuwegein Badminton"
          class="h-11 w-11 rounded-full object-cover shadow-sm ring-1 ring-slate-300"
        >
        <span class="hidden font-semibold text-slate-800 sm:inline">Nieuwegein Badminton</span>
      </router-link>

      <div class="hidden text-gray-500 md:block">
        <ul class="flex items-center gap-1 font-semibold">
          <li v-for="link in pageLinks" :key="link.label">
            <router-link :to="link.to" :class="navTextClass(link.to)">
              {{ link.label }}
            </router-link>
          </li>
        </ul>
      </div>

      <div class="relative" ref="accountMenuRef">
        <button
          v-if="isLoggedIn"
          type="button"
          class="flex h-11 w-11 items-center justify-center rounded-full bg-indigo-600 text-base font-bold uppercase text-white shadow-sm ring-2 ring-indigo-100 transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-200"
          :aria-expanded="isAccountMenuOpen"
          aria-label="Open account menu"
          @click="toggleAccountMenu"
        >
          {{ userInitial }}
        </button>
        <router-link
          v-else
          to="/login"
          class="flex items-center gap-2 rounded-xl bg-indigo-500 px-4 py-2 text-gray-50 hover:bg-indigo-600"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M3 3a1 1 0 011 1v12a1 1 0 11-2 0V4a1 1 0 011-1zm7.707 3.293a1 1 0 010 1.414L9.414 9H17a1 1 0 110 2H9.414l1.293 1.293a1 1 0 01-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0z" clip-rule="evenodd" />
          </svg>
          <span>Login</span>
        </router-link>

        <div
          v-if="isLoggedIn && isAccountMenuOpen"
          class="absolute right-0 mt-3 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-xl"
        >
          <div class="border-b border-slate-100 px-3 py-2">
            <p class="text-xs font-medium uppercase tracking-wide text-slate-400">Signed in as</p>
            <p class="truncate text-sm font-semibold text-slate-800">{{ userDisplayName }}</p>
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

  <nav class="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] shadow-[0_-10px_30px_rgba(15,23,42,0.08)] backdrop-blur md:hidden" aria-label="Mobile primary navigation">
    <ul class="mx-auto grid max-w-lg grid-cols-3 gap-1 py-2">
      <li v-for="link in mobilePageLinks" :key="link.label">
        <router-link :to="link.to" :class="mobileNavClass(link.to)">
          <component :is="link.icon" class="h-5 w-5" />
          <span>{{ link.mobileLabel }}</span>
        </router-link>
      </li>
    </ul>
  </nav>
</template>

<script>
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAuthSession, getAuthSessionVersion, getSessionValue, hasAuthSession } from '../authSession'
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

export default {
  name: 'Navbar',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const isAccountMenuOpen = ref(false)
    const accountMenuRef = ref(null)
    const isLoggedIn = computed(() => hasAuthSession())
    const userDisplayName = computed(() => {
      getAuthSessionVersion()
      return getSessionValue('member_name') || getSessionValue('member_email') || 'Member'
    })
    const userInitial = computed(() => userDisplayName.value.trim().charAt(0) || 'M')

    function logout() {
      isAccountMenuOpen.value = false
      clearAuthSession()
      router.replace('/availability')
    }

    function toggleAccountMenu() {
      isAccountMenuOpen.value = !isAccountMenuOpen.value
    }

    function closeAccountMenu(event) {
      if (!accountMenuRef.value?.contains(event.target)) {
        isAccountMenuOpen.value = false
      }
    }

    onMounted(() => document.addEventListener('click', closeAccountMenu))
    onBeforeUnmount(() => document.removeEventListener('click', closeAccountMenu))

    const pageLinks = computed(() => {
      const links = [
        { label: 'Play Availability', mobileLabel: 'Play', to: '/availability', icon: ShuttleIcon },
        { label: 'Bookings', mobileLabel: 'Booking', to: '/bookings', icon: CalendarIcon },
        { label: 'Costs', mobileLabel: 'Cost', to: '/costs', icon: CostIcon },
      ]
      getAuthSessionVersion()
      if (isLoggedIn.value && getSessionValue('member_role') === 'admin') {
        links.push({ label: 'Members', mobileLabel: 'Members', to: '/members', icon: ShuttleIcon })
      }
      return links
    })

    const mobilePageLinks = computed(() => pageLinks.value.slice(0, 3))

    function navTextClass(path) {
      const base = 'block rounded-lg px-4 py-2 text-sm transition hover:bg-indigo-50 hover:text-indigo-500'
      return route.path === path
        ? `${base} bg-indigo-50 text-indigo-600`
        : `${base} text-slate-600`
    }

    function mobileNavClass(path) {
      const base = 'flex flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-xs font-semibold transition'
      return route.path === path
        ? `${base} bg-indigo-50 text-indigo-600`
        : `${base} text-slate-500 hover:bg-slate-50 hover:text-indigo-500`
    }

    return { accountMenuRef, isAccountMenuOpen, isLoggedIn, logoUrl, logout, mobileNavClass, mobilePageLinks, navTextClass, pageLinks, toggleAccountMenu, userDisplayName, userInitial }
  }
}
</script>
