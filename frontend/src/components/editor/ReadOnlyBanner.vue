<script setup lang="ts">
/**
 * Story 4-6: sticky read-only banner for editor-like views.
 *
 * Renders only when the caller has no edit permission. Different copy
 * per role so users understand why (viewer vs runner), plus a mailto
 * fallback when `adminContactEmail` is configured.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  role: 'viewer' | 'runner' | 'editor' | 'admin'
  adminContactEmail?: string
}>()

const { t } = useI18n()

const visible = computed(() => props.role === 'viewer' || props.role === 'runner')

const message = computed(() => {
  if (props.role === 'viewer') {
    return t('editor.readOnly.viewer')
  }
  if (props.role === 'runner') {
    return t('editor.readOnly.runner')
  }
  return ''
})

const mailto = computed(() =>
  props.adminContactEmail
    ? `mailto:${props.adminContactEmail}?subject=${encodeURIComponent('Access request')}`
    : null,
)
</script>

<template>
  <div
    v-if="visible"
    :class="['read-only-banner', `read-only-banner--${role}`]"
    role="status"
    aria-live="polite"
  >
    <span class="read-only-banner__msg">{{ message }}</span>
    <a v-if="mailto" :href="mailto" class="read-only-banner__cta">
      {{ t('editor.readOnly.contactAdmin') }}
    </a>
  </div>
</template>

<style scoped>
.read-only-banner {
  position: sticky;
  top: 0;
  z-index: 10;
  padding: 0.5rem 0.75rem;
  background: #fff7e6;
  border-bottom: 1px solid #f0c36d;
  color: #7a4e00;
  display: flex;
  gap: 0.75rem;
  align-items: center;
  font-size: 0.9rem;
}

.read-only-banner--runner {
  background: #eef4ff;
  border-bottom-color: #7aa0e0;
  color: #1a3c7a;
}

.read-only-banner__cta {
  color: inherit;
  text-decoration: underline;
}
</style>
