<script setup lang="ts">
import { computed, ref, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { Handle, Position } from '@vue-flow/core'
import { activeSelector } from '@/types/recorder.types'
import { qualityBand } from '@/utils/selectorQuality'
import { getArgLabel, friendlyType } from '@/utils/robotKeywordSignatures'
import { DRAG_ARM_DELAY_MS } from './reorderDrag'
import type { FlowNodeData } from './flowConverter'

const props = defineProps<{
  data: FlowNodeData
  reorderEnabled?: boolean
  /** Set by the parent FlowEditor when the user has clicked this
   *  node — paints the thicker outline + primary tint so the
   *  active node reads at a glance against the canvas. */
  selected?: boolean
}>()

const emit = defineEmits<{
  (e: 'reorder-drag-start', event: DragEvent): void
}>()

const { t } = useI18n()

// Drag-arm gating: HTML5 native drag fires the moment the user
// nudges the mouse a few pixels with the button down. That meant a
// brief click on the handle could already start a reorder gesture.
// We defer setting `draggable=true` until the user has held the
// button for `DRAG_ARM_DELAY_MS` ms — tap-and-release before that
// never arms the drag. `pointerup` / `pointerleave` cancel the timer
// so a release-and-retry doesn't accumulate state.
const dragArmed = ref(false)
let armTimer: number | null = null
function armDrag() {
  cancelArm()
  armTimer = window.setTimeout(() => {
    dragArmed.value = true
  }, DRAG_ARM_DELAY_MS)
}
function cancelArm() {
  if (armTimer != null) {
    clearTimeout(armTimer)
    armTimer = null
  }
  dragArmed.value = false
}
onBeforeUnmount(cancelArm)

function onHandleDragStart(event: DragEvent) {
  emit('reorder-drag-start', event)
}
function onHandleDragEnd() {
  cancelArm()
}

// Story EDITOR-2 — render chips as `name: value` when the signature is
// known, fall back to plain `value` otherwise. The label resolver is the
// same one the detail panel uses, so node + panel never disagree.
function chipNameAt(index: number): string | null {
  const specs = props.data.argSpecs
  if (!specs || specs.length === 0) return null
  const label = getArgLabel(specs, index, t)
  // Don't prefix with the generic fallback ("arg N") — that's just noise
  // on the node body. Only show prefixes that carry real meaning.
  const fallback = t('flowEditor.argLabels.fallback', { n: index + 1 })
  return label === fallback ? null : label
}

function chipTitleAt(index: number): string | undefined {
  const value = props.data.step.args[index]
  const spec = props.data.argSpecs?.[index]
  // Always include the FULL arg value in the tooltip — `.flow-arg-value`
  // truncates with ellipsis at 200 px, so a long regex / selector / URL
  // is invisible without hover. Spec info (`name: type = default`)
  // appended as a second line when available so the user gets both
  // the typed slot meaning and the actual value.
  const lines: string[] = []
  if (value && value.length > 0) lines.push(value)
  if (spec?.name) {
    let specLine = spec.name
    if (spec.type) specLine += `: ${spec.type}`
    if (spec.defaultValue != null) specLine += ` = ${spec.defaultValue}`
    lines.push(specLine)
  }
  return lines.length > 0 ? lines.join('\n') : undefined
}

// Story EDITOR-3 — small friendly-type icon prefixed inside the chip.
function chipTypeIconAt(index: number): string | null {
  const spec = props.data.argSpecs?.[index]
  if (!spec?.type) return null
  const ft = friendlyType(spec.type)
  // Don't render the unknown bucket's `?` here — it adds noise on
  // every untyped chip (no signature info → noisy UI). Keep prefixes
  // for shapes the user genuinely benefits from recognising.
  if (ft.labelKey === 'flowEditor.argTypes.unknown') return null
  return ft.icon
}

// Story EDITOR-1 — selector-candidate badge for the first arg chip.
const candidateCount = computed(() => props.data.recording?.selector_candidates.length ?? 0)
const showCandidateBadge = computed(() => candidateCount.value > 0)
const candidateBand = computed(() => {
  const a = props.data.recording ? activeSelector(props.data.recording) : null
  return qualityBand(a?.quality_score ?? 0)
})
const candidateTooltip = computed(() =>
  t('flowEditor.selector.tooltipHasCandidates', { count: candidateCount.value }),
)
</script>

<template>
  <div class="flow-node flow-node-keyword" :class="{ 'flow-node--selected': selected }">
    <Handle type="target" :position="Position.Top" />
    <div class="flow-node-header">
      <div
        v-if="reorderEnabled"
        class="flow-drag-handle"
        :class="{ 'flow-drag-handle--armed': dragArmed }"
        :draggable="dragArmed"
        @pointerdown.stop="armDrag"
        @pointerup="cancelArm"
        @pointerleave="cancelArm"
        @pointercancel="cancelArm"
        @mousedown.stop
        @dragstart.stop="onHandleDragStart"
        @dragend="onHandleDragEnd"
      >&#x2630;</div>
      <span class="flow-node-icon">&#x2699;</span>
      <!-- Story FE-BDD — Gherkin prefix badge; the label then shows the
           keyword without the prefix so BDD suites read as BDD. -->
      <span
        v-if="data.bdd"
        class="flow-node-bdd-badge"
        data-testid="bdd-badge"
      >{{ data.bdd.prefix }}</span>
      <span class="flow-node-label">{{ data.bdd ? data.bdd.rest : (data.step.keyword || 'Keyword') }}</span>
      <!-- Story FE-ENV — environment-variable indicator. -->
      <span
        v-if="data.envRefs && data.envRefs.length"
        class="flow-node-env-badge"
        data-testid="env-badge"
        :title="data.envRefs.map((r) => r.default !== null ? `%{${r.name}=${r.default}}` : `%{${r.name}}`).join('\n')"
      >%{}</span>
    </div>
    <div v-if="data.step.args.length" class="flow-node-args">
      <span
        v-for="(arg, i) in data.step.args"
        :key="i"
        class="flow-arg"
        :class="{ 'flow-arg--has-candidates': i === 0 && showCandidateBadge }"
        :title="chipTitleAt(i)"
      >
        <span
          v-if="i === 0 && showCandidateBadge"
          :class="['flow-arg-dot', `flow-arg-dot--${candidateBand}`]"
          :title="candidateTooltip"
          aria-hidden="true"
        />
        <span
          v-if="chipTypeIconAt(i)"
          class="flow-arg-type-icon-prefix"
          data-testid="arg-type-icon"
        >{{ chipTypeIconAt(i) }}</span>
        <span v-if="chipNameAt(i)" class="flow-arg-name-prefix" data-testid="arg-name-prefix">
          {{ chipNameAt(i) }}:
        </span>
        <span class="flow-arg-value">{{ arg }}</span>
        <span
          v-if="i === 0 && showCandidateBadge"
          class="flow-arg-count"
          :title="candidateTooltip"
          data-testid="selector-candidate-count"
        >{{ t('flowEditor.selector.candidatesBadge', { count: candidateCount }) }}</span>
      </span>
    </div>
    <div v-if="data.step.returnVars.length" class="flow-node-return">
      {{ data.step.returnVars.join(', ') }} =
    </div>
    <Handle type="source" :position="Position.Bottom" />
  </div>
</template>

<style scoped>
.flow-node {
  padding: 8px 12px;
  border-radius: 8px;
  min-width: 180px;
  max-width: 320px;
  font-size: 13px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
}
.flow-node-keyword {
  background: #fff;
  border: 2px solid var(--color-primary, #3B7DD8);
}
/* Selected-node highlight — outline + tint so the active node
   stands out from the others. Mirrors the rule on inline
   comment / flow-control nodes inside FlowEditor.vue. */
.flow-node--selected {
  outline: 3px solid var(--color-primary, #3B7DD8);
  outline-offset: 2px;
  background: color-mix(in srgb, var(--color-primary, #3B7DD8) 10%, var(--color-bg-card, #fff));
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-primary, #3B7DD8) 18%, transparent),
              0 2px 6px rgba(0, 0, 0, 0.1);
}
.flow-node-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}
.flow-node-icon {
  font-size: 14px;
  opacity: 0.6;
}
.flow-node-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* Story FE-BDD — Gherkin prefix badge. */
.flow-node-bdd-badge {
  flex: 0 0 auto;
  margin-right: 4px;
  padding: 0 6px;
  border-radius: 8px;
  background: var(--color-accent, #D4883E);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  line-height: 16px;
}
/* Story FE-ENV — environment-variable indicator. */
.flow-node-env-badge {
  flex: 0 0 auto;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 6px;
  background: var(--color-navy, #1A2D50);
  color: #fff;
  font-size: 10px;
  font-family: var(--font-mono, monospace);
  line-height: 16px;
  cursor: help;
}
.flow-drag-handle {
  cursor: grab;
  color: var(--color-text-muted, #5A6380);
  font-size: 12px;
  line-height: 1;
  opacity: 0.4;
  padding: 2px;
  border-radius: 3px;
  user-select: none;
  flex-shrink: 0;
}
.flow-drag-handle:hover {
  opacity: 1;
  background: rgba(0, 0, 0, 0.06);
}
.flow-drag-handle:active,
.flow-drag-handle--armed {
  cursor: grabbing;
  background: rgba(59, 125, 216, 0.15);
  opacity: 1;
}
.flow-node-args {
  margin-top: 4px;
  /* Story EDITOR-8 — one chip per row so the rendered node height
     stays in sync with `estimateNodeHeight()` and nodes don't overlap
     when long selector / multi-arg values would otherwise wrap. */
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}
.flow-arg {
  background: var(--color-bg, #F4F7FA);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: var(--color-text-muted, #5A6380);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.flow-arg--has-candidates {
  background: rgba(59, 125, 216, 0.10);
  border: 1px solid rgba(59, 125, 216, 0.30);
  padding: 0 6px;
}
.flow-arg-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.flow-arg-dot--good { background: #2c9846; }
.flow-arg-dot--ok   { background: #d4883e; }
.flow-arg-dot--poor { background: #c0392b; }
.flow-arg-name-prefix {
  font-weight: 600;
  color: var(--color-navy, #1A2D50);
  opacity: 0.7;
}
.flow-arg-type-icon-prefix {
  font-family: var(--font-mono, monospace);
  font-size: 9px;
  font-weight: 700;
  color: var(--color-primary, #3B7DD8);
  opacity: 0.85;
}
.flow-arg-value {
  /* Used to be `white-space: nowrap` + `text-overflow: ellipsis` at
     200px — long regex / URL / selector args got clipped invisibly,
     and the surrounding chip didn't even hint that more text lived
     behind. Wrap at the chip ceiling instead so the user sees the
     full value (within reason); the title= tooltip still covers
     extreme-length cases. */
  word-break: break-word;
  white-space: pre-wrap;
  max-width: 240px;
}
.flow-arg-count {
  font-size: 10px;
  color: var(--color-primary, #3B7DD8);
  font-weight: 600;
}
.flow-node-return {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-accent, #D4883E);
  font-style: italic;
}
</style>
