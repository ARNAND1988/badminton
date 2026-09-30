<template>
<div v-if="monthlyInvoice" class="panel-card space-y-6">
    <div class="grid gap-3 sm:grid-cols-3">
      <div class="rounded-2xl border border-teal-100 bg-teal-50/80 p-4">
        <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Bookings</div>
        <div class="mt-1 text-2xl font-bold text-indigo-900">€{{ monthlyInvoice.booking_total }}</div>
      </div>
      <div class="rounded-2xl border border-teal-100 bg-teal-50/80 p-4">
        <div class="text-xs font-semibold uppercase tracking-wide text-teal-700">Misc costs</div>
        <div class="mt-1 text-2xl font-bold text-emerald-900">€{{ monthlyInvoice.misc_total }}</div>
      </div>
      <div class="rounded-2xl border p-4" :class="monthlyInvoice.balance_amount > 0 ? 'border-amber-100 bg-amber-50/80' : 'border-teal-100 bg-teal-50/80'">
        <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Total due</div>
        <div class="mt-1 text-2xl font-bold text-slate-900">€{{ monthlyInvoice.balance_amount ?? monthlyInvoice.total }}</div>
      </div>
    </div>

    <div v-if="currentPaymentInvoice && currentPaymentInvoice.payment_status !== 'PAID' && (monthlyInvoice.balance_amount ?? monthlyInvoice.total) > 0" class="rounded-2xl border border-teal-100 bg-teal-50/60 p-4 sm:p-5">
      <div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"><div><h4 class="font-semibold text-slate-900">{{ currentPaymentInvoice.payment_method === 'PERSONAL_TIKKIE' ? 'Pay with Tikkie' : 'Pay by business bank account' }}</h4><p class="text-sm text-slate-600">Scan the QR or open the payment link to pay this invoice.</p></div><span class="w-fit rounded-full bg-white px-3 py-1 text-sm font-bold text-indigo-800">{{ paymentStatusLabel(currentPaymentInvoice.payment_status) }}</span></div>
      <div v-if="currentPaymentInvoice.is_test_invoice" class="alert-warning">TEST MODE - This invoice is for testing only</div>
      <div class="grid gap-5 md:grid-cols-[180px_minmax(0,1fr)] md:items-start"><img v-if="currentPaymentInvoice.qr_code_data_url" :src="currentPaymentInvoice.qr_code_data_url" alt="Payment QR code" class="mx-auto w-full max-w-[180px] rounded-xl border bg-white p-2 md:mx-0" /><div class="space-y-3 text-sm text-slate-700"><p v-if="currentPaymentInvoice.payment_url"><a :href="currentPaymentInvoice.payment_url" target="_blank" rel="noopener" class="btn-dark inline-flex">Open {{ currentPaymentInvoice.payment_method === 'PERSONAL_TIKKIE' ? 'Tikkie' : 'payment link' }}</a></p><p><strong>Total amount due:</strong> €{{ monthlyInvoice.balance_amount ?? currentPaymentInvoice.amount_due }}</p><p><strong>Due date:</strong> {{ currentPaymentInvoice.due_date }}</p><p v-if="currentPaymentInvoice.payment_method !== 'PERSONAL_TIKKIE'" class="flex flex-wrap items-center gap-2"><strong>IBAN:</strong> <span class="break-all">{{ currentPaymentInvoice.iban }}</span> <button class="btn-muted" @click="copyText(currentPaymentInvoice.iban)">Copy IBAN</button></p><p><strong>Account holder:</strong> {{ currentPaymentInvoice.account_holder_name }}</p><p class="flex flex-wrap items-center gap-2"><strong>Payment reference:</strong> <span>{{ currentPaymentInvoice.payment_reference }}</span> <button class="btn-muted" @click="copyText(currentPaymentInvoice.payment_reference)">Copy reference</button></p></div></div>
    </div>

    <div class="space-y-3">
      <div>
        <h3 class="text-lg font-semibold text-slate-900">Booking details</h3>
        <p class="section-copy">Your share of each cost included in this month.</p>
      </div>
      <div class="overflow-x-auto rounded-xl border border-slate-200">
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
            <tr v-for="item in monthlyInvoice.booking_items" :key="`my-booking-${item.booking_id}`" class="align-top">
              <td class="whitespace-nowrap px-3 py-2 font-medium text-indigo-800">Booking</td>
              <td class="whitespace-nowrap px-3 py-2 text-slate-700">{{ item.date }}<span class="block text-xs text-slate-500">{{ item.start_time }}-{{ item.end_time }}</span></td>
              <td class="px-3 py-2 text-slate-700">{{ item.court || 'Court booking' }}</td>
              <td class="px-3 py-2 text-slate-700">{{ (item.family_members || item.participants || []).join(' & ') }}</td>
              <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">€{{ item.total_cost }}</td>
              <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">{{ item.total_people_played }} players</td>
              <td class="whitespace-nowrap px-3 py-2 text-right font-semibold text-slate-900">€{{ item.amount }}</td>
            </tr>
            <tr v-for="item in monthlyInvoice.misc_items" :key="`my-misc-${item.cost_id}`" class="align-top">
              <td class="whitespace-nowrap px-3 py-2 font-medium text-emerald-800">Misc</td>
              <td class="whitespace-nowrap px-3 py-2 text-slate-700">{{ item.purchase_date || 'No date' }}</td>
              <td class="px-3 py-2 text-slate-700">{{ item.title }}</td>
              <td class="px-3 py-2 text-slate-500">Family split</td>
              <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">€{{ item.amount_total || item.total_cost || 0 }}</td>
              <td class="whitespace-nowrap px-3 py-2 text-right text-slate-700">{{ item.split_count }} ways</td>
              <td class="whitespace-nowrap px-3 py-2 text-right font-semibold text-slate-900">€{{ item.amount }}</td>
            </tr>
            <tr v-if="!monthlyInvoice.booking_items?.length && !monthlyInvoice.misc_items?.length">
              <td colspan="7" class="px-3 py-4 text-center text-slate-500">No booking or misc costs for this month.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>


// This component renders dashboard-owned data and calls the existing handlers.
defineProps({
  copyText: Function,
  currentPaymentInvoice: Object,
  monthlyInvoice: Object,
  paymentStatusLabel: Function
})

</script>
