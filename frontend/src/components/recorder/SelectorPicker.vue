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
import { effectiveSelectorForCandidate } from '@/utils/effectiveSelector'

/**
 * Build the auto-composed effective form for a value+strategy pair
 * as if the user had a candidate with those edits but NO override.
 * Reuses `effectiveSelectorForCandidate` so the auto-compute logic
 * stays in one place. Used by the Edit + Add forms to (a) pre-fill
 * the Effektiv field and (b) decide whether the user's typed
 * effective is a "real override" or just the auto value.
 *
 * Edit/Add demote the candidate to `quality_score=50` +
 * `verified_unique=false`, so the tentative candidate uses the same
 * flags. This matters because `renderSelector` only appends the
 * defensive `>> nth=0` for risky-strategy + non-verified.
 */
function autoComposedEffective(
  cmd: RecordedCommand,
  value: string,
  strategy: SelectorStrategy,
): string {
  const tentative: SelectorCandidate = {
    strategy,
    value,
    quality_score: 50,
    verified_unique: false,
  }
  return effectiveSelectorForCandidate(cmd, tentative)
}

const props = defineProps<{
  command: RecordedCommand
  /** Compact mode hides the strategy label to fit into gutter annotations. */
  compact?: boolean
}>()

const emit = defineEmits<{
  'update:activeIndex': [index: number]
  /** User edited an existing candidate's value / strategy and
   *  optionally its verbatim emit-form override.
   *  - `effective: undefined` → no override change; recompose from
   *    value+strategy as before.
   *  - `effective: ""`       → clear an existing override.
   *  - `effective: "<str>"` → set/replace the override verbatim. */
  'update:candidate': [{ index: number; value: string; strategy: SelectorStrategy; effective?: string }]
  /** User added a brand-new candidate, optionally with a verbatim
   *  emit-form override (same `effective` semantics as above; an
   *  empty / undefined value means "auto-compose, no override"). */
  'add:candidate': [{ value: string; strategy: SelectorStrategy; effective?: string }]
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

/** Helper bound for the template — what gets emitted as the
 *  selector argument in the .robot line if THIS candidate were
 *  active. Mirrors the Python emitter's composition exactly via
 *  `effectiveSelectorForCandidate`, so the picker shows the
 *  cross-frame wrapper + defensive `>> nth=0` disambiguation
 *  alongside the raw candidate value. Closes the "the live view
 *  shows just `text=Zustimmen` but the saved .robot is something
 *  else" UX gap the user pointed at on the heise.de recording. */
function effectiveFor(c: SelectorCandidate): string {
  return effectiveSelectorForCandidate(props.command, c)
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
/** Verbatim emit-form for the candidate being edited. Bound to the
 *  third "Effektiv" input. Auto-syncs with value/strategy until
 *  `editEffectiveTouched` flips — once the user types here, the
 *  field decouples and becomes the override on commit. */
const editEffective = ref('')
const editEffectiveTouched = ref(false)
const editInputRef = ref<HTMLInputElement | null>(null)

/** When true, the "+ add custom" inline form is open. */
const addOpen = ref(false)
const addValue = ref('')
const addStrategy = ref<SelectorStrategy>('css')
/** Same as `editEffective` but for the Add form. */
const addEffective = ref('')
const addEffectiveTouched = ref(false)
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
  // Pre-fill Effektiv with the existing override (verbatim) OR the
  // auto-composed form. The user sees what's about to be written
  // to the .robot before they type — and any deviation from the
  // auto value is what triggers override-set on commit.
  editEffective.value =
    c.effective_override != null && c.effective_override.trim() !== ''
      ? c.effective_override
      : effectiveSelectorForCandidate(props.command, c)
  editEffectiveTouched.value = false
  nextTick(() => {
    // Guard the call entirely — in vitest + JSDOM the template ref
    // can resolve to a wrapper object whose `focus` is undefined,
    // surfacing as an unhandled rejection that fails CI even when
    // every test case passes. `?.focus?.()` short-circuits cleanly
    // in both prod and test.
    editInputRef.value?.focus?.()
  })
}

function commitEdit() {
  if (editingIndex.value === null) return
  const trimmed = editValue.value.trim()
  if (!trimmed) {
    // Empty value = cancel; the parent keeps the previous candidate.
    editingIndex.value = null
    return
  }
  // Decide override-vs-auto by comparing the typed Effektiv against
  // the auto-composed form FOR THE EDITED value+strategy. If they
  // match → no override (clearing any prior one with `""`). If
  // they differ → store override verbatim. Empty Effektiv input
  // also clears any prior override.
  const effInput = editEffective.value.trim()
  const auto = autoComposedEffective(props.command, trimmed, editStrategy.value)
  const effective: string = effInput === '' || effInput === auto ? '' : effInput
  emit('update:candidate', {
    index: editingIndex.value,
    value: trimmed,
    strategy: editStrategy.value,
    effective,
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
  addEffective.value = ''
  addEffectiveTouched.value = false
  nextTick(() => {
    // See the comment on `startEdit` — guard the focus call so a
    // JSDOM ref-resolution quirk doesn't surface as an unhandled
    // rejection in the vitest run.
    addInputRef.value?.focus?.()
  })
}

function commitAdd() {
  const trimmed = addValue.value.trim()
  if (!trimmed) {
    addOpen.value = false
    return
  }
  const effInput = addEffective.value.trim()
  const auto = autoComposedEffective(props.command, trimmed, addStrategy.value)
  const effective: string = effInput === '' || effInput === auto ? '' : effInput
  emit('add:candidate', {
    value: trimmed,
    strategy: addStrategy.value,
    effective,
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

// Keep the Effektiv field in lockstep with value/strategy edits
// UNTIL the user touches Effektiv directly. After that, the field
// becomes the verbatim override and stops auto-syncing — that's
// the whole point of the override (escape from auto-compose).
watch([editValue, editStrategy], ([v, s]) => {
  if (editingIndex.value === null) return
  if (editEffectiveTouched.value) return
  editEffective.value = autoComposedEffective(props.command, v, s)
})
watch([addValue, addStrategy], ([v, s]) => {
  if (!addOpen.value) return
  if (addEffectiveTouched.value) return
  addEffective.value = autoComposedEffective(props.command, v, s)
})

function onEditEffectiveInput() {
  editEffectiveTouched.value = true
}
function onAddEffectiveInput() {
  addEffectiveTouched.value = true
}
/** Reset Effektiv to the auto-composed form — drops any override
 *  the user typed and re-enables live sync with value/strategy. */
function resetEditEffective() {
  editEffective.value = autoComposedEffective(
    props.command, editValue.value.trim(), editStrategy.value,
  )
  editEffectiveTouched.value = false
}
function resetAddEffective() {
  addEffective.value = autoComposedEffective(
    props.command, addValue.value.trim(), addStrategy.value,
  )
  addEffectiveTouched.value = false
}

/** True iff the user has typed an Effektiv that differs from
 *  what auto-compose would produce for the current value+strategy.
 *  Used by the template to show an "Override aktiv" indicator. */
const editEffectiveIsOverride = computed(() => {
  if (editingIndex.value === null) return false
  const trimmed = editValue.value.trim()
  if (!trimmed) return false
  const auto = autoComposedEffective(props.command, trimmed, editStrategy.value)
  const eff = editEffective.value.trim()
  return eff !== '' && eff !== auto
})
const addEffectiveIsOverride = computed(() => {
  if (!addOpen.value) return false
  const trimmed = addValue.value.trim()
  if (!trimmed) return false
  const auto = autoComposedEffective(props.command, trimmed, addStrategy.value)
  const eff = addEffective.value.trim()
  return eff !== '' && eff !== auto
})
</script>

<template>
  <span v-if="active" :class="['selector-picker', { 'selector-picker--compact': compact }]">
    <span
      :class="['selector-picker__dot', `selector-picker__dot--${qualityBand(active.quality_score)}`]"
      :title="t(strategyLabelKey(active.strategy)) + ` · ${active.quality_score}/100`"
      aria-hidden="true"
    />
    <!-- Effective selector — what the emitter will write into the
         .robot file (iframe wrapper + inner + defensive `>> nth=0`).
         Falls back to the raw value for top-frame, fully-verified
         candidates where the inner IS the full string. The picker's
         user-facing contract is "what will I actually save?", not
         "what does Pydantic call this field?", so show the composite. -->
    <code class="selector-picker__value" :title="active.value">{{ effectiveFor(active) }}</code>
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
          <!-- Show the effective composite per-row so the user can
               see what each alternative ACTUALLY emits before picking
               it. Raw value stays on title= for hover when the user
               wants to compare with the original candidate. -->
          <code class="selector-picker__value" :title="c.value">{{ effectiveFor(c) }}</code>
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
          <!-- Effektiv (verbatim emit-form) row — sits below the
               strategy/value row, spans the full grid width.
               Editing it decouples the field from value/strategy
               and stores the typed string as `effective_override`
               on the candidate. Resetting brings live sync back. -->
          <div class="selector-picker__effective-row">
            <label class="selector-picker__effective-label">
              {{ t('recorder.selector.effectiveLabel') }}
            </label>
            <input
              v-model="editEffective"
              class="selector-picker__effective-input"
              :class="{ 'is-override': editEffectiveIsOverride }"
              :placeholder="t('recorder.selector.effectivePlaceholder')"
              :title="t('recorder.selector.effectiveTitle')"
              data-testid="selector-picker-effective-edit"
              @input="onEditEffectiveInput"
              @keydown.enter.prevent="commitEdit"
              @keydown.escape.prevent="cancelEdit"
            />
            <button
              v-if="editEffectiveIsOverride"
              type="button"
              class="selector-picker__effective-reset"
              :title="t('recorder.selector.effectiveResetTitle')"
              data-testid="selector-picker-effective-reset-edit"
              @click.stop="resetEditEffective"
            >↺</button>
            <span
              v-if="editEffectiveIsOverride"
              class="selector-picker__effective-badge"
              :title="t('recorder.selector.effectiveOverrideTitle')"
            >{{ t('recorder.selector.effectiveOverrideBadge') }}</span>
          </div>
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
          <!-- Effektiv row for the Add form — same UX as Edit. -->
          <div class="selector-picker__effective-row">
            <label class="selector-picker__effective-label">
              {{ t('recorder.selector.effectiveLabel') }}
            </label>
            <input
              v-model="addEffective"
              class="selector-picker__effective-input"
              :class="{ 'is-override': addEffectiveIsOverride }"
              :placeholder="t('recorder.selector.effectivePlaceholder')"
              :title="t('recorder.selector.effectiveTitle')"
              data-testid="selector-picker-effective-add"
              @input="onAddEffectiveInput"
              @keydown.enter.prevent="commitAdd"
              @keydown.escape.prevent="cancelAdd"
            />
            <button
              v-if="addEffectiveIsOverride"
              type="button"
              class="selector-picker__effective-reset"
              :title="t('recorder.selector.effectiveResetTitle')"
              data-testid="selector-picker-effective-reset-add"
              @click.stop="resetAddEffective"
            >↺</button>
            <span
              v-if="addEffectiveIsOverride"
              class="selector-picker__effective-badge"
              :title="t('recorder.selector.effectiveOverrideTitle')"
            >{{ t('recorder.selector.effectiveOverrideBadge') }}</span>
          </div>
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

/* Effektiv override row — second visual line of the edit/add form,
   spans the entire grid width. */
.selector-picker__effective-row {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 4px;
}

.selector-picker__effective-label {
  font-family: var(--font-sans, sans-serif);
  color: var(--color-text-secondary, #555);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  width: 70px;
}

.selector-picker__effective-input {
  flex: 1;
  font-family: var(--font-mono, monospace);
  font-size: 0.82rem;
  padding: 3px 6px;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 3px;
  outline: none;
  min-width: 0;
}
.selector-picker__effective-input:focus {
  border-color: var(--color-primary, #3B7DD8);
}
.selector-picker__effective-input.is-override {
  border-color: var(--color-accent, #D4883E);
  background: rgba(212, 136, 62, 0.06);
}

.selector-picker__effective-reset {
  background: transparent;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 3px;
  padding: 0 6px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--color-text-secondary, #555);
  line-height: 1.6;
  flex-shrink: 0;
}
.selector-picker__effective-reset:hover {
  border-color: var(--color-accent, #D4883E);
  background: rgba(212, 136, 62, 0.08);
}

.selector-picker__effective-badge {
  font-family: var(--font-sans, sans-serif);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--color-accent, #D4883E);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
}
</style>
