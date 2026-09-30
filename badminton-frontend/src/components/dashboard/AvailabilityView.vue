<template>
<section class="space-y-6">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
    <div>
      <p v-if="activeView === 'poll'" class="text-xs font-bold uppercase tracking-[0.24em] text-teal-700">Group poll</p>
      <div class="arena-view-heading"><ArenaIcon name="vote" /><h2 class="section-title">{{ activeView === 'poll' ? 'When can you play?' : 'Availability' }}</h2></div>
      <p class="section-copy mt-1">{{ activeView === 'poll' ? 'Add your name, choose one answer for each day, and save once.' : 'Next 7 days are always visible. Log in to cast or update your family vote.' }}</p>
    </div>
    <button v-if="activeView === 'availability' && isAdmin" type="button" class="btn-dark w-full sm:w-auto" @click="copyText(publicPollUrl)">
      Copy group poll link
    </button>
  </div>

  <form v-if="activeView === 'poll'" class="panel-card" @submit.prevent="savePublicAvailabilityPoll">
    <label class="block">
      <span class="form-label">Your name</span>
      <input v-model="publicPoll.name" class="form-input mt-1" maxlength="80" autocomplete="name" placeholder="Enter your name" required />
    </label>

    <fieldset class="mt-5">
      <legend class="form-label">Your availability</legend>
      <div class="mt-2 divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div v-for="day in playDays" :key="`public-poll-${day.date}`" class="p-3 sm:flex sm:items-center sm:justify-between sm:gap-4">
          <div class="mb-2 min-w-0 sm:mb-0">
            <strong class="block text-sm text-slate-900">{{ day.weekday }}</strong>
            <span class="text-xs text-slate-500">{{ day.date }}</span>
          </div>
          <div class="grid grid-cols-3 gap-1.5 sm:w-[22rem]">
            <button
              v-for="status in availabilityStatuses"
              :key="`public-${day.date}-${status.value}`"
              type="button"
              class="rounded-lg border px-2 py-2 text-xs font-bold transition"
              :class="publicPoll.responses[day.date] === status.value ? 'border-teal-700 bg-teal-50 text-teal-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'"
              @click="publicPoll.responses[day.date] = status.value"
            >
              {{ status.shortLabel || status.label }}
            </button>
          </div>
        </div>
      </div>
    </fieldset>

    <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
      <p class="text-xs text-slate-500">You can reopen this link on the same device to update your answers.</p>
      <button class="btn-primary sm:min-w-36" :disabled="publicPoll.saving || !publicPoll.name.trim() || !allPublicPollDaysAnswered">
        {{ publicPoll.saving ? 'Saving...' : 'Save availability' }}
      </button>
    </div>
  </form>

  <div v-if="activeView === 'availability' && !isLoggedIn" class="alert-info">
    You can view total attendance counts below. Log in to vote for your family.
  </div>

  <section v-if="activeView === 'availability' && isAdmin" class="panel-card space-y-4">
    <div>
      <h3 class="text-lg font-semibold text-slate-900">Prepare WhatsApp availability poll</h3>
      <p class="section-copy mt-1">Choose the dates and edit the English question. Each family receives its own existing member names on every linked number.</p>
    </div>
    <label class="block">
      <span class="form-label">Question</span>
      <textarea v-model="whatsappPollQuestion" rows="2" class="form-input" placeholder="Who can play badminton?"></textarea>
    </label>
    <div class="flex flex-wrap gap-2">
      <label v-for="day in playDays" :key="`whatsapp-${day.date}`" class="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
        <input v-model="whatsappPollDates" type="checkbox" :value="day.date" class="accent-emerald-600" />
        {{ day.weekday }} {{ day.date }}
      </label>
    </div>
    <div class="flex justify-end">
      <button class="btn-dark" :disabled="whatsappPollSending || !whatsappPollDates.length" @click="sendWhatsAppFamilyPolls">
        {{ whatsappPollSending ? 'Sending…' : 'Send to families' }}
      </button>
    </div>
  </section>

  <div v-if="activeView === 'availability' && isLoggedIn" class="panel-card">
    <div class="arena-family-heading mb-4">
      <img :src="familyArtwork" width="400" height="366" alt="" />
      <div>
        <div class="arena-view-heading"><ArenaIcon name="family" /><h3 class="text-lg font-semibold">Family members</h3></div>
        <p class="section-copy">Add family members once, then use the count when voting who will come to play.</p>
      </div>
    </div>

    <form class="grid gap-3 lg:grid-cols-[1fr_auto]" @submit.prevent="createFamilyMember">
      <input aria-label="Family member name" v-model="newFamilyName" placeholder="Family member name" class="form-input" />
      <button class="btn-dark">Add member</button>
    </form>

    <div class="mt-4 flex flex-wrap gap-2">
      <span v-for="member in familyMembers" :key="member.id" class="inline-flex items-center gap-2 rounded border border-green-200 bg-green-50 px-3 py-1 text-sm text-green-800">
        {{ member.name }}
        <button type="button" class="font-semibold text-green-900 hover:text-rose-700" @click="deleteFamilyMember(member)">Remove</button>
      </span>
      <span v-if="!familyMembers.length" class="text-sm text-slate-600">No family members added yet.</span>
    </div>
  </div>

  <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
    <article v-for="day in playDays" :key="day.date" class="sub-card overflow-hidden p-0">
      <div class="bg-gradient-to-br from-teal-50 to-white p-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="text-lg font-bold text-slate-900">{{ day.weekday }}</div>
            <div class="flex items-center gap-1 text-sm text-slate-600"><ArenaIcon name="calendar" class="h-4 w-4" />{{ day.date }}</div>
          </div>
          <div class="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm font-bold text-slate-800 shadow-sm">
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M7 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm6.5-.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM7 10.5c-2.67 0-5 1.34-5 3v1A1.5 1.5 0 0 0 3.5 16h7A1.5 1.5 0 0 0 12 14.5v-1c0-1.66-2.33-3-5-3Zm6.5-.5c-.48 0-.95.05-1.38.15 1.15.82 1.88 1.98 1.88 3.35v1c0 .54-.14 1.05-.4 1.5h2.9a1.5 1.5 0 0 0 1.5-1.5v-.75c0-1.52-2.1-2.75-4.5-2.75Z" />
            </svg>
            <span>{{ day.totals.attendee_count }} people</span>
          </div>
        </div>

        <div class="mt-3 grid grid-cols-2 gap-2 text-sm font-semibold">
          <div class="rounded-xl border border-teal-100 bg-white/80 p-3 text-teal-700"><ArenaIcon name="vote" class="mr-1 inline-block h-4 w-4" />{{ day.totals.available_count || 0 }} available</div>
          <div class="flex items-center gap-2 rounded-xl border border-amber-100 bg-white/80 p-3 text-amber-700"><TentativeIcon class="h-4 w-4 shrink-0" /> <span>{{ day.totals.tentative_count || 0 }} tentative</span></div>
        </div>
        <div v-if="isLoggedIn && (availabilityNamesByStatus(day, 'available').length || availabilityNamesByStatus(day, 'tentative').length)" class="mt-3 grid gap-2 rounded-xl border border-white/70 bg-white/80 p-3 text-sm text-slate-700 sm:grid-cols-2">
          <div>
            <div class="text-xs font-bold uppercase tracking-wide text-teal-700">Available</div>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <span v-for="name in availabilityNamesByStatus(day, 'available')" :key="`available-${day.date}-${name}`" class="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-700">{{ name }}</span>
              <span v-if="!availabilityNamesByStatus(day, 'available').length" class="text-xs text-slate-500">No available votes yet</span>
            </div>
          </div>
          <div>
            <div class="text-xs font-bold uppercase tracking-wide text-amber-600">Tentative</div>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <span v-for="name in availabilityNamesByStatus(day, 'tentative')" :key="`tentative-${day.date}-${name}`" class="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">{{ name }}</span>
              <span v-if="!availabilityNamesByStatus(day, 'tentative').length" class="text-xs text-slate-500">No tentative votes yet</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeView === 'availability' && isLoggedIn" class="space-y-3 p-4">
        <div>
          <label class="mb-1 block text-sm font-medium">Availability by member</label>
          <div class="space-y-2 rounded border bg-white p-3">
            <div v-for="person in availabilityPeople" :key="person.key" class="space-y-2 rounded border border-slate-100 p-2">
              <div class="text-sm font-medium text-slate-700">{{ person.name }}</div>
              <div class="grid grid-cols-3 gap-2">
                <button
                  v-for="status in availabilityStatuses"
                  :key="status.value"
                  type="button"
                  class="rounded border px-2 py-2 text-xs font-medium transition"
                  :class="availabilityPersonStatus(day, person) === status.value ? 'border-teal-700 bg-teal-50 text-teal-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'"
                  @click="setAvailabilityPersonStatus(day, person, status.value)"
                >
                  {{ status.label }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium">Notes</label>
          <input aria-label="Notes" v-model="day.notes" placeholder="Optional" class="form-input" />
        </div>

        <button class="btn-primary w-full" @click="saveAvailabilityVote(day)">Save vote</button>
      </div>
    </article>
  </div>
</section>
</template>

<script setup>
import ArenaIcon from '../ArenaIcon.vue'
import TentativeIcon from './TentativeIcon'
import familyArtwork from '../../assets/arena-family.webp'
import { computed } from 'vue'

// This component renders dashboard-owned data and calls the existing handlers.
const props = defineProps({
  activeView: String,
  allPublicPollDaysAnswered: Boolean,
  availabilityNamesByStatus: Function,
  availabilityPeople: Array,
  availabilityPersonStatus: Function,
  availabilityStatuses: Array,
  copyText: Function,
  createFamilyMember: Function,
  deleteFamilyMember: Function,
  familyMembers: Array,
  isAdmin: Boolean,
  isLoggedIn: Boolean,
  newFamilyName: String,
  playDays: Array,
  publicPoll: Object,
  publicPollUrl: String,
  saveAvailabilityVote: Function,
  savePublicAvailabilityPoll: Function,
  sendWhatsAppFamilyPolls: Function,
  setAvailabilityPersonStatus: Function,
  whatsappPollDates: Array,
  whatsappPollQuestion: String,
  whatsappPollSending: Boolean
})

const emit = defineEmits(['update:newFamilyName', 'update:whatsappPollQuestion', 'update:whatsappPollDates'])

// Scalar form edits go straight back to the dashboard-owned refs. Editable
// objects (days, poll responses, settings) retain their original references.
const newFamilyName = computed({
  get: () => props.newFamilyName,
  set: value => emit('update:newFamilyName', value)
})

const whatsappPollQuestion = computed({
  get: () => props.whatsappPollQuestion,
  set: value => emit('update:whatsappPollQuestion', value)
})

const whatsappPollDates = computed({
  get: () => props.whatsappPollDates,
  set: value => emit('update:whatsappPollDates', value)
})
</script>
