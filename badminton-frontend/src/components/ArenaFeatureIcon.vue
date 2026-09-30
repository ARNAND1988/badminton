<template>
  <svg class="arena-feature-icon" viewBox="0 0 80 80" fill="none" stroke="#10243b" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <ellipse cx="41" cy="71" rx="28" ry="5" fill="#eaf3f5" stroke="none" />
    <g v-if="name === 'calendar' || name === 'availability'" transform="rotate(-7 40 40)">
      <rect x="16" y="15" width="49" height="51" rx="6" fill="white" />
      <path d="M16 23q0-8 6-8h37q6 0 6 8v8H16Z" fill="#ff7028" />
      <path d="M28 11v11m24-11v11" stroke-width="4" />
      <path d="M24 39h7v7h-7Zm15 0h7v7h-7Zm15 0h5v7h-5ZM24 53h7v7h-7Zm15 0h7v7h-7Z" fill="#edf8f5" stroke-width="1.7" />
      <path d="m53 55 3 3 5-6" stroke="#0e756f" />
    </g>
    <g v-if="name === 'availability'" transform="rotate(28 20 36)">
      <ellipse cx="20" cy="24" rx="12" ry="18" fill="#e0f3f2" />
      <path d="M14 12v24m6-29v34m6-29v24m-17-17h22M8 24h24M9 31h22" stroke="#6fa6ac" stroke-width="1" />
      <path d="M20 42v25" stroke-width="5" /><path d="M20 55v12" stroke="#ff7028" stroke-width="5" />
    </g>
    <g v-else-if="name === 'invoice'" transform="rotate(6 40 40)">
      <path d="M16 9h35l5 6v53l-6-4-6 4-6-4-6 4-6-4-10 4Z" fill="white" />
      <path d="M47 9v9h9M25 24h21m-21 10h18m-18 10h12m-12 10h10" stroke-width="3" />
      <circle cx="57" cy="53" r="18" fill="#ff7028" /><circle cx="57" cy="53" r="13" fill="#ffdc85" stroke-width="1.7" />
      <path d="M62 44c-11-5-15 21-1 18m-14-12h12m-12 6h10" stroke-width="3" />
      <path d="M66 37q5 3 7 9" stroke="white" stroke-width="1.5" />
    </g>
    <g v-else-if="name === 'bookings'">
      <path d="M12 15h49l6 52H6Z" fill="#0e756f" />
      <path d="m19 22-6 38h46l-4-38ZM16 41h41M35 22v38M16 35h41m-43 13h45" stroke="white" stroke-width="1.3" />
      <path d="M10 16v-6m51 6v-6m-51 6h51" stroke-width="3" />
      <g transform="rotate(-9 58 45)">
        <rect x="43" y="28" width="27" height="40" rx="4" fill="white" />
        <rect x="50" y="24" width="13" height="8" rx="2" fill="#ff7028" />
        <path d="M49 41h15m-15 8h15m-15 8h10" stroke-width="2" />
      </g>
    </g>
    <g v-else-if="name === 'profile'">
      <circle cx="40" cy="37" r="29" fill="#ff7028" />
      <path d="M17 60v-3c0-13 46-13 46 0v3c-13 12-33 12-46 0Z" fill="#183857" />
      <path d="M31 43v8l9 7 9-7v-8" fill="#eeaa75" />
      <ellipse cx="40" cy="31" rx="13" ry="17" fill="#f3c190" />
      <path d="M27 30c-5-17 7-23 16-19 10-1 14 11 10 20l-7-12-8 5-9-1Z" fill="#10243b" />
      <path d="M36 33h1m9 0h1m-10 8q4 3 8 0" stroke-width="1.8" />
      <path d="M22 19q5-7 12-8" stroke="white" stroke-width="2" />
    </g>
    <g v-if="name === 'shuttle' || name === 'calendar'" :transform="name === 'calendar' ? 'translate(-1 36) scale(.52)' : 'translate(6 1) scale(.9)'">
      <g transform="rotate(32 40 40)">
        <path d="M31 56C20 45 5 20 12 16c6-4 15 12 18 17C18 11 24 4 29 8c5 3 10 23 11 27C36 9 42 3 47 8c5 4 1 24 0 28 9-25 16-29 20-23 3 6-10 25-13 30C70 22 77 24 77 31c0 8-21 23-27 29Z" fill="white" />
        <path d="m18 23 20 35m-9-43 12 42m4-42-2 42m19-34-16 35m23-24-21 25" stroke="#a5b4c4" stroke-width="1.5" />
        <path d="m30 54 21 4-3 8-22-5Z" fill="#ff7028" />
        <path d="M26 61c-15 19 12 29 22 5Z" fill="#edf8f5" />
        <path d="M29 66q-5 6 0 9" stroke="white" />
      </g>
    </g>
  </svg>
</template>

<script setup>
defineProps({ name: { type: String, default: 'calendar' } })
</script>
