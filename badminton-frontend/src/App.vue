<template>
  <div class="min-h-screen bg-slate-50 text-slate-800">
    <Navbar />

    <main class="mx-auto max-w-6xl px-3 pb-24 pt-4 sm:px-6 sm:py-6 lg:px-8">
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
      const isDashboardRoute = ['/bookings', '/availability', '/dashboard', '/costs', '/members'].includes(route.path)
      if (route.path === '/login') {
        return 'mx-auto max-w-6xl'
      }
      const width = isDashboardRoute ? 'max-w-6xl' : 'max-w-xl'
      return `mx-auto ${width} app-panel`
    })

    return { contentClass }
  }
}
</script>
