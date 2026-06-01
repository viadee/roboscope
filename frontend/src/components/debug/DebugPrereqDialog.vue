<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

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
  <!-- data-testid="debug-prereq-dialog" is on a sentinel span that is
       Teleported alongside the modal so E2E tests can assert presence /
       absence of the dialog without relying on BaseModal internals. -->
  <Teleport v-if="props.open" to="body">
    <span data-testid="debug-prereq-dialog" style="display:none" aria-hidden="true" />
  </Teleport>
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
      <BaseButton
        variant="ghost"
        :disabled="props.installing"
        data-testid="debug-prereq-cancel-btn"
        @click="onCancel"
      >
        {{ t('debug.prereq.cancel') }}
      </BaseButton>
      <BaseButton
        variant="primary"
        :loading="props.installing"
        :disabled="props.installing"
        data-testid="debug-prereq-install-btn"
        @click="onInstall"
      >
        {{ props.installing
          ? t('debug.prereq.installing', { package: props.packageName })
          : t('debug.prereq.install') }}
      </BaseButton>
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
