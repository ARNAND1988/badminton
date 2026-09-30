<template>
<div v-if="notificationPreview.open" class="arena-dialog fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4">
  <div class="w-full max-w-2xl rounded-2xl bg-white p-5 shadow-2xl">
    <div class="flex items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-bold text-slate-950">{{ notificationPreview.title }}</h3>
        <p class="mt-1 text-sm text-slate-600">Review and edit the WhatsApp message before sending.</p>
        <p v-if="notificationPreview.recipient" class="mt-1 text-xs text-slate-500">Group recipient: {{ notificationPreview.recipient }}</p>
      </div>
      <button class="btn-muted" @click="closeNotificationPreview">Close</button>
    </div>

    <label class="mt-4 block">
      <span class="form-label">Message content</span>
      <textarea v-model="notificationPreview.message" rows="10" class="form-input font-mono text-sm"></textarea>
    </label>

    <div class="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <label class="block">
        <span class="form-label">Send test to saved WhatsApp number</span>
        <select v-model="notificationPreview.testRecipient" class="form-input">
          <option value="">Choose saved test number</option>
          <option v-for="recipient in notificationPreview.testRecipients" :key="recipient.normalized || recipient.value" :value="recipient.value">
            {{ recipient.label }}
          </option>
        </select>
      </label>
      <p class="mt-1 text-xs text-slate-500">Saved numbers come from the WhatsApp Management page test recipient fields.</p>
      <button class="btn-secondary mt-3" :disabled="notificationPreview.sending || !notificationPreview.testRecipient" @click="sendNotificationPreview(true)">
        {{ notificationPreview.sending ? 'Sending...' : 'Send test notification' }}
      </button>
    </div>

    <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-end">
      <button class="btn-muted" @click="closeNotificationPreview">Cancel</button>
      <button class="btn-dark" :disabled="notificationPreview.sending || !notificationPreview.message.trim()" @click="sendNotificationPreview(false)">
        {{ notificationPreview.sending ? 'Sending...' : 'Send to group' }}
      </button>
    </div>
  </div>
</div>
</template>

<script setup>


// This component renders dashboard-owned data and calls the existing handlers.
defineProps({
  closeNotificationPreview: Function,
  notificationPreview: Object,
  sendNotificationPreview: Function
})

</script>
