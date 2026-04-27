<script setup lang="ts">
/**
 * Story EDITOR-7 — modal that shows the documentation for a keyword.
 *
 * Source: `useKeywordSignatures().getKeywordInfo(name)`. For dynamic-
 * library introspection (e.g. Browser, Collections, …) the doc string
 * is the libdoc summary. For static `RF_KEYWORD_SIGNATURES` fallback
 * keywords the doc is empty and we render a "no documentation" hint.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/ui/BaseModal.vue'
import { useKeywordSignatures } from '@/composables/useKeywordSignatures'
import { parseArgSignature } from '@/utils/robotKeywordSignatures'

const props = defineProps<{
  modelValue: boolean
  keyword: string
}>()

defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const { t } = useI18n()
const { getKeywordInfo } = useKeywordSignatures()

const info = computed(() => getKeywordInfo(props.keyword))

const parsedArgs = computed(() => {
  if (!info.value) return []
  return info.value.args.map(parseArgSignature)
})

function formatArg(parsed: ReturnType<typeof parseArgSignature>): string {
  let out = parsed.name
  if (parsed.kind === 'varargs') out = '*' + out
  if (parsed.kind === 'kwargs') out = '**' + out
  if (parsed.type) out += `: ${parsed.type}`
  if (parsed.defaultValue !== null) out += ` = ${parsed.defaultValue}`
  return out
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="t('flowEditor.docModal.title')"
    size="md"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-if="info" class="kw-doc">
      <div class="kw-doc-header">
        <span class="kw-doc-name">{{ info.display }}</span>
        <span class="kw-doc-lib">{{ info.library }}</span>
      </div>

      <div v-if="parsedArgs.length > 0" class="kw-doc-args">
        <h4>{{ t('flowEditor.docModal.argsHeader') }}</h4>
        <ul>
          <li v-for="(p, i) in parsedArgs" :key="i" class="kw-doc-arg">
            <code>{{ formatArg(p) }}</code>
          </li>
        </ul>
      </div>

      <div class="kw-doc-body">
        <pre v-if="info.doc.trim().length > 0">{{ info.doc }}</pre>
        <p v-else class="kw-doc-empty">{{ t('flowEditor.docModal.noDoc') }}</p>
      </div>
    </div>
    <div v-else class="kw-doc">
      <p class="kw-doc-empty">{{ t('flowEditor.docModal.noDoc') }}</p>
    </div>
  </BaseModal>
</template>

<style scoped>
.kw-doc {
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family: var(--font-sans, sans-serif);
}
.kw-doc-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  padding-bottom: 8px;
}
.kw-doc-name {
  font-family: var(--font-mono, monospace);
  font-size: 16px;
  font-weight: 700;
  color: var(--color-navy, #1A2D50);
}
.kw-doc-lib {
  font-size: 11px;
  color: var(--color-text-muted, #5A6380);
  background: var(--color-bg, #F4F7FA);
  padding: 2px 8px;
  border-radius: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.kw-doc-args h4 {
  margin: 0 0 6px 0;
  font-size: 12px;
  text-transform: uppercase;
  color: var(--color-text-muted, #5A6380);
  letter-spacing: 0.04em;
}
.kw-doc-args ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kw-doc-arg code {
  font-size: 12px;
  background: var(--color-bg, #F4F7FA);
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-block;
}
.kw-doc-body pre {
  margin: 0;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--color-text, #1A2D50);
  background: var(--color-bg, #F4F7FA);
  padding: 10px 12px;
  border-radius: 6px;
  max-height: 320px;
  overflow-y: auto;
}
.kw-doc-empty {
  margin: 0;
  font-style: italic;
  color: var(--color-text-muted, #5A6380);
}
</style>
