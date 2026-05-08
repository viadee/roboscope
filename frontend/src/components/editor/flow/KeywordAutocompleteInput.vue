<script setup lang="ts">
/**
 * Story EDITOR-4 — keyword input with autocomplete for the visual flow
 * editor's detail panel. Self-contained: source is the reactive
 * `useKeywordSignatures()` map (BuiltIn + dynamic library introspection),
 * no backend round-trip needed since the map already covers everything
 * the user sees in the keyword palette.
 *
 * Keyboard:
 *   Arrow ↑/↓  — move highlight (clamped at ends)
 *   Enter      — commit highlighted suggestion (or typed value if none)
 *   Esc        — close dropdown without committing
 *   Tab        — close dropdown, do NOT commit (RF keyword names contain
 *                spaces, Tab-to-commit misfires too easily)
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useKeywordSignatures } from '@/composables/useKeywordSignatures'
import { useExplorerStore } from '@/stores/explorer.store'

const props = defineProps<{
  value: string
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:value', v: string): void
  (e: 'select', name: string): void
}>()

const { t } = useI18n()
const { argsByName } = useKeywordSignatures()
const explorer = useExplorerStore()

// Local mirror so we can render dropdown without forcing the parent to
// re-render on every keystroke.
const localValue = ref(props.value)
watch(() => props.value, (v) => { localValue.value = v })

const inputRef = ref<HTMLInputElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const open = ref(false)
const highlightedIndex = ref(-1)

interface Suggestion {
  name: string
  library: string
}

// `argsByName` is keyed by lowercase, which loses the library author's
// original casing (e.g. `Get Element By XPath` would render as
// `Get Element By Xpath`). Resolve the original display name from
// `explorer.keywords` whenever possible, fall back to title-case for
// the static `RF_KEYWORD_SIGNATURES` map.
interface KwMeta { display: string; library: string }
const metaByLowerName = computed<Map<string, KwMeta>>(() => {
  const m = new Map<string, KwMeta>()
  for (const kw of explorer.keywords) {
    if (kw.name) {
      m.set(kw.name.toLowerCase(), { display: kw.name, library: kw.library || '' })
    }
  }
  return m
})

function titleCase(lower: string): string {
  return lower.replace(/\b\w/g, (c) => c.toUpperCase())
}

const suggestions = computed<Suggestion[]>(() => {
  const q = localValue.value.trim().toLowerCase()
  // Match RobotEditor.vue threshold (>= 2) for UX parity.
  if (q.length < 2) return []

  const all = Array.from(argsByName.value.keys())
  const prefix: Suggestion[] = []
  const substring: Suggestion[] = []

  for (const lower of all) {
    if (lower === q) continue // exact match — no suggestion needed
    const meta = metaByLowerName.value.get(lower)
    const entry: Suggestion = {
      name: meta?.display ?? titleCase(lower),
      library: meta?.library ?? 'BuiltIn',
    }
    if (lower.startsWith(q)) prefix.push(entry)
    else if (lower.includes(q)) substring.push(entry)
  }

  prefix.sort((a, b) => a.name.length - b.name.length || a.name.localeCompare(b.name))
  substring.sort((a, b) => a.name.localeCompare(b.name))

  return [...prefix.slice(0, 15), ...substring.slice(0, 15)]
})

function onInput(e: Event) {
  const v = (e.target as HTMLInputElement).value
  localValue.value = v
  emit('update:value', v)
  open.value = true
  highlightedIndex.value = -1
}

function commit(name: string) {
  localValue.value = name
  emit('update:value', name)
  emit('select', name)
  open.value = false
  highlightedIndex.value = -1
}

function onKeydown(e: KeyboardEvent) {
  const items = suggestions.value
  if (e.key === 'Enter') {
    e.preventDefault()
    if (open.value && highlightedIndex.value >= 0 && highlightedIndex.value < items.length) {
      commit(items[highlightedIndex.value].name)
    } else {
      // Bare commit of typed value — emit select so the parent persists.
      emit('select', localValue.value)
      open.value = false
    }
    return
  }
  if (e.key === 'Escape') {
    open.value = false
    highlightedIndex.value = -1
    return
  }
  if (e.key === 'Tab') {
    open.value = false
    highlightedIndex.value = -1
    return
  }
  if (!open.value || items.length === 0) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlightedIndex.value = Math.min(highlightedIndex.value + 1, items.length - 1)
    scrollHighlightedIntoView()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
    scrollHighlightedIntoView()
  }
}

function scrollHighlightedIntoView() {
  nextTick(() => {
    const el = dropdownRef.value?.children?.[highlightedIndex.value] as HTMLElement | undefined
    // jsdom (used in Vitest) doesn't implement scrollIntoView; gate the call
    // so unit tests don't blow up.
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' })
    }
  })
}

function onFocus() {
  if (suggestions.value.length > 0) open.value = true
}

function onDocClick(e: MouseEvent) {
  const t = e.target
  if (!(t instanceof Element)) return
  if (t.closest('.kw-autocomplete')) return
  open.value = false
}

// Bind the document listener only while the dropdown is open — matches
// the SelectorPicker pattern and avoids a permanent global listener for
// every detail panel that has ever been opened.
let docListenerBound = false
function bindOutsideClick() {
  if (docListenerBound) return
  document.addEventListener('click', onDocClick)
  docListenerBound = true
}
function unbindOutsideClick() {
  if (!docListenerBound) return
  document.removeEventListener('click', onDocClick)
  docListenerBound = false
}
watch(open, (isOpen) => {
  if (isOpen) bindOutsideClick()
  else unbindOutsideClick()
})
onBeforeUnmount(unbindOutsideClick)
</script>

<template>
  <div class="kw-autocomplete">
    <input
      ref="inputRef"
      :value="localValue"
      :placeholder="placeholder ?? t('flowEditor.keyword')"
      class="flow-input"
      autocomplete="off"
      data-testid="kw-autocomplete-input"
      @input="onInput"
      @focus="onFocus"
      @keydown="onKeydown"
    />
    <ul
      v-if="open && suggestions.length > 0"
      ref="dropdownRef"
      class="kw-autocomplete-dropdown"
      role="listbox"
      data-testid="kw-autocomplete-dropdown"
    >
      <li
        v-for="(s, i) in suggestions"
        :key="`${s.library}-${s.name}-${i}`"
        :class="['kw-autocomplete-item', { 'is-highlighted': i === highlightedIndex }]"
        role="option"
        :aria-selected="i === highlightedIndex"
        @mouseenter="highlightedIndex = i"
        @mousedown="commit(s.name)"
      >
        <span class="kw-autocomplete-name">{{ s.name }}</span>
        <span class="kw-autocomplete-lib">{{ s.library }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.kw-autocomplete {
  position: relative;
  width: 100%;
}
.flow-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 5px;
  font-size: 12px;
  font-family: monospace;
  outline: none;
  box-sizing: border-box;
}
.flow-input:focus {
  border-color: var(--color-primary, #3B7DD8);
}
.kw-autocomplete-dropdown {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  right: 0;
  margin: 0;
  padding: 2px 0;
  list-style: none;
  background: #fff;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 5px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.10);
  max-height: 220px;
  overflow-y: auto;
  z-index: 1000;
}
.kw-autocomplete-item {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 12px;
  font-family: monospace;
}
.kw-autocomplete-item.is-highlighted,
.kw-autocomplete-item:hover {
  background: var(--color-bg, #F4F7FA);
}
.kw-autocomplete-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kw-autocomplete-lib {
  font-size: 10px;
  color: var(--color-text-muted, #5A6380);
  font-family: var(--font-sans, sans-serif);
  flex-shrink: 0;
}
</style>
