import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { clearAuthSession, getAuthSessionVersion, getSessionValue, hasAuthSession, setSessionValue } from '../../authSession'

// Shared dashboard controller: state, API calls, permissions and lifecycle stay
// together. The function body is unchanged from Dashboard.vue before extraction.
export default function useDashboard(props) {
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
    const miscCostArchiveCutoffDate = ref(null)
    const selectedClubMemberKeys = ref([])
    const monthlyInvoice = ref(null)
    const currentPaymentInvoice = ref(null)
    const defaultWiseRedirectUrl = `${window.location.origin}/my-invoices`
    const defaultWiseWebhookUrl = `${window.location.origin}/api/webhooks/wise/incoming-transfer`
    const publicPollUrl = `${window.location.origin}/poll`
    const adminMonthlyInvoices = ref(null)
    const monthlyInvoiceMonth = ref(localIsoMonth())
    const monthlyPaymentMethod = ref('BUSINESS_BANK')
    const whatsappSettings = ref([])
    const whatsappLogs = ref([])
    const notificationPreview = ref({ open: false, type: '', title: '', endpoint: '', payload: {}, message: '', recipient: '', testRecipient: '', testRecipients: [], sending: false })
    const publicPoll = ref({
      name: window.localStorage.getItem('badminton_poll_name') || '',
      voterToken: window.localStorage.getItem('badminton_poll_voter_token') || '',
      responses: loadSavedPublicPollResponses(),
      saving: false
    })
    const systemChecks = ref(null)
    const systemCheckQuery = ref('')
    const systemCheckWhatsAppRecipient = ref('')
    const passwordResetTestIdentifier = ref('')
    const passwordResetTestResult = ref(null)
    const adminAuditLogs = ref([])
    const completedBookingPagination = ref({ page: 1, per_page: 12, total: 0, pages: 0 })
    const archivedBookingPagination = ref({ page: 1, per_page: 12, total: 0, pages: 0 })
    const adminAuditPagination = ref({ page: 1, per_page: 50, total: 0, pages: 0 })
    const openBookingIds = ref(new Set())
    const openCompletedBookingIds = ref(new Set())
    const openMiscCostIds = ref(new Set())
    const loading = ref(false)
    const paymentSettingsSaving = ref(false)
    const paymentTestGenerating = ref(false)
    const paymentTestRefreshing = ref(false)
    const paymentWebhookSubscribing = ref(false)
    const paymentWebhookStatusLoading = ref(false)
    const systemCheckRefreshing = ref(false)
    const systemCheckWhatsAppTesting = ref(false)
    const whatsappReconnecting = ref(false)
    let whatsappConnectionTimer
    const passwordResetTesting = ref(false)
    const retryingWiseEventId = ref(null)
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
    const memberSearch = ref('')
    const whatsappBackfillRunning = ref(false)
    const whatsappPollDates = ref([])
    const whatsappPollQuestion = ref('Who can play badminton?')
    const whatsappPollSending = ref(false)
    const newMiscTitle = ref('')
    const newMiscDescription = ref('')
    const newMiscAmount = ref('')
    const newMiscPaidBy = ref('')
    const newMiscPurchaseDate = ref(localIsoDate())
    const newMiscSplitCount = ref(1)
    const newMiscSplitScope = ref('all_members')
    const msg = ref('')
    const verificationDetails = ref(null)
    const isAdmin = ref(false)
    const isSuperAdmin = ref(false)
    const paymentSettings = ref({ qr_enabled: true, test_mode: true, default_due_days: 14 })
    const paymentWebhookStatus = ref(null)
    const paymentMonthOptions = computed(() => {
      const options = []
      const current = new Date()
      for (let offset = 12; offset >= -12; offset -= 1) {
        const date = new Date(current.getFullYear(), current.getMonth() - offset, 1)
        options.push(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`)
      }
      return options
    })

    const wiseWebhookHealthText = computed(() => {
      const status = paymentWebhookStatus.value
      if (!status) return 'Connection status has not been checked in this browser session.'
      if (!status.subscription_configured) return 'Create the Wise webhook subscription once, then make a test payment using the exact invoice reference.'
      if (!status.latest_event) return 'Subscription is saved, but no Wise webhook event has reached this app yet.'
      if (status.latest_event.status === 'MATCHED') return 'Connection is working: the latest Wise webhook matched an invoice and updated its payment status.'
      if (status.latest_event.status === 'UNMATCHED') return 'Webhook reached the app, but no invoice reference matched the incoming transfer.'
      if (status.latest_event.status === 'ERROR') return `Webhook reached the app, but Wise transfer lookup failed: ${status.latest_event.error_message || 'unknown error'}.`
      return `Webhook reached the app with status ${status.latest_event.status}.`
    })
    const paymentInvoices = ref([])
    const paymentStatusSavingId = ref(null)
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
    const clubMemberOptions = computed(() => buildClubMemberOptions())
    const filteredAdminUsers = computed(() => {
      const query = memberSearch.value.trim().toLowerCase()
      if (!query) return adminUsers.value
      return adminUsers.value.filter((member) => [
        member.name, member.email, member.phone, member.whatsapp_number,
        ...(member.family_members || []).map((item) => item.name)
      ].some((value) => String(value || '').toLowerCase().includes(query)))
    })
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
      { value: 'available', label: 'Available', shortLabel: 'Yes' },
      { value: 'tentative', label: 'Tentative', shortLabel: 'Maybe' },
      { value: 'not_available', label: 'No', shortLabel: 'No' }
    ]
    const allPublicPollDaysAnswered = computed(() => playDays.value.length > 0 && playDays.value.every(
      (day) => availabilityStatuses.some((status) => status.value === publicPoll.value.responses[day.date])
    ))

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
      if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json'
      }
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
      if (!attendees.length && status !== 'not_available') {
        attendees.push({
          type: 'self',
          name: getSessionValue('member_name') || getSessionValue('member_email') || getSessionValue('member_phone') || 'You',
          phone: getSessionValue('member_phone') || '',
          status
        })
      }
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
      systemChecks.value = null
      systemCheckQuery.value = ''
      systemCheckWhatsAppRecipient.value = ''
      isAdmin.value = false
      isSuperAdmin.value = false
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
      if (options.scope) params.set('scope', options.scope)
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

    function loadSavedPublicPollResponses() {
      try {
        return JSON.parse(window.localStorage.getItem('badminton_poll_responses') || '{}')
      } catch (_error) {
        return {}
      }
    }

    function publicPollVoterToken() {
      if (!publicPoll.value.voterToken) {
        const randomPart = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
        publicPoll.value.voterToken = randomPart.replace(/[^A-Za-z0-9_-]/g, '')
        window.localStorage.setItem('badminton_poll_voter_token', publicPoll.value.voterToken)
      }
      return publicPoll.value.voterToken
    }

    async function savePublicAvailabilityPoll() {
      publicPoll.value.saving = true
      errorMsg.value = ''
      msg.value = ''
      try {
        const responses = playDays.value.map((day) => ({
          play_date: day.date,
          status: publicPoll.value.responses[day.date]
        }))
        await fetchJson('/api/play-availability/public', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: publicPoll.value.name.trim(),
            voter_token: publicPollVoterToken(),
            responses
          })
        })
        window.localStorage.setItem('badminton_poll_name', publicPoll.value.name.trim())
        window.localStorage.setItem('badminton_poll_responses', JSON.stringify(publicPoll.value.responses))
        msg.value = 'Your availability is saved. You can update it here at any time.'
        await loadPlayAvailability()
        window.scrollTo({ top: 0, behavior: 'smooth' })
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        publicPoll.value.saving = false
      }
    }

    async function loadMiscCosts(options = {}) {
      const params = new URLSearchParams()
      if (options.status) params.set('status', options.status)
      const query = params.toString()
      const data = await fetchJson(`/api/misc-costs${query ? `?${query}` : ''}`)
      miscCosts.value = data.costs || []
      miscCostArchiveCutoffDate.value = data.archive_cutoff_date || miscCostArchiveCutoffDate.value
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
      monthlyPaymentMethod.value = data.month_status?.payment_method || 'BUSINESS_BANK'
      completedBookingPagination.value = { ...completedBookingPagination.value, page: 1 }
      await loadBookings({ status: 'completed', month: monthlyInvoiceMonth.value, page: completedBookingPagination.value.page, perPage: completedBookingPagination.value.per_page })
    }

    async function loadAdminUsers() {
      const data = await fetchJson('/api/admin/users')
      adminUsers.value = data.users || []
      syncSelectedClubMembers()
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


    function normalizePaymentSettings(settings = {}) {
      settings = settings || {}
      const textFields = [
        'account_holder_name',
        'bank_name',
        'bic',
        'iban',
        'description_prefix',
        'wise_api_base_url',
        'wise_client_key',
        'wise_payment_url',
        'wise_profile_id',
        'wise_redirect_url',
        'wise_webhook_url',
        'wise_webhook_subscription_id'
      ]
      const normalized = {
        qr_enabled: true,
        test_mode: true,
        default_due_days: 14,
        wise_api_base_url: 'https://api.wise.com',
        ...settings,
        wise_api_token: '',
        wise_redirect_url: settings.wise_redirect_url || defaultWiseRedirectUrl,
        wise_webhook_url: settings.wise_webhook_url || defaultWiseWebhookUrl
      }
      normalized.tikkie_month = settings.tikkie_month || localIsoMonth()
      normalized.monthly_tikkie_links = settings.monthly_tikkie_links || []
      for (const field of textFields) {
        normalized[field] = normalized[field] ?? ''
      }
      normalized.default_due_days = Number(normalized.default_due_days || 14)
      normalized.qr_enabled = Boolean(normalized.qr_enabled)
      normalized.test_mode = Boolean(normalized.test_mode)
      normalized.wise_api_token_configured = Boolean(normalized.wise_api_token_configured)
      return normalized
    }

    function applyMonthlyTikkieLink() {
      const saved = (paymentSettings.value.monthly_tikkie_links || []).find((item) => item.month === paymentSettings.value.tikkie_month)
      paymentSettings.value.monthly_tikkie_payment_url = saved?.tikkie_payment_url || ''
      paymentSettings.value.monthly_tikkie_account_holder_name = saved?.tikkie_account_holder_name || ''
    }

    async function loadPaymentSettings() {
      if (!isSuperAdmin.value) return
      const settings = await fetchJson('/api/admin/payment-settings')
      paymentSettings.value = normalizePaymentSettings(settings)
      applyMonthlyTikkieLink()
    }

    async function savePaymentSettings() {
      paymentSettingsSaving.value = true
      try {
        const settings = await fetchJson('/api/admin/payment-settings', { method: 'PUT', body: JSON.stringify(paymentSettings.value) })
        paymentSettings.value = normalizePaymentSettings(settings)
        applyMonthlyTikkieLink()
        msg.value = 'Payment settings saved.'
        errorMsg.value = ''
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        paymentSettingsSaving.value = false
      }
    }

    async function persistPaymentSettingsForTest() {
      const settings = await fetchJson('/api/admin/payment-settings', { method: 'PUT', body: JSON.stringify(paymentSettings.value) })
      paymentSettings.value = normalizePaymentSettings(settings)
    }

    async function createWiseWebhookSubscription() {
      paymentWebhookSubscribing.value = true
      try {
        const data = await fetchJson('/api/admin/payment-settings/wise-webhook-subscription', { method: 'POST', body: JSON.stringify(paymentSettings.value) })
        paymentSettings.value = normalizePaymentSettings(data.settings)
        await loadWiseWebhookStatus()
        msg.value = 'Wise webhook subscription created.'
        errorMsg.value = ''
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        paymentWebhookSubscribing.value = false
      }
    }

    async function loadWiseWebhookStatus() {
      if (!isSuperAdmin.value) return
      paymentWebhookStatusLoading.value = true
      try {
        paymentWebhookStatus.value = await fetchJson('/api/admin/payment-settings/wise-webhook-status')
        errorMsg.value = ''
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        paymentWebhookStatusLoading.value = false
      }
    }

    async function loadPaymentInvoices() {
      if (!isAdmin.value) return
      const data = await fetchJson(`/api/admin/payment-invoices?status=${paymentFilter.value}`)
      paymentInvoices.value = data.invoices || []
    }

    async function loadPaymentInvoice(id) {
      selectedPaymentInvoice.value = await fetchJson(`/api/payment-invoices/${id}`)
    }

    async function downloadPaymentInvoicePdf(invoice) {
      const response = await fetch(`${apiBase}/api/payment-invoices/${invoice.id}/pdf`, {
        headers: token() ? { Authorization: `Bearer ${token()}` } : {},
        cache: 'no-store'
      })
      if (!response.ok) throw new Error('Unable to generate invoice PDF.')
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${invoice.invoice_number || 'invoice'}.pdf`
      anchor.click()
      URL.revokeObjectURL(url)
    }

    async function loadLatestTestInvoice() {
      paymentTestRefreshing.value = true
      try {
        const data = await fetchJson('/api/admin/payment-invoices/test/latest')
        selectedPaymentInvoice.value = data.invoice || null
        errorMsg.value = ''
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        paymentTestRefreshing.value = false
      }
    }

    async function setPaymentStatus(invoice, status) {
      paymentStatusSavingId.value = invoice.id
      errorMsg.value = ''
      try {
        const updated = await fetchJson(`/api/admin/payment-invoices/${invoice.id}/status`, { method: 'POST', body: JSON.stringify({ payment_status: status }) })
        selectedPaymentInvoice.value = updated
        msg.value = `${updated.invoice_number} marked ${paymentStatusLabel(updated.payment_status).toLowerCase()}.`
        await loadPaymentInvoices()
        if (adminMonthlyInvoices.value) await loadAdminMonthlyInvoices()
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        paymentStatusSavingId.value = null
      }
    }

    async function setMonthlyInvoiceStatus(status) {
      const data = await fetchJson('/api/admin/invoices/monthly/status', { method: 'POST', body: JSON.stringify({ month: monthlyInvoiceMonth.value, status, payment_method: monthlyPaymentMethod.value }) })
      msg.value = `${monthStatusLabel(data.month_status?.status)} saved for ${monthName(monthlyInvoiceMonth.value)}.`
      if (data.payment_generation_errors?.length) {
        errorMsg.value = 'The month status was saved, but one or more payment invoices need Wise payment details regenerated.'
      } else {
        errorMsg.value = ''
      }
      await loadAdminMonthlyInvoices()
    }

    async function generateTestInvoice() {
      paymentTestGenerating.value = true
      try {
        msg.value = 'Preparing Wise test invoice...'
        await persistPaymentSettingsForTest()
        selectedPaymentInvoice.value = await fetchJson('/api/admin/payment-invoices/test', { method: 'POST', body: JSON.stringify({}) })
        msg.value = '€1 test invoice generated.'
        errorMsg.value = ''
        if (isAdmin.value) await loadPaymentInvoices()
        await loadWiseWebhookStatus()
      } catch (err) {
        errorMsg.value = err.message
        msg.value = ''
      } finally {
        paymentTestGenerating.value = false
      }
    }

    async function openNotificationPreview({ type, title, previewEndpoint, sendEndpoint, payload }) {
      const data = await fetchJson(previewEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
      })
      notificationPreview.value = {
        open: true,
        type,
        title,
        endpoint: sendEndpoint,
        payload: payload || {},
        message: data.message || '',
        recipient: data.recipient || '',
        testRecipient: data.test_recipients?.[0]?.value || '',
        testRecipients: data.test_recipients || [],
        sending: false
      }
      errorMsg.value = ''
    }

    async function openSettingNotificationPreview(setting) {
      await openNotificationPreview({
        type: setting.event_key,
        title: `${setting.title || 'WhatsApp'} notification`,
        previewEndpoint: `/api/admin/whatsapp-notifications/${setting.id}/preview`,
        sendEndpoint: `/api/admin/whatsapp-notifications/${setting.id}/send`,
        payload: {}
      })
    }

    async function openMonthlyInvoiceNotificationPreview() {
      await openNotificationPreview({
        type: 'monthly_invoice_ready',
        title: 'Monthly invoice notification',
        previewEndpoint: '/api/admin/payment-invoices/monthly/notify/preview',
        sendEndpoint: '/api/admin/payment-invoices/monthly/notify',
        payload: { month: monthlyInvoiceMonth.value }
      })
    }

    async function openPendingPaymentNotificationPreview() {
      await openNotificationPreview({
        type: 'monthly_payment_pending',
        title: `Pending payment reminder · ${monthName(monthlyInvoiceMonth.value)}`,
        previewEndpoint: '/api/admin/payment-invoices/monthly/pending/preview',
        sendEndpoint: '/api/admin/payment-invoices/monthly/pending',
        payload: { month: monthlyInvoiceMonth.value, payment_method: monthlyPaymentMethod.value }
      })
    }

    function closeNotificationPreview() {
      notificationPreview.value.open = false
    }

    async function sendNotificationPreview(test = false) {
      notificationPreview.value.sending = true
      try {
        const data = await fetchJson(notificationPreview.value.endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...notificationPreview.value.payload,
            message: notificationPreview.value.message,
            test,
            recipient: test ? notificationPreview.value.testRecipient : undefined
          })
        })
        msg.value = test
          ? `Test notification ${data.status || data.log?.status || 'sent'} to ${data.log?.recipient || notificationPreview.value.testRecipient}.`
          : `Notification ${data.status || data.log?.status || 'sent'} to group.`
        errorMsg.value = ''
        if (!test) closeNotificationPreview()
        await loadWhatsAppNotifications().catch(() => {})
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        notificationPreview.value.sending = false
      }
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

    function connectionStatusLabel(status) {
      return ({
        ok: 'OK',
        warning: 'Warning',
        error: 'Error',
        not_configured: 'Not configured',
        matched: 'Matched',
        unmatched: 'Unmatched',
        received: 'Received',
        sent: 'Sent',
        failed: 'Failed',
        skipped: 'Skipped',
        full_reference: 'Full reference',
        suffix_reference: 'Suffix reference',
        contains_reference: 'Contains reference',
      })[status] || statusLabel(status, 'Unknown')
    }

    function connectionStatusClass(status) {
      return ({
        ok: 'bg-emerald-100 text-emerald-700',
        matched: 'bg-emerald-100 text-emerald-700',
        sent: 'bg-emerald-100 text-emerald-700',
        warning: 'bg-amber-100 text-amber-700',
        unmatched: 'bg-amber-100 text-amber-700',
        not_configured: 'bg-slate-200 text-slate-700',
        received: 'bg-sky-100 text-sky-700',
        error: 'bg-rose-100 text-rose-700',
        failed: 'bg-rose-100 text-rose-700',
        skipped: 'bg-slate-200 text-slate-700',
      })[status] || 'bg-slate-200 text-slate-700'
    }

    function connectionStatusTextClass(status) {
      return ({
        ok: 'text-emerald-700',
        matched: 'text-emerald-700',
        sent: 'text-emerald-700',
        warning: 'text-amber-700',
        unmatched: 'text-amber-700',
        not_configured: 'text-slate-700',
        received: 'text-sky-700',
        error: 'text-rose-700',
        failed: 'text-rose-700',
        skipped: 'text-slate-700',
      })[status] || 'text-slate-700'
    }

    async function loadSystemChecks(query = systemCheckQuery.value.trim()) {
      systemCheckRefreshing.value = true
      try {
        const params = new URLSearchParams()
        const trimmedQuery = (query || '').trim()
        if (trimmedQuery) params.set('query', trimmedQuery)
        const suffix = params.toString() ? `?${params.toString()}` : ''
        systemChecks.value = await fetchJson(`/api/admin/system-checks${suffix}`)
        systemCheckQuery.value = trimmedQuery
        if (!systemCheckWhatsAppRecipient.value && systemChecks.value?.whatsapp?.default_test_recipient) {
          systemCheckWhatsAppRecipient.value = systemChecks.value.whatsapp.default_test_recipient
        }
      } finally {
        systemCheckRefreshing.value = false
      }
    }

    async function refreshWhatsAppConnection() {
      if (activeView.value !== 'system-checks' || !hasToken() || !systemChecks.value || whatsappReconnecting.value) return
      try {
        systemChecks.value.whatsapp = {
          ...systemChecks.value.whatsapp,
          ...await fetchJson('/api/admin/system-checks/whatsapp-connection')
        }
      } catch (_) { /* Keep the last result until the next refresh. */ }
    }

    async function reconnectWhatsApp(resetSession = false) {
      if (resetSession && !window.confirm('Reset the WhatsApp session? You will need to scan a new QR code to link WhatsApp again.')) return
      whatsappReconnecting.value = true
      try {
        await fetchJson('/api/admin/system-checks/whatsapp-connection', {
          method: 'POST', body: JSON.stringify({ reset_session: resetSession })
        })
        msg.value = resetSession ? 'WhatsApp session reset. Scan the new QR code when it appears.' : 'WhatsApp is reconnecting.'
        errorMsg.value = ''
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        whatsappReconnecting.value = false
        await refreshWhatsAppConnection()
      }
    }

    async function runWhatsAppConnectionTest() {
      systemCheckWhatsAppTesting.value = true
      try {
        const payload = await fetchJson('/api/admin/system-checks/whatsapp-test', {
          method: 'POST',
          body: JSON.stringify({ recipient: (systemCheckWhatsAppRecipient.value || '').trim() })
        })
        msg.value = `${payload.message} (${payload.recipient})`
        errorMsg.value = ''
        await loadSystemChecks(systemCheckQuery.value)
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        systemCheckWhatsAppTesting.value = false
      }
    }

    async function runPasswordResetDeliveryTest() {
      passwordResetTesting.value = true
      passwordResetTestResult.value = null
      try {
        const payload = await fetchJson('/api/admin/system-checks/password-reset-test', {
          method: 'POST',
          body: JSON.stringify({ identifier: passwordResetTestIdentifier.value.trim() })
        })
        passwordResetTestResult.value = payload
        msg.value = `Password-reset delivery test sent to ${payload.recipient}.`
        errorMsg.value = ''
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        passwordResetTesting.value = false
      }
    }

    async function retryWiseWebhookEvent(event) {
      retryingWiseEventId.value = event.id
      try {
        const payload = await fetchJson(`/api/admin/wise-webhook-events/${event.id}/retry`, { method: 'POST' })
        msg.value = `Wise webhook retry result: ${connectionStatusLabel(payload.status)}.`
        errorMsg.value = ''
        await loadSystemChecks(systemCheckQuery.value)
      } catch (err) {
        errorMsg.value = err.message
      } finally {
        retryingWiseEventId.value = null
      }
    }

    async function clearSystemCheckLookup() {
      systemCheckQuery.value = ''
      await loadSystemChecks('')
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

    async function loadDashboard() {
      loading.value = true
      errorMsg.value = ''
      try {
        const loggedIn = hasToken()
        if (!loggedIn) {
          isAdmin.value = false
          isSuperAdmin.value = false
        }

        if (activeView.value === 'bookings') {
          await Promise.all([
            loadBookings({ status: 'upcoming', perPage: 100 }),
            loadPlayAvailability()
          ])
          if (loggedIn) {
            await loadFamilyMembers()
            await loadBookings({ status: 'completed', scope: 'mine', month: monthlyInvoiceMonth.value, page: completedBookingPagination.value.page, perPage: completedBookingPagination.value.per_page })
          }
          if (loggedIn && isAdmin.value) {
            await loadCourts()
          }
        } else if (activeView.value === 'availability' || activeView.value === 'poll') {
          await loadPlayAvailability()
          if (loggedIn && activeView.value === 'availability') {
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
            loadAdminUsers(),
            loadMiscCosts({ status: 'all' })
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
            loadPaymentInvoices(),
            loadBookings({ status: 'archive', page: archivedBookingPagination.value.page, perPage: archivedBookingPagination.value.per_page }),
            loadAdminUsers()
          ])
        } else if (activeView.value === 'payment-settings') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
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
        } else if (activeView.value === 'system-checks') {
          if (!loggedIn) {
            router.push('/login')
            return
          }
          if (!isAdmin.value) {
            errorMsg.value = 'Admin access is required.'
            return
          }
          await loadSystemChecks()
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
        if (activeView.value === 'admin-bookings' || activeView.value === 'admin-costs') await loadDashboard()
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

    function isArchivedMiscCost(cost) {
      return Boolean(cost?.purchase_date && miscCostArchiveCutoffDate.value && cost.purchase_date < miscCostArchiveCutoffDate.value)
    }

    function clubMemberLabel(person) {
      return person.name || person.email || person.phone || 'Unnamed player'
    }

    function buildClubMemberOptions() {
      const options = []
      const seenUserIds = new Set()
      for (const member of adminUsers.value) {
        const key = `user:${member.id}`
        seenUserIds.add(Number(member.id))
        const linkedNames = (member.family_members || [])
          .filter((familyMember) => Number(familyMember.linked_user_id) === Number(member.id))
          .map((familyMember) => familyMember.name)
          .filter(Boolean)
        options.push({
          key,
          type: 'user',
          id: member.id,
          familyIds: (member.family_members || [])
            .filter((familyMember) => Number(familyMember.linked_user_id) === Number(member.id))
            .map((familyMember) => familyMember.id),
          label: linkedNames.length ? `${clubMemberLabel(member)} (${linkedNames.join(', ')})` : clubMemberLabel(member),
          selected: Boolean(member.is_club_member)
        })
      }
      for (const owner of adminUsers.value) {
        for (const familyMember of owner.family_members || []) {
          if (familyMember.linked_user_id && seenUserIds.has(Number(familyMember.linked_user_id))) continue
          options.push({
            key: `family:${familyMember.id}`,
            type: 'family',
            id: familyMember.id,
            label: `${clubMemberLabel(familyMember)} · family of ${clubMemberLabel(owner)}`,
            selected: Boolean(familyMember.is_club_member)
          })
        }
      }
      return options.sort((a, b) => a.label.localeCompare(b.label))
    }

    function syncSelectedClubMembers() {
      selectedClubMemberKeys.value = buildClubMemberOptions()
        .filter((option) => option.selected)
        .map((option) => option.key)
    }

    async function saveClubMemberSelection() {
      const selected = new Set(selectedClubMemberKeys.value)
      try {
        const requests = []
        for (const option of buildClubMemberOptions()) {
          const isSelected = selected.has(option.key)
          if (option.type === 'user') {
            const member = adminUsers.value.find((user) => Number(user.id) === Number(option.id))
            if (member && Boolean(member.is_club_member) !== isSelected) {
              requests.push(fetchJson(`/api/admin/users/${member.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_club_member: isSelected })
              }))
            }
            for (const familyId of option.familyIds || []) {
              const familyMember = adminUsers.value.flatMap((user) => user.family_members || []).find((item) => Number(item.id) === Number(familyId))
              if (familyMember && Boolean(familyMember.is_club_member) !== isSelected) {
                requests.push(fetchJson(`/api/admin/family-members/${familyMember.id}`, {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ is_club_member: isSelected })
                }))
              }
            }
          } else {
            const familyMember = adminUsers.value.flatMap((user) => user.family_members || []).find((item) => Number(item.id) === Number(option.id))
            if (familyMember && Boolean(familyMember.is_club_member) !== isSelected) {
              requests.push(fetchJson(`/api/admin/family-members/${familyMember.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_club_member: isSelected })
              }))
            }
          }
        }
        await Promise.all(requests)
        msg.value = requests.length ? `Updated ${selected.size} club members.` : 'Club member selection is already up to date.'
        await loadAdminUsers()
      } catch (err) {
        msg.value = err.message
        await loadAdminUsers()
      }
    }

    function splitScopeLabel(scope) {
      return scope === 'club_members' ? 'Club members only' : 'All members'
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
            split_count: newMiscSplitCount.value,
            split_scope: newMiscSplitScope.value
          })
        })
        msg.value = `Added cost ${data.title}.`
        newMiscTitle.value = ''
        newMiscDescription.value = ''
        newMiscAmount.value = ''
        newMiscPaidBy.value = ''
        newMiscPurchaseDate.value = localIsoDate()
        newMiscSplitCount.value = 1
        newMiscSplitScope.value = 'all_members'
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
          whatsapp_is_primary: member.whatsapp_link?.is_primary || false,
          whatsapp_notifications_enabled: member.whatsapp_link?.notifications_enabled !== false,
          whatsapp_delivery_mode: member.whatsapp_delivery_mode || 'ALL_LINKED',
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

    async function backfillWhatsAppFamilyDetails() {
      if (!window.confirm('Link all existing member WhatsApp numbers to their current families? This is safe to run more than once.')) return
      whatsappBackfillRunning.value = true
      try {
        const result = await fetchJson('/api/admin/whatsapp-family-links/backfill', { method: 'POST' })
        msg.value = `WhatsApp details ready: ${result.created} added, ${result.updated} refreshed, ${result.skipped} without a number${result.errors.length ? `, ${result.errors.length} need attention` : ''}.`
        await loadAdminUsers()
      } catch (err) {
        msg.value = err.message
      } finally {
        whatsappBackfillRunning.value = false
      }
    }

    async function sendWhatsAppFamilyPolls() {
      whatsappPollSending.value = true
      try {
        const result = await fetchJson('/api/admin/availability-polls/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dates: whatsappPollDates.value,
            question_prefix: whatsappPollQuestion.value,
            send_to_families: true
          })
        })
        msg.value = `Sent ${result.sent} poll message(s) to ${result.families} families.`
      } catch (err) {
        msg.value = err.message
      } finally {
        whatsappPollSending.value = false
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
      whatsappConnectionTimer = window.setInterval(refreshWhatsAppConnection, 5000)
      window.addEventListener('badminton-auth-changed', handleAuthChanged)
      if (token()) {
        await loadCurrentUser()
      } else {
        isAdmin.value = false
      }
      await loadDashboard()
    })

    onBeforeUnmount(() => {
      window.clearInterval(whatsappConnectionTimer)
      window.removeEventListener('badminton-auth-changed', handleAuthChanged)
    })

    return {
      activeView,
      activeCourts,
      adminUsers,
      filteredAdminUsers,
      memberSearch,
      whatsappBackfillRunning,
      whatsappPollDates,
      whatsappPollQuestion,
      whatsappPollSending,
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
      selectedClubMemberKeys,
      clubMemberOptions,
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
      publicPoll,
      publicPollUrl,
      allPublicPollDaysAnswered,
      miscCosts,
      isArchivedMiscCost,
      saveClubMemberSelection,
      backfillWhatsAppFamilyDetails,
      sendWhatsAppFamilyPolls,
      monthlyInvoice,
      currentPaymentInvoice,
      memberOptions,
      adminMonthlyInvoices,
      monthlyInvoiceMonth,
      paymentMonthOptions,
      monthlyPaymentMethod,
      whatsappSettings,
      whatsappLogs,
      notificationPreview,
      systemChecks,
      systemCheckQuery,
      systemCheckWhatsAppRecipient,
      passwordResetTestIdentifier,
      passwordResetTestResult,
      isLoggedIn,
      isAdmin,
      isSuperAdmin,
      paymentSettingsSaving,
      paymentTestGenerating,
      paymentTestRefreshing,
      paymentWebhookSubscribing,
      paymentWebhookStatusLoading,
      systemCheckRefreshing,
      systemCheckWhatsAppTesting,
      whatsappReconnecting,
      reconnectWhatsApp,
      passwordResetTesting,
      retryingWiseEventId,
      paymentSettings,
      paymentWebhookStatus,
      wiseWebhookHealthText,
      defaultWiseRedirectUrl,
      defaultWiseWebhookUrl,
      paymentInvoices,
      paymentStatusSavingId,
      selectedPaymentInvoice,
      paymentFilter,
      apiBase,
      isBookingOpen,
      toggleBooking,
      isCompletedBookingOpen,
      toggleCompletedBooking,
      isMiscCostOpen,
      toggleMiscCost,
      splitScopeLabel,
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
      newMiscSplitScope,
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
      loadSystemChecks,
      loadWhatsAppNotifications,
      loadPaymentSettings,
      savePaymentSettings,
      applyMonthlyTikkieLink,
      createWiseWebhookSubscription,
      loadWiseWebhookStatus,
      loadPaymentInvoices,
      loadPaymentInvoice,
      downloadPaymentInvoicePdf,
      loadLatestTestInvoice,
      setPaymentStatus,
      setMonthlyInvoiceStatus,
      generateTestInvoice,
      openSettingNotificationPreview,
      openMonthlyInvoiceNotificationPreview,
      openPendingPaymentNotificationPreview,
      closeNotificationPreview,
      sendNotificationPreview,
      clearSystemCheckLookup,
      copyText,
      paymentStatusLabel,
      monthStatusLabel,
      monthStatusClass,
      monthName,
      dateTimeLabel,
      connectionStatusLabel,
      connectionStatusClass,
      connectionStatusTextClass,
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
      savePublicAvailabilityPoll,
      saveBookingRsvp,
      saveFamilyPersonAttendance,
      saveWhatsAppNotification,
      runWhatsAppConnectionTest,
      runPasswordResetDeliveryTest,
      testWhatsAppNotification,
      retryWiseWebhookEvent,
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
