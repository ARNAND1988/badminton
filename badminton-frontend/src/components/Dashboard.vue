<template>
  <div class="arena-dashboard space-y-6">
    <PublicWelcome v-if="activeView === 'availability' && !isLoggedIn" />
    <div v-if="loading" class="alert-info" role="status">
      Loading data...
    </div>
    <div v-if="errorMsg" class="alert-warning" role="alert">
      {{ errorMsg }}
    </div>
    <p v-if="msg" class="alert-muted" role="status">{{ msg }}</p>

    <NotificationPreviewDialog
      :close-notification-preview="closeNotificationPreview"
      :notification-preview="notificationPreview"
      :send-notification-preview="sendNotificationPreview"
    />

    <MemberBookingsView v-if="activeView === 'bookings'"
      :attendance-statuses="attendanceStatuses"
      :booking-date-label="bookingDateLabel"
      :booking-day-label="bookingDayLabel"
      :booking-interest="bookingInterest"
      :booking-status-summary="bookingStatusSummary"
      :change-completed-booking-page="changeCompletedBookingPage"
      :completed-booking-pagination="completedBookingPagination"
      :completed-bookings="completedBookings"
      :family-attendance-people="familyAttendancePeople"
      :family-person-booking-status="familyPersonBookingStatus"
      :is-completed-booking-open="isCompletedBookingOpen"
      :is-logged-in="isLoggedIn"
      :loading="loading"
      :participant-completed-status-label="participantCompletedStatusLabel"
      :participant-name="participantName"
      :participant-names-by-status="participantNamesByStatus"
      :participant-status-counts="participantStatusCounts"
      :planning-names="planningNames"
      :save-family-person-attendance="saveFamilyPersonAttendance"
      :toggle-completed-booking="toggleCompletedBooking"
      :upcoming-bookings="upcomingBookings"
    />

    <section v-if="activeView === 'admin-bookings'" class="space-y-6">
      <div>
        <div class="arena-view-heading"><ArenaIcon name="calendar" /><h2 class="section-title">Manage Bookings</h2></div>
        <p class="section-copy mt-1">Create court bookings, update attendance, shared misc costs, and per-booking invoices.</p>
        <div class="mt-3 grid gap-2 sm:inline-grid sm:grid-flow-col sm:auto-cols-fr sm:rounded-xl sm:bg-slate-100 sm:p-1">
          <button class="btn-secondary w-full justify-center" :class="adminBookingTab === 'bookings' ? 'bg-white text-indigo-800 shadow-sm' : ''" @click="adminBookingTab = 'bookings'">Court bookings</button>
          <button class="btn-secondary w-full justify-center" :class="adminBookingTab === 'misc' ? 'bg-white text-emerald-800 shadow-sm' : ''" @click="adminBookingTab = 'misc'">Misc costs</button>
        </div>
      </div>

      <div v-if="adminBookingTab === 'bookings'" class="space-y-6">
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
              <label class="form-label flex items-center gap-1"><ArenaIcon name="participation" class="h-4 w-4" />Court</label>
              <select aria-label="Court" v-model="selectedCourtId" class="form-input">
                <option value="">Select a court</option>
                <option v-for="court in activeCourts" :key="court.id" :value="court.id">{{ court.name }} · {{ court.location || 'No location' }}</option>
              </select>
            </div>
            <div>
              <label class="form-label flex items-center gap-1"><ArenaIcon name="calendar" class="h-4 w-4" />Date</label>
              <input aria-label="Date" v-model="bookingDate" type="date" class="form-input" />
            </div>
            <div>
              <label class="form-label flex items-center gap-1"><ArenaIcon name="clock" class="h-4 w-4" />Start time</label>
              <input aria-label="Start time" v-model="startTime" type="time" class="form-input" />
            </div>
            <div>
              <label class="form-label flex items-center gap-1"><ArenaIcon name="clock" class="h-4 w-4" />End time</label>
              <input aria-label="End time" v-model="endTime" type="time" class="form-input" />
            </div>
            <div>
              <label class="form-label flex items-center gap-1"><ArenaIcon name="invoice" class="h-4 w-4" />Cost</label>
              <input aria-label="Cost" v-if="editingBookingId" v-model="bookingCost" type="number" min="0" step="0.01" class="form-input" />
              <input aria-label="Cost" v-else :value="calculatedBookingCost" type="number" min="0" step="0.01" class="form-input" readonly />
              <p class="mt-1 text-xs text-slate-500">{{ editingBookingId ? 'Override the saved booking cost.' : 'Calculated from court rates and duration.' }}</p>
            </div>
            <div v-if="editingBookingId">
              <label class="form-label flex items-center gap-1"><ArenaIcon name="vote" class="h-4 w-4" />Status</label>
              <select aria-label="Status" v-model="bookingStatus" class="form-input">
                <option value="confirmed">Created</option>
                <option value="completed">Completed</option>
                <option value="settled">Settled</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div v-if="!editingBookingId">
              <label class="form-label flex items-center gap-1"><ArenaIcon name="calendar" class="h-4 w-4" />Recurring</label>
              <select aria-label="Recurring" v-model="recurringMode" class="form-input">
                <option :value="false">One-off</option>
                <option :value="true">Every week on the same day</option>
              </select>
            </div>
            <div class="sm:col-span-2 lg:col-span-4">
              <label class="form-label flex items-center gap-1"><ArenaIcon name="note" class="h-4 w-4" />Notes</label>
              <input aria-label="Notes" v-model="bookingNotes" placeholder="Optional booking notes" class="form-input" />
            </div>
          </div>
          <div v-if="recurringMode && !editingBookingId" class="mt-3 grid gap-2 sm:grid-cols-2 sm:gap-3">
            <div>
              <label class="form-label">Repeat every</label>
              <input aria-label="Repeat every" v-model.number="recurringIntervalWeeks" type="number" min="1" class="form-input" />
              <p class="mt-1 text-xs text-slate-500">weeks</p>
            </div>
            <div>
              <label class="form-label">Stop after</label>
              <input aria-label="Stop after" v-model="recurringEndDate" type="date" class="form-input" />
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
              <select aria-label="Player account" class="form-input" @change="applyParticipantMember(participant, $event.target.value)">
                <option value="">Keep / ad hoc player</option>
                <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
              </select>
              <input aria-label="Player name" v-model="participant.name" class="form-input" placeholder="Player name" />
              <select aria-label="Player attendance status" v-model="participant.status" class="form-input">
                <option value="attending">Attending</option>
                <option value="participated">Participated</option>
                <option value="not_attending">Not attending</option>
                <option value="tentative">Tentative</option>
              </select>
              <button class="btn-secondary" @click.stop="updateParticipant(booking, participant)">Save</button>
              <button class="btn-muted" @click.stop="deleteParticipant(booking, participant)">Remove</button>
            </div>
            <div class="grid gap-2 sm:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
              <select aria-label="Player account" v-model="newParticipantMember[booking.id]" class="form-input">
                <option value="">New player (not a member)</option>
                <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
              </select>
              <input aria-label="New player name" v-model="newParticipantName[booking.id]" class="form-input" placeholder="New player name" :disabled="!!newParticipantMember[booking.id]" />
              <input aria-label="Phone or label" v-model="newParticipantPhone[booking.id]" class="form-input" placeholder="Phone or label" :disabled="!!newParticipantMember[booking.id]" />
              <select aria-label="New player attendance status" v-model="newParticipantStatus[booking.id]" class="form-input">
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
                <select aria-label="Player account" class="form-input" @change="applyParticipantMember(participant, $event.target.value)">
                  <option value="">Keep / ad hoc player</option>
                  <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
                </select>
                <input aria-label="Player name" v-model="participant.name" class="form-input" placeholder="Player name" />
                <select aria-label="Player attendance status" v-model="participant.status" class="form-input">
                  <option value="attending">Attending</option>
                  <option value="participated">Participated</option>
                  <option value="not_attending">Not attending</option>
                  <option value="tentative">Tentative</option>
                </select>
                <button class="btn-secondary" @click.stop="updateParticipant(booking, participant)">Save</button>
                <button class="btn-muted" @click.stop="deleteParticipant(booking, participant)">Remove</button>
              </div>
              <div class="grid gap-2 sm:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
                <select aria-label="Player account" v-model="newParticipantMember[booking.id]" class="form-input">
                  <option value="">New player (not a member)</option>
                  <option v-for="member in memberOptions" :key="member.key" :value="member.key">{{ member.label }}</option>
                </select>
                <input aria-label="New player name" v-model="newParticipantName[booking.id]" class="form-input" placeholder="New player name" :disabled="!!newParticipantMember[booking.id]" />
                <input aria-label="Phone or label" v-model="newParticipantPhone[booking.id]" class="form-input" placeholder="Phone or label" :disabled="!!newParticipantMember[booking.id]" />
                <select aria-label="New player attendance status" v-model="newParticipantStatus[booking.id]" class="form-input">
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
      </div>

      <div v-if="adminBookingTab === 'misc'" class="space-y-4">
        <details class="panel-card" open>
          <summary class="cursor-pointer text-lg font-semibold text-slate-900">Add shared misc cost</summary>
          <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <input aria-label="Title" v-model="newMiscTitle" class="form-input" placeholder="Title" />
            <input aria-label="Paid by" v-model="newMiscPaidBy" class="form-input" placeholder="Paid by" />
            <input aria-label="Amount" v-model="newMiscAmount" type="number" min="0" step="0.01" class="form-input" placeholder="Amount" />
            <input aria-label="Purchase date" v-model="newMiscPurchaseDate" type="date" class="form-input" />
            <select aria-label="Player account" v-model="newMiscSplitScope" class="form-input">
              <option value="all_members">All members</option>
              <option value="club_members">Club members only</option>
            </select>
            <input aria-label="Split count" v-model.number="newMiscSplitCount" type="number" min="1" class="form-input" placeholder="Split count" :disabled="true" />
            <input aria-label="Description" v-model="newMiscDescription" class="form-input md:col-span-2" placeholder="Description" />
          </div>
          <button class="btn-dark mt-3 w-full sm:w-auto" @click="createMiscCost">Add cost</button>
        </details>

        <div class="grid gap-4 lg:grid-cols-2">
          <article v-for="cost in miscCosts" :key="cost.id" class="sub-card overflow-hidden p-0">
            <button type="button" class="flex w-full items-start justify-between gap-3 p-4 text-left transition hover:bg-slate-50" :aria-expanded="isMiscCostOpen(cost.id)" @click="toggleMiscCost(cost.id)">
              <div>
                <h3 class="font-semibold text-slate-900">{{ cost.title }}</h3>
                <p class="text-sm text-slate-600">{{ cost.description || 'No description' }}</p>
                <p class="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{{ cost.status }}<span v-if="isArchivedMiscCost(cost)" class="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-[0.65rem] text-amber-700">Archived</span> · {{ cost.purchase_date || 'No date' }} · {{ splitScopeLabel(cost.split_scope) }} · split {{ cost.split_count }}</p>
              </div>
              <div class="flex shrink-0 items-center gap-3">
                <span class="rounded bg-slate-900 px-2 py-1 text-sm font-semibold text-white">€{{ cost.amount }}</span>
                <span class="text-slate-400" aria-hidden="true">{{ isMiscCostOpen(cost.id) ? '−' : '+' }}</span>
              </div>
            </button>
            <div v-if="isMiscCostOpen(cost.id)" class="space-y-3 border-t border-slate-100 p-4">
              <div class="rounded border bg-slate-50 p-2 text-sm text-slate-700">{{ splitScopeLabel(cost.split_scope) }} · split by {{ cost.split_count }} members · €{{ cost.cost_per_person }} each</div>
              <div class="grid gap-3 sm:grid-cols-2">
                <input aria-label="Title" v-model="cost.title" class="form-input" placeholder="Title" />
                <input aria-label="Paid by" v-model="cost.paid_by" class="form-input" placeholder="Paid by" />
                <input aria-label="Shared cost amount" v-model.number="cost.amount" type="number" min="0" step="0.01" class="form-input" />
                <input aria-label="Purchase date" v-model="cost.purchase_date" type="date" class="form-input" />
                <select aria-label="Player account" v-model="cost.split_scope" class="form-input">
                  <option value="all_members">All members</option>
                  <option value="club_members">Club members only</option>
                </select>
                <input aria-label="Split count" v-model.number="cost.split_count" type="number" min="1" class="form-input" :disabled="cost.status !== 'settled'" />
                <select aria-label="Shared cost status" v-model="cost.status" class="form-input" @change="updateMiscCost(cost)">
                  <option value="open">Open</option>
                  <option value="settled">Settled</option>
                </select>
                <textarea aria-label="Description" v-model="cost.description" class="form-input sm:col-span-2" placeholder="Description"></textarea>
              </div>
              <div class="grid gap-2 sm:grid-cols-2">
                <button class="btn-secondary" @click="updateMiscCost(cost)">Save changes</button>
                <button class="btn-muted" @click="deleteMiscCost(cost)">Delete</button>
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section v-if="activeView === 'admin-courts'" class="space-y-6">
      <div>
        <div class="arena-view-heading"><ArenaIcon name="participation" /><h2 class="section-title">Manage Courts</h2></div>
        <p class="section-copy mt-1">Maintain courts, locations, map links, hourly rates, and vacation freeze periods.</p>
      </div>

      <div class="grid gap-6 lg:grid-cols-2">
        <div class="panel-card">
          <h3 class="mb-3 text-lg font-semibold">Add court</h3>
          <div class="space-y-3">
            <input aria-label="Court name" v-model="newCourtName" placeholder="Court name" class="form-input" />
            <input aria-label="Location" v-model="newCourtLocation" placeholder="Location" class="form-input" />
            <input aria-label="Google Maps link" v-model="newCourtMapLink" placeholder="Google Maps link" class="form-input" />
            <input aria-label="Description" v-model="newCourtDescription" placeholder="Description" class="form-input" />
            <input aria-label="Hourly rate" v-model="newCourtRate" type="number" min="0" step="0.01" placeholder="Hourly rate" class="form-input" />
            <input aria-label="30-minute rate" v-model="newCourtHalfHourRate" type="number" min="0" step="0.01" placeholder="30-minute rate" class="form-input" />
            <button class="btn-dark w-full" @click="createCourt">Add court</button>
          </div>
        </div>

        <div class="panel-card">
          <h3 class="mb-3 text-lg font-semibold">Courts</h3>
          <div class="space-y-3">
            <article v-for="court in courts" :key="court.id" class="sub-card space-y-3">
              <div class="grid gap-2">
                <input aria-label="Court name" v-model="court.name" class="form-input" />
                <input aria-label="Location" v-model="court.location" class="form-input" placeholder="Location" />
                <input aria-label="Google Maps link" v-model="court.map_link" class="form-input" placeholder="Google Maps link" />
                <input aria-label="Description" v-model="court.description" class="form-input" placeholder="Description" />
                <input aria-label="Hourly rate" v-model.number="court.hourly_rate" type="number" min="0" step="0.01" class="form-input" placeholder="Hourly rate" />
                <input aria-label="30-minute rate" v-model.number="court.half_hour_rate" type="number" min="0" step="0.01" class="form-input" placeholder="30-minute rate" />
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
          <input aria-label="Freeze period title" v-model="newFreezeTitle" class="form-input" placeholder="Vacation / hall closed" />
          <input aria-label="Freeze period start date" v-model="newFreezeStartDate" type="date" class="form-input" />
          <input aria-label="Freeze period end date" v-model="newFreezeEndDate" type="date" class="form-input" />
          <input aria-label="Optional reason" v-model="newFreezeReason" class="form-input" placeholder="Optional reason" />
          <button class="btn-dark">Add</button>
        </form>

        <div class="mt-4 space-y-3">
          <article v-for="period in freezePeriods" :key="period.id" class="sub-card space-y-3">
            <div class="grid gap-2 lg:grid-cols-[1.2fr_1fr_1fr_1.4fr_auto]">
              <input aria-label="Freeze period title" v-model="period.title" class="form-input" />
              <input aria-label="Freeze period start date" v-model="period.start_date" type="date" class="form-input" />
              <input aria-label="Freeze period end date" v-model="period.end_date" type="date" class="form-input" />
              <input aria-label="Reason" v-model="period.reason" class="form-input" placeholder="Reason" />
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

    <AvailabilityView v-if="activeView === 'availability' || activeView === 'poll'"
      :active-view="activeView"
      :all-public-poll-days-answered="allPublicPollDaysAnswered"
      :availability-names-by-status="availabilityNamesByStatus"
      :availability-people="availabilityPeople"
      :availability-person-status="availabilityPersonStatus"
      :availability-statuses="availabilityStatuses"
      :copy-text="copyText"
      :create-family-member="createFamilyMember"
      :delete-family-member="deleteFamilyMember"
      :family-members="familyMembers"
      :is-admin="isAdmin"
      :is-logged-in="isLoggedIn"
      v-model:newFamilyName="newFamilyName"
      :play-days="playDays"
      :public-poll="publicPoll"
      :public-poll-url="publicPollUrl"
      :save-availability-vote="saveAvailabilityVote"
      :save-public-availability-poll="savePublicAvailabilityPoll"
      :send-whats-app-family-polls="sendWhatsAppFamilyPolls"
      :set-availability-person-status="setAvailabilityPersonStatus"
      v-model:whatsappPollDates="whatsappPollDates"
      v-model:whatsappPollQuestion="whatsappPollQuestion"
      :whatsapp-poll-sending="whatsappPollSending"
    />

    <section v-if="activeView === 'costs'" class="space-y-6">
      <div>
        <div class="arena-view-heading"><ArenaIcon name="invoice" /><h2 class="section-title">My Costs</h2></div>
        <p class="section-copy mt-1">Review your family total, payment status, and every booking or shared cost included in the selected month.</p>
      </div>

      <div class="panel-card">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">Monthly period</h3>
            <p class="section-copy">Choose the month used for invoice and split details.</p>
          </div>
          <label class="block sm:w-52">
            <span class="form-label">Month</span>
            <input v-model="monthlyInvoiceMonth" type="month" class="form-input" @change="loadMonthlyInvoice" />
          </label>
        </div>
      </div>

      <MonthlyInvoiceDetails
      :copy-text="copyText"
      :current-payment-invoice="currentPaymentInvoice"
      :monthly-invoice="monthlyInvoice"
      :payment-status-label="paymentStatusLabel"
    />
    </section>


    <PaymentSettingsView v-if="activeView === 'payment-settings'"
      :apply-monthly-tikkie-link="applyMonthlyTikkieLink"
      :is-super-admin="isSuperAdmin"
      :month-name="monthName"
      :payment-month-options="paymentMonthOptions"
      :payment-settings="paymentSettings"
      :payment-settings-saving="paymentSettingsSaving"
      :save-payment-settings="savePaymentSettings"
    />

    <section v-if="activeView === 'admin-costs'" class="space-y-6">
      <div>
        <div class="arena-view-heading"><ArenaIcon name="invoice" /><h2 class="section-title">Invoices & Payments</h2></div>
        <p class="section-copy mt-1">Review family totals, prepare monthly invoices, and reconcile payments in one place.</p>
        <div class="mt-3 grid gap-2 sm:inline-grid sm:grid-flow-col sm:auto-cols-fr sm:rounded-xl sm:bg-slate-100 sm:p-1">
          <button class="btn-secondary w-full justify-center" :class="adminCostTab === 'invoices' ? 'bg-white text-indigo-800 shadow-sm' : ''" @click="adminCostTab = 'invoices'">Monthly invoices</button>
          <button class="btn-secondary w-full justify-center" :class="adminCostTab === 'booking' ? 'bg-white text-indigo-800 shadow-sm' : ''" @click="adminCostTab = 'booking'">Booking costs</button>
        </div>
      </div>

      <div v-if="adminCostTab === 'invoices'" class="panel-card">
        <div class="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">Monthly family invoices</h3>
            <p class="section-copy">Review each family's booking, shared-cost, and total amount for the selected month.</p>
          </div>
          <div class="grid gap-2 sm:grid-cols-2 xl:grid-cols-[minmax(10rem,12rem)_minmax(12rem,16rem)_minmax(12rem,16rem)_auto_auto] xl:items-end">
            <label class="block sm:w-48">
              <span class="form-label">Month</span>
              <input v-model="monthlyInvoiceMonth" type="month" class="form-input" @change="loadAdminMonthlyInvoices" />
            </label>
            <label class="block">
              <span class="form-label">Payment method</span>
              <select v-model="monthlyPaymentMethod" class="form-input">
                <option value="BUSINESS_BANK">Business bank account</option>
                <option value="PERSONAL_TIKKIE">Personal Tikkie</option>
              </select>
            </label>
            <label class="block">
              <span class="form-label">Month status</span>
              <select :value="adminMonthlyInvoices?.month_status?.status || 'OPEN'" class="form-input" @change="setMonthlyInvoiceStatus($event.target.value)">
                <option value="OPEN">Open</option>
                <option value="READY_FOR_PAYMENT">Ready for payment</option>
                <option value="SETTLED">Settled</option>
              </select>
            </label>
            <button class="btn-secondary" @click="openMonthlyInvoiceNotificationPreview">Notify group</button>
            <button
              v-if="adminMonthlyInvoices?.month_status?.status === 'READY_FOR_PAYMENT'"
              class="btn-secondary border-amber-300 bg-amber-50 text-amber-900 hover:bg-amber-100"
              @click="openPendingPaymentNotificationPreview"
            >
              Pending notification
            </button>
          </div>
        </div>
        <div v-if="adminMonthlyInvoices" class="mt-4 space-y-4">
          <div class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <span class="text-slate-600">Month status</span>
            <span :class="monthStatusClass(adminMonthlyInvoices.month_status?.status)" class="rounded-full px-3 py-1 text-xs font-bold">{{ monthStatusLabel(adminMonthlyInvoices.month_status?.status) }}</span>
            <span v-if="adminMonthlyInvoices.month_status?.ready_at" class="text-slate-500">Ready {{ dateTimeLabel(adminMonthlyInvoices.month_status.ready_at) }}</span>
          </div>
          <div class="grid gap-3 sm:grid-cols-3">
            <div class="rounded border border-teal-100 bg-teal-50 p-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Booking total</div>
              <div class="mt-1 text-2xl font-bold text-indigo-900">€{{ adminMonthlyInvoices.totals.booking_total }}</div>
            </div>
            <div class="rounded border border-teal-100 bg-teal-50 p-3">
              <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Shared costs</div>
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
                    <label v-if="invoice.payment_invoice" class="mt-2 block max-w-48" @click.stop>
                      <span class="form-label">Payment status</span>
                      <select
                        :value="invoice.payment_invoice.payment_status"
                        class="form-input min-w-40"
                        :disabled="paymentStatusSavingId === invoice.payment_invoice.id"
                        @change="setPaymentStatus(invoice.payment_invoice, $event.target.value)"
                      >
                        <option value="UNPAID">Payment pending</option>
                        <option value="PAID">Paid</option>
                      </select>
                    </label>
                  </div>
                  <div class="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                    <div class="rounded bg-slate-50 p-2"><div class="text-xs text-slate-500">Total cost</div><div class="font-bold">€{{ invoice.total }}</div></div>
                    <div class="rounded bg-teal-50 p-2"><div class="text-xs text-slate-500">Amount paid</div><div class="font-bold text-emerald-800">€{{ invoice.paid_amount || 0 }}</div></div>
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
                <div v-if="invoice.payment_invoice" class="flex flex-col gap-2 rounded-lg border border-teal-100 bg-teal-50/60 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between">
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
                    <button class="btn-secondary" :disabled="paymentStatusSavingId === invoice.payment_invoice.id" @click="setPaymentStatus(invoice.payment_invoice, 'PAID')">Paid</button>
                    <button class="btn-muted" :disabled="paymentStatusSavingId === invoice.payment_invoice.id" @click="setPaymentStatus(invoice.payment_invoice, 'UNPAID')">Unpaid</button>
                  </div>
                </div>
              </div>
            </details>
          </div>

          <div class="rounded-lg border border-slate-200 bg-white p-3">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h4 class="font-semibold text-slate-900">Payment invoices</h4>
                <p class="text-sm text-slate-600">Open Wise details or update status after verifying an offline payment.</p>
              </div>
              <label class="block sm:w-48">
                <span class="form-label">Filter</span>
                <select v-model="paymentFilter" class="form-input" @change="loadPaymentInvoices">
                  <option value="all">All invoices</option>
                  <option value="unpaid">Pending</option>
                  <option value="paid">Paid</option>
                  <option value="overdue">Overdue</option>
                  <option value="test">Test invoices</option>
                </select>
              </label>
            </div>
            <div class="mt-3 overflow-x-auto rounded-lg border border-slate-200">
              <table class="min-w-full divide-y divide-slate-200 text-sm">
                <thead class="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"><tr><th class="px-3 py-2">Invoice</th><th class="px-3 py-2">Family</th><th class="px-3 py-2">Month</th><th class="px-3 py-2 text-right">Due</th><th class="px-3 py-2">Status</th><th class="px-3 py-2 text-right">Actions</th></tr></thead>
                <tbody class="divide-y divide-slate-100 bg-white">
                  <tr v-for="invoice in paymentInvoices" :key="invoice.id">
                    <td class="px-3 py-2 font-semibold text-slate-900">{{ invoice.invoice_number }}<span v-if="invoice.is_test_invoice" class="ml-2 rounded bg-indigo-100 px-2 py-0.5 text-xs text-teal-800">Test</span><div class="text-xs font-normal text-slate-500">{{ invoice.payment_reference }}</div></td>
                    <td class="px-3 py-2 text-slate-700">{{ invoice.user?.name || invoice.user?.email || invoice.user?.phone || invoice.billing_name || 'Ad hoc player' }}</td>
                    <td class="whitespace-nowrap px-3 py-2 text-slate-700">{{ invoice.month || '—' }}<div class="text-xs text-slate-500">Due {{ invoice.due_date || '—' }}</div></td>
                    <td class="whitespace-nowrap px-3 py-2 text-right font-semibold text-slate-900">€{{ invoice.amount_due }}<div class="text-xs font-normal text-teal-700">Paid €{{ invoice.paid_amount || 0 }}</div></td>
                    <td class="px-3 py-2"><select aria-label="Player account" :value="invoice.payment_status" class="form-input min-w-36" @change="setPaymentStatus(invoice, $event.target.value)"><option value="UNPAID">Payment pending</option><option value="PARTIALLY_PAID">Partially paid</option><option value="PAID">Paid</option><option value="CANCELLED">Cancelled</option><option value="EXPIRED">Expired</option></select></td>
                    <td class="px-3 py-2 text-right"><button class="btn-secondary" @click="loadPaymentInvoice(invoice.id)">Wise details</button></td>
                  </tr>
                  <tr v-if="!paymentInvoices.length"><td colspan="6" class="px-3 py-4 text-center text-slate-500">No payment invoices match this filter.</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="selectedPaymentInvoice" class="rounded-lg border border-indigo-200 bg-teal-50/60 p-3">
            <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h4 class="font-semibold text-slate-900">Wise payment details</h4>
                <p class="text-sm text-slate-600">{{ selectedPaymentInvoice.user?.name || selectedPaymentInvoice.user?.email || selectedPaymentInvoice.billing_name || 'Ad hoc player' }} · {{ paymentStatusLabel(selectedPaymentInvoice.payment_status) }}</p>
              </div>
              <button class="btn-muted" @click="selectedPaymentInvoice = null">Close</button>
            </div>
            <div class="grid items-start gap-4 md:grid-cols-[160px_minmax(0,1fr)]">
              <img v-if="selectedPaymentInvoice.qr_code_data_url" :src="selectedPaymentInvoice.qr_code_data_url" alt="Payment QR code" class="w-40 max-w-full rounded border bg-white p-2" />
              <div class="rounded border border-white/70 bg-white text-sm">
                <p class="border-b border-slate-100 px-4 py-3 text-slate-600">Scan this QR or open the Wise payment link.</p>
                <dl class="grid grid-cols-[9rem_minmax(0,1fr)] divide-y divide-slate-100">
                  <template v-if="selectedPaymentInvoice.payment_url"><dt class="px-4 py-3 font-semibold text-slate-600">Wise link</dt><dd class="px-4 py-3 text-slate-700"><a :href="selectedPaymentInvoice.payment_url" target="_blank" rel="noopener" class="btn-dark inline-flex">Open Wise payment link</a></dd></template>
                  <dt class="px-4 py-3 font-semibold text-slate-600">Invoice PDF</dt><dd class="px-4 py-3 text-slate-700"><button class="btn-secondary" @click="downloadPaymentInvoicePdf(selectedPaymentInvoice)">Download PDF</button></dd>
                  <dt class="px-4 py-3 font-semibold text-slate-600">Amount due</dt><dd class="px-4 py-3 font-semibold text-slate-900">€{{ selectedPaymentInvoice.amount_due }}</dd>
                  <dt class="px-4 py-3 font-semibold text-slate-600">Due date</dt><dd class="px-4 py-3 text-slate-700">{{ selectedPaymentInvoice.due_date }}</dd>
                  <dt class="px-4 py-3 font-semibold text-slate-600">IBAN</dt><dd class="flex flex-wrap items-center gap-2 px-4 py-3 text-slate-700"><span>{{ selectedPaymentInvoice.iban }}</span><button class="btn-muted" @click="copyText(selectedPaymentInvoice.iban)">Copy</button></dd>
                  <dt class="px-4 py-3 font-semibold text-slate-600">Account holder</dt><dd class="px-4 py-3 text-slate-700">{{ selectedPaymentInvoice.account_holder_name }}</dd>
                  <dt class="px-4 py-3 font-semibold text-slate-600">Reference</dt><dd class="flex flex-wrap items-center gap-2 px-4 py-3 text-slate-700"><span>{{ selectedPaymentInvoice.payment_reference }}</span><button class="btn-muted" @click="copyText(selectedPaymentInvoice.payment_reference)">Copy</button></dd>
                </dl>
              </div>
            </div>
          </div>

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
        <div class="arena-view-heading"><ArenaIcon name="family" /><h2 class="section-title">Members</h2></div>
        <p class="section-copy mt-1">Find a family, update its contact details, and expand it only when you need more options.</p>
      </div>

      <div v-if="!isAdmin" class="alert-warning">
        Admin access is required to manage members.
      </div>

      <div v-else class="space-y-4">
        <section class="panel-card grid gap-4 p-4 sm:grid-cols-[1fr_auto] sm:items-end sm:p-5">
          <div>
            <label class="form-label">Find a member or family</label>
            <input aria-label="Find a member or family" v-model="memberSearch" type="search" class="form-input" placeholder="Search name, email, phone, or family member" />
            <p class="mt-1 text-xs text-slate-500">Showing {{ filteredAdminUsers.length }} of {{ adminUsers.length }} accounts.</p>
          </div>
          <button class="btn-dark" :disabled="whatsappBackfillRunning" @click="backfillWhatsAppFamilyDetails">
            {{ whatsappBackfillRunning ? 'Preparing…' : 'Prepare WhatsApp families' }}
          </button>
        </section>

        <details class="panel-card p-4 sm:p-5">
          <summary class="cursor-pointer list-none font-semibold text-slate-900">Club player selection <span class="ml-2 text-sm font-normal text-slate-500">{{ selectedClubMemberKeys.length }} selected</span></summary>
          <div class="mt-4 space-y-3">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h3 class="text-base font-semibold text-slate-900">Club member selection</h3>
              <p class="section-copy mt-1">Select all active club players once. Linked family members are merged with their player account to keep the list unique.</p>
            </div>
            <div class="rounded-2xl bg-teal-50 px-4 py-2 text-center text-indigo-900">
              <div class="text-xs font-bold uppercase tracking-wide text-indigo-500">Club members</div>
              <div class="text-2xl font-black">{{ selectedClubMemberKeys.length }}</div>
            </div>
          </div>
          <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div>
              <label class="form-label">Players</label>
              <select aria-label="Players" v-model="selectedClubMemberKeys" multiple size="6" class="form-input min-h-36">
                <option v-for="option in clubMemberOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
              </select>
              <p class="mt-1 text-xs text-slate-500">Tip: use Ctrl/⌘ or Shift to select multiple players.</p>
            </div>
            <button class="btn-dark w-full lg:w-auto" @click="saveClubMemberSelection">Save club members</button>
          </div>
          </div>
        </details>

        <article v-for="member in filteredAdminUsers" :key="member.id" class="panel-card space-y-3 p-4 sm:p-5">
          <div class="grid gap-3 lg:grid-cols-[1.1fr_1fr_1fr_auto] lg:items-end">
            <div>
              <label class="form-label">Name</label>
              <input aria-label="Name" v-model="member.name" class="form-input" placeholder="Name" />
            </div>
            <div>
              <label class="form-label">Email</label>
              <input aria-label="Email" v-model="member.email" type="email" class="form-input" placeholder="Email" />
            </div>
            <div>
              <label class="form-label">WhatsApp</label>
              <input aria-label="WhatsApp" v-model="member.whatsapp_number" class="form-input" placeholder="+31..." />
            </div>
            <div class="grid gap-2">
              <button class="btn-secondary" @click="updateAdminUser(member)">Save</button>
              <button class="btn-muted" @click="deleteAdminUser(member)">Remove family</button>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2 text-xs font-semibold">
            <span class="rounded-full bg-slate-100 px-2.5 py-1 text-slate-700">{{ member.family_members?.length || 0 }} family members</span>
            <span :class="member.whatsapp_link ? 'bg-teal-100 text-emerald-800' : 'bg-amber-100 text-amber-800'" class="rounded-full px-2.5 py-1">
              {{ member.whatsapp_link ? (member.whatsapp_link.is_primary ? 'Primary WhatsApp' : 'WhatsApp linked') : 'WhatsApp not prepared' }}
            </span>
          </div>

          <details class="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <summary class="cursor-pointer font-semibold text-slate-800">Family and account details</summary>
            <div class="mt-4 grid gap-3 md:grid-cols-3">
            <div>
              <label class="form-label">Reset password</label>
              <input aria-label="Reset password"
                v-model="newAdminUserPassword[member.id]"
                type="password"
                minlength="6"
                class="form-input"
                placeholder="Leave blank to keep"
              />
            </div>
            <label class="flex items-center gap-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700">
              <input
                :checked="['admin', 'super_admin'].includes(member.role)"
                type="checkbox"
                class="rounded border-slate-300 text-teal-700 focus:ring-indigo-500"
                :disabled="member.role === 'super_admin' && !isSuperAdmin"
                @change="member.role = $event.target.checked ? 'admin' : 'member'"
              />
              Admin
            </label>
            <label v-if="isSuperAdmin" class="flex items-center gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800">
              <input
                :checked="member.role === 'super_admin'"
                type="checkbox"
                class="rounded border-amber-300 text-amber-600 focus:ring-amber-500"
                @change="member.role = $event.target.checked ? 'super_admin' : 'admin'"
              />
              Super Admin
            </label>
            <div class="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              Login id: {{ member.email || member.phone }}
            </div>
          </div>

          <div class="mt-3 grid gap-3 rounded-xl border border-emerald-200 bg-teal-50 p-3 md:grid-cols-3">
            <label class="flex items-center gap-2 text-sm font-medium text-emerald-900">
              <input :checked="member.whatsapp_link?.is_primary" type="checkbox" @change="member.whatsapp_link = { ...(member.whatsapp_link || {}), is_primary: $event.target.checked }" />
              Primary family number
            </label>
            <label class="flex items-center gap-2 text-sm font-medium text-emerald-900">
              <input :checked="member.whatsapp_link?.notifications_enabled !== false" type="checkbox" @change="member.whatsapp_link = { ...(member.whatsapp_link || {}), notifications_enabled: $event.target.checked }" />
              Receive notifications
            </label>
            <label class="text-sm font-medium text-emerald-900">
              Family delivery
              <select v-model="member.whatsapp_delivery_mode" class="form-input mt-1">
                <option value="PRIMARY_ONLY">Primary only</option>
                <option value="ALL_LINKED">All linked numbers</option>
              </select>
            </label>
          </div>

          <div class="border-t border-slate-100 pt-3">
            <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div class="arena-view-heading"><ArenaIcon name="family" /><h3 class="text-sm font-semibold text-slate-900">Family members</h3></div>
              <button class="btn-dark" @click="createAdminFamilyMember(member)">Add family member</button>
            </div>
            <div class="mb-3 grid gap-2 md:grid-cols-3">
              <input aria-label="Family member name" v-model="newAdminFamilyName[member.id]" class="form-input" placeholder="Family member name" />
              <input aria-label="Relationship" v-model="newAdminFamilyRelationship[member.id]" class="form-input" placeholder="Relationship" />
              <select aria-label="Linked player account" v-model="newAdminFamilyLinkedUser[member.id]" class="form-input">
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
                <input aria-label="Family member name" v-model="familyMember.name" class="form-input" placeholder="Family member name" />
                <input aria-label="Relationship" v-model="familyMember.relationship" class="form-input" placeholder="Relationship" />
                <select aria-label="Linked player account" v-model="familyMember.linked_user_id" class="form-input">
                  <option :value="null">No linked account</option>
                  <option v-for="option in linkableUserOptions(member.id)" :key="option.id" :value="option.id">{{ option.label }}</option>
                </select>
                <div class="flex items-center justify-end">
                  <button class="btn-secondary" @click="updateAdminFamilyMember(member, familyMember)">Save</button>
                </div>
                <button class="btn-muted" @click="deleteAdminFamilyMember(member, familyMember)">Remove</button>
              </div>
            </div>
            <p v-else class="text-sm text-slate-600">No family members added for this user.</p>
          </div>
          </details>
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
                <td class="px-3 py-3"><span class="rounded-full bg-teal-50 px-2 py-1 text-xs font-bold uppercase text-teal-800">{{ log.event_type }}</span></td>
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

    <section v-if="activeView === 'system-checks'" class="space-y-6">
      <div class="rounded-3xl border border-sky-100 bg-gradient-to-br from-sky-50 via-white to-emerald-50 p-4 shadow-sm sm:p-6">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.24em] text-sky-700">Admin diagnostics</p>
            <h2 class="mt-1 text-2xl font-black text-slate-950">Third-party connection checks</h2>
            <p class="mt-2 max-w-3xl text-sm text-slate-600">Check backend reachability, WhatsApp bot health, Wise profile access, and Wise webhook subscription status. You can also send a direct WhatsApp test and inspect recent Wise webhook events here.</p>
          </div>
          <button class="btn-dark w-full sm:w-auto" :disabled="systemCheckRefreshing" @click="loadSystemChecks()">
            {{ systemCheckRefreshing ? 'Refreshing...' : 'Refresh checks' }}
          </button>
        </div>
      </div>

      <div v-if="!isAdmin" class="alert-warning">
        Admin access is required to use diagnostics.
      </div>

      <div v-else class="space-y-6">
        <div class="grid gap-4 xl:grid-cols-4">
          <article class="panel-card space-y-3">
            <div class="flex items-center justify-between gap-3">
              <h3 class="font-semibold text-slate-900">Backend API</h3>
              <span class="rounded-full px-3 py-1 text-xs font-bold" :class="connectionStatusClass(systemChecks?.backend?.status)">
                {{ connectionStatusLabel(systemChecks?.backend?.status) }}
              </span>
            </div>
            <p class="text-sm text-slate-600">{{ systemChecks?.backend?.message || 'Waiting for diagnostics data.' }}</p>
          </article>

          <article class="panel-card space-y-3">
            <div class="flex items-center justify-between gap-3">
              <h3 class="font-semibold text-slate-900">WhatsApp bot</h3>
              <span class="rounded-full px-3 py-1 text-xs font-bold" :class="connectionStatusClass(systemChecks?.whatsapp?.status)">
                {{ connectionStatusLabel(systemChecks?.whatsapp?.status) }}
              </span>
            </div>
            <p class="text-sm text-slate-600">{{ systemChecks?.whatsapp?.message || 'Waiting for diagnostics data.' }}</p>
            <div class="grid gap-2 text-xs text-slate-500">
              <div><strong class="text-slate-700">Bot URL:</strong> {{ systemChecks?.whatsapp?.bot_url || 'Not configured' }}</div>
              <div><strong class="text-slate-700">Token:</strong> {{ systemChecks?.whatsapp?.token_configured ? 'Configured' : 'Missing' }}</div>
              <div><strong class="text-slate-700">Ready:</strong> {{ systemChecks?.whatsapp?.ready ? 'Yes' : 'No' }}</div>
            </div>
            <template v-if="systemChecks?.whatsapp?.provider === 'whatsapp_web'">
              <img v-if="systemChecks.whatsapp.qr_image" :src="systemChecks.whatsapp.qr_image" alt="WhatsApp linking QR code" class="mx-auto w-64 max-w-full rounded-xl bg-white p-2" />
              <p v-if="systemChecks.whatsapp.state === 'qr_required'" class="text-sm text-slate-600">On your phone, open WhatsApp → Linked devices → Link a device, then scan this code. It refreshes automatically.</p>
              <p v-if="systemChecks.whatsapp.error" class="text-sm text-red-700">{{ systemChecks.whatsapp.error }}</p>
              <div class="flex flex-wrap gap-2">
                <button class="btn-dark" :disabled="whatsappReconnecting" @click="reconnectWhatsApp(false)">{{ whatsappReconnecting ? 'Reconnecting…' : 'Reconnect WhatsApp' }}</button>
                <button class="btn-outline" :disabled="whatsappReconnecting" @click="reconnectWhatsApp(true)">Reset session and get QR code</button>
              </div>
            </template>
          </article>

          <article class="panel-card space-y-3">
            <div class="flex items-center justify-between gap-3">
              <h3 class="font-semibold text-slate-900">Wise profile</h3>
              <span class="rounded-full px-3 py-1 text-xs font-bold" :class="connectionStatusClass(systemChecks?.wise?.profile_check?.status)">
                {{ connectionStatusLabel(systemChecks?.wise?.profile_check?.status) }}
              </span>
            </div>
            <p class="text-sm text-slate-600">{{ systemChecks?.wise?.profile_check?.message || 'Waiting for diagnostics data.' }}</p>
            <div class="grid gap-2 text-xs text-slate-500">
              <div><strong class="text-slate-700">Profile ID:</strong> {{ systemChecks?.wise?.profile_check?.resolved_profile_id || systemChecks?.wise?.settings?.wise_profile_id || 'Not resolved' }}</div>
              <div><strong class="text-slate-700">API token:</strong> {{ systemChecks?.wise?.settings?.wise_api_token_configured ? 'Configured' : 'Missing' }}</div>
              <div><strong class="text-slate-700">API base URL:</strong> {{ systemChecks?.wise?.settings?.wise_api_base_url || 'https://api.wise.com' }}</div>
            </div>
          </article>

          <article class="panel-card space-y-3">
            <div class="flex items-center justify-between gap-3">
              <h3 class="font-semibold text-slate-900">Wise webhook</h3>
              <span class="rounded-full px-3 py-1 text-xs font-bold" :class="connectionStatusClass(systemChecks?.wise?.subscription_check?.status)">
                {{ connectionStatusLabel(systemChecks?.wise?.subscription_check?.status) }}
              </span>
            </div>
            <p class="text-sm text-slate-600">{{ systemChecks?.wise?.subscription_check?.message || 'Waiting for diagnostics data.' }}</p>
            <div class="grid gap-2 text-xs text-slate-500">
              <div><strong class="text-slate-700">Subscription ID:</strong> {{ systemChecks?.wise?.settings?.wise_webhook_subscription_id || 'Not configured' }}</div>
              <div><strong class="text-slate-700">Webhook URL:</strong> {{ systemChecks?.wise?.settings?.wise_webhook_url || 'Not configured' }}</div>
              <div><strong class="text-slate-700">Client key:</strong> {{ systemChecks?.wise?.settings?.wise_client_key_configured ? 'Configured' : 'Missing' }}</div>
            </div>
          </article>
        </div>

        <div class="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <section class="panel-card space-y-4">
            <div>
              <h3 class="font-semibold text-slate-900">WhatsApp connection test</h3>
              <p class="mt-1 text-sm text-slate-600">Send a direct test message through the bot and confirm the current delivery status without changing notification templates.</p>
            </div>
            <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <label class="block">
                <span class="form-label">Test recipient</span>
                <input v-model="systemCheckWhatsAppRecipient" class="form-input" placeholder="+31612345678 or 31612345678@c.us" />
              </label>
              <button class="btn-dark" :disabled="systemCheckWhatsAppTesting" @click="runWhatsAppConnectionTest">
                {{ systemCheckWhatsAppTesting ? 'Sending...' : 'Send connection test' }}
              </button>
            </div>
            <div class="grid gap-3 md:grid-cols-2">
              <div class="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                <div class="font-semibold text-slate-900">Saved default recipient</div>
                <div class="mt-1">{{ systemChecks?.whatsapp?.default_test_recipient || 'No saved WhatsApp test number yet.' }}</div>
              </div>
              <div class="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                <div class="font-semibold text-slate-900">Last direct test</div>
                <div class="mt-1" v-if="systemChecks?.whatsapp?.last_test_log">
                  {{ systemChecks.whatsapp.last_test_log.recipient || 'No recipient' }} ·
                  <span class="font-semibold" :class="connectionStatusTextClass(systemChecks.whatsapp.last_test_log.status)">
                    {{ connectionStatusLabel(systemChecks.whatsapp.last_test_log.status) }}
                  </span>
                </div>
                <div class="mt-1" v-else>No direct connection test sent yet.</div>
              </div>
            </div>
          </section>

          <aside class="panel-card space-y-4">
            <div>
              <h3 class="font-semibold text-slate-900">Recent WhatsApp logs</h3>
              <p class="mt-1 text-sm text-slate-600">Latest sends, including direct connection tests.</p>
            </div>
            <div class="space-y-3">
              <div v-for="log in systemChecks?.whatsapp?.recent_logs || []" :key="log.id" class="rounded-xl border border-slate-100 bg-slate-50 p-3 text-sm">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-semibold text-slate-800">{{ log.event_key }}</span>
                  <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="connectionStatusClass(log.status)">{{ connectionStatusLabel(log.status) }}</span>
                </div>
                <p class="mt-1 text-xs text-slate-500">{{ log.recipient || 'No recipient' }} · {{ dateTimeLabel(log.created_at) }}</p>
                <p class="mt-2 line-clamp-3 whitespace-pre-line text-xs text-slate-600">{{ log.message }}</p>
              </div>
              <p v-if="!(systemChecks?.whatsapp?.recent_logs || []).length" class="text-sm text-slate-500">No WhatsApp logs yet.</p>
            </div>
          </aside>
        </div>

        <section class="panel-card space-y-4">
          <div>
            <h3 class="font-semibold text-slate-900">Password-reset WhatsApp test</h3>
            <p class="mt-1 text-sm text-slate-600">Send a harmless test through the exact WhatsApp delivery path used for reset codes. This does not create or reveal a reset code.</p>
          </div>
          <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <label class="block">
              <span class="form-label">Member email, name, or phone</span>
              <input v-model="passwordResetTestIdentifier" class="form-input" placeholder="member@example.com" />
            </label>
            <button class="btn-dark" :disabled="passwordResetTesting || !passwordResetTestIdentifier.trim()" @click="runPasswordResetDeliveryTest">
              {{ passwordResetTesting ? 'Sending...' : 'Test reset delivery' }}
            </button>
          </div>
          <div v-if="passwordResetTestResult" class="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
            <strong>Status:</strong> {{ connectionStatusLabel(passwordResetTestResult.status) }} ·
            <strong>Recipient:</strong> {{ passwordResetTestResult.recipient }}
            <span v-if="passwordResetTestResult.provider"> · <strong>Provider:</strong> {{ passwordResetTestResult.provider }}</span>
          </div>
        </section>

        <section class="panel-card space-y-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h3 class="font-semibold text-slate-900">Wise payment lookup</h3>
              <p class="mt-1 text-sm text-slate-600">Search by invoice number or payment reference to find the invoice and the most relevant webhook events.</p>
            </div>
            <div class="grid gap-2 sm:grid-cols-[minmax(14rem,20rem)_auto_auto] sm:items-end">
              <label class="block">
                <span class="form-label">Invoice or reference</span>
                <input v-model="systemCheckQuery" class="form-input" placeholder="INV-2026-00039" @keyup.enter="loadSystemChecks()" />
              </label>
              <button class="btn-secondary" :disabled="systemCheckRefreshing" @click="loadSystemChecks()">Check reference</button>
              <button class="btn-muted" :disabled="systemCheckRefreshing" @click="clearSystemCheckLookup">Clear</button>
            </div>
          </div>

          <div v-if="systemCheckQuery && systemChecks?.payment_lookup" class="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div class="flex items-center justify-between gap-3">
                <h4 class="font-semibold text-slate-900">Matched invoice</h4>
                <span class="rounded-full px-3 py-1 text-xs font-bold" :class="systemChecks.payment_lookup.invoice ? 'bg-teal-100 text-teal-700' : 'bg-amber-100 text-amber-700'">
                  {{ systemChecks.payment_lookup.invoice ? 'Found' : 'No match' }}
                </span>
              </div>
              <div v-if="systemChecks.payment_lookup.invoice" class="mt-3 space-y-2 text-sm text-slate-700">
                <div><strong>Invoice:</strong> {{ systemChecks.payment_lookup.invoice.invoice_number }}</div>
                <div><strong>Reference:</strong> {{ systemChecks.payment_lookup.invoice.payment_reference }}</div>
                <div><strong>Status:</strong> {{ paymentStatusLabel(systemChecks.payment_lookup.invoice.payment_status) }}</div>
                <div><strong>Amount due:</strong> €{{ systemChecks.payment_lookup.invoice.amount_due }}</div>
                <div><strong>Paid amount:</strong> €{{ systemChecks.payment_lookup.invoice.paid_amount || 0 }}</div>
                <div><strong>Match reason:</strong> {{ connectionStatusLabel(systemChecks.payment_lookup.match_reason) }}</div>
              </div>
              <p v-else class="mt-3 text-sm text-slate-600">No invoice matched this query.</p>
            </div>

            <div class="rounded-2xl border border-slate-200 bg-white p-4">
              <h4 class="font-semibold text-slate-900">Related Wise events</h4>
              <div class="mt-3 space-y-3">
                <div v-for="event in systemChecks.payment_lookup.related_events || []" :key="event.id" class="rounded-xl border border-slate-100 bg-slate-50 p-3 text-sm">
                  <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div class="font-semibold text-slate-900">{{ event.incoming_transfer_id || `Event #${event.id}` }}</div>
                      <div class="text-xs text-slate-500">{{ event.reference || 'No reference' }} · {{ dateTimeLabel(event.created_at) }}</div>
                    </div>
                    <div class="flex items-center gap-2">
                      <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="connectionStatusClass((event.status || '').toLowerCase())">{{ connectionStatusLabel((event.status || '').toLowerCase()) }}</span>
                      <button class="btn-secondary" :disabled="retryingWiseEventId === event.id || !event.incoming_transfer_id" @click="retryWiseWebhookEvent(event)">
                        {{ retryingWiseEventId === event.id ? 'Retrying...' : 'Retry' }}
                      </button>
                    </div>
                  </div>
                  <p v-if="event.error_message" class="mt-2 text-xs text-rose-700">{{ event.error_message }}</p>
                </div>
                <p v-if="!(systemChecks.payment_lookup.related_events || []).length" class="text-sm text-slate-500">No related Wise events found for this query.</p>
              </div>
            </div>
          </div>
        </section>

        <section class="panel-card space-y-4">
          <div class="flex items-center justify-between gap-3">
            <div>
              <h3 class="font-semibold text-slate-900">Recent Wise webhook events</h3>
              <p class="mt-1 text-sm text-slate-600">Inspect recent incoming-transfer events and retry reconciliation if the reference match failed.</p>
            </div>
            <p class="text-xs text-slate-500">Checked {{ dateTimeLabel(systemChecks?.checked_at) }}</p>
          </div>
          <div class="space-y-3">
            <div v-for="event in systemChecks?.wise?.recent_events || []" :key="event.id" class="rounded-xl border border-slate-100 bg-slate-50 p-4 text-sm">
              <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="font-semibold text-slate-900">{{ event.incoming_transfer_id || `Event #${event.id}` }}</span>
                    <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="connectionStatusClass((event.status || '').toLowerCase())">{{ connectionStatusLabel((event.status || '').toLowerCase()) }}</span>
                  </div>
                  <p class="mt-1 text-xs text-slate-500">{{ event.event_type || 'Unknown type' }} · {{ dateTimeLabel(event.created_at) }}</p>
                  <div class="mt-2 grid gap-1 text-xs text-slate-600 sm:grid-cols-2">
                    <div><strong>Reference:</strong> {{ event.reference || 'No reference' }}</div>
                    <div><strong>Amount:</strong> {{ event.currency || 'EUR' }} {{ event.amount || 0 }}</div>
                    <div><strong>Sender:</strong> {{ event.sender_name || 'Unknown sender' }}</div>
                    <div><strong>Invoice ID:</strong> {{ event.invoice_id || 'Not matched' }}</div>
                  </div>
                  <p v-if="event.error_message" class="mt-2 text-xs text-rose-700">{{ event.error_message }}</p>
                </div>
                <button class="btn-secondary self-start" :disabled="retryingWiseEventId === event.id || !event.incoming_transfer_id" @click="retryWiseWebhookEvent(event)">
                  {{ retryingWiseEventId === event.id ? 'Retrying...' : 'Retry match' }}
                </button>
              </div>
            </div>
            <p v-if="!(systemChecks?.wise?.recent_events || []).length" class="text-sm text-slate-500">No Wise webhook events recorded yet.</p>
          </div>
        </section>
      </div>
    </section>

    <NotificationSettingsView v-if="activeView === 'notifications'"
      :load-whats-app-notifications="loadWhatsAppNotifications"
      :loading="loading"
      :open-setting-notification-preview="openSettingNotificationPreview"
      :save-whats-app-notification="saveWhatsAppNotification"
      :test-whats-app-notification="testWhatsAppNotification"
      :whatsapp-logs="whatsappLogs"
      :whatsapp-settings="whatsappSettings"
    />

    <CostVerificationDialog
      :close-verification-details="closeVerificationDetails"
      :verification-details="verificationDetails"
    />

  </div>
</template>

<script>
import ArenaIcon from './ArenaIcon.vue'
import TentativeIcon from './dashboard/TentativeIcon'
import useDashboard from './dashboard/useDashboard'
import PublicWelcome from './dashboard/PublicWelcome.vue'
import NotificationPreviewDialog from './dashboard/NotificationPreviewDialog.vue'
import MemberBookingsView from './dashboard/MemberBookingsView.vue'
import AvailabilityView from './dashboard/AvailabilityView.vue'
import PaymentSettingsView from './dashboard/PaymentSettingsView.vue'
import NotificationSettingsView from './dashboard/NotificationSettingsView.vue'
import CostVerificationDialog from './dashboard/CostVerificationDialog.vue'
import MonthlyInvoiceDetails from './dashboard/MonthlyInvoiceDetails.vue'

export default {
  components: {
    ArenaIcon, TentativeIcon,
    PublicWelcome,
    NotificationPreviewDialog,
    MemberBookingsView,
    AvailabilityView,
    PaymentSettingsView,
    NotificationSettingsView,
    CostVerificationDialog,
    MonthlyInvoiceDetails
  },
  props: {
    initialView: { type: String, default: 'availability' }
  },
  setup: useDashboard
}
</script>
