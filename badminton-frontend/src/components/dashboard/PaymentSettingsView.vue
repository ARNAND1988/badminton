<template>
<section class="space-y-6">
  <div>
    <h2 class="section-title">Payment settings</h2>
    <p class="section-copy mt-1">Add the two ways members can pay their monthly invoice.</p>
  </div>
  <div v-if="!isSuperAdmin" class="alert-warning">Only Super Admin can manage payment settings.</div>
  <form v-else class="space-y-5" @submit.prevent="savePaymentSettings">
    <section class="panel-card space-y-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-900">Business bank account</h3>
        <p class="section-copy mt-1">These details appear when Business bank account is selected for a month.</p>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <label><span class="form-label">Account holder</span><input v-model="paymentSettings.account_holder_name" class="form-input" placeholder="Club or business name" /></label>
        <label><span class="form-label">Bank name</span><input v-model="paymentSettings.bank_name" class="form-input" placeholder="Bank name" /></label>
        <label><span class="form-label">IBAN</span><input v-model="paymentSettings.iban" class="form-input uppercase" placeholder="NL00 BANK 0000 0000 00" /></label>
        <label><span class="form-label">BIC <span class="font-normal text-slate-400">(optional)</span></span><input v-model="paymentSettings.bic" class="form-input uppercase" placeholder="BIC" /></label>
      </div>
    </section>

    <section class="panel-card space-y-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-900">Monthly Tikkie link</h3>
        <p class="section-copy mt-1">Choose a month and save the Tikkie link that belongs only to that month's invoices and reminders.</p>
      </div>
      <div class="grid gap-4 sm:grid-cols-3">
        <label><span class="form-label">Invoice month</span><select v-model="paymentSettings.tikkie_month" class="form-input" @change="applyMonthlyTikkieLink"><option v-for="month in paymentMonthOptions" :key="month" :value="month">{{ monthName(month) }}</option></select></label>
        <label><span class="form-label">Account holder</span><input v-model="paymentSettings.monthly_tikkie_account_holder_name" class="form-input" placeholder="Personal account holder name" /></label>
        <label><span class="form-label">Tikkie link</span><input v-model="paymentSettings.monthly_tikkie_payment_url" type="url" class="form-input" placeholder="https://tikkie.me/pay/..." /></label>
      </div>
      <p class="text-xs text-slate-500">Changing the month loads its saved link. Saving updates only the selected month.</p>
    </section>

    <section class="panel-card space-y-4">
      <div>
        <h3 class="text-lg font-semibold text-slate-900">Invoice defaults</h3>
        <p class="section-copy mt-1">Used for every newly generated monthly invoice.</p>
      </div>
      <div class="grid gap-4 sm:grid-cols-2">
        <label><span class="form-label">Payment description</span><input v-model="paymentSettings.description_prefix" class="form-input" placeholder="Nieuwegein Badminton Invoice" /></label>
        <label><span class="form-label">Payment due after</span><div class="flex items-center gap-2"><input v-model.number="paymentSettings.default_due_days" type="number" min="1" max="60" class="form-input" /><span class="text-sm text-slate-600">days</span></div></label>
      </div>
    </section>

    <div class="flex items-center gap-3">
      <button type="submit" class="btn-dark" :disabled="paymentSettingsSaving">{{ paymentSettingsSaving ? 'Saving...' : 'Save payment settings' }}</button>
      <span class="text-sm text-slate-500">Choose the payment method later on the monthly invoice page.</span>
    </div>
  </form>
</section>
</template>

<script setup>


// This component renders dashboard-owned data and calls the existing handlers.
defineProps({
  applyMonthlyTikkieLink: Function,
  isSuperAdmin: Boolean,
  monthName: Function,
  paymentMonthOptions: Array,
  paymentSettings: Object,
  paymentSettingsSaving: Boolean,
  savePaymentSettings: Function
})

</script>
