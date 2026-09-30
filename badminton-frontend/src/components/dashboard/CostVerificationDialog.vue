<template>
<div v-if="verificationDetails" class="arena-dialog fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4" @click.self="closeVerificationDetails">
  <div class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl">
    <div class="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
      <div>
        <h3 class="text-lg font-bold text-slate-900">Cost verification</h3>
        <p class="text-sm text-slate-600">{{ verificationDetails.title }}</p>
      </div>
      <button class="btn-muted" @click="closeVerificationDetails">Close</button>
    </div>
    <div class="mt-4 grid gap-3 sm:grid-cols-4">
      <div class="rounded border border-teal-100 bg-teal-50 p-3">
        <div class="text-xs font-semibold uppercase text-teal-700">{{ verificationDetails.itemLabel }}</div>
        <div class="mt-1 text-xl font-bold text-indigo-900">{{ verificationDetails.items.length }}</div>
      </div>
      <div class="rounded border border-teal-100 bg-teal-50 p-3">
        <div class="text-xs font-semibold uppercase text-teal-700">{{ verificationDetails.peopleLabel }}</div>
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
</template>

<script setup>


// This component renders dashboard-owned data and calls the existing handlers.
defineProps({
  closeVerificationDetails: Function,
  verificationDetails: Object
})

</script>
