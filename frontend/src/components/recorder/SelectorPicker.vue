<script setup lang="ts">
/**
 * Story S.4 — inline selector-picker for recorded commands.
 *
 * Renders the active candidate inline with a color-coded quality dot.
 * Clicking opens a menu with every other candidate sorted by quality.
 * Emits `update:activeIndex` when the user swaps.
 *
 * Story EDITOR-CUSTOM-SEL — the picker also lets the user *edit* an
 * existing candidate (✏ button per row) or *add* a brand-new
 * candidate at the bottom (+ Eigener Selektor). Both go through
 * `update:candidate` / `add:candidate` emits; the parent FlowEditor
 * mutates the sidecar in place and persists via the existing
 * `update:sidecar` flow. User-touched candidates are demoted to
 * `quality_score=50` and `verified_unique=false` — they're
 * trusted-by-the-user but never auto-verified, and shouldn't
 * outrank a real visibility-checked candidate.
 *
 * Used inline in the Visual-Flow editor (step nodes) and as a gutter
 * annotation in the Text editor.
 */
import { computed, ref, onBeforeUnmount, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RecordedCommand, SelectorCandidate, SelectorStrategy } from '@/types/recorder.types'
import { qualityBand } from '@/utils/selectorQuality'

const props = defineProps<{
  command: RecordedCommand
  /** Compact mode hides the strategy label to fit into gutter annotations. */
  compact?: boolean
}>()

const emit = defineEmits<{
  'update:activeIndex': [index: number]
  /** User edited an existing candidate's value / strategy. */
  'update:candidate': [{ index: number; value: string; strategy: SelectorStrategy }]
  /** User added a brand-new candidate. */
  'add:candidate': [{ value: string; strategy: SelectorStrategy }]
}>()

const { t } = useI18n()

const menuOpen = ref(false)

/** Strategies the user can pick when editing / adding. The legacy
 *  `pw_locator` is deliberately excluded — see LEGACY_HIDDEN_STRATEGIES
 *  below. The desktop strategies (uia_*, automation_id) ARE allowed:
 *  desktop recordings produce them, and a user might want to tweak. */
const EDITABLE_STRATEGIES: readonly SelectorStrategy[] = [
  'css', 'xpath', 'text', 'aria', 'testid',
  'automation_id', 'uia_name', 'uia_class_name',
]

const active = computed<SelectorCandidate | null>(() => {
  if (props.command.selector_candidates.length === 0) return null
  return (
    props.command.selector_candidates[props.command.active_candidate_index] ?? null
  )
})

/**
 * Strategies that the synthesizer no longer produces but legacy
 * sidecars (recorded before commit 0c62c7a) may still contain.
 * `pw_locator` emitted Playwright JS API syntax (`getByRole(...)`,
 * `getByText(...)`) which Browser library cannot parse — those
 * candidates always failed verify in production, so the active
 * candidate they're attached to is never one of them. But the
 * picker dropdown listed them anyway, and a user clicking to
 * "swap" to a `pw_locator` row would commit a broken selector to
 * the .robot. Hide them from the menu so the swap path can't pick
 * a known-broken alternative. Active display is intentionally NOT
 * filtered — if a legacy file actually has it as the active row,
 * we keep showing it so the user can see what's there and pick a
 * working sibling instead.
 */
const LEGACY_HIDDEN_STRATEGIES: ReadonlySet<string> = new Set(['pw_locator'])

interface VisibleCandidate {
  candidate: SelectorCandidate
  originalIndex: number
}

const visibleCandidates = computed<VisibleCandidate[]>(() =>
  props.command.selector_candidates
    .map((c, i) => ({ candidate: c, originalIndex: i }))
    .filter(({ candidate }) => !LEGACY_HIDDEN_STRATEGIES.has(candidate.strategy)),
)

const hasChoices = computed(() => visibleCandidates.value.length > 1)
/** The picker still wants to be openable even with a single
 *  candidate — the user might want to edit it or add a custom
 *  alternative. */
const hasMenu = computed(() => visibleCandidates.value.length >= 1)

function pick(index: number) {
  emit('update:activeIndex', index)
  menuOpen.value = false
}

function strategyLabelKey(strategy: SelectorStrategy): string {
  return `recorder.selector.strategy.${strategy}`
}

function onDocClick(event: MouseEvent) {
  const target = event.target
  if (target && target instanceof Element) {
    if (target.closest('.selector-picker')) return
  }
  menuOpen.value = false
  closeAllInlineEditors()
}
function bindOutsideClick() {
  document.addEventListener('click', onDocClick)
}
function unbindOutsideClick() {
  document.removeEventListener('click', onDocClick)
}
function toggleMenu() {
  menuOpen.value = !menuOpen.value
  if (menuOpen.value) bindOutsideClick()
  else unbindOutsideClick()
}
onBeforeUnmount(unbindOutsideClick)

// ─── Edit / Add inline editors ───────────────────────────────────

/** When non-null, the row at this `originalIndex` is in edit mode.
 *  Single editor active at a time (avoids two pending unsaved
 *  changes diverging). */
const editingIndex = ref<number | null>(null)
const editValue = ref('')
const editStrategy = ref<SelectorStrategy>('css')
const editInputRef = ref<HTMLInputElement | null>(null)

/** When true, the "+ add custom" inline form is open. */
const addOpen = ref(false)
const addValue = ref('')
const addStrategy = ref<SelectorStrategy>('css')
const addInputRef = ref<HTMLInputElement | null>(null)

function closeAllInlineEditors() {
  editingIndex.value = null
  addOpen.value = false
}

function startEdit(originalIndex: number) {
  const c = props.command.selector_candidates[originalIndex]
  if (!c) return
  // Switching from add → edit: drop the unsaved add form.
  addOpen.value = false
  editingIndex.value = originalIndex
  editValue.value = c.value
  editStrategy.value = c.strategy
  nextTick(() => editInputRef.value?.focus())
}

function commitEdit() {
  if (editingIndex.value === null) return
  const trimmed = editValue.value.trim()
  if (!trimmed) {
    // Empty value = cancel; the parent keeps the previous candidate.
    editingIndex.value = null
    return
  }
  emit('update:candidate', {
    index: editingIndex.value,
    value: trimmed,
    strategy: editStrategy.value,
  })
  editingIndex.value = null
}

function cancelEdit() {
  editingIndex.value = null
}

function startAdd() {
  editingIndex.value = null
  addOpen.value = true
  addValue.value = ''
  addStrategy.value = 'css'
  nextTick(() => addInputRef.value?.focus())
}

function commitAdd() {
  const trimmed = addValue.value.trim()
  if (!trimmed) {
    addOpen.value = false
    return
  }
  emit('add:candidate', {
    value: trimmed,
    strategy: addStrategy.value,
  })
  addOpen.value = false
}

function cancelAdd() {
  addOpen.value = false
}

/** Auto-detect the strategy from a typed value so the user doesn't
 *  HAVE to pick one — but they always can override via the dropdown.
 *  Order matters: each pattern matches against an early prefix or
 *  unambiguous shape so we don't accidentally classify `text=…` as
 *  CSS. Falls back to 'css' which is the most common case in the
 *  Browser library. */
function detectStrategy(raw: string): SelectorStrategy {
  const v = raw.trim()
  if (v.startsWith('//') || v.startsWith('..') || v.startsWith('xpath=')) return 'xpath'
  if (v.startsWith('text=')) return 'text'
  if (/^\[(data-test-id|data-testid|data-qa|data-test)=/i.test(v)) return 'testid'
  if (/^\[role=/.test(v)) return 'aria'
  if (v.startsWith('aria/') || /^role=/.test(v)) return 'aria'
  return 'css'
}

watch(addValue, (v) => {
  // Only auto-update strategy if the user hasn't manually picked
  // one yet. We approximate "hasn't picked" by detecting from value
  // and only overwriting when the previous strategy was also auto-
  // detected from the previous value. To keep this simple and
  // predictable, ALWAYS update the strategy as the user types — if
  // they want a different one they pick from the dropdown AFTER
  // typing. The dropdown is right next to the input so this stays
  // discoverable.
  addStrategy.value = detectStrategy(v)
})
</script>

<template>
  <span v-if="active" :class="['selector-picker', { 'selector-picker--compact': compact }]">
    <span
      :class="['selector-picker__dot', `selector-picker__dot--${qualityBand(active.quality_score)}`]"
      :title="t(strategyLabelKey(active.strategy)) + ` · ${active.quality_score}/100`"
      aria-hidden="true"
    />
    <code class="selector-picker__value">{{ active.value }}</code>
    <button
      v-if="hasMenu"
      type="button"
      class="selector-picker__toggle"
      :aria-expanded="menuOpen"
      :aria-label="hasChoices
        ? t('recorder.selector.swapAriaLabel')
        : t('recorder.selector.editOrAddAriaLabel')"
      @click.stop="toggleMenu"
    >
      ▾
    </button>

    <ul v-if="menuOpen" class="selector-picker__menu" role="listbox">
      <li
        v-for="{ candidate: c, originalIndex } in visibleCandidates"
        :key="`${c.strategy}-${c.value}-${originalIndex}`"
        role="option"
        :aria-selected="originalIndex === command.active_candidate_index"
        :class="['selector-picker__item', { 'is-active': originalIndex === command.active_candidate_index }]"
        @click="editingIndex !== originalIndex && pick(originalIndex)"
      >
        <!-- Display row (default) — click anywhere on the row swaps
             to this candidate. The pencil button stops propagation
             so editing doesn't double-fire as a swap. -->
        <template v-if="editingIndex !== originalIndex">
          <span
            :class="['selector-picker__dot', `selector-picker__dot--${qualityBand(c.quality_score)}`]"
            aria-hidden="true"
          />
          <span class="selector-picker__strategy">{{ t(strategyLabelKey(c.strategy)) }}</span>
          <code class="selector-picker__value">{{ c.value }}</code>
          <span class="selector-picker__score">{{ c.quality_score }}</span>
          <span v-if="c.verified_unique" class="selector-picker__unique" aria-hidden="true" :title="t('recorder.selector.verifiedUniqueTitle')">✓</span>
          <button
            type="button"
            class="selector-picker__edit"
            :title="t('recorder.selector.editTitle')"
            :aria-label="t('recorder.selector.editTitle')"
            @click.stop="startEdit(originalIndex)"
          >✏</button>
        </template>

        <!-- Inline edit form — strategy dropdown + value input + Save / Cancel. -->
        <template v-else>
          <span
            :class="['selector-picker__dot', `selector-picker__dot--${qualityBand(c.quality_score)}`]"
            aria-hidden="true"
          />
          <select
            v-model="editStrategy"
            class="selector-picker__strategy-select"
            :title="t('recorder.selector.strategyLabel')"
          >
            <option v-for="s in EDITABLE_STRATEGIES" :key="s" :value="s">
              {{ t(strategyLabelKey(s)) }}
            </option>
          </select>
          <input
            ref="editInputRef"
            v-model="editValue"
            class="selector-picker__edit-input"
            :placeholder="t('recorder.selector.valuePlaceholder')"
            @keydown.enter.prevent="commitEdit"
            @keydown.escape.prevent="cancelEdit"
          />
          <button
            type="button"
            class="selector-picker__edit-action selector-picker__edit-action--save"
            :title="t('common.save')"
            @click.stop="commitEdit"
          >✓</button>
          <button
            type="button"
            class="selector-picker__edit-action selector-picker__edit-action--cancel"
            :title="t('common.cancel')"
            @click.stop="cancelEdit"
          >×</button>
        </template>
      </li>

      <!-- Custom-add row at the bottom of the menu. -->
      <li class="selector-picker__add-row" role="presentation">
        <template v-if="!addOpen">
          <button
            type="button"
            class="selector-picker__add-btn"
            data-testid="selector-picker-add"
            @click.stop="startAdd"
          >+ {{ t('recorder.selector.addCustom') }}</button>
        </template>
        <template v-else>
          <span class="selector-picker__dot selector-picker__dot--neutral" aria-hidden="true" />
          <select
            v-model="addStrategy"
            class="selector-picker__strategy-select"
            :title="t('recorder.selector.strategyLabel')"
          >
            <option v-for="s in EDITABLE_STRATEGIES" :key="s" :value="s">
              {{ t(strategyLabelKey(s)) }}
            </option>
          </select>
          <input
            ref="addInputRef"
            v-model="addValue"
            class="selector-picker__edit-input"
            :placeholder="t('recorder.selector.valuePlaceholder')"
            @keydown.enter.prevent="commitAdd"
            @keydown.escape.prevent="cancelAdd"
          />
          <button
            type="button"
            class="selector-picker__edit-action selector-picker__edit-action--save"
            data-testid="selector-picker-add-save"
            :title="t('common.save')"
            @click.stop="commitAdd"
          >✓</button>
          <button
            type="button"
            class="selector-picker__edit-action selector-picker__edit-action--cancel"
            :title="t('common.cancel')"
            @click.stop="cancelAdd"
          >×</button>
        </template>
      </li>
    </ul>
  </span>
</template>

<style scoped>
.selector-picker {
  display: inline-flex;
  gap: 0.35rem;
  align-items: center;
  position: relative;
  font-family: var(--font-mono, monospace);
  font-size: 0.85rem;
}

.selector-picker__dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.selector-picker__dot--good {
  background: #2c9846;
}

.selector-picker__dot--ok {
  background: #d4883e;
}

.selector-picker__dot--poor {
  background: #c0392b;
}

.selector-picker__dot--neutral {
  background: var(--color-text-muted, #5A6380);
  opacity: 0.5;
}

.selector-picker__value {
  background: var(--color-surface-subtle, rgba(0, 0, 0, 0.04));
  padding: 2px 6px;
  border-radius: 3px;
}

.selector-picker__toggle {
  background: transparent;
  border: none;
  padding: 0 4px;
  cursor: pointer;
  color: var(--color-text-secondary, #555);
}

.selector-picker__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 380px;
  margin: 0;
  padding: 4px 0;
  list-style: none;
  background: var(--color-surface, white);
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  z-index: 100;
}

.selector-picker__item {
  display: grid;
  grid-template-columns: 16px 110px 1fr auto auto auto;
  gap: 0.5rem;
  align-items: center;
  padding: 6px 10px;
  cursor: default;
}

.selector-picker__item:hover,
.selector-picker__item.is-active {
  background: rgba(59, 125, 216, 0.08);
}

.selector-picker__item .selector-picker__dot,
.selector-picker__item .selector-picker__strategy,
.selector-picker__item .selector-picker__value,
.selector-picker__item .selector-picker__score {
  cursor: pointer;
}

.selector-picker__strategy {
  font-family: var(--font-sans, sans-serif);
  color: var(--color-text-secondary, #555);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.selector-picker__strategy-select {
  font-family: var(--font-sans, sans-serif);
  font-size: 0.78rem;
  padding: 2px 4px;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 3px;
  background: var(--color-surface, white);
  text-transform: uppercase;
}

.selector-picker__edit-input {
  font-family: var(--font-mono, monospace);
  font-size: 0.85rem;
  padding: 3px 6px;
  border: 1px solid var(--color-primary, #3B7DD8);
  border-radius: 3px;
  outline: none;
  min-width: 0;
}

.selector-picker__score {
  font-family: var(--font-mono, monospace);
  color: var(--color-text-secondary, #777);
  font-size: 0.75rem;
}

.selector-picker__unique {
  color: #2c9846;
  font-weight: 600;
}

.selector-picker__edit,
.selector-picker__edit-action {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 3px;
  padding: 0 6px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--color-text-secondary, #555);
  line-height: 1.6;
}

.selector-picker__edit:hover {
  border-color: var(--color-border, #ddd);
  background: rgba(0, 0, 0, 0.04);
}

.selector-picker__edit-action--save {
  color: #2c9846;
}
.selector-picker__edit-action--save:hover {
  background: rgba(44, 152, 70, 0.12);
}
.selector-picker__edit-action--cancel:hover {
  background: rgba(192, 57, 43, 0.12);
  color: #c0392b;
}

.selector-picker__add-row {
  display: grid;
  grid-template-columns: 16px 110px 1fr auto auto auto;
  gap: 0.5rem;
  align-items: center;
  padding: 6px 10px;
  border-top: 1px dashed var(--color-border, #ddd);
}

.selector-picker__add-btn {
  grid-column: 1 / -1;
  background: transparent;
  border: 1px dashed var(--color-border, #ddd);
  border-radius: 3px;
  padding: 4px 8px;
  cursor: pointer;
  color: var(--color-primary, #3B7DD8);
  font-family: var(--font-sans, sans-serif);
  font-size: 0.82rem;
  text-align: left;
}
.selector-picker__add-btn:hover {
  border-color: var(--color-primary, #3B7DD8);
  background: rgba(59, 125, 216, 0.06);
}

.selector-picker--compact .selector-picker__value {
  font-size: 0.8rem;
}
</style>
