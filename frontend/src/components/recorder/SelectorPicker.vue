<script setup lang="ts">
/**
 * Story S.4 — inline selector-picker for recorded commands.
 *
 * Renders the active candidate inline with a color-coded quality dot.
 * Clicking opens a menu with every other candidate sorted by quality.
 * Emits `update:activeIndex` when the user swaps.
 *
 * Used inline in the Visual-Flow editor (step nodes) and as a gutter
 * annotation in the Text editor.
 */
import { computed, ref, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import type { RecordedCommand, SelectorCandidate, SelectorStrategy } from '@/types/recorder.types'

const props = defineProps<{
  command: RecordedCommand
  /** Compact mode hides the strategy label to fit into gutter annotations. */
  compact?: boolean
}>()

const emit = defineEmits<{
  'update:activeIndex': [index: number]
}>()

const { t } = useI18n()

const menuOpen = ref(false)

const active = computed<SelectorCandidate | null>(() => {
  if (props.command.selector_candidates.length === 0) return null
  return (
    props.command.selector_candidates[props.command.active_candidate_index] ?? null
  )
})

const hasChoices = computed(() => props.command.selector_candidates.length > 1)

function pick(index: number) {
  emit('update:activeIndex', index)
  menuOpen.value = false
}

/** Quality → colour band matching AR-7: testid/aria (>=80) green,
 *  pw_locator/text/short-css (50..79) amber, xpath/fragile (<50) red. */
function qualityBand(score: number): 'good' | 'ok' | 'poor' {
  if (score >= 80) return 'good'
  if (score >= 50) return 'ok'
  return 'poor'
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
      v-if="hasChoices"
      type="button"
      class="selector-picker__toggle"
      :aria-expanded="menuOpen"
      :aria-label="t('recorder.selector.swapAriaLabel')"
      @click.stop="toggleMenu"
    >
      ▾
    </button>

    <ul v-if="menuOpen" class="selector-picker__menu" role="listbox">
      <li
        v-for="(c, i) in command.selector_candidates"
        :key="`${c.strategy}-${c.value}-${i}`"
        role="option"
        :aria-selected="i === command.active_candidate_index"
        :class="['selector-picker__item', { 'is-active': i === command.active_candidate_index }]"
        @click="pick(i)"
      >
        <span
          :class="['selector-picker__dot', `selector-picker__dot--${qualityBand(c.quality_score)}`]"
          aria-hidden="true"
        />
        <span class="selector-picker__strategy">{{ t(strategyLabelKey(c.strategy)) }}</span>
        <code class="selector-picker__value">{{ c.value }}</code>
        <span class="selector-picker__score">{{ c.quality_score }}</span>
        <span v-if="c.verified_unique" class="selector-picker__unique" aria-hidden="true">✓</span>
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
  min-width: 340px;
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
  grid-template-columns: 16px 90px 1fr auto auto;
  gap: 0.5rem;
  align-items: center;
  padding: 6px 10px;
  cursor: pointer;
}

.selector-picker__item:hover,
.selector-picker__item.is-active {
  background: rgba(59, 125, 216, 0.08);
}

.selector-picker__strategy {
  font-family: var(--font-sans, sans-serif);
  color: var(--color-text-secondary, #555);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
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

.selector-picker--compact .selector-picker__value {
  font-size: 0.8rem;
}
</style>
