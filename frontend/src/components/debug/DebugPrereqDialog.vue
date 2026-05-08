<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/ui/BaseModal.vue'

const props = defineProps<{
  open: boolean
  packageName: string
  installing: boolean
  installError: string | null
}>()

const emit = defineEmits<{
  install: []
  cancel: []
}>()

const { t } = useI18n()

function onInstall(): void {
  emit('install')
}

function onCancel(): void {
  emit('cancel')
}
</script>

<template>
  <BaseModal :model-value="props.open" :title="t('debug.prereq.title')" size="md">
    <p class="prereq-body">
      {{ t('debug.prereq.body', { package: props.packageName }) }}
    </p>
    <p v-if="props.installError" class="prereq-error" role="alert">
      {{ props.installError }}
    </p>
    <p v-else-if="props.installing" class="prereq-status">
      {{ t('debug.prereq.installing', { package: props.packageName }) }}
    </p>

    <template #footer>
      <button
        type="button"
        class="btn-secondary"
        :disabled="props.installing"
        @click="onCancel"
      >
        {{ t('debug.prereq.cancel') }}
      </button>
      <button
        type="button"
        class="btn-primary"
        :disabled="props.installing"
        @click="onInstall"
      >
        {{ props.installing
          ? t('debug.prereq.installing', { package: props.packageName })
          : t('debug.prereq.install') }}
      </button>
    </template>
  </BaseModal>
</template>

<style scoped>
.prereq-body {
  margin: 0 0 0.75rem 0;
  color: var(--color-text);
  line-height: 1.5;
}
.prereq-error {
  margin: 0.5rem 0 0 0;
  padding: 0.5rem 0.75rem;
  background: rgba(220, 53, 69, 0.08);
  border-left: 3px solid var(--color-danger, #dc3545);
  color: var(--color-danger, #dc3545);
  font-size: 0.9em;
  white-space: pre-wrap;
}
.prereq-status {
  margin: 0.5rem 0 0 0;
  color: var(--color-text-muted);
  font-size: 0.9em;
  font-style: italic;
}
</style>
