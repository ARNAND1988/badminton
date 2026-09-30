<template>
  <section class="arena-home">
    <ArenaHero />
    <div class="arena-home-body">
      <div class="arena-welcome">
        <div>
          <p class="arena-eyebrow">Welcome to Nieuwegein Badminton</p>
          <h2>Ready for your next rally?</h2>
          <p class="section-copy mt-2">Friendly people. Shared courts. A community that plays together.</p>
        </div>
        <div class="arena-mascot" aria-hidden="true">
          <img :src="mascotArtwork" width="400" height="366" alt="" />
          <span>Same people.<br />New rallies!</span>
        </div>
      </div>
      <div class="arena-feature-links">
        <router-link to="/bookings" class="arena-feature-link arena-feature-bookings">
          <ArenaFeatureIcon name="calendar" />
          <span><strong>Bookings</strong><small>View scheduled court sessions.</small></span>
          <span class="arena-quick-arrow" aria-hidden="true">›</span>
        </router-link>
        <router-link to="/login" class="arena-feature-link arena-feature-family">
          <img :src="familyArtwork" class="arena-family-art" width="400" height="366" alt="" />
          <span><strong>Play together</strong><small>Log in to vote for your family.</small><span class="arena-card-hint">Family participation <span aria-hidden="true">→</span></span></span>
        </router-link>
        <router-link to="/costs" class="arena-feature-link">
          <ArenaFeatureIcon name="invoice" />
          <span><strong>My Invoices</strong><small>Log in to view your costs.</small></span>
          <span class="arena-quick-arrow" aria-hidden="true">›</span>
        </router-link>
      </div>
      <div class="arena-quick-heading"><h3>Quick actions</h3><span aria-hidden="true"></span></div>
      <div class="arena-quick-links">
        <router-link to="/availability" class="arena-quick-link">
          <ArenaFeatureIcon name="availability" /><span><strong>Availability</strong><small>Check when you can play.</small></span><span class="arena-quick-arrow" aria-hidden="true">›</span>
        </router-link>
        <router-link to="/bookings" class="arena-quick-link">
          <ArenaFeatureIcon name="bookings" /><span><strong>Bookings</strong><small>View scheduled court sessions.</small></span><span class="arena-quick-arrow" aria-hidden="true">›</span>
        </router-link>
        <router-link to="/login" class="arena-quick-link">
          <ArenaFeatureIcon name="profile" /><span><strong>Login</strong><small>Access your member account.</small></span><span class="arena-quick-arrow" aria-hidden="true">›</span>
        </router-link>
      </div>
    </div>
  </section>
</template>

<script setup>
import ArenaHero from '../ArenaHero.vue'
import ArenaFeatureIcon from '../ArenaFeatureIcon.vue'
import mascotArtwork from '../../assets/arena-mascot.webp'
import familyArtwork from '../../assets/arena-family.webp'

</script>
