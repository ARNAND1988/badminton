<template>
  <div class="space-y-6">
    <div v-if="loading" class="alert-info">
      Loading data...
    </div>
    <div v-if="errorMsg" class="alert-warning">
      {{ errorMsg }}
    </div>
    <p v-if="msg" class="alert-muted">{{ msg }}</p>

    <section v-if="activeView === 'bookings'" class="space-y-6">
      <div class="rounded-lg bg-white p-6 shadow-sm">
        <div class="flex w-full items-center justify-between p-3">
          <div>
            <h2 class="text-xl font-semibold text-slate-900">Upcoming Bookings</h2>
            <p class="mt-1 text-sm text-slate-600">{{ upcomingBookings.length }} scheduled court sessions</p>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-2">
          <article
            v-for="booking in upcomingBookings"
            :key="booking.id"
            class="cursor-pointer rounded-md border-2 border-slate-50 bg-white/20 p-6 shadow-sm transition-colors duration-300 hover:border-black"
          >
            <div class="flex items-start justify-between gap-3">
              <div>
                <h3 class="mb-2 text-xl font-semibold text-slate-900">
                  {{ booking.court?.name || 'Court booking' }}
                </h3>
                <p class="text-sm font-medium text-indigo-600">
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
                <span aria-hidden="true">⏰</span>
                <span>{{ booking.start_time }} - {{ booking.end_time }}</span>
              </p>
              <p v-if="booking.court?.location" class="flex items-center gap-2">
                <span aria-hidden="true">📍</span>
                <span>{{ booking.court.location }}</span>
                <a
                  v-if="booking.court?.map_link"
                  :href="booking.court.map_link"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ml-auto inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 transition hover:bg-emerald-100"
                  @click.stop
                >
                  🗺️ Open map
                </a>
              </p>
            </div>
            <p class="mt-2 min-h-[2.5rem] text-sm leading-5 text-slate-600">
              📝 {{ booking.notes || booking.court?.description || 'No notes added for this booking.' }}
            </p>

            <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="rounded border border-indigo-100 bg-white p-3">
                  <div class="text-xs font-semibold uppercase tracking-wide text-indigo-600">Interested before booking</div>
                  <div class="mt-2 flex items-end gap-2">
                    <span class="text-2xl font-bold text-indigo-900">{{ bookingInterest(booking).attendee_count }}</span>
                    <span class="pb-1 text-xs text-indigo-700">people interested</span>
                  </div>
                  <div class="mt-2 flex flex-wrap gap-1.5 text-xs font-medium">
                    <span class="rounded bg-indigo-50 px-2 py-1 text-indigo-700">{{ bookingInterest(booking).available_count || 0 }} available</span>
                    <span class="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-amber-700"><TentativeIcon class="h-3.5 w-3.5" />{{ bookingInterest(booking).tentative_count || 0 }} tentative</span>
                  </div>
                  <div v-if="planningNames(booking, 'available').length || planningNames(booking, 'tentative').length" class="mt-2 space-y-1 text-xs leading-5 text-slate-600">
                    <div v-if="planningNames(booking, 'available').length">Available: {{ planningNames(booking, 'available').join(', ') }}</div>
                    <div v-if="planningNames(booking, 'tentative').length">Tentative: {{ planningNames(booking, 'tentative').join(', ') }}</div>
                  </div>
                </div>

                <div class="rounded border border-emerald-100 bg-white p-3">
                  <div class="text-xs font-semibold uppercase tracking-wide text-emerald-600">Confirmed for this booking</div>
                  <div class="mt-2 flex items-end gap-2">
                    <span class="text-2xl font-bold text-emerald-800">{{ participantStatusCounts(booking).attending }}</span>
                    <span class="pb-1 text-xs text-emerald-700">confirmed yes</span>
                  </div>
                  <div class="mt-2 flex flex-wrap gap-1.5 text-xs font-medium">
                    <span class="rounded bg-emerald-50 px-2 py-1 text-emerald-700">{{ participantStatusCounts(booking).attending }} yes</span>
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
                    :class="familyPersonBookingStatus(booking, person) === status.value ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'"
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
              <div class="rounded border border-emerald-100 bg-emerald-50 p-3">
                <div class="text-xs font-semibold uppercase tracking-wide text-emerald-600">Participated</div>
                <div class="mt-1 text-xl font-bold text-emerald-900">{{ booking.cost_split.attended_count }}</div>
              </div>
              <div class="rounded border border-indigo-100 bg-indigo-50 p-3">
                <div class="text-xs font-semibold uppercase tracking-wide text-indigo-600">Each</div>
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

    <section v-if="activeView === 'admin-bookings'" class="space-y-6">
      <div>
        <h2 class="section-title">Manage Bookings</h2>
        <p class="section-copy mt-1">Create court bookings, update attendance, and generate per-booking invoices.</p>
      </div>

      <div class="panel-card p-4 sm:p-5">
          <div class="mb-3 flex items-center justify-between gap-3">
            <div class="min-w-0">
              <h3 class="text-base font-semibold sm:text-lg">{{ editingBookingId ? 'Edit booking' : 'Create booking' }}</h3>
              <p class="hidden text-sm text-slate-600 sm:block">Choose a court, schedule, and cost.</p>
            </div>
            <button v-if="editingBookingId" class="btn-muted shrink-0" @click="resetBookingForm">Cancel</button>
          </div>
          <div class="grid gap-2 sm:grid-cols-2 sm:gap-3 lg:grid-cols-4">
            <div>
              <label class="form-label">🏸 Court</label>
              <select v-model="selectedCourtId" class="form-input">
                <option value="">Select a court</option>
                <option v-for="court in activeCourts" :key="court.id" :value="court.id">{{ court.name }} · {{ court.location || 'No location' }}</option>
              </select>
            </div>
            <div>
              <label class="form-label">📅 Date</label>
              <input v-model="bookingDate" type="date" class="form-input" />
            </div>
            <div>
              <label class="form-label">⏰ Start time</label>
              <input v-model="startTime" type="time" class="form-input" />
            </div>
            <div>
              <label class="form-label">⏱️ End time</label>
              <input v-model="endTime" type="time" class="form-input" />
            </div>
            <div>
              <label class="form-label">💶 Cost</label>
              <input v-if="editingBookingId" v-model="bookingCost" type="number" min="0" step="0.01" class="form-input" />
              <input v-else :value="calculatedBookingCost" type="number" min="0" step="0.01" class="form-input" readonly />
              <p class="mt-1 text-xs text-slate-500">{{ editingBookingId ? 'Override the saved booking cost.' : 'Calculated from court rates and duration.' }}</p>
            </div>
            <div v-if="editingBookingId">
              <label class="form-label">📌 Status</label>
              <select v-model="bookingStatus" class="form-input">
                <option value="confirmed">Created</option>
                <option value="completed">Completed</option>
                <option value="settled">Settled</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div v-if="!editingBookingId">
              <label class="form-label">🔁 Recurring</label>
              <select v-model="recurringMode" class="form-input">
                <option :value="false">One-off</option>
                <option :value="true">Every week on the same day</option>
              </select>
            </div>
            <div class="sm:col-span-2 lg:col-span-4">
              <label class="form-label">📝 Notes</label>
              <input v-model="bookingNotes" placeholder="Optional booking notes" class="form-input" />
            </div>
          </div>
          <div v-if="recurringMode && !editingBookingId" class="mt-3 grid gap-2 sm:grid-cols-2 sm:gap-3">
            <div>
              <label class="form-label">Repeat every</label>
              <input v-model.number="recurringIntervalWeeks" type="number" min="1" class="form-input" />
              <p class="mt-1 text-xs text-slate-500">weeks</p>
            </div>
            <div>
              <label class="form-label">Stop after</label>
              <input v-model="recurringEndDate" type="date" class="form-input" />
            </div>
          </div>

          <div class="mt-3 flex justify-end">
            <button class="btn-primary w-full sm:w-auto" @click="saveBooking">{{ editingBookingId ? 'Update booking' : 'Create booking' }}</button>
          </div>
      </div>

      <div class="space-y-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900">Upcoming bookings</h3>
          <p class="section-copy">Bookings still to be played. Expand a booking to edit attendance, details, or invoices.</p>
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
          <article v-for="booking in upcomingBookings" :key="booking.id" class="sub-card overflow-hidden p-0">
            <button type="button" class="flex w-full items-start justify-between gap-3 p-4 text-left transition hover:bg-slate-50" :aria-expanded="isBookingOpen(booking.id)" @click="toggleBooking(booking.id)">
              <div>
                <h4 class="font-semibold text-slate-900">{{ booking.court?.name || 'Court booking' }}</h4>
                <p class="text-sm text-slate-600">{{ bookingDayLabel(booking.booking_date) }} · {{ bookingDateLabel(booking.booking_date) }} · {{ booking.start_time }} - {{ booking.end_time }}</p>
                <p class="mt-1 text-sm text-slate-600">{{ participantStatusCounts(booking).attending }} attending · {{ participantStatusCounts(booking).tentative }} tentative · {{ bookingStatusSummary(booking) }}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="rounded bg-slate-900 px-2 py-1 text-sm font-semibold text-white">€{{ booking.cost || 0 }}</span>
                <span class="text-slate-400" aria-hidden="true">{{ isBookingOpen(booking.id) ? '−' : '+' }}</span>
              </div>
            </button>
            <div v-if="isBookingOpen(booking.id)" class="space-y-3 border-t border-slate-100 p-4">
              <div class="flex flex-wrap justify-end gap-2">
                <button class="btn-secondary" @click.stop="startEditBooking(booking)">Edit booking details</button>
                <button class="btn-muted" @click.stop="deleteBooking(booking)">Delete</button>
              </div>

            <h4 class="text-sm font-semibold text-slate-900">Attendance</h4>
            <div v-for="participant in booking.participants" :key="participant.id" class="grid gap-2 rounded border bg-white p-2 sm:grid-cols-[1.2fr_1fr_1fr_auto_auto]">
              <select class="form-input" @change="applyParticipantMember(participant, $event.target.value)">
                <option value="">Keep / ad hoc player</option>
                <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
              </select>
              <input v-model="participant.name" class="form-input" placeholder="Player name" />
              <select v-model="participant.status" class="form-input">
                <option value="attending">Attending</option>
                <option value="participated">Participated</option>
                <option value="not_attending">Not attending</option>
                <option value="tentative">Tentative</option>
              </select>
              <button class="btn-secondary" @click.stop="updateParticipant(booking, participant)">Save</button>
              <button class="btn-muted" @click.stop="deleteParticipant(booking, participant)">Remove</button>
            </div>
            <div class="grid gap-2 sm:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
              <select v-model="newParticipantMember[booking.id]" class="form-input">
                <option value="">New player (not a member)</option>
                <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
              </select>
              <input v-model="newParticipantName[booking.id]" class="form-input" placeholder="New player name" :disabled="!!newParticipantMember[booking.id]" />
              <input v-model="newParticipantPhone[booking.id]" class="form-input" placeholder="Phone or label" :disabled="!!newParticipantMember[booking.id]" />
              <select v-model="newParticipantStatus[booking.id]" class="form-input">
                <option value="attending">Attending</option>
                <option value="participated">Participated</option>
                <option value="not_attending">Not attending</option>
                <option value="tentative">Tentative</option>
              </select>
              <button class="btn-dark" @click.stop="addParticipant(booking)">Add</button>
            </div>

            </div>
          </article>
        </div>
      </div>


      <div class="mt-8 space-y-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900">Completed bookings</h3>
          <p class="section-copy">Admins can edit completed bookings in the active cost year, including participants, attendance status, booking details, and invoice status.</p>
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
          <article v-for="booking in completedBookings" :key="booking.id" class="sub-card overflow-hidden p-0">
            <button type="button" class="flex w-full items-start justify-between gap-3 p-4 text-left transition hover:bg-slate-50" :aria-expanded="isCompletedBookingOpen(booking.id)" @click="toggleCompletedBooking(booking.id)">
              <div>
                <h4 class="font-semibold text-slate-900">{{ booking.court?.name || 'Court booking' }}</h4>
                <p class="text-sm text-slate-600">{{ bookingDayLabel(booking.booking_date) }} · {{ bookingDateLabel(booking.booking_date) }} · {{ booking.start_time }} - {{ booking.end_time }}</p>
                <p class="mt-1 text-sm text-slate-600">{{ booking.cost_split.attended_count }} participated · €{{ booking.cost_split.cost_per_person }} each · {{ bookingStatusSummary(booking) }}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="rounded bg-slate-900 px-2 py-1 text-sm font-semibold text-white">€{{ booking.cost || 0 }}</span>
                <span class="text-slate-400" aria-hidden="true">{{ isCompletedBookingOpen(booking.id) ? '−' : '+' }}</span>
              </div>
            </button>
            <div v-if="isCompletedBookingOpen(booking.id)" class="space-y-3 border-t border-slate-100 p-4">
              <div class="flex justify-end"><button class="btn-secondary" @click.stop="startEditBooking(booking)">Edit booking details</button></div>
              <h5 class="text-sm font-semibold text-slate-900">Attendance</h5>
              <div v-for="participant in booking.participants" :key="participant.id" class="grid gap-2 rounded border bg-white p-2 sm:grid-cols-[1.2fr_1fr_1fr_auto_auto]">
                <select class="form-input" @change="applyParticipantMember(participant, $event.target.value)">
                  <option value="">Keep / ad hoc player</option>
                  <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
                </select>
                <input v-model="participant.name" class="form-input" placeholder="Player name" />
                <select v-model="participant.status" class="form-input">
                  <option value="attending">Attending</option>
                  <option value="participated">Participated</option>
                  <option value="not_attending">Not attending</option>
                  <option value="tentative">Tentative</option>
                </select>
                <button class="btn-secondary" @click.stop="updateParticipant(booking, participant)">Save</button>
                <button class="btn-muted" @click.stop="deleteParticipant(booking, participant)">Remove</button>
              </div>
              <div class="grid gap-2 sm:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
                <select v-model="newParticipantMember[booking.id]" class="form-input">
                  <option value="">New player (not a member)</option>
                  <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
                </select>
                <input v-model="newParticipantName[booking.id]" class="form-input" placeholder="New player name" :disabled="!!newParticipantMember[booking.id]" />
                <input v-model="newParticipantPhone[booking.id]" class="form-input" placeholder="Phone or label" :disabled="!!newParticipantMember[booking.id]" />
                <select v-model="newParticipantStatus[booking.id]" class="form-input">
                  <option value="attending">Attending</option>
                  <option value="participated">Participated</option>
                  <option value="not_attending">Not attending</option>
                  <option value="tentative">Tentative</option>
                </select>
                <button class="btn-dark" @click.stop="addParticipant(booking)">Add</button>
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section v-if="activeView === 'admin-courts'" class="space-y-6">
      <div>
        <h2 class="section-title">Manage Courts</h2>
        <p class="section-copy mt-1">Maintain courts, locations, map links, hourly rates, and vacation freeze periods.</p>
      </div>

      <div class="grid gap-6 lg:grid-cols-2">
        <div class="panel-card">
          <h3 class="mb-3 text-lg font-semibold">Add court</h3>
          <div class="space-y-3">
            <input v-model="newCourtName" placeholder="Court name" class="form-input" />
            <input v-model="newCourtLocation" placeholder="Location" class="form-input" />
            <input v-model="newCourtMapLink" placeholder="Google Maps link" class="form-input" />
            <input v-model="newCourtDescription" placeholder="Description" class="form-input" />
            <input v-model="newCourtRate" type="number" min="0" step="0.01" placeholder="Hourly rate" class="form-input" />
            <input v-model="newCourtHalfHourRate" type="number" min="0" step="0.01" placeholder="30-minute rate" class="form-input" />
            <button class="btn-dark w-full" @click="createCourt">Add court</button>
          </div>
        </div>

        <div class="panel-card">
          <h3 class="mb-3 text-lg font-semibold">Courts</h3>
          <div class="space-y-3">
            <article v-for="court in courts" :key="court.id" class="sub-card space-y-3">
              <div class="grid gap-2">
                <input v-model="court.name" class="form-input" />
                <input v-model="court.location" class="form-input" placeholder="Location" />
                <input v-model="court.map_link" class="form-input" placeholder="Google Maps link" />
                <input v-model="court.description" class="form-input" placeholder="Description" />
                <input v-model.number="court.hourly_rate" type="number" min="0" step="0.01" class="form-input" placeholder="Hourly rate" />
                <input v-model.number="court.half_hour_rate" type="number" min="0" step="0.01" class="form-input" placeholder="30-minute rate" />
              </div>
              <div class="grid grid-cols-2 gap-2">
                <button class="btn-secondary" @click="updateCourt(court)">Save</button>
                <button class="btn-muted" @click="deleteCourt(court)">Delete</button>
              </div>
            </article>
          </div>
          <p v-if="!courts.length && !loading" class="text-sm text-slate-600">No courts found.</p>
        </div>
      </div>

      <div class="panel-card">
        <div class="mb-4">
          <h3 class="text-lg font-semibold">No-play freeze periods</h3>
          <p class="section-copy">Dates in these ranges are skipped on the availability calendar.</p>
        </div>

        <form class="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr_1.4fr_auto]" @submit.prevent="createFreezePeriod">
          <input v-model="newFreezeTitle" class="form-input" placeholder="Vacation / hall closed" />
          <input v-model="newFreezeStartDate" type="date" class="form-input" />
          <input v-model="newFreezeEndDate" type="date" class="form-input" />
          <input v-model="newFreezeReason" class="form-input" placeholder="Optional reason" />
          <button class="btn-dark">Add</button>
        </form>

        <div class="mt-4 space-y-3">
          <article v-for="period in freezePeriods" :key="period.id" class="sub-card space-y-3">
            <div class="grid gap-2 lg:grid-cols-[1.2fr_1fr_1fr_1.4fr_auto]">
              <input v-model="period.title" class="form-input" />
              <input v-model="period.start_date" type="date" class="form-input" />
              <input v-model="period.end_date" type="date" class="form-input" />
              <input v-model="period.reason" class="form-input" placeholder="Reason" />
              <label class="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-700">
                <input v-model="period.is_active" type="checkbox" class="h-5 w-5 accent-emerald-600" />
                Active
              </label>
            </div>
            <div class="grid grid-cols-2 gap-2 sm:flex sm:justify-end">
              <button class="btn-secondary" @click="updateFreezePeriod(period)">Save</button>
              <button class="btn-muted" @click="deleteFreezePeriod(period)">Delete</button>
            </div>
          </article>
          <p v-if="!freezePeriods.length && !loading" class="text-sm text-slate-600">No freeze periods configured.</p>
        </div>
      </div>
    </section>

    <section v-if="activeView === 'availability'" class="space-y-6">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 class="section-title">Availability</h2>
          <p class="section-copy mt-1">Next 7 days are always visible. Log in to cast or update your family vote.</p>
        </div>
        <button v-if="isAdmin" type="button" class="btn-dark w-full sm:w-auto" @click="sendAvailabilitySummary">
          Send availability overview
        </button>
      </div>

      <div v-if="!isLoggedIn" class="alert-info">
        You can view total attendance counts below. Log in to vote for your family.
      </div>

      <div v-if="isLoggedIn" class="panel-card">
        <div class="mb-4">
          <h3 class="text-lg font-semibold">Family members</h3>
          <p class="section-copy">Add family members once, then use the count when voting who will come to play.</p>
        </div>

        <form class="grid gap-3 lg:grid-cols-[1fr_auto]" @submit.prevent="createFamilyMember">
          <input v-model="newFamilyName" placeholder="Family member name" class="form-input" />
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
          <div class="bg-gradient-to-br from-emerald-50 to-sky-50 p-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="text-lg font-bold text-slate-900">{{ day.weekday }}</div>
                <div class="text-sm text-slate-600">📅 {{ day.date }}</div>
              </div>
              <div class="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-sm font-bold text-slate-800 shadow-sm">
                <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                  <path d="M7 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm6.5-.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM7 10.5c-2.67 0-5 1.34-5 3v1A1.5 1.5 0 0 0 3.5 16h7A1.5 1.5 0 0 0 12 14.5v-1c0-1.66-2.33-3-5-3Zm6.5-.5c-.48 0-.95.05-1.38.15 1.15.82 1.88 1.98 1.88 3.35v1c0 .54-.14 1.05-.4 1.5h2.9a1.5 1.5 0 0 0 1.5-1.5v-.75c0-1.52-2.1-2.75-4.5-2.75Z" />
                </svg>
                <span>{{ day.totals.attendee_count }} people</span>
              </div>
            </div>

            <div class="mt-3 grid grid-cols-2 gap-2 text-sm font-semibold">
              <div class="rounded-xl border border-emerald-100 bg-white/80 p-3 text-emerald-700">✅ {{ day.totals.available_count || 0 }} available</div>
              <div class="flex items-center gap-2 rounded-xl border border-amber-100 bg-white/80 p-3 text-amber-700"><TentativeIcon class="h-4 w-4 shrink-0" /> <span>{{ day.totals.tentative_count || 0 }} tentative</span></div>
            </div>
            <div v-if="isLoggedIn && (availabilityNamesByStatus(day, 'available').length || availabilityNamesByStatus(day, 'tentative').length)" class="mt-3 grid gap-2 rounded-xl border border-white/70 bg-white/80 p-3 text-sm text-slate-700 sm:grid-cols-2">
              <div>
                <div class="text-xs font-bold uppercase tracking-wide text-emerald-600">Available</div>
                <div class="mt-2 flex flex-wrap gap-1.5">
                  <span v-for="name in availabilityNamesByStatus(day, 'available')" :key="`available-${day.date}-${name}`" class="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">{{ name }}</span>
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

          <div v-if="isLoggedIn" class="space-y-3 p-4">
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
                      :class="availabilityPersonStatus(day, person) === status.value ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'"
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
              <input v-model="day.notes" placeholder="Optional" class="form-input" />
            </div>

            <button class="btn-primary w-full" @click="saveAvailabilityVote(day)">Save vote</button>
          </div>
        </article>
      </div>
    </section>

    <section v-if="activeView === 'costs'" class="space-y-6">
      <div>
        <h2 class="section-title">My Costs</h2>
        <p class="section-copy mt-1">Review your family total, payment status, and every booking or shared cost included in the selected month.</p>
      </div>

      <div class="panel-card">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">Monthly period</h3>
            <p class="section-copy">Choose the month used for invoice and split details.</p>
          </div>
          <label class="block sm:w-48">
            <span class="form-label">Month</span>
            <input v-model="monthlyInvoiceMonth" type="month" class="form-input" @change="loadMonthlyInvoice" />
          </label>
        </div>
      </div>

      <div class="panel-card space-y-5">
        <div class="flex flex-col gap-1">
          <h3 class="text-lg font-semibold text-slate-900">Summary / Total</h3>
          <p class="section-copy">Everything for this month is shown below in one view.</p>
        </div>
        <div v-if="monthlyInvoice" class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <span class="text-slate-600">Month status</span>
          <span :class="monthStatusClass(monthlyInvoice.month_status?.status)" class="rounded-full px-3 py-1 text-xs font-bold">{{ monthStatusLabel(monthlyInvoice.month_status?.status) }}</span>
          <span class="text-slate-500">{{ monthlyInvoice.family_title || monthlyInvoice.family_owner?.name || 'Family invoice' }}</span>
        </div>
        <div v-if="monthlyInvoice" class="mt-4 grid gap-3 sm:grid-cols-3">
          <div class="rounded border border-indigo-100 bg-indigo-50 p-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-indigo-600">Bookings</div>
            <div class="mt-1 text-2xl font-bold text-indigo-900">€{{ monthlyInvoice.booking_total }}</div>
          </div>
          <div class="rounded border border-emerald-100 bg-emerald-50 p-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-emerald-600">Misc costs</div>
            <div class="mt-1 text-2xl font-bold text-emerald-900">€{{ monthlyInvoice.misc_total }}</div>
          </div>
          <div class="rounded border border-slate-200 bg-slate-50 p-3">
            <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Total due</div>
            <div class="mt-1 text-2xl font-bold text-slate-900">€{{ monthlyInvoice.total }}</div>
          </div>
        </div>

        <div v-if="currentPaymentInvoice" class="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
          <div class="mb-3 flex items-center justify-between gap-3"><div><h4 class="font-semibold text-slate-900">Pay by bank transfer</h4><p class="text-sm text-slate-600">Scan with your banking app or use this reference when paying.</p></div><span class="rounded-full bg-white px-3 py-1 text-sm font-bold text-indigo-800">{{ paymentStatusLabel(currentPaymentInvoice.payment_status) }}</span></div>
          <div v-if="currentPaymentInvoice.is_test_invoice" class="alert-warning">TEST MODE - This invoice is for testing only</div>
          <div class="grid gap-4 md:grid-cols-[180px_1fr]"><img v-if="currentPaymentInvoice.qr_code_data_url" :src="currentPaymentInvoice.qr_code_data_url" alt="Payment QR code" class="rounded border bg-white p-2" /><div class="space-y-2 text-sm"><p><strong>Total amount due:</strong> €{{ currentPaymentInvoice.amount_due }}</p><p><strong>Due date:</strong> {{ currentPaymentInvoice.due_date }}</p><p><strong>IBAN:</strong> {{ currentPaymentInvoice.iban }} <button class="btn-muted ml-2" @click="copyText(currentPaymentInvoice.iban)">Copy IBAN</button></p><p><strong>Account holder:</strong> {{ currentPaymentInvoice.account_holder_name }}</p><p><strong>Payment reference:</strong> {{ currentPaymentInvoice.payment_reference }} <button class="btn-muted ml-2" @click="copyText(currentPaymentInvoice.payment_reference)">Copy payment reference</button></p></div></div>
        </div>
        <div v-else-if="monthlyInvoice" class="rounded-xl border border-amber-100 bg-amber-50/70 p-4 text-sm text-amber-900">
          Payment QR and bank details will appear here when an admin marks {{ monthName(monthlyInvoice.month) }} as ready for payment.
        </div>

        <div v-if="monthlyInvoice" class="space-y-5">
          <section class="space-y-3">
            <div class="flex flex-col gap-1">
              <h4 class="font-semibold text-slate-900">Bookings included</h4>
              <p class="text-sm text-slate-600">Each booking shows the family members counted in your family share.</p>
            </div>
            <div v-if="monthlyInvoice.booking_items?.length" class="grid gap-3 lg:grid-cols-2">
              <article v-for="item in monthlyInvoice.booking_items" :key="item.booking_id" class="rounded-xl border border-indigo-100 bg-indigo-50/50 p-3 text-sm">
                <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h5 class="font-semibold text-slate-900">{{ item.court || 'Court booking' }}</h5>
                    <p class="text-slate-600">{{ item.date }} · {{ item.start_time }}-{{ item.end_time }}</p>
                  </div>
                  <span class="rounded-full bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-700">{{ bookingItemStatusSummary(item) }}</span>
                </div>
                <div v-if="(item.family_members || item.participants)?.length" class="mt-3 rounded-lg border border-indigo-100 bg-white p-2">
                  <div class="text-xs font-semibold uppercase tracking-wide text-indigo-600">Family members in this booking</div>
                  <div class="mt-1 font-medium text-slate-900">{{ (item.family_members || item.participants).join(' & ') }}</div>
                </div>
                <div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <div class="rounded bg-white p-2"><div class="text-xs text-slate-500">Players</div><div class="font-semibold">{{ item.total_people_played }}</div></div>
                  <div class="rounded bg-white p-2"><div class="text-xs text-slate-500">Total</div><div class="font-semibold">€{{ item.total_cost }}</div></div>
                  <div class="rounded bg-white p-2"><div class="text-xs text-slate-500">Each</div><div class="font-semibold">€{{ item.cost_per_person }}</div></div>
                  <div class="rounded bg-white p-2"><div class="text-xs text-slate-500">Family share</div><div class="font-semibold">€{{ item.amount }}</div></div>
                </div>
              </article>
            </div>
            <p v-if="!monthlyInvoice.booking_items?.length" class="text-sm text-slate-600">No booking costs for this month.</p>
          </section>

          <section class="space-y-3">
            <h4 class="font-semibold text-slate-900">Miscellaneous costs</h4>
            <div v-if="monthlyInvoice.misc_items?.length" class="grid gap-3 lg:grid-cols-2">
              <article v-for="item in monthlyInvoice.misc_items" :key="item.cost_id" class="rounded-xl border border-emerald-100 bg-emerald-50/70 p-3 text-sm">
              <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h5 class="font-semibold text-slate-900">{{ item.title }}</h5>
                  <p class="text-slate-600">{{ item.purchase_date || 'No purchase date' }} · {{ item.status }}</p>
                </div>
                <span class="rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700">€{{ item.amount }} each</span>
              </div>
              <p class="mt-2 text-sm text-slate-700">Split by {{ item.split_count }} members · Total €{{ item.amount_total || item.total_cost || 0 }}</p>
              </article>
            </div>
            <p v-if="!monthlyInvoice.misc_items?.length" class="text-sm text-slate-600">No misc costs for this month.</p>
          </section>
        </div>
      </div>
    </section>


    <section v-if="activeView === 'payment-settings'" class="space-y-6">
      <div><h2 class="section-title">Payment settings</h2><p class="section-copy mt-1">Configure bank-transfer account details and QR code test mode.</p></div>
      <div v-if="!isSuperAdmin" class="alert-warning">Only Super Admin can manage payment settings.</div>
      <div v-else class="panel-card space-y-4">
        <div class="grid gap-3 sm:grid-cols-2"><label><span class="form-label">Account holder name</span><input v-model="paymentSettings.account_holder_name" class="form-input" /></label><label><span class="form-label">Business bank name</span><input v-model="paymentSettings.bank_name" class="form-input" /></label><label><span class="form-label">IBAN</span><input v-model="paymentSettings.iban" class="form-input" /></label><label><span class="form-label">BIC optional</span><input v-model="paymentSettings.bic" class="form-input" /></label><label><span class="form-label">Payment description prefix</span><input v-model="paymentSettings.description_prefix" class="form-input" /></label><label><span class="form-label">Default due days</span><input v-model.number="paymentSettings.default_due_days" type="number" min="1" class="form-input" /></label></div>
        <label class="flex gap-2"><input v-model="paymentSettings.qr_enabled" type="checkbox" /> Enable QR payment feature</label><label class="flex gap-2"><input v-model="paymentSettings.test_mode" type="checkbox" /> Test mode</label>
        <div class="flex flex-wrap gap-2"><button class="btn-dark" @click="savePaymentSettings">Save settings</button><button class="btn-secondary" @click="generateTestInvoice">Generate Test Invoice</button></div>
      </div>
    </section>

    <section v-if="activeView === 'admin-costs'" class="space-y-6">
      <div>
        <h2 class="section-title">Invoices & Payments</h2>
        <p class="section-copy mt-1">Review family totals, prepare monthly invoices, and reconcile payments in one place.</p>
        <div class="mt-3 grid gap-2 sm:inline-grid sm:grid-flow-col sm:auto-cols-fr sm:rounded-xl sm:bg-slate-100 sm:p-1">
          <button class="btn-secondary w-full justify-center" :class="adminCostTab === 'invoices' ? 'bg-white text-indigo-800 shadow-sm' : ''" @click="adminCostTab = 'invoices'">Monthly invoices</button>
          <button class="btn-secondary w-full justify-center" :class="adminCostTab === 'misc' ? 'bg-white text-emerald-800 shadow-sm' : ''" @click="adminCostTab = 'misc'">Misc costs</button>
          <button class="btn-secondary w-full justify-center" :class="adminCostTab === 'booking' ? 'bg-white text-indigo-800 shadow-sm' : ''" @click="adminCostTab = 'booking'">Booking costs</button>
        </div>
      </div>

      <div v-if="adminCostTab === 'invoices'" class="panel-card">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">Monthly family invoices</h3>
            <p class="section-copy">Review each family's booking, shared-cost, and total amount for the selected month.</p>
          </div>
          <div class="grid gap-2 sm:grid-cols-[minmax(10rem,12rem)_minmax(12rem,16rem)_auto] sm:items-end">
            <label class="block sm:w-48">
              <span class="form-label">Month</span>
              <input v-model="monthlyInvoiceMonth" type="month" class="form-input" @change="loadAdminMonthlyInvoices" />
            </label>
            <label class="block">
              <span class="form-label">Month status</span>
              <select :value="adminMonthlyInvoices?.month_status?.status || 'OPEN'" class="form-input" @change="setMonthlyInvoiceStatus($event.target.value)">
                <option value="OPEN">Open</option>
                <option value="READY_FOR_PAYMENT">Ready for payment</option>
                <option value="SETTLED">Settled</option>
              </select>
            </label>
            <button class="btn-secondary" @click="notifyMonthlyInvoicesReady">Notify group</button>
          </div>
        </div>
        <div v-if="adminMonthlyInvoices" class="mt-4 space-y-4">
          <div class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <span class="text-slate-600">Month status</span>
            <span :class="monthStatusClass(adminMonthlyInvoices.month_status?.status)" class="rounded-full px-3 py-1 text-xs font-bold">{{ monthStatusLabel(adminMonthlyInvoices.month_status?.status) }}</span>
            <span v-if="adminMonthlyInvoices.month_status?.ready_at" class="text-slate-500">Ready {{ dateTimeLabel(adminMonthlyInvoices.month_status.ready_at) }}</span>
          </div>
          <div class="grid gap-3 sm:grid-cols-3">
            <div class="rounded border border-indigo-100 bg-indigo-50 p-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-indigo-600">Booking total</div>
              <div class="mt-1 text-2xl font-bold text-indigo-900">€{{ adminMonthlyInvoices.totals.booking_total }}</div>
            </div>
            <div class="rounded border border-emerald-100 bg-emerald-50 p-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-emerald-600">Shared costs</div>
              <div class="mt-1 text-2xl font-bold text-emerald-900">€{{ adminMonthlyInvoices.totals.misc_total }}</div>
            </div>
            <div class="rounded border border-slate-200 bg-slate-50 p-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Grand total</div>
              <div class="mt-1 text-2xl font-bold text-slate-900">€{{ adminMonthlyInvoices.totals.total }}</div>
            </div>
          </div>
          <div class="grid gap-3">
            <details v-for="invoice in adminMonthlyInvoices.invoices" :key="invoice.id || invoice.user.id" class="rounded-xl border border-slate-200 bg-white p-4">
              <summary class="cursor-pointer list-none">
                <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h4 class="font-semibold text-slate-900">{{ invoice.family_title || invoice.user.name || invoice.user.email || invoice.user.phone }}</h4>
                    <p class="text-sm text-slate-600">{{ adminMonthlyInvoices.month }} · {{ (invoice.booking_items || []).length }} booking costs · {{ (invoice.misc_items || []).length }} misc costs</p>
                  </div>
                  <div class="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                    <div class="rounded bg-slate-50 p-2"><div class="text-xs text-slate-500">Total cost</div><div class="font-bold">€{{ invoice.total }}</div></div>
                    <div class="rounded bg-emerald-50 p-2"><div class="text-xs text-slate-500">Amount paid</div><div class="font-bold text-emerald-800">€{{ invoice.paid_amount || 0 }}</div></div>
                    <div class="rounded bg-amber-50 p-2"><div class="text-xs text-slate-500">Balance</div><div class="font-bold text-amber-800">€{{ invoice.balance_amount ?? invoice.total }}</div></div>
                  </div>
                </div>
              </summary>
              <div class="mt-4 space-y-3">
                <div class="overflow-x-auto rounded-lg border border-slate-200">
                  <table class="min-w-full divide-y divide-slate-200 text-sm">
                    <thead class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <tr>
                        <th class="px-3 py-2">Type</th>
                        <th class="px-3 py-2">Date</th>
                        <th class="px-3 py-2">Details</th>
                        <th class="px-3 py-2">Members</th>
                        <th class="px-3 py-2 text-right">Total</th>
                        <th class="px-3 py-2 text-right">Split</th>
                        <th class="px-3 py-2 text-right">Share</th>
                      </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 bg-white">
                      <tr v-for="item in invoice.booking_items" :key="`booking-${invoice.id}-${item.booking_id}`" class="align-top">
                        <td class="whitespace-nowrap px-3 py-2 font-medium text-indigo-800">Booking</td>
                        <td class="whitespace-nowrap px-3 py-2 text-slate-700">{{ item.date }}<span class="block text-xs text-slate-500">{{ item.start_time }}-{{ item.end_time }}</span></td>
                        <td class="px-3 py-2 text-slate-700">{{ item.court }}</td>
                        <td class="px-3 py-2 text-slate-700">{{ (item.family_members || item.participants || []).join(' & ') }}</td>
                        <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">€{{ item.total_cost }}</td>
                        <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">{{ item.total_people_played }} players</td>
                        <td class="whitespace-nowrap px-3 py-2 text-right font-semibold text-slate-900">€{{ item.amount }}</td>
                      </tr>
                      <tr v-for="item in invoice.misc_items" :key="`misc-${invoice.id}-${item.cost_id}`" class="align-top">
                        <td class="whitespace-nowrap px-3 py-2 font-medium text-emerald-800">Misc</td>
                        <td class="whitespace-nowrap px-3 py-2 text-slate-700">{{ item.purchase_date || 'No date' }}</td>
                        <td class="px-3 py-2 text-slate-700">{{ item.title }}</td>
                        <td class="px-3 py-2 text-slate-500">Family split</td>
                        <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">€{{ item.amount_total }}</td>
                        <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">{{ item.split_count }} ways</td>
                        <td class="whitespace-nowrap px-3 py-2 text-right font-semibold text-slate-900">€{{ item.amount }}</td>
                      </tr>
                      <tr v-if="!invoice.booking_items?.length && !invoice.misc_items?.length">
                        <td colspan="7" class="px-3 py-4 text-center text-slate-500">No booking or misc costs.</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-if="invoice.payment_invoice" class="flex flex-col gap-2 rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <div class="min-w-0 text-slate-700">
                    <span class="font-semibold text-indigo-950">Payment</span>
                    <span class="mx-1 text-slate-400">·</span>
                    <span>{{ invoice.payment_invoice.invoice_number }}</span>
                    <span class="mx-1 text-slate-400">·</span>
                    <span>Due {{ invoice.payment_invoice.due_date }}</span>
                    <span class="mx-1 text-slate-400">·</span>
                    <span>{{ paymentStatusLabel(invoice.payment_invoice.payment_status) }}</span>
                    <span class="mx-1 text-slate-400">·</span>
                    <span class="font-semibold">€{{ invoice.payment_invoice.amount_due }}</span>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <button class="btn-secondary" @click="loadPaymentInvoice(invoice.payment_invoice.id)">QR</button>
                    <button class="btn-secondary" @click="setPaymentStatus(invoice.payment_invoice, 'PAID')">Paid</button>
                    <button class="btn-muted" @click="setPaymentStatus(invoice.payment_invoice, 'UNPAID')">Unpaid</button>
                  </div>
                </div>
              </div>
            </details>
          </div>

          <div v-if="adminMonthlyInvoices.month_status?.status === 'OPEN'" class="rounded-lg border border-amber-100 bg-amber-50/70 p-3 text-sm text-amber-900">
            Payment QR codes and bank details become available after the month status is changed to Ready for payment.
          </div>

          <div v-if="selectedPaymentInvoice" class="rounded-lg border border-indigo-200 bg-indigo-50/60 p-3">
            <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h4 class="font-semibold text-slate-900">QR and bank details</h4>
                <p class="text-sm text-slate-600">{{ selectedPaymentInvoice.user?.name || selectedPaymentInvoice.user?.email || 'Family invoice' }} · {{ paymentStatusLabel(selectedPaymentInvoice.payment_status) }}</p>
              </div>
              <button class="btn-muted" @click="selectedPaymentInvoice = null">Close</button>
            </div>
            <div class="grid gap-3 md:grid-cols-[140px_1fr]">
              <img v-if="selectedPaymentInvoice.qr_code_data_url" :src="selectedPaymentInvoice.qr_code_data_url" alt="Payment QR code" class="w-32 rounded border bg-white p-2" />
              <div class="overflow-x-auto rounded border border-white/70 bg-white">
                <table class="min-w-full text-sm">
                  <tbody class="divide-y divide-slate-100">
                    <tr><th class="w-40 px-3 py-2 text-left font-semibold text-slate-600">Amount due</th><td class="px-3 py-2 font-semibold text-slate-900">€{{ selectedPaymentInvoice.amount_due }}</td></tr>
                    <tr><th class="px-3 py-2 text-left font-semibold text-slate-600">Due date</th><td class="px-3 py-2 text-slate-700">{{ selectedPaymentInvoice.due_date }}</td></tr>
                    <tr><th class="px-3 py-2 text-left font-semibold text-slate-600">IBAN</th><td class="px-3 py-2 text-slate-700">{{ selectedPaymentInvoice.iban }} <button class="btn-muted ml-2" @click="copyText(selectedPaymentInvoice.iban)">Copy</button></td></tr>
                    <tr><th class="px-3 py-2 text-left font-semibold text-slate-600">Account holder</th><td class="px-3 py-2 text-slate-700">{{ selectedPaymentInvoice.account_holder_name }}</td></tr>
                    <tr><th class="px-3 py-2 text-left font-semibold text-slate-600">Reference</th><td class="px-3 py-2 text-slate-700">{{ selectedPaymentInvoice.payment_reference }} <button class="btn-muted ml-2" @click="copyText(selectedPaymentInvoice.payment_reference)">Copy</button></td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

        </div>
      </div>

      <div v-if="adminCostTab === 'misc'" class="space-y-4">
        <details class="panel-card" open>
          <summary class="cursor-pointer text-lg font-semibold text-slate-900">Add shared misc cost</summary>
          <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <input v-model="newMiscTitle" class="form-input" placeholder="Title" />
            <input v-model="newMiscPaidBy" class="form-input" placeholder="Paid by" />
            <input v-model="newMiscAmount" type="number" min="0" step="0.01" class="form-input" placeholder="Amount" />
            <input v-model="newMiscPurchaseDate" type="date" class="form-input" />
            <input v-model.number="newMiscSplitCount" type="number" min="1" class="form-input" placeholder="Split count" />
            <input v-model="newMiscDescription" class="form-input md:col-span-2" placeholder="Description" />
          </div>
          <button class="btn-dark mt-3 w-full sm:w-auto" @click="createMiscCost">Add cost</button>
        </details>

        <div class="grid gap-4 lg:grid-cols-2">
          <article v-for="cost in miscCosts" :key="cost.id" class="sub-card overflow-hidden p-0">
            <button type="button" class="flex w-full items-start justify-between gap-3 p-4 text-left transition hover:bg-slate-50" :aria-expanded="isMiscCostOpen(cost.id)" @click="toggleMiscCost(cost.id)">
              <div>
                <h3 class="font-semibold text-slate-900">{{ cost.title }}</h3>
                <p class="text-sm text-slate-600">{{ cost.description || 'No description' }}</p>
                <p class="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{{ cost.status }} · {{ cost.purchase_date || 'No date' }} · split {{ cost.split_count }}</p>
              </div>
              <div class="flex shrink-0 items-center gap-3">
                <span class="rounded bg-slate-900 px-2 py-1 text-sm font-semibold text-white">€{{ cost.amount }}</span>
                <span class="text-slate-400" aria-hidden="true">{{ isMiscCostOpen(cost.id) ? '−' : '+' }}</span>
              </div>
            </button>
            <div v-if="isMiscCostOpen(cost.id)" class="space-y-3 border-t border-slate-100 p-4">
              <div class="rounded border bg-slate-50 p-2 text-sm text-slate-700">Split by {{ cost.split_count }} members · €{{ cost.cost_per_person }} each</div>
              <div class="grid gap-3 sm:grid-cols-2">
                <input v-model="cost.title" class="form-input" placeholder="Title" />
                <input v-model="cost.paid_by" class="form-input" placeholder="Paid by" />
                <input v-model.number="cost.amount" type="number" min="0" step="0.01" class="form-input" />
                <input v-model="cost.purchase_date" type="date" class="form-input" />
                <input v-model.number="cost.split_count" type="number" min="1" class="form-input" />
                <select v-model="cost.status" class="form-input">
                  <option value="open">Open</option>
                  <option value="settled">Settled</option>
                </select>
                <textarea v-model="cost.description" class="form-input sm:col-span-2" placeholder="Description"></textarea>
              </div>
              <div class="grid gap-2 sm:grid-cols-2">
                <button class="btn-secondary" @click="updateMiscCost(cost)">Save changes</button>
                <button class="btn-muted" @click="deleteMiscCost(cost)">Delete</button>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div v-if="adminCostTab === 'booking'" class="mt-8 space-y-4">
        <div>
          <h3 class="text-lg font-semibold text-slate-900">Booking settlement archive</h3>
          <p class="section-copy">Completed booking editing and settlement is handled on Manage Bookings. This page only keeps the older archive for cost reference.</p>
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
          <article v-for="booking in archivedBookings" :key="booking.id" class="sub-card p-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <h4 class="font-semibold text-slate-900">{{ booking.court?.name || 'Court booking' }}</h4>
                <p class="text-sm text-slate-600">{{ bookingDayLabel(booking.booking_date) }} · {{ bookingDateLabel(booking.booking_date) }} · {{ booking.start_time }} - {{ booking.end_time }}</p>
                <p class="mt-1 text-sm text-slate-600">{{ booking.cost_split.attended_count }} participated · €{{ booking.cost_split.cost_per_person }} each · {{ bookingStatusSummary(booking) }}</p>
              </div>
              <span class="rounded bg-slate-900 px-2 py-1 text-sm font-semibold text-white">€{{ booking.cost || 0 }}</span>
            </div>
          </article>
        </div>
        <div v-if="archivedBookingPagination.pages > 1" class="mt-4 flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
          <span class="text-slate-600">Page {{ archivedBookingPagination.page }} of {{ archivedBookingPagination.pages }} · {{ archivedBookingPagination.total }} archived bookings</span>
          <div class="flex gap-2">
            <button class="btn-secondary" :disabled="archivedBookingPagination.page <= 1" @click="changeArchivedBookingPage(archivedBookingPagination.page - 1)">Previous</button>
            <button class="btn-secondary" :disabled="archivedBookingPagination.page >= archivedBookingPagination.pages" @click="changeArchivedBookingPage(archivedBookingPagination.page + 1)">Next</button>
          </div>
        </div>
      </div>
    </section>

    <section v-if="activeView === 'members'" class="space-y-6">
      <div>
        <h2 class="section-title">Members</h2>
        <p class="section-copy mt-1">Manage registered club members, family members, and admin access.</p>
      </div>

      <div v-if="!isAdmin" class="alert-warning">
        Admin access is required to manage members.
      </div>

      <div v-else class="space-y-4">
        <article v-for="member in adminUsers" :key="member.id" class="panel-card space-y-4">
          <div class="grid gap-3 lg:grid-cols-[1.1fr_1fr_1fr_auto] lg:items-end">
            <div>
              <label class="form-label">Name</label>
              <input v-model="member.name" class="form-input" placeholder="Name" />
            </div>
            <div>
              <label class="form-label">Email</label>
              <input v-model="member.email" type="email" class="form-input" placeholder="Email" />
            </div>
            <div>
              <label class="form-label">WhatsApp</label>
              <input v-model="member.whatsapp_number" class="form-input" placeholder="+31..." />
            </div>
            <div class="grid gap-2">
              <button class="btn-secondary" @click="updateAdminUser(member)">Save</button>
              <button class="btn-muted" @click="deleteAdminUser(member)">Remove family</button>
            </div>
          </div>

          <div class="grid gap-3 md:grid-cols-4">
            <div>
              <label class="form-label">Reset password</label>
              <input
                v-model="newAdminUserPassword[member.id]"
                type="password"
                minlength="6"
                class="form-input"
                placeholder="Leave blank to keep"
              />
            </div>
            <label class="flex items-center gap-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
              <input v-model="member.is_club_member" type="checkbox" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
              Club member
            </label>
            <label class="flex items-center gap-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
              <input
                :checked="member.role === 'admin'"
                type="checkbox"
                class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                @change="member.role = $event.target.checked ? 'admin' : 'member'"
              />
              Admin
            </label>
            <div class="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              Login id: {{ member.email || member.phone }}
            </div>
          </div>

          <div class="border-t border-slate-100 pt-3">
            <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <h3 class="text-sm font-semibold text-slate-900">Family members</h3>
              <button class="btn-dark" @click="createAdminFamilyMember(member)">Add family member</button>
            </div>
            <div class="mb-3 grid gap-2 md:grid-cols-3">
              <input v-model="newAdminFamilyName[member.id]" class="form-input" placeholder="Family member name" />
              <input v-model="newAdminFamilyRelationship[member.id]" class="form-input" placeholder="Relationship" />
              <select v-model="newAdminFamilyLinkedUser[member.id]" class="form-input">
                <option value="">No linked account</option>
                <option v-for="option in linkableUserOptions(member.id)" :key="option.id" :value="option.id">{{ option.label }}</option>
              </select>
            </div>
            <div v-if="member.family_members?.length" class="space-y-2">
              <div
                v-for="familyMember in member.family_members"
                :key="familyMember.id"
                class="grid gap-2 rounded border bg-white p-3 md:grid-cols-[1fr_1fr_1fr_auto_auto]"
              >
                <input v-model="familyMember.name" class="form-input" placeholder="Family member name" />
                <input v-model="familyMember.relationship" class="form-input" placeholder="Relationship" />
                <select v-model="familyMember.linked_user_id" class="form-input">
                  <option :value="null">No linked account</option>
                  <option v-for="option in linkableUserOptions(member.id)" :key="option.id" :value="option.id">{{ option.label }}</option>
                </select>
                <div class="flex items-center gap-2">
                  <label class="flex items-center gap-2 text-sm font-medium text-slate-700">
                    <input v-model="familyMember.is_club_member" type="checkbox" class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                    Club member
                  </label>
                  <button class="btn-secondary" @click="updateAdminFamilyMember(member, familyMember)">Save</button>
                </div>
                <button class="btn-muted" @click="deleteAdminFamilyMember(member, familyMember)">Remove</button>
              </div>
            </div>
            <p v-else class="text-sm text-slate-600">No family members added for this user.</p>
          </div>
        </article>
        <p v-if="!adminUsers.length && !loading" class="text-sm text-slate-600">No users found.</p>
      </div>
    </section>


    <section v-if="activeView === 'admin-audit-logs'" class="space-y-6">
      <div>
        <h2 class="section-title">Admin Audit Logs</h2>
        <p class="section-copy mt-1">Append-only activity history for admin actions. These rows are read-only and show when an event happened, who did it, the event type, and what changed.</p>
      </div>

      <div class="panel-card overflow-hidden p-0">
        <div class="border-b border-slate-100 bg-slate-50 px-4 py-3">
          <h3 class="text-base font-semibold text-slate-900">Recent admin activity</h3>
          <p class="text-sm text-slate-600">Newest events first.</p>
        </div>
        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-slate-200 text-sm">
            <thead class="bg-white text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th class="px-3 py-2">When</th>
                <th class="px-3 py-2">Admin</th>
                <th class="px-3 py-2">Event</th>
                <th class="px-3 py-2">Entity</th>
                <th class="px-3 py-2">Summary</th>
                <th class="px-3 py-2">Details</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="log in adminAuditLogs" :key="log.id" class="align-top">
                <td class="whitespace-nowrap px-3 py-3 font-medium text-slate-900">{{ auditLogDate(log.occurred_at) }}</td>
                <td class="px-3 py-3 text-slate-700">
                  <div class="font-semibold text-slate-900">{{ log.admin_name || log.admin_email || log.admin_phone || 'Unknown admin' }}</div>
                  <div class="text-xs text-slate-500">{{ log.admin_email || log.admin_phone || `User ${log.admin_user_id || 'unknown'}` }}</div>
                </td>
                <td class="px-3 py-3"><span class="rounded-full bg-indigo-50 px-2 py-1 text-xs font-bold uppercase text-indigo-700">{{ log.event_type }}</span></td>
                <td class="px-3 py-3 text-slate-700">{{ log.entity_type }}<div v-if="log.entity_id" class="text-xs text-slate-500">#{{ log.entity_id }}</div></td>
                <td class="px-3 py-3 text-slate-800">{{ log.summary }}</td>
                <td class="px-3 py-3"><ul class="max-w-md space-y-1 text-xs text-slate-700"><li v-for="line in auditLogDetails(log.details)" :key="line" class="rounded bg-slate-50 px-2 py-1">{{ line }}</li></ul></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!adminAuditLogs.length && !loading" class="p-4 text-sm text-slate-600">No admin audit logs found.</p>
        <div v-if="adminAuditPagination.pages > 1" class="flex items-center justify-between border-t border-slate-100 p-3 text-sm">
          <span class="text-slate-600">Page {{ adminAuditPagination.page }} of {{ adminAuditPagination.pages }} · {{ adminAuditPagination.total }} logs</span>
          <div class="flex gap-2">
            <button class="btn-secondary" :disabled="adminAuditPagination.page <= 1" @click="changeAdminAuditPage(adminAuditPagination.page - 1)">Previous</button>
            <button class="btn-secondary" :disabled="adminAuditPagination.page >= adminAuditPagination.pages" @click="changeAdminAuditPage(adminAuditPagination.page + 1)">Next</button>
          </div>
        </div>
      </div>
    </section>

    <section v-if="activeView === 'notifications'" class="space-y-6">
      <div class="rounded-3xl border border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-sky-50 p-4 shadow-sm sm:p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.24em] text-emerald-700">WhatsApp bot</p>
            <h2 class="mt-1 text-2xl font-black text-slate-950">Group notification admin</h2>
            <p class="mt-2 max-w-2xl text-sm text-slate-600">Choose which app events can notify the group, edit message templates, and send a safe test message to your WhatsApp number before enabling a template.</p>
          </div>
          <button class="btn-dark w-full sm:w-auto" @click="loadWhatsAppNotifications">Refresh</button>
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div class="space-y-4">
          <article v-for="setting in whatsappSettings" :key="setting.id" class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div class="min-w-0">
                <p class="text-xs font-bold uppercase tracking-wide text-slate-400">{{ setting.event_key }}</p>
                <input v-model="setting.title" class="mt-1 w-full rounded-xl border border-transparent bg-slate-50 px-3 py-2 text-lg font-bold text-slate-900 focus:border-emerald-400 focus:outline-none" />
                <p class="mt-1 text-sm text-slate-600">{{ setting.description }}</p>
              </div>
              <label class="flex items-center justify-between gap-3 rounded-full border px-3 py-2 text-sm font-semibold" :class="setting.is_enabled ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-slate-50 text-slate-500'">
                Enabled
                <input v-model="setting.is_enabled" type="checkbox" class="h-5 w-5 accent-emerald-600" />
              </label>
            </div>
            <div class="mt-4 grid gap-3 sm:grid-cols-2">
              <label class="block">
                <span class="form-label">Group / chat id override</span>
                <input v-model="setting.group_id" class="form-input" placeholder="1203...@g.us (optional)" />
              </label>
              <label class="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-700">
                <input v-model="setting.send_to_group" type="checkbox" class="h-5 w-5 accent-emerald-600" />
                Send to group by default
              </label>
              <label class="block sm:col-span-2">
                <span class="form-label">Test WhatsApp number</span>
                <input v-model="setting.test_recipient_number" class="form-input" placeholder="+31612345678 (test sends only)" />
                <span class="mt-1 block text-xs text-slate-500">Send test uses this number instead of the group. Use international format; it will be sent as a direct WhatsApp chat.</span>
              </label>
              <label class="block sm:col-span-2">
                <span class="form-label">Message template</span>
                <textarea v-model="setting.template" rows="5" class="form-input font-mono text-sm" placeholder="Use placeholders like {{date}}, {{court}}, {{available_count}}"></textarea>
              </label>
            </div>
            <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-end">
              <button class="btn-secondary" @click="testWhatsAppNotification(setting)">Send test</button>
              <button class="btn-dark" @click="saveWhatsAppNotification(setting)">Save template</button>
            </div>
          </article>
          <p v-if="!whatsappSettings.length && !loading" class="text-sm text-slate-600">No notification settings found.</p>
        </div>

        <aside class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:sticky lg:top-24 lg:self-start">
          <h3 class="font-bold text-slate-900">Recent test sends</h3>
          <div class="mt-3 space-y-3">
            <div v-for="log in whatsappLogs" :key="log.id" class="rounded-xl border border-slate-100 bg-slate-50 p-3 text-sm">
              <div class="flex items-center justify-between gap-2">
                <span class="font-semibold text-slate-800">{{ log.event_key }}</span>
                <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="log.status === 'sent' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'">{{ log.status }}</span>
              </div>
              <p class="mt-2 line-clamp-4 whitespace-pre-line text-xs text-slate-600">{{ log.message }}</p>
            </div>
            <p v-if="!whatsappLogs.length" class="text-sm text-slate-500">No sends yet.</p>
          </div>
        </aside>
      </div>
    </section>

    <div v-if="verificationDetails" class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4" @click.self="closeVerificationDetails">
      <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl">
        <div class="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
          <div>
            <h3 class="text-lg font-bold text-slate-900">Cost verification</h3>
            <p class="text-sm text-slate-600">{{ verificationDetails.title }}</p>
          </div>
          <button class="btn-muted" @click="closeVerificationDetails">Close</button>
        </div>
        <div class="mt-4 grid gap-3 sm:grid-cols-4">
          <div class="rounded border border-indigo-100 bg-indigo-50 p-3">
            <div class="text-xs font-semibold uppercase text-indigo-600">{{ verificationDetails.itemLabel }}</div>
            <div class="mt-1 text-xl font-bold text-indigo-900">{{ verificationDetails.items.length }}</div>
          </div>
          <div class="rounded border border-emerald-100 bg-emerald-50 p-3">
            <div class="text-xs font-semibold uppercase text-emerald-600">{{ verificationDetails.peopleLabel }}</div>
            <div class="mt-1 text-xl font-bold text-emerald-900">{{ verificationDetails.totalPeople }}</div>
          </div>
          <div class="rounded border border-slate-200 bg-slate-50 p-3">
            <div class="text-xs font-semibold uppercase text-slate-500">Total cost</div>
            <div class="mt-1 text-xl font-bold text-slate-900">€{{ verificationDetails.totalCost }}</div>
          </div>
          <div class="rounded border border-amber-100 bg-amber-50 p-3">
            <div class="text-xs font-semibold uppercase text-amber-600">Your share</div>
            <div class="mt-1 text-xl font-bold text-amber-900">€{{ verificationDetails.shareCost }}</div>
          </div>
        </div>
        <div class="mt-4 overflow-x-auto rounded border border-slate-200">
          <table class="min-w-full divide-y divide-slate-200 text-sm">
            <thead class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr><th class="px-3 py-2">Item</th><th class="px-3 py-2">Split count</th><th class="px-3 py-2">Total cost</th><th class="px-3 py-2">Per share</th><th class="px-3 py-2">Member share</th></tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="item in verificationDetails.items" :key="item.booking_id || item.date">
                <td class="px-3 py-2 font-medium text-slate-900">{{ item.date || item.purchase_date }}<div class="text-xs font-normal text-slate-500">{{ item.detail || `${item.court || item.title || 'Cost'} · ${item.start_time || ''}${item.end_time ? '-' + item.end_time : ''}` }}</div></td>
                <td class="px-3 py-2">{{ item.total_people_played || item.split_count }}</td>
                <td class="px-3 py-2">€{{ item.total_cost || item.amount_total }}</td>
                <td class="px-3 py-2">€{{ item.cost_per_person || item.amount }}</td>
                <td class="px-3 py-2 font-semibold">€{{ item.amount }}<div v-if="item.participants?.length" class="text-xs font-normal text-slate-500">{{ item.participants.join(', ') }}</div></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </div>
</template>

<script>
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { clearAuthSession, getAuthSessionVersion, getSessionValue, hasAuthSession, setSessionValue } from '../authSession'

const TentativeIcon = (props) => h('svg', {
  ...props,
  viewBox: '0 0 20 20',
  fill: 'currentColor',
  'aria-hidden': 'true'
}, [
  h('path', { d: 'M10 2a8 8 0 1 0 0 16 8 8 0 0 0 0-16Zm0 13.25a1 1 0 1 1 0-2 1 1 0 0 1 0 2Zm1.27-4.88c-.47.28-.52.42-.52.88a.75.75 0 0 1-1.5 0c0-1.21.58-1.78 1.25-2.17.68-.4 1.1-.7 1.1-1.43 0-.8-.63-1.35-1.55-1.35-.82 0-1.42.43-1.74 1.25a.75.75 0 0 1-1.4-.54c.54-1.4 1.74-2.21 3.14-2.21 1.78 0 3.05 1.16 3.05 2.85 0 1.58-1.04 2.2-1.83 2.67Z' })
])

export default {
  components: { TentativeIcon },
  props: {
    initialView: {
      type: String,
      default: 'availability'
    }
  },
  setup(props) {
    const router = useRouter()
    const activeView = ref(props.initialView)
    const bookings = ref([])
    const completedBookingHistory = ref([])
    const archivedBookingHistory = ref([])
    const courts = ref([])
    const freezePeriods = ref([])
    const familyMembers = ref([])
    const adminUsers = ref([])
    const playDays = ref([])
    const miscCosts = ref([])
    const monthlyInvoice = ref(null)
    const currentPaymentInvoice = ref(null)
    const adminMonthlyInvoices = ref(null)
    const monthlyInvoiceMonth = ref(localIsoMonth())
    const whatsappSettings = ref([])
    const whatsappLogs = ref([])
    const adminAuditLogs = ref([])
    const completedBookingPagination = ref({ page: 1, per_page: 12, total: 0, pages: 0 })
    const archivedBookingPagination = ref({ page: 1, per_page: 12, total: 0, pages: 0 })
    const adminAuditPagination = ref({ page: 1, per_page: 50, total: 0, pages: 0 })
    const openBookingIds = ref(new Set())
    const openCompletedBookingIds = ref(new Set())
    const openMiscCostIds = ref(new Set())
    const loading = ref(false)
    const errorMsg = ref('')
    const editingBookingId = ref(null)
    const bookingDate = ref(localIsoDate())
    const startTime = ref('18:00')
    const endTime = ref('19:00')
    const bookingCost = ref('0')
    const bookingStatus = ref('confirmed')
    const bookingNotes = ref('')
    const selectedCourtId = ref('')
    const recurringMode = ref(false)
    const recurringIntervalWeeks = ref(1)
    const recurringCount = ref(1)
    const recurringEndDate = ref(localIsoDate())
    const adminBookingTab = ref('bookings')
    const adminCostTab = ref('invoices')
    const completedBookingTab = ref('completed')
    const invoiceDetailTab = ref('booking')
    const newCourtName = ref('')
    const newCourtLocation = ref('')
    const newCourtDescription = ref('')
    const newCourtMapLink = ref('')
    const newCourtRate = ref('25')
    const newCourtHalfHourRate = ref('12.5')
    const newFreezeTitle = ref('')
    const newFreezeStartDate = ref(localIsoDate())
    const newFreezeEndDate = ref(localIsoDate())
    const newFreezeReason = ref('')
    const newFamilyName = ref('')
    const newParticipantName = ref({})
    const newParticipantPhone = ref({})
    const newParticipantStatus = ref({})
    const newParticipantMember = ref({})
    const newAdminUserPassword = ref({})
    const newAdminFamilyName = ref({})
    const newAdminFamilyRelationship = ref({})
    const newAdminFamilyLinkedUser = ref({})
    const newMiscTitle = ref('')
    const newMiscDescription = ref('')
    const newMiscAmount = ref('')
    const newMiscPaidBy = ref('')
    const newMiscPurchaseDate = ref(localIsoDate())
    const newMiscSplitCount = ref(1)
    const msg = ref('')
    const verificationDetails = ref(null)
    const isAdmin = ref(false)
    const isSuperAdmin = ref(false)
    const paymentSettings = ref({ qr_enabled: true, test_mode: true, default_due_days: 14 })
    const paymentInvoices = ref([])
    const selectedPaymentInvoice = ref(null)
    const paymentFilter = ref('all')
    const apiBase = import.meta.env.VITE_API_BASE || ''

    function localIsoDate(date = new Date()) {
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      return `${year}-${month}-${day}`
    }

    function localIsoMonth(date = new Date()) {
      return localIsoDate(date).slice(0, 7)
    }

    const token = () => getSessionValue('auth_token')
    const hasToken = () => hasAuthSession()
    const isLoggedIn = computed(() => hasAuthSession())
    const activeCourts = computed(() => courts.value.filter((court) => court.is_active !== false))
    const selectedCourt = computed(() => activeCourts.value.find((court) => String(court.id) === String(selectedCourtId.value)) || null)
    const calculatedBookingCost = computed(() => {
      const court = selectedCourt.value
      const duration = bookingDurationMinutes(startTime.value, endTime.value)
      if (!court || !duration) return '0.00'
      const hourlyRate = Number(court.hourly_rate || 0)
      const halfHourRate = Number(court.half_hour_rate ?? (hourlyRate / 2))
      const hours = Math.floor(duration / 60)
      const remainder = duration % 60
      const halfHours = Math.ceil(remainder / 30)
      return ((hours * hourlyRate) + (halfHours * halfHourRate)).toFixed(2)
    })
    const todayIso = () => localIsoDate()
    const upcomingBookings = computed(() => {
      const today = todayIso()
      return bookings.value.filter((booking) => booking.booking_date >= today && booking.status !== 'completed')
    })
    const completedBookings = computed(() => completedBookingHistory.value)
    const archivedBookings = computed(() => archivedBookingHistory.value)
    const maxFamilyAttendees = computed(() => familyMembers.value.length + 1)
    const familyAttendancePeople = computed(() => {
      getAuthSessionVersion()
      const selfName = getSessionValue('member_name') || getSessionValue('member_email') || getSessionValue('member_phone') || 'You'
      return [
        { key: 'self', type: 'self', name: selfName, phone: getSessionValue('member_phone') || '' },
        ...familyMembers.value.map((member) => ({
          key: `family:${member.id}`,
          type: 'family',
          family_member_id: member.id,
          name: member.name
        }))
      ]
    })
    const availabilityPeople = computed(() => familyAttendancePeople.value)
    function linkableUserOptions(ownerId) {
      return adminUsers.value
        .filter((candidate) => candidate.id !== ownerId)
        .map((candidate) => ({
          id: candidate.id,
          label: candidate.name || candidate.email || candidate.phone || `User ${candidate.id}`
        }))
    }

    const memberOptions = computed(() => adminUsers.value.flatMap((member) => {
      const ownerLabel = member.name || member.email || member.phone || 'Member'
      const options = [{
        key: `user:${member.id}`,
        label: ownerLabel,
        name: ownerLabel,
        phone: member.phone || member.email || ownerLabel,
        is_adhoc: false
      }]
      for (const familyMember of member.family_members || []) {
        options.push({
          key: `family:${familyMember.id}`,
          label: `${familyMember.name} (${ownerLabel})`,
          name: familyMember.name,
          phone: `family:${familyMember.id}`,
          is_adhoc: false
        })
      }
      return options
    }))
    const playTotalsByDate = computed(() => {
      return playDays.value.reduce((totals, day) => {
        totals[day.date] = day.totals || defaultPlayTotals()
        return totals
      }, {})
    })
    const attendanceStatuses = [
      { value: 'attending', label: 'Attending' },
      { value: 'participated', label: 'Participated' },
      { value: 'not_attending', label: 'No' },
      { value: 'tentative', label: 'Tentative' }
    ]
    const availabilityStatuses = [
      { value: 'available', label: 'Available' },
      { value: 'tentative', label: 'Tentative' },
      { value: 'not_available', label: 'No' }
    ]

    function parseBookingDate(dateValue) {
      return new Date(`${dateValue}T00:00:00`)
    }

    function bookingDurationMinutes(startValue, endValue) {
      const [startHour, startMinute] = (startValue || '').split(':').map(Number)
      const [endHour, endMinute] = (endValue || '').split(':').map(Number)
      if ([startHour, startMinute, endHour, endMinute].some((value) => Number.isNaN(value))) return 0
      const start = startHour * 60 + startMinute
      const end = endHour * 60 + endMinute
      return end > start ? end - start : 0
    }

    function bookingDayLabel(dateValue) {
      const date = parseBookingDate(dateValue)
      return date.toLocaleDateString(undefined, { weekday: 'short' })
    }

    function bookingDateLabel(dateValue) {
      const date = parseBookingDate(dateValue)
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    }

    function statusLabel(value, fallback = 'Not started') {
      const rawStatus = (value || '').toString().trim().toLowerCase()
      if (!rawStatus) return fallback
      const labels = {
        confirmed: 'Created',
        pending: 'Created',
        not_generated: 'Created',
        deleted: 'Cancelled',
        cancelled: 'Cancelled',
        completed: 'Completed',
        settled: 'Settled',
      }
      if (labels[rawStatus]) return labels[rawStatus]
      return rawStatus
        .split('_')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ')
    }

    function invoiceStatusLabel(value) {
      return statusLabel(value, 'Created')
    }

    function bookingLifecycleStatus(booking) {
      return statusLabel(booking?.status, 'Created')
    }

    function bookingStatusSummary(booking) {
      return bookingLifecycleStatus(booking)
    }

    function bookingItemStatusSummary(item) {
      return statusLabel(item?.booking_status, 'Completed')
    }

    function isBookingOpen(bookingId) {
      return openBookingIds.value.has(bookingId)
    }

    function toggleBooking(bookingId) {
      const nextOpenIds = new Set(openBookingIds.value)
      if (nextOpenIds.has(bookingId)) nextOpenIds.delete(bookingId)
      else nextOpenIds.add(bookingId)
      openBookingIds.value = nextOpenIds
    }

    function isCompletedBookingOpen(bookingId) {
      return openCompletedBookingIds.value.has(bookingId)
    }

    function toggleCompletedBooking(bookingId) {
      const nextOpenIds = new Set(openCompletedBookingIds.value)
      if (nextOpenIds.has(bookingId)) nextOpenIds.delete(bookingId)
      else nextOpenIds.add(bookingId)
      openCompletedBookingIds.value = nextOpenIds
    }

    function isMiscCostOpen(costId) {
      return openMiscCostIds.value.has(costId)
    }

    function toggleMiscCost(costId) {
      const nextOpenIds = new Set(openMiscCostIds.value)
      if (nextOpenIds.has(costId)) nextOpenIds.delete(costId)
      else nextOpenIds.add(costId)
      openMiscCostIds.value = nextOpenIds
    }

    function participantStatusCounts(booking) {
      return (booking.participants || []).reduce((counts, participant) => {
        const status = participant.status || 'tentative'
        if (status === 'attending' || status === 'participated') counts.attending += 1
        else if (status === 'not_attending') counts.not_attending += 1
        else counts.tentative += 1
        return counts
      }, { attending: 0, not_attending: 0, tentative: 0 })
    }

    function participantCompletedStatusLabel(participant) {
      return participant?.status === 'participated' ? 'Participated' : statusLabel(participant?.status, 'Participated')
    }

    function participantName(participant) {
      return participant.name || participant.phone || 'Player'
    }

    function participantNamesByStatus(booking, status) {
      return (booking.participants || [])
        .filter((participant) => (participant.status || 'tentative') === status)
        .map(participantName)
        .filter(Boolean)
    }

    function familyPersonBookingStatus(booking, person) {
      const participantKey = person.type === 'self' ? person.phone : `family:${person.family_member_id}`
      const participant = (booking.participants || []).find((item) => item.phone === participantKey)
      return participant?.status || 'not_attending'
    }

    function bookingInterest(booking) {
      return playTotalsByDate.value[booking.booking_date] || defaultPlayTotals()
    }

    function defaultPlayTotals() {
      return {
        available_families: 0,
        tentative_families: 0,
        attendee_count: 0,
        available_count: 0,
        tentative_count: 0,
        available_attendees: [],
        tentative_attendees: []
      }
    }

    function completedInvoiceViewActive() {
      return activeView.value === 'costs' || activeView.value === 'admin-costs'
    }

    function planningNames(booking, status) {
      const totals = bookingInterest(booking)
      const attendees = status === 'tentative'
        ? totals.tentative_attendees || []
        : totals.available_attendees || []
      return attendees.map((attendee) => attendee.name).filter(Boolean)
    }

    function availabilityNamesByStatus(day, status) {
      const totals = day?.totals || defaultPlayTotals()
      const attendees = status === 'tentative' ? totals.tentative_attendees || [] : totals.available_attendees || []
      const names = attendees.map((attendee) => attendee.name).filter(Boolean)
      return [...new Set(names)].slice(0, 18)
    }

    function availabilityVoterNames(day) {
      return [
        ...availabilityNamesByStatus(day, 'available'),
        ...availabilityNamesByStatus(day, 'tentative')
      ].slice(0, 12)
    }

    function showVerificationDetails(invoice, title = 'Cost verification') {
      const bookingItems = invoice?.booking_items || []
      const miscItems = (invoice?.misc_items || []).map((item) => ({
        ...item,
        date: item.purchase_date || 'No purchase date',
        detail: `${item.title || 'Misc cost'} · ${item.status || 'open'}`,
        amount_total: Number(item.amount || 0) * Number(item.split_count || 1),
        cost_per_person: item.amount,
        total_people_played: item.split_count,
      }))
      const items = [...bookingItems, ...miscItems]
      verificationDetails.value = {
        title,
        items,
        itemLabel: 'Cost items',
        peopleLabel: 'Split entries',
        totalPeople: items.reduce((sum, item) => sum + Number(item.total_people_played || item.split_count || 0), 0),
        totalCost: items.reduce((sum, item) => sum + Number(item.total_cost ?? item.amount_total ?? 0), 0).toFixed(2),
        shareCost: Number(invoice?.total ?? ((invoice?.booking_total || 0) + (invoice?.misc_total || 0))).toFixed(2)
      }
    }

    function closeVerificationDetails() {
      verificationDetails.value = null
    }

    async function fetchJson(url, options = {}) {
      const headers = { Accept: 'application/json', ...(options.headers || {}) }
      if (token()) headers.Authorization = `Bearer ${token()}`
      const fullUrl = /^https?:\/\//.test(url) ? url : `${apiBase}${url}`
      const res = await fetch(fullUrl, { ...options, headers, cache: 'no-store' })
      const text = await res.text()
      let data = {}
      if (text) {
        try {
          data = JSON.parse(text)
        } catch (err) {
          const plainText = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
          data = { error: plainText || `Request failed (${res.status})` }
        }
      }
      if (!res.ok) {
        const fallback = res.status === 401
          ? 'Please log in to continue.'
          : res.status === 404
            ? 'The requested service was not found.'
            : `Request failed (${res.status})`
        if (res.status === 401) clearAuthSession()
        throw new Error(data.error || fallback)
      }
      return data
    }

    function normalizePlayDay(day) {
      const vote = day.vote || {}
      const status = vote.status || (vote.available ? 'available' : 'not_available')
      const attendees = (vote.attendee_details || []).map((attendee) => ({
        ...attendee,
        status: attendee.status || 'available'
      }))
      return {
        ...day,
        status,
        available: status === 'available',
        attendee_count: status === 'available' ? Math.max(1, vote.attendee_count || 1) : 0,
        attendees,
        notes: vote.notes || '',
        totals: day.totals || defaultPlayTotals()
      }
    }

    function normalizeVote(day) {
      const availableCount = (day.attendees || []).filter((attendee) => attendee.status === 'available').length
      const tentativeCount = (day.attendees || []).filter((attendee) => attendee.status === 'tentative').length
      day.status = availableCount ? 'available' : tentativeCount ? 'tentative' : 'not_available'
      day.available = availableCount > 0
      day.attendee_count = availableCount
    }

    function setAvailabilityStatus(day, status) {
      day.status = status
      day.available = status === 'available'
      normalizeVote(day)
    }

    function availabilityPersonPayload(person) {
      return {
        type: person.type,
        family_member_id: person.family_member_id,
        name: person.name,
        phone: person.phone,
        status: 'available'
      }
    }

    function availabilityPersonKey(person) {
      return person.type === 'self' ? 'self' : `family:${person.family_member_id}`
    }

    function availabilityPersonIndex(day, person) {
      const key = availabilityPersonKey(person)
      return (day.attendees || []).findIndex((attendee) => {
        return attendee.type === 'self'
          ? key === 'self'
          : key === `family:${attendee.family_member_id}`
      })
    }

    function availabilityPersonStatus(day, person) {
      const index = availabilityPersonIndex(day, person)
      return index >= 0 ? day.attendees[index].status || 'available' : 'not_available'
    }

    function setAvailabilityPersonStatus(day, person, status) {
      const current = [...(day.attendees || [])]
      const index = availabilityPersonIndex(day, person)
      if (status === 'not_available') {
        if (index >= 0) {
          current.splice(index, 1)
        }
      } else {
        const payload = { ...availabilityPersonPayload(person), status }
        if (index >= 0) {
          current[index] = { ...current[index], ...payload }
        } else {
          current.push(payload)
        }
      }
      day.attendees = current
      normalizeVote(day)
    }

    function clearPrivateState() {
      familyMembers.value = []
      adminUsers.value = []
      courts.value = []
      freezePeriods.value = []
      isAdmin.value = false
      newParticipantName.value = {}
      newParticipantPhone.value = {}
      newParticipantStatus.value = {}
      newParticipantMember.value = {}
      errorMsg.value = ''
      msg.value = ''
    }

    async function handleAuthChanged() {
      if (!hasToken()) {
        clearPrivateState()
      } else {
        await loadCurrentUser()
      }
      await loadDashboard()
    }

    async function loadBookings(options = {}) {
      const params = new URLSearchParams()
      if (options.status) params.set('status', options.status)
      if (options.page) params.set('page', options.page)
      if (options.perPage) params.set('per_page', options.perPage)
      if (options.month) params.set('month', options.month)
      const query = params.toString()
      const bookingsData = await fetchJson(`/api/bookings${query ? `?${query}` : ''}`)
      if (options.status === 'completed') {
        completedBookingPagination.value = bookingsData.pagination || completedBookingPagination.value
        completedBookingHistory.value = bookingsData.bookings || []
      } else if (options.status === 'archive') {
        archivedBookingPagination.value = bookingsData.pagination || archivedBookingPagination.value
        archivedBookingHistory.value = bookingsData.bookings || []
      } else {
        bookings.value = bookingsData.bookings || []
      }
    }

    async function loadCourts() {
      const courtsData = await fetchJson('/api/admin/courts?include_inactive=0')
      courts.value = courtsData.courts || []
      if (!selectedCourtId.value && activeCourts.value.length) {
        selectedCourtId.value = activeCourts.value[0].id
      }
    }

    async function loadFreezePeriods() {
      const data = await fetchJson('/api/admin/freeze-periods')
      freezePeriods.value = data.periods || []
    }

    async function loadFamilyMembers() {
      const data = await fetchJson('/api/family-members')
      familyMembers.value = data.members || []
    }

    async function loadPlayAvailability() {
      const params = new URLSearchParams({ start_date: localIsoDate(), days: '7' })
      const data = await fetchJson(`/api/play-availability?${params.toString()}`)
      playDays.value = (data.days || []).map(normalizePlayDay)
    }

    async function loadMiscCosts() {
      const data = await fetchJson('/api/misc-costs')
      miscCosts.value = data.costs || []
    }

    async function loadMonthlyInvoice() {
      const data = await fetchJson(`/api/invoices/monthly?month=${monthlyInvoiceMonth.value}`)
      monthlyInvoice.value = data
      const paymentData = await fetchJson(`/api/payment-invoices/current?month=${monthlyInvoiceMonth.value}`)
      currentPaymentInvoice.value = paymentData.invoice === undefined ? paymentData : paymentData.invoice
      completedBookingPagination.value = { ...completedBookingPagination.value, page: 1 }
      await loadBookings({ status: 'completed', month: monthlyInvoiceMonth.value, page: completedBookingPagination.value.page, perPage: completedBookingPagination.value.per_page })
    }

    async function loadAdminMonthlyInvoices() {
      const data = await fetchJson(`/api/admin/invoices/monthly?month=${monthlyInvoiceMonth.value}`)
      adminMonthlyInvoices.value = data
      completedBookingPagination.value = { ...completedBookingPagination.value, page: 1 }
      await loadBookings({ status: 'completed', month: monthlyInvoiceMonth.value, page: completedBookingPagination.value.page, perPage: completedBookingPagination.value.per_page })
    }

    async function loadAdminUsers() {
      const data = await fetchJson('/api/admin/users')
      adminUsers.value = data.users || []
    }


    async function loadAdminAuditLogs() {
      const data = await fetchJson(`/api/admin/audit-logs?page=${adminAuditPagination.value.page}&per_page=${adminAuditPagination.value.per_page}`)
      adminAuditLogs.value = data.logs || []
      adminAuditPagination.value = data.pagination || adminAuditPagination.value
    }

    function auditLogDate(value) {
      if (!value) return 'Unknown time'
      return new Date(value).toLocaleString()
    }

    function auditLogDetails(details) {
      if (!details || (typeof details === 'object' && !Object.keys(details).length)) return ['No additional details']
      const lines = []
      const source = details.booking || details.court || details.user || details.family_member || details.cost || details.invoice || details.freeze_period || details
      if (source.name || source.title) lines.push(`Name: ${source.name || source.title}`)
      if (source.booking_date || source.date) lines.push(`Date: ${source.booking_date || source.date}${source.start_time ? ` ${source.start_time}-${source.end_time || ''}` : ''}`)
      if (source.court?.name || source.court) lines.push(`Court: ${source.court?.name || source.court}`)
      if (source.amount || source.total_amount || source.cost) lines.push(`Amount: €${source.amount || source.total_amount || source.cost}`)
      if (details.owner_id) lines.push(`Owner user: #${details.owner_id}`)
      if (details.changes) {
        Object.entries(details.changes).forEach(([field, change]) => lines.push(`${field.replaceAll('_', ' ')}: ${change.from ?? 'blank'} → ${change.to ?? 'blank'}`))
      }
      return lines.length ? lines : Object.entries(source).slice(0, 6).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${typeof value === 'object' ? 'updated' : value}`)
    }

    async function changeAdminAuditPage(page) {
      if (page < 1 || (adminAuditPagination.value.pages && page > adminAuditPagination.value.pages)) return
      adminAuditPagination.value = { ...adminAuditPagination.value, page }
      await loadDashboard()
    }


    async function loadPaymentSettings() {
      if (!isSuperAdmin.value) return
      paymentSettings.value = await fetchJson('/api/admin/payment-settings')
    }

    async function savePaymentSettings() {
      paymentSettings.value = await fetchJson('/api/admin/payment-settings', { method: 'PUT', body: JSON.stringify(paymentSettings.value) })
      msg.value = 'Payment settings saved.'
    }

    async function loadPaymentInvoices() {
      if (!isAdmin.value) return
      const data = await fetchJson(`/api/admin/payment-invoices?status=${paymentFilter.value}`)
      paymentInvoices.value = data.invoices || []
    }

    async function loadPaymentInvoice(id) {
      selectedPaymentInvoice.value = await fetchJson(`/api/payment-invoices/${id}`)
    }

    async function setPaymentStatus(invoice, status) {
      const updated = await fetchJson(`/api/admin/payment-invoices/${invoice.id}/status`, { method: 'POST', body: JSON.stringify({ payment_status: status }) })
      selectedPaymentInvoice.value = updated
      await loadPaymentInvoices()
      if (adminMonthlyInvoices.value) await loadAdminMonthlyInvoices()
    }

    async function setMonthlyInvoiceStatus(status) {
      const data = await fetchJson('/api/admin/invoices/monthly/status', { method: 'POST', body: JSON.stringify({ month: monthlyInvoiceMonth.value, status }) })
      msg.value = `${monthStatusLabel(data.month_status?.status)} saved for ${monthName(monthlyInvoiceMonth.value)}.`
      await loadAdminMonthlyInvoices()
    }

    async function generateTestInvoice() {
      selectedPaymentInvoice.value = await fetchJson('/api/admin/payment-invoices/test', { method: 'POST', body: JSON.stringify({}) })
      msg.value = 'Test invoice generated.'
      if (isAdmin.value) await loadPaymentInvoices()
    }

    async function notifyMonthlyInvoicesReady() {
      const data = await fetchJson('/api/admin/payment-invoices/monthly/notify', { method: 'POST', body: JSON.stringify({ month: monthlyInvoiceMonth.value }) })
      msg.value = `Monthly payment notification ${data.status}.`
    }

    async function copyText(value) {
      if (navigator?.clipboard) await navigator.clipboard.writeText(value || '')
      msg.value = 'Copied.'
    }

    function paymentStatusLabel(status) {
      return ({ UNPAID: 'Payment pending', PAID: 'Paid', PARTIALLY_PAID: 'Partially paid', CANCELLED: 'Cancelled', EXPIRED: 'Expired' })[status] || status
    }

    function monthStatusLabel(status) {
      return ({ OPEN: 'Open', READY_FOR_PAYMENT: 'Ready for payment', SETTLED: 'Settled' })[status] || 'Open'
    }

    function monthStatusClass(status) {
      return ({
        OPEN: 'bg-slate-200 text-slate-800',
        READY_FOR_PAYMENT: 'bg-indigo-100 text-indigo-800',
        SETTLED: 'bg-emerald-100 text-emerald-800'
      })[status] || 'bg-slate-200 text-slate-800'
    }

    function monthName(value) {
      if (!value) return 'this month'
      const [year, month] = value.split('-').map(Number)
      return new Date(year, (month || 1) - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
    }

    function dateTimeLabel(value) {
      if (!value) return ''
      return new Date(value).toLocaleString()
    }

    async function loadWhatsAppNotifications() {
      const data = await fetchJson('/api/admin/whatsapp-notifications')
      whatsappSettings.value = data.settings || []
      whatsappLogs.value = data.logs || []
    }

    async function saveWhatsAppNotification(setting) {
      await fetchJson(`/api/admin/whatsapp-notifications/${setting.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(setting)
      })
      msg.value = 'WhatsApp notification template saved.'
      await loadWhatsAppNotifications()
    }

    async function testWhatsAppNotification(setting) {
      const data = await fetchJson(`/api/admin/whatsapp-notifications/${setting.id}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipient: setting.test_recipient_number || '' })
      })
      msg.value = `Test sent to ${data.log.recipient || 'configured group'}: ${data.log.status}`
      await loadWhatsAppNotifications()
    }

    async function sendAvailabilitySummary() {
      const data = await fetchJson('/api/admin/availability-summary/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days: 7 })
      })
      if (data.log) {
        const statusLabel = data.log.status === 'sent' ? 'sent' : `prepared but ${data.log.status}`
        msg.value = `Availability overview ${statusLabel}.`
      } else {
        msg.value = 'Availability overview was not sent. Check that the WhatsApp availability setting is enabled and set to send to group.'
      }
      await loadPlayAvailability()
      if (isAdmin.value) await loadWhatsAppNotifications()
    }

    async function loadDashboard() {
      loading.value = true
      errorMsg.value = ''
      try {
        const loggedIn = hasToken()
        if (!loggedIn) {
          isAdmin.value = false
        }

        if (activeView.value === 'bookings') {
          await Promise.all([
            loadBookings({ status: 'upcoming', perPage: 100 }),
            loadPlayAvailability()
          ])
          if (loggedIn) {
            await loadFamilyMembers()
            await loadBookings({ status: 'completed', month: monthlyInvoiceMonth.value, page: completedBookingPagination.value.page, perPage: completedBookingPagination.value.per_page })
          }
          if (loggedIn && isAdmin.value) {
            await loadCourts()
          }
        } else if (activeView.value === 'availability') {
          await loadPlayAvailability()
          if (loggedIn) {
            await loadFamilyMembers()
          }
        } else if (activeView.value === 'costs') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          await Promise.all([
            loadMiscCosts(),
            loadMonthlyInvoice(),
            loadBookings({ status: 'archive', page: archivedBookingPagination.value.page, perPage: archivedBookingPagination.value.per_page })
          ])
        } else if (activeView.value === 'admin-bookings') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          if (!isAdmin.value) {
            errorMsg.value = 'Admin access is required.'
            return
          }
          await Promise.all([
            loadBookings({ status: 'upcoming', perPage: 100 }),
            loadBookings({ status: 'completed', month: monthlyInvoiceMonth.value, page: completedBookingPagination.value.page, perPage: completedBookingPagination.value.per_page }),
            loadPlayAvailability(),
            loadCourts(),
            loadAdminUsers()
          ])
        } else if (activeView.value === 'admin-courts') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          if (!isAdmin.value) {
            errorMsg.value = 'Admin access is required.'
            return
          }
          await Promise.all([
            loadCourts(),
            loadFreezePeriods()
          ])
        } else if (activeView.value === 'admin-costs') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          if (!isAdmin.value) {
            errorMsg.value = 'Admin access is required.'
            return
          }
          await Promise.all([
            loadMiscCosts(),
            loadAdminMonthlyInvoices(),
            loadBookings({ status: 'archive', page: archivedBookingPagination.value.page, perPage: archivedBookingPagination.value.per_page }),
            loadAdminUsers()
          ])
        } else if (activeView.value === 'payment-settings') {
          if (!isSuperAdmin.value) { errorMsg.value = 'Only Super Admin can manage payment settings.'; return }
          await loadPaymentSettings()
        } else if (activeView.value === 'admin-audit-logs') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          if (!isAdmin.value) {
            errorMsg.value = 'Admin access is required.'
            return
          }
          await loadAdminAuditLogs()
        } else if (activeView.value === 'notifications') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          if (!isAdmin.value) {
            errorMsg.value = 'Admin access is required.'
            return
          }
          await loadWhatsAppNotifications()
        } else if (activeView.value === 'members') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          if (!isAdmin.value) {
            errorMsg.value = 'Admin access is required.'
            return
          }
          await loadAdminUsers()
        }
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        loading.value = false
      }
    }

    async function changeArchivedBookingPage(page) {
      if (page < 1 || (archivedBookingPagination.value.pages && page > archivedBookingPagination.value.pages)) {
        return
      }
      archivedBookingPagination.value = { ...archivedBookingPagination.value, page }
      await loadDashboard()
    }

    async function changeCompletedBookingPage(page) {
      if (page < 1 || (completedBookingPagination.value.pages && page > completedBookingPagination.value.pages)) {
        return
      }
      completedBookingPagination.value = { ...completedBookingPagination.value, page }
      await loadDashboard()
    }

    async function createFamilyMember() {
      msg.value = ''
      if (!newFamilyName.value.trim()) {
        msg.value = 'Please enter a family member name.'
        return
      }

      try {
        await fetchJson('/api/family-members', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newFamilyName.value
          })
        })
        newFamilyName.value = ''
        msg.value = 'Family member added.'
        await loadFamilyMembers()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function deleteFamilyMember(member) {
      try {
        await fetchJson(`/api/family-members/${member.id}`, { method: 'DELETE' })
        msg.value = `Removed ${member.name}.`
        await loadFamilyMembers()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function saveAvailabilityVote(day) {
      msg.value = ''
      if (!hasToken()) {
        router.push('/login')
        return
      }
      normalizeVote(day)
      const attendeeCount = day.status === 'available' ? (day.attendees || []).length : 0

      try {
        await fetchJson('/api/play-availability', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            play_date: day.date,
            status: day.status,
            available: day.status === 'available',
            attendee_count: attendeeCount,
            attendees: day.attendees || [],
            notes: day.notes
          })
        })
        msg.value = `Vote saved for ${day.date}.`
        await loadPlayAvailability()
      } catch (err) {
        msg.value = err.message
      }
    }

    function resetBookingForm() {
      editingBookingId.value = null
      bookingDate.value = localIsoDate()
      startTime.value = '18:00'
      endTime.value = '19:00'
      bookingCost.value = '0'
      bookingStatus.value = 'confirmed'
      bookingNotes.value = ''
      recurringMode.value = false
      recurringIntervalWeeks.value = 1
      recurringCount.value = 1
      recurringEndDate.value = bookingDate.value
      if (activeCourts.value.length) {
        selectedCourtId.value = activeCourts.value[0].id
      }
    }

    function startEditBooking(booking) {
      editingBookingId.value = booking.id
      selectedCourtId.value = booking.court?.id || ''
      bookingDate.value = booking.booking_date
      startTime.value = booking.start_time
      endTime.value = booking.end_time
      bookingCost.value = String(booking.cost || 0)
      bookingStatus.value = booking.status || 'confirmed'
      bookingNotes.value = booking.notes || ''
      recurringMode.value = false
      msg.value = ''
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    async function saveBooking() {
      if (editingBookingId.value) {
        await updateBooking()
        return
      }
      await createBooking()
    }

    async function createBooking() {
      const courtId = selectedCourtId.value
      if (!courtId) {
        msg.value = 'Please select a court first.'
        return
      }
      try {
        await fetchJson('/api/bookings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            court_id: courtId,
            booking_date: bookingDate.value,
            start_time: startTime.value,
            end_time: endTime.value,
            recurring: recurringMode.value,
            recurring_interval_weeks: recurringIntervalWeeks.value,
            recurring_count: recurringCount.value,
            recurring_end_date: recurringEndDate.value,
            notes: bookingNotes.value,
            participants: []
          })
        })
        msg.value = recurringMode.value ? 'Recurring booking created successfully.' : 'Booking created successfully.'
        await loadBookings({ status: 'upcoming', perPage: 100 })
        resetBookingForm()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function updateBooking() {
      if (!selectedCourtId.value) {
        msg.value = 'Please select a court first.'
        return
      }
      try {
        await fetchJson(`/api/bookings/${editingBookingId.value}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            court_id: selectedCourtId.value,
            booking_date: bookingDate.value,
            start_time: startTime.value,
            end_time: endTime.value,
            manual_cost: true,
            cost: parseFloat(bookingCost.value || 0),
            notes: bookingNotes.value,
            status: bookingStatus.value
          })
        })
        msg.value = 'Booking updated successfully.'
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: 'upcoming', perPage: 100 })
        resetBookingForm()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function deleteBooking(booking) {
      const label = `${booking.court?.name || 'booking'} on ${booking.booking_date} ${booking.start_time}-${booking.end_time}`
      if (!window.confirm(`Delete ${label}? This will also remove its participants and invoice.`)) {
        return
      }
      try {
        await fetchJson(`/api/bookings/${booking.id}`, { method: 'DELETE' })
        msg.value = 'Booking deleted successfully.'
        if (editingBookingId.value === booking.id) resetBookingForm()
        await loadBookings({ status: 'upcoming', perPage: 100 })
        if (activeView.value === 'admin-bookings' || activeView.value === 'admin-costs') {
          await loadDashboard()
        }
      } catch (err) {
        msg.value = err.message
      }
    }

    async function createInvoice(bookingId) {
      try {
        const data = await fetchJson(`/api/bookings/${bookingId}/invoice`, { method: 'POST' })
        msg.value = `Invoice generated: €${data.total_amount}`
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: completedInvoiceViewActive() ? 'completed' : 'upcoming', month: completedInvoiceViewActive() ? monthlyInvoiceMonth.value : undefined, page: completedBookingPagination.value.page, perPage: completedInvoiceViewActive() ? completedBookingPagination.value.per_page : 100 })
      } catch (err) {
        msg.value = err.message
      }
    }

    async function saveBookingRsvp(booking, status) {
      try {
        await fetchJson(`/api/bookings/${booking.id}/rsvp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status })
        })
        msg.value = 'Attendance updated.'
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: completedInvoiceViewActive() ? 'completed' : 'upcoming', month: completedInvoiceViewActive() ? monthlyInvoiceMonth.value : undefined, page: completedBookingPagination.value.page, perPage: completedInvoiceViewActive() ? completedBookingPagination.value.per_page : 100 })
      } catch (err) {
        msg.value = err.message
      }
    }

    async function saveFamilyPersonAttendance(booking, person, status) {
      try {
        await fetchJson(`/api/bookings/${booking.id}/family-attendance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            attendees: [{
              type: person.type,
              family_member_id: person.family_member_id,
              status
            }]
          })
        })
        msg.value = 'Attendance updated.'
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: completedInvoiceViewActive() ? 'completed' : 'upcoming', month: completedInvoiceViewActive() ? monthlyInvoiceMonth.value : undefined, page: completedBookingPagination.value.page, perPage: completedInvoiceViewActive() ? completedBookingPagination.value.per_page : 100 })
      } catch (err) {
        msg.value = err.message
      }
    }

    function selectedMemberOption(key) {
      return memberOptions.value.find((member) => member.key === key) || null
    }

    function applyParticipantMember(participant, key) {
      const member = selectedMemberOption(key)
      if (!member) return
      participant.name = member.name
      participant.phone = member.phone
      participant.is_adhoc = member.is_adhoc
    }

    async function addParticipant(booking) {
      const member = selectedMemberOption(newParticipantMember.value[booking.id])
      const name = member?.name || newParticipantName.value[booking.id] || ''
      const phone = member?.phone || newParticipantPhone.value[booking.id] || name
      const status = newParticipantStatus.value[booking.id] || 'attending'
      try {
        await fetchJson(`/api/bookings/${booking.id}/participants`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, phone, status, is_adhoc: !member })
        })
        newParticipantMember.value[booking.id] = ''
        newParticipantName.value[booking.id] = ''
        newParticipantPhone.value[booking.id] = ''
        newParticipantStatus.value[booking.id] = 'attending'
        msg.value = 'Participant added.'
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: completedInvoiceViewActive() ? 'completed' : 'upcoming', month: completedInvoiceViewActive() ? monthlyInvoiceMonth.value : undefined, page: completedBookingPagination.value.page, perPage: completedInvoiceViewActive() ? completedBookingPagination.value.per_page : 100 })
      } catch (err) {
        msg.value = err.message
      }
    }

    async function updateParticipant(booking, participant) {
      try {
        await fetchJson(`/api/bookings/${booking.id}/participants/${participant.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(participant)
        })
        msg.value = 'Participant updated.'
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: completedInvoiceViewActive() ? 'completed' : 'upcoming', month: completedInvoiceViewActive() ? monthlyInvoiceMonth.value : undefined, page: completedBookingPagination.value.page, perPage: completedInvoiceViewActive() ? completedBookingPagination.value.per_page : 100 })
      } catch (err) {
        msg.value = err.message
      }
    }

    async function deleteParticipant(booking, participant) {
      const label = participantName(participant)
      if (!window.confirm(`Remove ${label} from this booking?`)) {
        return
      }
      try {
        await fetchJson(`/api/bookings/${booking.id}/participants/${participant.id}`, { method: 'DELETE' })
        msg.value = 'Participant removed.'
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: completedInvoiceViewActive() ? 'completed' : 'upcoming', month: completedInvoiceViewActive() ? monthlyInvoiceMonth.value : undefined, page: completedBookingPagination.value.page, perPage: completedInvoiceViewActive() ? completedBookingPagination.value.per_page : 100 })
      } catch (err) {
        msg.value = err.message
      }
    }

    async function createCourt() {
      try {
        const data = await fetchJson('/api/admin/courts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newCourtName.value,
            location: newCourtLocation.value,
            description: newCourtDescription.value,
            map_link: newCourtMapLink.value,
            hourly_rate: parseFloat(newCourtRate.value || 25),
            half_hour_rate: newCourtHalfHourRate.value === '' ? null : parseFloat(newCourtHalfHourRate.value || 0)
          })
        })
        msg.value = `Added court ${data.name}.`
        newCourtName.value = ''
        newCourtLocation.value = ''
        newCourtDescription.value = ''
        newCourtMapLink.value = ''
        newCourtRate.value = '25'
        newCourtHalfHourRate.value = '12.5'
        await loadCourts()
        selectedCourtId.value = data.id
      } catch (err) {
        msg.value = err.message
      }
    }

    async function updateCourt(court) {
      try {
        const data = await fetchJson(`/api/admin/courts/${court.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: court.name,
            location: court.location,
            description: court.description,
            map_link: court.map_link,
            hourly_rate: court.hourly_rate,
            half_hour_rate: court.half_hour_rate,
            is_active: court.is_active
          })
        })
        msg.value = `Updated court ${data.name}.`
        await loadCourts()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function deleteCourt(court) {
      try {
        await fetchJson(`/api/admin/courts/${court.id}`, { method: 'DELETE' })
        msg.value = `Deleted court ${court.name}.`
        await loadCourts()
        await loadBookings({ status: 'upcoming', perPage: 100 })
      } catch (err) {
        msg.value = err.message
      }
    }

    async function createFreezePeriod() {
      try {
        const data = await fetchJson('/api/admin/freeze-periods', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: newFreezeTitle.value,
            start_date: newFreezeStartDate.value,
            end_date: newFreezeEndDate.value,
            reason: newFreezeReason.value,
            is_active: true
          })
        })
        msg.value = `Added freeze period ${data.title}.`
        newFreezeTitle.value = ''
        newFreezeReason.value = ''
        await Promise.all([loadFreezePeriods(), loadPlayAvailability()])
      } catch (err) {
        msg.value = err.message
      }
    }

    async function updateFreezePeriod(period) {
      try {
        const data = await fetchJson(`/api/admin/freeze-periods/${period.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(period)
        })
        msg.value = `Updated freeze period ${data.title}.`
        await Promise.all([loadFreezePeriods(), loadPlayAvailability()])
      } catch (err) {
        msg.value = err.message
      }
    }

    async function deleteFreezePeriod(period) {
      if (!window.confirm(`Delete freeze period ${period.title}?`)) {
        return
      }
      try {
        await fetchJson(`/api/admin/freeze-periods/${period.id}`, { method: 'DELETE' })
        msg.value = `Deleted freeze period ${period.title}.`
        await Promise.all([loadFreezePeriods(), loadPlayAvailability()])
      } catch (err) {
        msg.value = err.message
      }
    }

    async function createMiscCost() {
      try {
        const data = await fetchJson('/api/misc-costs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: newMiscTitle.value,
            description: newMiscDescription.value,
            amount: parseFloat(newMiscAmount.value || 0),
            paid_by: newMiscPaidBy.value,
            purchase_date: newMiscPurchaseDate.value,
            split_count: newMiscSplitCount.value
          })
        })
        msg.value = `Added cost ${data.title}.`
        newMiscTitle.value = ''
        newMiscDescription.value = ''
        newMiscAmount.value = ''
        newMiscPaidBy.value = ''
        newMiscPurchaseDate.value = localIsoDate()
        newMiscSplitCount.value = 1
        await loadMiscCosts()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function updateMiscCost(cost) {
      try {
        await fetchJson(`/api/misc-costs/${cost.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cost)
        })
        msg.value = 'Cost updated.'
        await loadMiscCosts()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function deleteMiscCost(cost) {
      try {
        await fetchJson(`/api/misc-costs/${cost.id}`, { method: 'DELETE' })
        msg.value = `Deleted cost ${cost.title}.`
        await loadMiscCosts()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function settleBookingCost(booking) {
      try {
        await fetchJson(`/api/bookings/${booking.id}/settle`, { method: 'POST' })
        msg.value = 'Booking cost settled.'
        if (activeView.value === 'admin-bookings') await loadDashboard()
        else await loadBookings({ status: 'completed', month: monthlyInvoiceMonth.value, page: completedBookingPagination.value.page, perPage: completedBookingPagination.value.per_page })
      } catch (err) {
        msg.value = err.message
      }
    }

    async function updateAdminUser(member) {
      try {
        const payload = {
          name: member.name,
          email: member.email,
          phone: member.phone,
          whatsapp_number: member.whatsapp_number,
          role: member.role,
          is_club_member: member.is_club_member
        }
        const password = (newAdminUserPassword.value[member.id] || '').trim()
        if (password) payload.password = password
        const data = await fetchJson(`/api/admin/users/${member.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        Object.assign(member, data)
        newAdminUserPassword.value[member.id] = ''
        msg.value = `Updated ${data.name || data.email || data.phone}.`
      } catch (err) {
        msg.value = err.message
        await loadAdminUsers()
      }
    }

    async function deleteAdminUser(member) {
      try {
        await fetchJson(`/api/admin/users/${member.id}`, { method: 'DELETE' })
        msg.value = `Removed ${member.name || member.email || member.phone}.`
        await loadAdminUsers()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function updateAdminFamilyMember(owner, familyMember) {
      try {
        const data = await fetchJson(`/api/admin/family-members/${familyMember.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: familyMember.name,
            relationship: familyMember.relationship,
            is_club_member: familyMember.is_club_member,
            linked_user_id: familyMember.linked_user_id || null
          })
        })
        Object.assign(familyMember, data)
        msg.value = `Updated ${data.name}.`
      } catch (err) {
        msg.value = err.message
        await loadAdminUsers()
      }
    }

    async function createAdminFamilyMember(owner) {
      const name = (newAdminFamilyName.value[owner.id] || '').trim()
      if (!name) {
        msg.value = 'Please enter a family member name.'
        return
      }
      try {
        await fetchJson('/api/admin/family-members', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: owner.id,
            name,
            relationship: newAdminFamilyRelationship.value[owner.id] || '',
            linked_user_id: newAdminFamilyLinkedUser.value[owner.id] || null
          })
        })
        newAdminFamilyName.value[owner.id] = ''
        newAdminFamilyRelationship.value[owner.id] = ''
        newAdminFamilyLinkedUser.value[owner.id] = ''
        msg.value = `Added family member for ${owner.name || owner.email || owner.phone}.`
        await loadAdminUsers()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function deleteAdminFamilyMember(owner, familyMember) {
      try {
        await fetchJson(`/api/admin/family-members/${familyMember.id}`, { method: 'DELETE' })
        msg.value = `Removed ${familyMember.name}.`
        await loadAdminUsers()
      } catch (err) {
        msg.value = err.message
      }
    }

    async function loadCurrentUser() {
      try {
        const meRes = await fetchJson('/api/auth/me')
        setSessionValue('member_name', meRes.user?.name || '')
        setSessionValue('member_email', meRes.user?.email || '')
        setSessionValue('member_phone', meRes.user?.phone || '')
        setSessionValue('member_role', meRes.user?.role || 'member')
        isAdmin.value = ['admin', 'super_admin'].includes(meRes.user?.role)
        isSuperAdmin.value = meRes.user?.role === 'super_admin'
      } catch (err) {
        const savedRole = getSessionValue('member_role')
        isAdmin.value = ['admin', 'super_admin'].includes(savedRole)
        isSuperAdmin.value = savedRole === 'super_admin'
      }
    }

    watch(() => props.initialView, async (view) => {
      activeView.value = view || 'availability'
      if (!hasToken()) {
        clearPrivateState()
      }
      await loadDashboard()
    })

    onMounted(async () => {
      window.addEventListener('badminton-auth-changed', handleAuthChanged)
      if (token()) {
        await loadCurrentUser()
      } else {
        isAdmin.value = false
      }
      await loadDashboard()
    })

    onBeforeUnmount(() => {
      window.removeEventListener('badminton-auth-changed', handleAuthChanged)
    })

    return {
      activeView,
      activeCourts,
      adminUsers,
      adminAuditLogs,
      adminAuditPagination,
      auditLogDate,
      auditLogDetails,
      availabilityVoterNames,
      availabilityNamesByStatus,
      bookingInterest,
      bookingDateLabel,
      bookingDayLabel,
      bookingStatusSummary,
      bookingItemStatusSummary,
      invoiceStatusLabel,
      bookings,
      upcomingBookings,
      completedBookings,
      archivedBookings,
      completedBookingPagination,
      archivedBookingPagination,
      completedBookingTab,
      invoiceDetailTab,
      courts,
      calculatedBookingCost,
      freezePeriods,
      familyMembers,
      familyAttendancePeople,
      availabilityPeople,
      miscCosts,
      monthlyInvoice,
      currentPaymentInvoice,
      memberOptions,
      adminMonthlyInvoices,
      monthlyInvoiceMonth,
      whatsappSettings,
      whatsappLogs,
      isLoggedIn,
      isAdmin,
      isSuperAdmin,
      paymentSettings,
      paymentInvoices,
      selectedPaymentInvoice,
      paymentFilter,
      isBookingOpen,
      toggleBooking,
      isCompletedBookingOpen,
      toggleCompletedBooking,
      isMiscCostOpen,
      toggleMiscCost,
      participantCompletedStatusLabel,
      loading,
      errorMsg,
      msg,
      verificationDetails,
      editingBookingId,
      playDays,
      maxFamilyAttendees,
      bookingDate,
      adminBookingTab,
      adminCostTab,
      startTime,
      endTime,
      bookingCost,
      bookingStatus,
      bookingNotes,
      selectedCourtId,
      recurringMode,
      recurringIntervalWeeks,
      recurringCount,
      recurringEndDate,
      newCourtName,
      newCourtLocation,
      newCourtDescription,
      newCourtMapLink,
      newCourtRate,
      newCourtHalfHourRate,
      newFreezeTitle,
      newFreezeStartDate,
      newFreezeEndDate,
      newFreezeReason,
      newFamilyName,
      newAdminUserPassword,
      newAdminFamilyName,
      newAdminFamilyRelationship,
      newAdminFamilyLinkedUser,
      newParticipantName,
      newParticipantPhone,
      newParticipantStatus,
      newParticipantMember,
      newMiscTitle,
      newMiscDescription,
      newMiscAmount,
      newMiscPaidBy,
      newMiscPurchaseDate,
      newMiscSplitCount,
      attendanceStatuses,
      availabilityStatuses,
      addParticipant,
      applyParticipantMember,
      createCourt,
      createFreezePeriod,
      createAdminFamilyMember,
      changeArchivedBookingPage,
      changeAdminAuditPage,
      changeCompletedBookingPage,
      createFamilyMember,
      createMiscCost,
      closeVerificationDetails,
      deleteCourt,
      deleteFreezePeriod,
      deleteAdminFamilyMember,
      deleteAdminUser,
      deleteBooking,
      deleteFamilyMember,
      deleteMiscCost,
      deleteParticipant,
      linkableUserOptions,
      loadMonthlyInvoice,
      loadAdminMonthlyInvoices,
      loadPlayAvailability,
      loadFreezePeriods,
      loadWhatsAppNotifications,
      loadPaymentSettings,
      savePaymentSettings,
      loadPaymentInvoices,
      loadPaymentInvoice,
      setPaymentStatus,
      setMonthlyInvoiceStatus,
      generateTestInvoice,
      notifyMonthlyInvoicesReady,
      copyText,
      paymentStatusLabel,
      monthStatusLabel,
      monthStatusClass,
      monthName,
      dateTimeLabel,
      familyPersonBookingStatus,
      availabilityPersonStatus,
      normalizeVote,
      participantName,
      participantNamesByStatus,
      participantStatusCounts,
      planningNames,
      resetBookingForm,
      saveBooking,
      saveAvailabilityVote,
      saveBookingRsvp,
      saveFamilyPersonAttendance,
      saveWhatsAppNotification,
      sendAvailabilitySummary,
      testWhatsAppNotification,
      setAvailabilityPersonStatus,
      startEditBooking,
      showVerificationDetails,
      updateCourt,
      updateFreezePeriod,
      updateAdminFamilyMember,
      updateAdminUser,
      updateMiscCost,
      updateParticipant
    }
  }
}
</script>
