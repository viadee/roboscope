<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAiStore } from '@/stores/ai.store'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps<{
  content: string
  filePath: string
}>()

const emit = defineEmits<{
  save: [content: string]
}>()

const { t } = useI18n()
const aiStore = useAiStore()

const validation = ref<{ valid: boolean; errors: string[]; test_count: number } | null>(null)
const validating = ref(false)

const isRoboscope = computed(() => props.filePath.endsWith('.roboscope'))

watch(() => props.content, () => {
  validation.value = null
})

async function handleValidate() {
  validating.value = true
  try {
    validation.value = await aiStore.validateSpec(props.content)
  } catch {
    validation.value = { valid: false, errors: ['Validation request failed'], test_count: 0 }
  } finally {
    validating.value = false
  }
}
</script>

<template>
  <div v-if="isRoboscope" class="spec-toolbar">
    <div class="spec-info">
      <span class="badge badge-spec">.roboscope</span>
      <span v-if="validation?.valid" class="badge badge-success">
        {{ t('ai.valid') }} ({{ validation.test_count }} {{ t('ai.tests') }})
      </span>
      <span v-else-if="validation && !validation.valid" class="badge badge-danger">
        {{ t('ai.invalid') }}
      </span>
    </div>
    <div class="spec-actions">
      <BaseButton size="sm" variant="secondary" :loading="validating" @click="handleValidate">
        {{ t('ai.validate') }}
      </BaseButton>
    </div>
  </div>
  <div v-if="validation && !validation.valid" class="validation-errors">
    <ul>
      <li v-for="(err, i) in validation.errors" :key="i">{{ err }}</li>
    </ul>
  </div>
</template>

<style scoped>
.spec-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}

.spec-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spec-actions {
  display: flex;
  gap: 6px;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.badge-spec {
  background: #f0e6ff;
  color: #7c3aed;
}

.badge-success {
  background: #e8f5e9;
  color: var(--color-success);
}

.badge-danger {
  background: #fce4e4;
  color: var(--color-danger);
}

.validation-errors {
  padding: 8px 12px;
  background: #fce4e4;
  border-bottom: 1px solid var(--color-border);
}

.validation-errors ul {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--color-danger);
}
</style>
