<template>
  <nav class="w-full bg-gray-200 px-4 shadow shadow-gray-300 sm:px-8">
    <div class="container mx-auto flex h-28 flex-wrap items-center justify-between md:h-16 md:flex-nowrap md:px-4">
      <router-link to="/availability" class="order-1 flex items-center gap-3 text-indigo-500">
        <img
          :src="logoUrl"
          alt="Nieuwegein Badminton"
          class="h-12 w-12 rounded-full object-cover shadow-sm ring-1 ring-slate-300"
        >
        <span class="hidden font-semibold text-slate-800 sm:inline">Nieuwegein Badminton</span>
      </router-link>

      <div class="order-3 w-full text-gray-500 md:order-2 md:w-auto">
        <ul class="flex justify-between gap-2 font-semibold md:gap-0">
          <li v-for="link in pageLinks" :key="link.label" class="md:px-4 md:py-2">
            <router-link :to="link.to" :class="navTextClass(link.to)">
              {{ link.label }}
            </router-link>
          </li>
        </ul>
      </div>

      <div class="order-2 md:order-3">
        <button
          v-if="isLoggedIn"
          class="flex items-center gap-2 rounded-xl bg-indigo-500 px-4 py-2 text-gray-50 hover:bg-indigo-600"
          @click="logout"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M3 3a1 1 0 011 1v12a1 1 0 11-2 0V4a1 1 0 011-1zm10.293 3.293a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 01-1.414-1.414L14.586 11H7a1 1 0 110-2h7.586l-1.293-1.293a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
          <span>Logout</span>
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
      </div>
    </div>
  </nav>
</template>

<script>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAuthSession, getAuthSessionVersion, getSessionValue, hasAuthSession } from '../authSession'
import logoUrl from '../assets/nieuwegein-badminton-logo.svg'

export default {
  name: 'Navbar',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const isLoggedIn = computed(() => hasAuthSession())

    function logout() {
      clearAuthSession()
      router.replace('/availability')
    }

    const pageLinks = computed(() => {
      const links = [
        { label: 'Play Availability', to: '/availability' },
        { label: 'Bookings', to: '/bookings' },
        { label: 'Costs', to: '/costs' },
      ]
      getAuthSessionVersion()
      if (isLoggedIn.value && getSessionValue('member_role') === 'admin') {
        links.push({ label: 'Members', to: '/members' })
      }
      return links
    })

    function navTextClass(path) {
      const base = 'block text-sm transition hover:text-indigo-400'
      return route.path === path
        ? `${base} text-indigo-500`
        : base
    }

    return { isLoggedIn, logoUrl, logout, navTextClass, pageLinks }
  }
}
</script>
