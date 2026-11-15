<template>
  <div class="panel-card space-y-4">
    <h3 class="text-lg font-semibold">Participation report</h3>
    <p class="section-copy">All completed sessions through now, including archived bookings. Dates use Europe/Amsterdam. Court costs only; read-only.</p>
    <form class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" @submit.prevent="load()">
      <label class="form-label">From (inclusive)<input v-model="filters.start" type="date" class="form-input" /></label>
      <label class="form-label">Through (inclusive)<input v-model="filters.end" type="date" class="form-input" /></label>
      <label class="form-label">Payment status<select v-model="filters.status" class="form-input"><option value="all">All statuses</option><option value="paid">Paid</option><option value="partial">Partially paid</option><option value="invoiced_unpaid">Invoiced and unpaid</option><option value="not_invoiced">Not yet invoiced</option></select></label>
      <label class="form-label">Family<select v-model="filters.family" class="form-input"><option value="">All families</option><option v-for="family in report?.family_options || []" :key="family.id" :value="family.id">{{ family.name }}</option></select></label>
      <label class="form-label">View<select v-model="filters.view" class="form-input"><option value="both">Both</option><option value="person">By person</option><option value="family">By family</option></select></label>
      <div class="flex flex-wrap items-end gap-2"><button class="btn-primary" :disabled="loading">Apply filters</button><button type="button" class="btn-secondary" :disabled="loading" @click="load(true)">Download CSV</button></div>
    </form>
    <p class="text-sm text-slate-600">Payments are allocated across the full invoice, including non-court charges, before filtering. A family session counts once; appearances count every player. Members with zero sessions appear when all statuses are selected.</p>
    <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
    <p v-if="loading" role="status">Loading report…</p>
    <template v-if="report && !loading">
      <section v-for="table in tables" :key="table.key" class="space-y-2">
        <h4 class="font-semibold">{{ table.title }}</h4>
        <div class="overflow-x-auto"><table class="w-full text-left text-sm">
          <thead><tr><th class="p-2">Name</th><th class="p-2">Sessions played</th><th v-if="table.key === 'families'" class="p-2">Player appearances</th><th class="p-2">Court cost</th><th class="p-2">Paid</th><th class="p-2">Outstanding</th><th class="p-2">Payment statuses</th></tr></thead>
          <tbody><tr v-for="row in report[table.key]" :key="row.id" class="border-t"><td class="p-2">{{ row.name }}</td><td class="p-2">{{ row.sessions }}</td><td v-if="table.key === 'families'" class="p-2">{{ row.appearances }}</td><td class="p-2">{{ money(row.court_cost) }}</td><td class="p-2">{{ money(row.paid_amount) }}</td><td class="p-2">{{ money(row.balance) }}</td><td class="p-2">{{ row.payment_statuses.map(statusLabel).join(', ') || 'No sessions' }}</td></tr></tbody>
        </table></div>
        <p v-if="!report[table.key].length" class="section-copy">No matching participation.</p>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getSessionValue } from '../../authSession'
const filters = ref({ start: '', end: '', status: 'all', family: '', view: 'both' })
const report = ref(null)
const appliedView = ref('both')
const loading = ref(false)
const error = ref('')
const tables = computed(() => [
  ...(appliedView.value !== 'family' ? [{ key: 'people', title: 'By person' }] : []),
  ...(appliedView.value !== 'person' ? [{ key: 'families', title: 'By family' }] : [])
])
const money = value => new Intl.NumberFormat('nl-NL', { style: 'currency', currency: 'EUR' }).format(value)
const statusLabel = value => ({ paid: 'Paid', partial: 'Partially paid', invoiced_unpaid: 'Invoiced and unpaid', not_invoiced: 'Not yet invoiced' })[value]
async function load(csv = false) {
  loading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams(filters.value)
    if (csv) query.set('format', 'csv')
    const response = await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/admin/reports/participation?${query}`, {
      headers: { Authorization: `Bearer ${getSessionValue('auth_token')}` }, cache: 'no-store'
    })
    if (!response.ok) throw new Error((await response.json()).error || 'Unable to load report')
    if (csv) {
      const url = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = 'participation-report.csv'
      link.click()
      URL.revokeObjectURL(url)
    } else {
      report.value = await response.json()
      appliedView.value = filters.value.view
    }
  } catch (err) { error.value = err.message }
  finally { loading.value = false }
}
onMounted(() => load())
</script>
