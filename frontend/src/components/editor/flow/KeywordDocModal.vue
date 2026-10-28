<script setup lang="ts">
/**
 * Story EDITOR-7 — modal that shows the documentation for a keyword.
 *
 * Source: `useKeywordSignatures().getKeywordInfo(name)` for the
 * synchronous lookup. When the cached entry has no doc string (most
 * BuiltIn keywords land here because the wildcard preload skips them),
 * we lazy-load via `fetchKeywordInfo()` so the user gets the libdoc
 * summary without re-opening the modal.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import DOMPurify from 'dompurify'
import BaseModal from '@/components/ui/BaseModal.vue'
import { useKeywordSignatures } from '@/composables/useKeywordSignatures'
import { parseArgSignature } from '@/utils/robotKeywordSignatures'

const props = defineProps<{
  modelValue: boolean
  keyword: string
  repoId?: number
}>()

defineEmits<{
  (e: 'update:modelValue', v: boolean): void
}>()

const { t } = useI18n()
const { getKeywordInfo, fetchKeywordInfo } = useKeywordSignatures()

const fetchedInfo = ref<ReturnType<typeof getKeywordInfo>>(null)
const fetching = ref(false)

const info = computed(() => fetchedInfo.value ?? getKeywordInfo(props.keyword))

async function refreshIfNeeded() {
  fetchedInfo.value = null
  if (!props.modelValue || !props.keyword) return
  const cached = getKeywordInfo(props.keyword)
  // Skip the network call when we already have a doc string.
  if (cached?.doc && cached.doc.trim().length > 0) return
  fetching.value = true
  try {
    const fresh = await fetchKeywordInfo(props.keyword, props.repoId)
    if (fresh) fetchedInfo.value = fresh
  } finally {
    fetching.value = false
  }
}

watch(() => [props.modelValue, props.keyword], refreshIfNeeded, { immediate: true })

const parsedArgs = computed(() => {
  if (!info.value) return []
  return info.value.args.map(parseArgSignature)
})

// libdoc emits HTML for ROBOT/REST/TEXT-format library keywords (see
// `_resolve_library_keywords` calling `LibraryDoc.convert_docs_to_html()`).
// Project-resource keywords stay plain text. We sanitize defensively
// even though library content is admin-installed — DOMPurify strips
// <script>, on*= handlers, javascript: URIs while keeping libdoc's
// <p>/<ul>/<code>/<a>/<table> output intact.
const isHtml = computed(() => info.value?.docFormat === 'html')
const sanitizedHtml = computed(() => {
  if (!info.value || !isHtml.value) return ''
  return DOMPurify.sanitize(info.value.doc, {
    ALLOWED_TAGS: [
      'p', 'br', 'hr',
      'a', 'code', 'pre', 'span',
      'strong', 'b', 'em', 'i', 'u',
      'ul', 'ol', 'li',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'blockquote',
    ],
    ALLOWED_ATTR: ['href', 'title', 'class'],
    ALLOW_DATA_ATTR: false,
  })
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
    size="lg"
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
        <!-- eslint-disable-next-line vue/no-v-html — sanitized via DOMPurify above -->
        <div v-if="isHtml && info.doc.trim().length > 0" class="kw-doc-html" v-html="sanitizedHtml" />
        <pre v-else-if="info.doc.trim().length > 0">{{ info.doc }}</pre>
        <p v-else-if="fetching" class="kw-doc-empty">{{ t('flowEditor.docModal.loading') }}</p>
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
}
.kw-doc-html {
  font-size: 13px;
  line-height: 1.55;
  color: var(--color-text, #1A2D50);
}
.kw-doc-html :deep(p) { margin: 0 0 10px; }
.kw-doc-html :deep(p:last-child) { margin-bottom: 0; }
.kw-doc-html :deep(ul),
.kw-doc-html :deep(ol) { margin: 0 0 10px; padding-left: 22px; }
.kw-doc-html :deep(li) { margin: 2px 0; }
.kw-doc-html :deep(h1),
.kw-doc-html :deep(h2),
.kw-doc-html :deep(h3),
.kw-doc-html :deep(h4) {
  margin: 14px 0 6px;
  font-weight: 700;
  font-size: 14px;
  color: var(--color-navy, #1A2D50);
}
.kw-doc-html :deep(code) {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  background: var(--color-bg, #F4F7FA);
  padding: 1px 5px;
  border-radius: 3px;
}
.kw-doc-html :deep(pre) {
  margin: 0 0 10px;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--color-bg, #F4F7FA);
  padding: 10px 12px;
  border-radius: 6px;
}
.kw-doc-html :deep(a) {
  color: var(--color-primary, #2D63B0);
  text-decoration: underline;
}
.kw-doc-html :deep(table) {
  border-collapse: collapse;
  margin: 0 0 10px;
  font-size: 12px;
}
.kw-doc-html :deep(th),
.kw-doc-html :deep(td) {
  border: 1px solid var(--color-border, #e2e8f0);
  padding: 4px 8px;
  text-align: left;
}
.kw-doc-html :deep(th) {
  background: var(--color-bg, #F4F7FA);
}
.kw-doc-html :deep(blockquote) {
  margin: 0 0 10px;
  padding: 4px 12px;
  border-left: 3px solid var(--color-border, #e2e8f0);
  color: var(--color-text-muted, #5A6380);
}
.kw-doc-empty {
  margin: 0;
  font-style: italic;
  color: var(--color-text-muted, #5A6380);
}
</style>
