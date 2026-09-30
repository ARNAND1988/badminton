<template>
  <section class="arena-hero" :class="{ 'arena-hero-login': compact }" aria-label="Nieuwegein Badminton community">
    <picture class="arena-hero-art">
      <source :srcset="`${heroSmall} 768w, ${heroWebp} 1536w`" :sizes="compact ? '(min-width: 1024px) 600px, 100vw' : '(min-width: 1200px) 1152px, 100vw'" type="image/webp" />
      <img :src="heroJpg" width="1536" height="1024" alt="Adult badminton players enjoying a doubles rally on an indoor court, illustrated in anime style." fetchpriority="high" />
    </picture>
    <div class="arena-hero-content">
      <p class="arena-eyebrow">Nieuwegein Badminton</p>
      <h1 class="arena-slogan"><span>PLAY.</span><span>PASSION.</span><span>PRIDE.</span></h1>
      <p class="arena-hero-copy">Your community. Your court.</p>
      <div v-if="!compact" class="arena-hero-actions">
        <router-link to="/login" class="btn-primary">Join the rally <span aria-hidden="true">↗</span></router-link>
        <router-link to="/bookings" class="arena-hero-secondary">View bookings <span aria-hidden="true">→</span></router-link>
      </div>
    </div>
    <div class="arena-hero-caption" aria-hidden="true">GOOD PEOPLE.<br />GREAT RALLIES.</div>
  </section>
</template>

<script setup>
import heroWebp from '../assets/arena-hero.webp'
import heroSmall from '../assets/arena-hero-small.webp'
import heroJpg from '../assets/arena-hero.jpg'
defineProps({ compact: Boolean })
</script>
