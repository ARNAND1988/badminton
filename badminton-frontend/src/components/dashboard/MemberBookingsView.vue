<template>
<section class="space-y-6">
  <div class="panel-card">
    <div class="flex w-full items-center justify-between p-3">
      <div>
        <div class="arena-view-heading"><ArenaIcon name="calendar" /><h2 class="text-xl font-semibold text-slate-900">Upcoming Bookings</h2></div>
        <p class="mt-1 text-sm text-slate-600">{{ upcomingBookings.length }} scheduled court sessions</p>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-2">
      <article
        v-for="(booking, bookingIndex) in upcomingBookings"
        :key="booking.id"
        class="panel-card arena-booking-card"
        :class="{ 'arena-next-session': bookingIndex === 0 }"
      >
        <div v-if="bookingIndex === 0" class="arena-session-heading">
          <p class="arena-eyebrow"><ArenaIcon name="calendar" />Next session</p>
          <ArenaFeatureIcon name="shuttle" />
        </div>
        <div class="flex items-start justify-between gap-3">
          <div>
            <h3 class="mb-2 text-xl font-semibold text-slate-900">
              {{ booking.court?.name || 'Court booking' }}
            </h3>
            <p class="text-sm font-medium text-teal-700">
              {{ bookingDayLabel(booking.booking_date) }} · {{ bookingDateLabel(booking.booking_date) }}
            </p>
            <p class="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{{ bookingStatusSummary(booking) }}</p>
          </div>
          <div class="rounded bg-slate-900 px-2 py-1 text-sm font-semibold text-white">
            €{{ booking.cost || 0 }}
          </div>
        </div>

        <div class="mt-4 grid gap-2 text-sm text-slate-700">
          <p class="flex items-center gap-2">
            <ArenaIcon name="clock" class="h-4 w-4" />
            <span>{{ booking.start_time }} - {{ booking.end_time }}</span>
          </p>
          <p v-if="booking.court?.location" class="flex items-center gap-2">
            <ArenaIcon name="location" class="h-4 w-4" />
            <span>{{ booking.court.location }}</span>
            <a
              v-if="booking.court?.map_link"
              :href="booking.court.map_link"
              target="_blank"
              rel="noopener noreferrer"
              class="ml-auto inline-flex items-center gap-1 rounded-full bg-teal-50 px-3 py-1 text-xs font-bold text-teal-700 transition hover:bg-teal-100"
              @click.stop
            >
              <ArenaIcon name="location" class="h-4 w-4" /> Open map
            </a>
          </p>
        </div>
        <p class="mt-2 min-h-[2.5rem] text-sm leading-5 text-slate-600">
          <ArenaIcon name="note" class="mr-1 inline-block h-4 w-4 align-text-bottom" /> {{ booking.notes || booking.court?.description || 'No notes added for this booking.' }}
        </p>

        <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="rounded border border-teal-100 bg-white p-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Interested before booking</div>
              <div class="mt-2 flex items-end gap-2">
                <span class="text-2xl font-bold text-indigo-900">{{ bookingInterest(booking).attendee_count }}</span>
                <span class="pb-1 text-xs text-teal-800">people interested</span>
              </div>
              <div class="mt-2 flex flex-wrap gap-1.5 text-xs font-medium">
                <span class="rounded bg-teal-50 px-2 py-1 text-teal-800">{{ bookingInterest(booking).available_count || 0 }} available</span>
                <span class="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-amber-700"><TentativeIcon class="h-3.5 w-3.5" />{{ bookingInterest(booking).tentative_count || 0 }} tentative</span>
              </div>
              <div v-if="planningNames(booking, 'available').length || planningNames(booking, 'tentative').length" class="mt-2 space-y-1 text-xs leading-5 text-slate-600">
                <div v-if="planningNames(booking, 'available').length">Available: {{ planningNames(booking, 'available').join(', ') }}</div>
                <div v-if="planningNames(booking, 'tentative').length">Tentative: {{ planningNames(booking, 'tentative').join(', ') }}</div>
              </div>
            </div>

            <div class="rounded border border-teal-100 bg-white p-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Confirmed for this booking</div>
              <div class="mt-2 flex items-end gap-2">
                <span class="text-2xl font-bold text-emerald-800">{{ participantStatusCounts(booking).attending }}</span>
                <span class="pb-1 text-xs text-teal-700">confirmed yes</span>
              </div>
              <div class="mt-2 flex flex-wrap gap-1.5 text-xs font-medium">
                <span class="rounded bg-teal-50 px-2 py-1 text-teal-700">{{ participantStatusCounts(booking).attending }} yes</span>
                <span class="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-amber-700"><TentativeIcon class="h-3.5 w-3.5" />{{ participantStatusCounts(booking).tentative }} maybe</span>
              </div>
              <div v-if="participantNamesByStatus(booking, 'attending').length || participantNamesByStatus(booking, 'tentative').length" class="mt-2 space-y-1 text-xs leading-5 text-slate-600">
                <div v-if="participantNamesByStatus(booking, 'attending').length">Confirmed: {{ participantNamesByStatus(booking, 'attending').join(', ') }}</div>
                <div v-if="participantNamesByStatus(booking, 'tentative').length">Maybe: {{ participantNamesByStatus(booking, 'tentative').join(', ') }}</div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="isLoggedIn" class="mt-4 space-y-3 border-t border-slate-100 pt-4">
          <h4 class="text-sm font-semibold text-slate-900">Your family attendance</h4>
          <div v-for="person in familyAttendancePeople" :key="person.key" class="rounded border bg-white p-3">
            <div class="mb-2 flex items-center justify-between gap-3">
              <span class="text-sm font-medium text-slate-800">{{ person.name }}</span>
              <span class="text-xs text-slate-500">{{ person.type === 'self' ? 'You' : 'Family' }}</span>
            </div>
            <div class="grid grid-cols-3 gap-2">
              <button
                v-for="status in attendanceStatuses"
                :key="status.value"
                type="button"
                class="rounded border px-2 py-2 text-xs font-medium transition"
                :class="familyPersonBookingStatus(booking, person) === status.value ? 'border-teal-700 bg-teal-50 text-teal-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50'"
                @click.stop="saveFamilyPersonAttendance(booking, person, status.value)"
              >
                {{ status.label }}
              </button>
            </div>
          </div>
        </div>

      </article>
    </div>
    <p v-if="!upcomingBookings.length && !loading" class="p-3 text-sm text-slate-600">No upcoming bookings found.</p>
  </div>

  <div v-if="isLoggedIn" class="mt-8 space-y-4">
    <div>
      <h3 class="text-lg font-semibold text-slate-900">My completed bookings</h3>
      <p class="section-copy">Completed bookings you or your family attended. Cost details are available only after login.</p>
    </div>

    <div class="grid gap-4 lg:grid-cols-2">
      <article v-for="booking in completedBookings" :key="booking.id" class="sub-card overflow-hidden p-0">
        <button
          type="button"
          class="grid w-full grid-cols-[1fr_auto_auto] items-center gap-2 p-3 text-left transition hover:bg-slate-50 sm:gap-4 sm:p-4"
          :aria-expanded="isCompletedBookingOpen(booking.id)"
          @click="toggleCompletedBooking(booking.id)"
        >
          <div class="min-w-0">
            <h4 class="truncate font-semibold text-slate-900">{{ booking.court?.name || 'Court booking' }}</h4>
            <p class="truncate text-xs text-slate-600 sm:text-sm">
              {{ bookingDayLabel(booking.booking_date) }} · {{ bookingDateLabel(booking.booking_date) }} · {{ booking.start_time }} - {{ booking.end_time }}
            </p>
            <p class="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{{ bookingStatusSummary(booking) }}</p>
          </div>
          <span class="rounded bg-slate-900 px-2 py-1 text-sm font-semibold text-white sm:px-3">€{{ booking.cost || 0 }}</span>
          <span class="text-slate-400" aria-hidden="true">{{ isCompletedBookingOpen(booking.id) ? '−' : '+' }}</span>
        </button>

        <div v-if="isCompletedBookingOpen(booking.id)" class="space-y-4 border-t border-slate-100 p-4">
        <div class="grid gap-2 sm:grid-cols-3">
          <div class="rounded border border-teal-100 bg-teal-50 p-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Participated</div>
            <div class="mt-1 text-xl font-bold text-emerald-900">{{ booking.cost_split.attended_count }}</div>
          </div>
          <div class="rounded border border-teal-100 bg-teal-50 p-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Each</div>
            <div class="mt-1 text-xl font-bold text-indigo-900">€{{ booking.cost_split.cost_per_person }}</div>
          </div>
          <div class="rounded border border-slate-200 bg-slate-50 p-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</div>
            <div class="mt-1 text-sm font-semibold text-slate-900">{{ bookingStatusSummary(booking) }}</div>
          </div>
        </div>

        <div class="space-y-2">
          <div
            v-for="participant in booking.participants.filter((item) => ['attending', 'participated'].includes(item.status))"
            :key="participant.id"
            class="flex items-center justify-between rounded border bg-white px-3 py-2 text-sm"
          >
            <span class="font-medium text-slate-800">{{ participantName(participant) }}</span>
            <span class="text-slate-500">{{ participantCompletedStatusLabel(participant) }}</span>
          </div>
          <p v-if="!booking.cost_split.attended_count" class="text-sm text-slate-600">No participated players recorded.</p>
        </div>

        </div>
      </article>
    </div>

    <div v-if="completedBookingPagination.pages > 1" class="mt-4 flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <span class="text-slate-600">Page {{ completedBookingPagination.page }} of {{ completedBookingPagination.pages }} · {{ completedBookingPagination.total }} completed bookings</span>
      <div class="flex gap-2">
        <button class="btn-secondary" :disabled="completedBookingPagination.page <= 1" @click="changeCompletedBookingPage(completedBookingPagination.page - 1)">Previous</button>
        <button class="btn-secondary" :disabled="completedBookingPagination.page >= completedBookingPagination.pages" @click="changeCompletedBookingPage(completedBookingPagination.page + 1)">Next</button>
      </div>
    </div>
    <p v-if="!completedBookings.length && !loading" class="text-sm text-slate-600">No completed bookings to settle yet.</p>
  </div>
</section>
</template>

<script setup>
import ArenaIcon from '../ArenaIcon.vue'
import ArenaFeatureIcon from '../ArenaFeatureIcon.vue'
import TentativeIcon from './TentativeIcon'

// This component renders dashboard-owned data and calls the existing handlers.
defineProps({
  attendanceStatuses: Array,
  bookingDateLabel: Function,
  bookingDayLabel: Function,
  bookingInterest: Function,
  bookingStatusSummary: Function,
  changeCompletedBookingPage: Function,
  completedBookingPagination: Object,
  completedBookings: Array,
  familyAttendancePeople: Array,
  familyPersonBookingStatus: Function,
  isCompletedBookingOpen: Function,
  isLoggedIn: Boolean,
  loading: Boolean,
  participantCompletedStatusLabel: Function,
  participantName: Function,
  participantNamesByStatus: Function,
  participantStatusCounts: Function,
  planningNames: Function,
  saveFamilyPersonAttendance: Function,
  toggleCompletedBooking: Function,
  upcomingBookings: Array
})

</script>
