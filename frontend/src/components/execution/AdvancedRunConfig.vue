<script setup lang="ts">
/**
 * EXEC.3 — advanced execution config for the run dialog.
 *
 * Pure presentational grouping: a variables key/value editor and a freeform
 * `robot` args field. Parsing + the (server-authoritative) three-zone
 * validation happen on submit / in the backend; this component only edits text.
 * Rendered ONLY when the `executionAdvancedArgs` feature flag is on (the caller
 * gates with `v-if` — never render-then-403).
 */
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{ argsText: string; variablesText: string }>()
defineEmits<{
  'update:argsText': [value: string]
  'update:variablesText': [value: string]
}>()
</script>

<template>
  <div class="advanced-run-config" data-testid="advanced-section">
    <h4 class="advanced-title">{{ t('execution.advanced.title') }}</h4>

    <div class="form-group">
      <label class="form-label">{{ t('execution.advanced.variables') }}</label>
      <textarea
        :value="variablesText"
        class="form-input"
        rows="3"
        :placeholder="t('execution.advanced.variablesPlaceholder')"
        data-testid="advanced-vars-input"
        @input="$emit('update:variablesText', ($event.target as HTMLTextAreaElement).value)"
      ></textarea>
      <span class="text-muted text-sm">{{ t('execution.advanced.variablesHint') }}</span>
    </div>

    <div class="form-group">
      <label class="form-label">{{ t('execution.advanced.args') }}</label>
      <textarea
        :value="argsText"
        class="form-input"
        rows="2"
        :placeholder="t('execution.advanced.argsPlaceholder')"
        data-testid="advanced-args-input"
        @input="$emit('update:argsText', ($event.target as HTMLTextAreaElement).value)"
      ></textarea>
      <span class="text-muted text-sm">{{ t('execution.advanced.argsHint') }}</span>
    </div>
  </div>
</template>

<style scoped>
.advanced-run-config {
  border-top: 1px solid var(--color-border, #e2e8f0);
  margin-top: 0.75rem;
  padding-top: 0.75rem;
}
.advanced-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-navy, #1a2d50);
  margin: 0 0 0.5rem;
}
</style>
