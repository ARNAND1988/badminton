<template>
  <svg class="arena-icon" viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <template v-if="name === 'clock'">
      <circle cx="16" cy="16" r="12" /><path class="arena-icon-orange" d="M16 8v9l6 3" />
    </template>
    <template v-else-if="name === 'location'">
      <path d="M26 13c0 8-10 16-10 16S6 21 6 13a10 10 0 0 1 20 0Z" /><circle class="arena-icon-orange" cx="16" cy="13" r="4" />
    </template>
    <template v-else-if="name === 'note'">
      <path d="M7 4h13l6 6v18H7Zm13 0v7h6" /><path class="arena-icon-teal" d="M11 16h11m-11 5h8" />
    </template>
    <template v-else-if="name === 'calendar'">
      <rect x="5" y="7" width="22" height="21" rx="4" />
      <path class="arena-icon-orange" d="M5 13h22M11 4v6m10-6v6" />
      <path d="M10 18h3m6 0h3m-12 5h3m6 0h3" />
    </template>
    <template v-else-if="name === 'invoice'">
      <path d="M7 28V4h17v16M7 28l3-2 3 2 3-2" />
      <path d="M11 10h9m-9 5h7m-7 5h3" />
      <circle class="arena-icon-orange" cx="23" cy="24" r="6" />
      <path class="arena-icon-orange" d="M25 21c-4-2-6 5-1 6m-5-4h5m-5 2h4" />
    </template>
    <template v-else-if="name === 'family'">
      <circle cx="11" cy="10" r="5" /><circle class="arena-icon-teal" cx="23" cy="11" r="4" />
      <path d="M2 27v-3a9 9 0 0 1 18 0v3Z" /><path class="arena-icon-teal" d="M22 19a7 7 0 0 1 8 7v1h-6" />
    </template>
    <template v-else-if="name === 'profile'">
      <circle class="arena-icon-orange" cx="16" cy="16" r="14" />
      <circle cx="16" cy="11" r="5" /><path d="M7 27v-2a9 9 0 0 1 18 0v2" />
    </template>
    <template v-else-if="name === 'bell'">
      <path d="M5 24h22l-3-5v-7a8 8 0 0 0-16 0v7Zm7 4h8" /><circle class="arena-icon-orange" cx="25" cy="6" r="3" fill="currentColor" stroke="none" />
    </template>
    <template v-else-if="name === 'admin'">
      <path d="M16 3 28 7v10c0 6-7 10-12 12C11 27 4 23 4 17V7Z" />
      <ellipse class="arena-icon-teal" cx="12" cy="12" rx="3" ry="5" transform="rotate(-35 12 12)" /><ellipse class="arena-icon-orange" cx="20" cy="12" rx="3" ry="5" transform="rotate(35 20 12)" />
      <path d="m14 16 7 8m-3-8-7 8" />
    </template>
    <template v-else-if="name === 'vote'">
      <path d="M27 19a4 4 0 0 1-4 4H12l-7 5V8a4 4 0 0 1 4-4h14a4 4 0 0 1 4 4Z" /><path class="arena-icon-teal" d="m10 13 4 4 8-8" />
    </template>
    <template v-else>
      <ellipse cx="12" cy="11" rx="6" ry="9" transform="rotate(30 12 11)" />
      <path class="arena-icon-teal" d="m8 6 9 5m-11 0 9 5m-3-12-6 12m10-9-6 12" />
      <path d="m8 19-5 9m16-8 4 4 7-9-9-2Z" /><path class="arena-icon-orange" d="m19 20 4 4m-1-10 2 6m3-5-3 5" />
    </template>
  </svg>
</template>

<script setup>
defineProps({ name: { type: String, default: 'participation' } })
</script>
