<template>
  <section class="space-y-6 text-center">
    <div>
      <p class="text-sm font-bold uppercase tracking-[0.24em] text-emerald-700">404</p>
      <h1 class="mt-2 text-3xl font-black text-slate-950 sm:text-4xl">Page not found</h1>
      <p class="mx-auto mt-3 max-w-xl text-sm leading-6 text-slate-600">
        This page is not part of the badminton app. Use the navigation to continue, or return to play availability.
      </p>
    </div>

    <div class="flex flex-col justify-center gap-3 sm:flex-row">
      <router-link to="/availability" class="btn-primary">Go to availability</router-link>
      <router-link to="/bookings" class="btn-muted">View bookings</router-link>
    </div>
  </section>
</template>

<script>
export default {
  name: 'NotFound'
}
</script>
