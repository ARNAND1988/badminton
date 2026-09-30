<template>
  <div class="badminton-shell min-h-screen text-slate-800">
    <Navbar />

    <main class="arena-main relative mx-auto max-w-6xl px-3 pb-24 pt-4 sm:px-6 sm:py-6 lg:px-8">
      <div :class="contentClass">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Navbar from './components/Navbar.vue'

export default {
  name: 'App',
  components: {
    Navbar
  },
  setup() {
    const route = useRoute()

    const contentClass = computed(() => {
      const isDashboardRoute = ['/bookings', '/availability', '/poll', '/dashboard', '/costs', '/my-invoices'].includes(route.path) || route.path.startsWith('/admin/')
      if (route.path === '/login') {
        return 'mx-auto max-w-6xl'
      }
      if (isDashboardRoute) return 'mx-auto max-w-6xl'
      return 'mx-auto max-w-2xl app-panel'
    })

    return { contentClass }
  }
}
</script>
