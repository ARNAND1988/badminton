<template>
<section class="space-y-6">
  <div class="rounded-3xl border border-teal-100 bg-gradient-to-br from-emerald-50 via-white to-sky-50 p-4 shadow-sm sm:p-6">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p class="text-xs font-bold uppercase tracking-[0.24em] text-teal-700">Meta Cloud API</p>
        <div class="arena-view-heading"><ArenaIcon name="bell" /><h2 class="mt-1 text-2xl font-black text-slate-950">WhatsApp notification admin</h2></div>
        <p class="mt-2 max-w-2xl text-sm text-slate-600">Prepare English message content, control each event, and send a safe direct test before notifying families.</p>
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
            <input aria-label="Notification title" v-model="setting.title" class="mt-1 w-full rounded-xl border border-transparent bg-slate-50 px-3 py-2 text-lg font-bold text-slate-900 focus:border-emerald-400 focus:outline-none" />
            <p class="mt-1 text-sm text-slate-600">{{ setting.description }}</p>
          </div>
          <label class="flex items-center justify-between gap-3 rounded-full border px-3 py-2 text-sm font-semibold" :class="setting.is_enabled ? 'border-emerald-200 bg-teal-50 text-emerald-800' : 'border-slate-200 bg-slate-50 text-slate-500'">
            Enabled
            <input v-model="setting.is_enabled" type="checkbox" class="h-5 w-5 accent-emerald-600" />
          </label>
        </div>
        <div class="mt-4 grid gap-3 sm:grid-cols-2">
          <label class="block">
            <span class="form-label">Fallback recipient number</span>
            <input v-model="setting.group_id" class="form-input" placeholder="+31612345678 (optional)" />
          </label>
          <label class="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-700">
            <input v-model="setting.send_to_group" type="checkbox" class="h-5 w-5 accent-emerald-600" />
            Enable automatic delivery
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
          <button class="btn-secondary" @click="openSettingNotificationPreview(setting)">Notify group</button>
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
            <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="log.status === 'sent' ? 'bg-teal-100 text-teal-700' : 'bg-amber-100 text-amber-700'">{{ log.status }}</span>
          </div>
          <p class="mt-2 line-clamp-4 whitespace-pre-line text-xs text-slate-600">{{ log.message }}</p>
        </div>
        <p v-if="!whatsappLogs.length" class="text-sm text-slate-500">No sends yet.</p>
      </div>
    </aside>
  </div>
</section>
</template>

<script setup>
import ArenaIcon from '../ArenaIcon.vue'

// This component renders dashboard-owned data and calls the existing handlers.
defineProps({
  loadWhatsAppNotifications: Function,
  loading: Boolean,
  openSettingNotificationPreview: Function,
  saveWhatsAppNotification: Function,
  testWhatsAppNotification: Function,
  whatsappLogs: Array,
  whatsappSettings: Array
})

</script>
