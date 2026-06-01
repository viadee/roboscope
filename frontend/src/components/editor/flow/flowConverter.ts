/**
 * Converts between RobotForm AST and Vue Flow graph (nodes + edges).
 *
 * RobotForm → { nodes, edges }  (for rendering)
 * User edits graph → updated nodes/edges → RobotForm  (for serialization back to .robot)
 */

import type { Node, Edge } from '@vue-flow/core'
import type { RecordedCommand, RecordedFlow, SelectorCandidate } from '@/types/recorder.types'
import { parseArgSignature, type ParsedArg } from '@/utils/robotKeywordSignatures'
import { effectiveSelectorForCandidate, renderSelector } from '@/utils/effectiveSelector'

// Map of lowercase-keyword-name → raw libdoc args; produced by
// `useKeywordSignatures()`. Threaded through the converter so node
// data carries pre-parsed argSpecs that the UI can label without
// re-parsing on every render.
export type SignatureMap = Map<string, string[]>

// --- Types matching RobotEditor.vue ---

export type StepType =
  | 'keyword' | 'assignment' | 'var' | 'for' | 'end' | 'if' | 'else_if' | 'else'
  | 'while' | 'try' | 'except' | 'finally' | 'break' | 'continue' | 'return' | 'comment'

const STEP_TYPE_VALUES: ReadonlySet<StepType> = new Set<StepType>([
  'keyword', 'assignment', 'var', 'for', 'end', 'if', 'else_if', 'else',
  'while', 'try', 'except', 'finally', 'break', 'continue', 'return', 'comment',
])

/** Type guard for runtime-supplied step-type strings (e.g. drag-drop
 *  payloads). Returns true only when `s` is a known StepType. */
export function isStepType(s: string): s is StepType {
  return STEP_TYPE_VALUES.has(s as StepType)
}

export interface RobotStep {
  type: StepType
  keyword: string
  args: string[]
  returnVars: string[]
  condition: string
  loopVar: string
  loopFlavor: string
  loopValues: string[]
  exceptPattern: string
  exceptVar: string
  varScope: string
  comment: string
  /**
   * Story RECORDER-IDMAP — position-independent link to the matching
   * sidecar `RecordedCommand`. Parsed from the trailing
   * `# rbs:<id>` comment on the line. When set,
   * `matchStepToCommand` looks up by id; falls back to positional
   * match when missing (legacy recordings, hand-written tests).
   * Optional / blank for any step that wasn't recorded.
   */
  rbs_id?: string
  /**
   * Story DEBUG-3 — 1-based source line of this step inside the
   * `.robot` file as parsed. Set by `parseRobotToForm`; omitted on
   * steps the user added in the editor (no source line yet — they
   * become real line numbers on the next save+parse roundtrip).
   * The Flow Editor's "Run up to here" debug button reads this to
   * tell the backend where to break.
   */
  _lineNumber?: number
}

export interface RobotTestCase {
  name: string
  documentation: string
  tags: string[]
  setup: string
  teardown: string
  timeout: string
  template: string
  steps: RobotStep[]
}

export interface RobotKeywordDef {
  name: string
  documentation: string
  arguments: string[]
  tags: string[]
  setup: string
  teardown: string
  timeout: string
  returnValue: string
  steps: RobotStep[]
}

export interface RobotForm {
  settings: { key: string; value: string; args: string[] }[]
  variables: { name: string; value: string }[]
  testCases: RobotTestCase[]
  keywords: RobotKeywordDef[]
  preambleLines: string[]
}

// --- Node data interfaces ---

export interface FlowNodeData {
  label: string
  stepType: StepType
  step: RobotStep
  section: 'testcase' | 'keyword'
  sectionIndex: number
  stepIndex: number
  /**
   * Story EDITOR-1 — sidecar command matched to this step (if any).
   * Set when a `<file>.rbs.json` exists alongside the `.robot` file
   * and the step's positional index in the visible (non-control-flow)
   * step sequence has a corresponding `RecordedCommand`. `null` for
   * hand-written steps, control-flow steps, or excess hand-inserted
   * steps beyond the sidecar length.
   */
  recording: RecordedCommand | null
  /**
   * Story EDITOR-2 — parsed argument signature for this keyword,
   * resolved from the dynamic library introspection + the static RF
   * fallback via `useKeywordSignatures`. Null when the keyword is not
   * known to the signature map; the UI then falls back to "arg N"
   * labels and plain text inputs.
   */
  argSpecs: ParsedArg[] | null
}

// --- Sidecar matching (Story EDITOR-1) ---
//
// Strategy: iterate the section's flat step list, skip every control-flow /
// non-keyword step (`if`, `for`, `while`, `try`, `except`, `finally`, `else`,
// `else_if`, `end`, `break`, `continue`, `return`, `comment`, `var`), and
// match the N-th remaining keyword/assignment step to the N-th
// `RecordedCommand` in the sidecar.
//
// Limits (acceptable for V1, see story EDITOR-1 AC10):
//   - A hand-inserted keyword in the middle of a recorded suite shifts every
//     subsequent match by one. The picker simply disappears for the
//     unmatched steps; nothing crashes.
//   - Re-ordering steps does NOT re-fingerprint — the step at the new
//     position picks up that position's recorded command. Re-recording is
//     the recommended workflow for invalidated suites.

const RECORDED_STEP_TYPES = new Set<StepType>(['keyword', 'assignment'])

export function isRecordedStep(step: RobotStep): boolean {
  return RECORDED_STEP_TYPES.has(step.type)
}

/**
 * Returns the visible (recorded-step-only) index of `stepIndex` inside
 * `steps`, or -1 if the step at `stepIndex` is not recorded-eligible.
 */
export function recordedIndex(steps: RobotStep[], stepIndex: number): number {
  if (stepIndex < 0 || stepIndex >= steps.length) return -1
  if (!isRecordedStep(steps[stepIndex])) return -1
  let n = 0
  for (let i = 0; i < stepIndex; i++) {
    if (isRecordedStep(steps[i])) n++
  }
  return n
}

/**
 * Match the step at `stepIndex` to a sidecar command, or `null` if no
 * match can be made.
 *
 * RECORDER-IDMAP — Story W.6 originally matched by POSITION
 * (`sidecar.commands[recordedIndex(...)]`). Reordering or deleting a
 * step in the FlowEditor silently shifted the candidate group onto
 * a different row. Now we prefer the position-independent id parsed
 * from the line's trailing `# rbs:<id>` comment, and fall back to
 * the positional lookup only when the step has no id (legacy
 * recordings, hand-written tests). The fallback is safe because the
 * positional match has been the de-facto contract for months — id
 * lookup just becomes the better answer when both exist.
 */
export function matchStepToCommand(
  steps: RobotStep[],
  sidecar: RecordedFlow | null,
  stepIndex: number,
): RecordedCommand | null {
  if (!sidecar) return null
  if (stepIndex < 0 || stepIndex >= steps.length) return null
  const step = steps[stepIndex]
  if (!isRecordedStep(step)) return null

  // RECORDER-IDMAP — three cases:
  //
  // 1. Step has an `rbs_id` → id-lookup only. If no match, return
  //    null (drift detection — the sidecar lost the command, or the
  //    user ID-typo'd in source view; positional fallback would
  //    silently show wrong selectors).
  if (step.rbs_id) {
    return sidecar.commands.find((c) => c.id === step.rbs_id) ?? null
  }
  // 2. Step has no id, but ANOTHER step in the file does. That means
  //    the file is identity-tracked (post-IDMAP recording) and this
  //    specific step was hand-inserted / had its `# rbs:<id>` comment
  //    deleted. Positional fallback would phantom-match it; null is
  //    accurate. (We check the STEPS array, not the sidecar — Phase 1
  //    made every backend command get a fresh id even on legacy
  //    sidecars, so `sidecar.commands.some(c => c.id)` would always
  //    be true and break the legacy fallback.)
  const fileIsIdTracked = steps.some((s) => isRecordedStep(s) && Boolean(s.rbs_id))
  if (fileIsIdTracked) return null
  // 3. Legacy recording — no ids in the .robot file. Positional
  //    fallback is the de-facto pre-IDMAP contract.
  const idx = recordedIndex(steps, stepIndex)
  if (idx < 0) return null
  return sidecar.commands[idx] ?? null
}

/**
 * Story EDITOR-2 — resolve parsed arg specs for the keyword on `step`
 * via the signature map. Returns null for unknown keywords (the caller
 * falls back to "arg N" labels).
 */
export function resolveArgSpecs(
  step: RobotStep, signatures: SignatureMap | null,
): ParsedArg[] | null {
  if (!signatures || !step.keyword) return null
  const raw = signatures.get(step.keyword.toLowerCase())
  if (!raw) return null
  // Drop libdoc separator markers (`/`, `*`, `?`). They are Python-
  // signature shape hints — not real argument slots — and Robot
  // Framework's `libdoc` emits them inline with the parameter list.
  // Without this filter, e.g. `Heal Click` (signature
  // `selector, /, *args, **kwargs`) would yield argSpecs
  // `[selector, /, args, kwargs]`, and the detail panel would label
  // slot 1 as `/`, the `+ Add argument` picker would offer `/` as a
  // clickable option, and `addArgOptions` would mis-track which
  // positional slot is filled for multi-arg Heal keywords. None of
  // that is meaningful to the user — separators are structural.
  return raw
    .map(parseArgSignature)
    .filter(
      (s) =>
        s.kind !== 'positional-only-sep' &&
        s.kind !== 'named-only-sep' &&
        s.kind !== 'optional-sep',
    )
}

/**
 * Apply a SelectorPicker swap to a step + its matched RecordedCommand.
 * Both arguments are mutated in place: `step.args[0]` becomes the
 * EFFECTIVE composite selector for the picked candidate (iframe-chain
 * prefix + inner value + defensive `>> nth=0` disambiguation), and
 * `cmd.active_candidate_index` is updated. Returns `true` if anything
 * changed (or `false` if the index was out of range).
 *
 * Why the composite (not the raw `candidate.value`): the picker shows
 * `effectiveSelectorForCandidate(cmd, c)` to every row — including the
 * iframe-chain prefix synthesised from `cmd.frame_chain`. If we wrote
 * just the raw inner here, the .robot file would lose the iframe wrap
 * the moment the user swapped to a different candidate, even though
 * the picker advertised the wrapped composite as "what gets saved".
 * Mirroring the Python `_emit_command` composition keeps the swap
 * round-trip-safe — the same string the user saw in the menu is the
 * string that lands in args[0] and the same string the emitter would
 * have written from `cmd.frame_chain` + the new active candidate.
 *
 * Pure data transform — extracted so it can be tested without mounting
 * Vue Flow / the visual editor.
 */
export function applySelectorSwap(
  step: RobotStep,
  cmd: RecordedCommand,
  newIndex: number,
): boolean {
  const candidate = cmd.selector_candidates[newIndex]
  if (!candidate) return false
  const composite = effectiveSelectorForCandidate(cmd, candidate)
  if (step.args.length === 0) {
    step.args.push(composite)
  } else {
    step.args[0] = composite
  }
  cmd.active_candidate_index = newIndex
  return true
}

/**
 * Shared composite-write helper for the EDIT and ADD picker paths.
 * Same iframe-chain + defensive-nth composition as
 * `applySelectorSwap`, but takes a free-standing `SelectorCandidate`
 * (the user-typed payload) rather than indexing into `cmd`. Keeping
 * a single composition site means the three picker actions
 * (swap / edit-active / add-new) can never drift out of sync on
 * iframe wrapping.
 */
export function composeEffectiveSelector(
  cmd: RecordedCommand,
  candidate: SelectorCandidate,
): string {
  return effectiveSelectorForCandidate(cmd, candidate)
}

/**
 * Detects whether `step.args[0]` is a value the user typed by hand
 * rather than one of the recorded selector candidates. Used to gate a
 * confirmation prompt before overwriting a custom selector during swap
 * AND a "custom value" badge in the detail panel.
 *
 * Match strategy — try, in order:
 *
 * 1. **Raw exact match** against `candidate.value`. Catches legacy
 *    .robot files written before the defensive-nth + iframe-chain
 *    composition existed, hand-edited values that happen to equal a
 *    candidate verbatim, and the simple top-frame `Click  text=X`
 *    case where the emitter's renderSelector would have produced
 *    the identical string anyway.
 *
 * 2. **Effective-composite match** — compute
 *    `effectiveSelectorForCandidate(cmd, c)` for every candidate
 *    and compare against `current`. This is the SAME function the
 *    `applySelectorSwap` / `composeEffectiveSelector` write path
 *    uses, so the comparison is symmetric with the write by
 *    construction: any value that COULD have been written by a
 *    legitimate swap of any candidate is recognised here as
 *    non-custom. Handles iframe-chain prefix (any strategy), the
 *    `xpath=` / `text=` prefixes that `renderSelector` adds, and
 *    the defensive `>> nth=0` suffix uniformly.
 *
 * Returns true only when neither match hits — i.e. the user genuinely
 * typed something the picker would never have produced.
 *
 * The earlier shape-specific strip approach was abandoned as the
 * PRIMARY check because it required knowing every decoration the
 * emitter might add (iframe prefix shapes, `xpath=` vs `text=`
 * prefixes, defensive nth thresholds, future strategies) and would
 * silently mis-classify any value whose decoration set didn't fit the
 * regex. The composite comparison delegates that knowledge to the
 * single source of truth (`effectiveSelectorForCandidate`).
 *
 * Step 3 (loose fallback) is the only remaining piece that uses the
 * strip — it's a backward-compat path for **legacy sidecars** where
 * `frame_chain` wasn't yet captured but the .robot still has an
 * iframe wrap (older recordings, hand-merged sidecars, frame_url-
 * only fallbacks where the URL-derived prefix happens to differ
 * from what the user typed in the .robot). The strip is defensive
 * (`lastIndexOf(' >>> ')` covers any frame-rung strategy + nesting
 * depth) and the comparison still anchors on the inner half — so a
 * genuinely-typed value like `iframe[...] >>> #manual-id` correctly
 * stays "custom" because no candidate's inner matches `#manual-id`.
 */
const _NTH_SUFFIX_RE = /\s*>>\s*nth=\d+\s*$/
function _stripFrameChainAndNth(value: string): string {
  let out = value
  const lastChain = out.lastIndexOf(' >>> ')
  if (lastChain >= 0) out = out.slice(lastChain + 5)
  return out.replace(_NTH_SUFFIX_RE, '').trim()
}

export function isCustomSelectorValue(step: RobotStep, cmd: RecordedCommand): boolean {
  if (cmd.selector_candidates.length === 0) return false
  const current = step.args[0] ?? ''
  if (current === '') return false
  // 1. Raw exact match — fastest, covers hand-written / legacy bare
  //    values and the simple top-frame case where the emitter would
  //    have produced the identical string anyway.
  if (cmd.selector_candidates.some((c) => c.value === current)) return false
  // 2. Strict composite match — symmetric with `applySelectorSwap` /
  //    `composeEffectiveSelector`. Anything any swap COULD have
  //    written is recognised as non-custom by construction.
  if (cmd.selector_candidates.some(
    (c) => effectiveSelectorForCandidate(cmd, c) === current,
  )) return false
  // 3. Loose fallback for legacy sidecars (no `frame_chain` /
  //    `frame_url`) whose .robot still has an iframe wrap from a
  //    previous recording. Strip a frame-chain prefix + defensive
  //    nth from `current` and match the inner against each
  //    candidate's raw value OR its `renderSelector` form
  //    (covers the `xpath=` / `text=` asymmetry too).
  const inner = _stripFrameChainAndNth(current)
  if (inner === current) return true
  return !cmd.selector_candidates.some(
    (c) => c.value === inner || renderSelector(c) === inner,
  )
}

// --- Layout constants ---

export const NODE_GAP = 50
export const NODE_START_Y = 60
export const NODE_X = 0
export const NODE_SPACING_Y = 80 // backward compat
const FRAME_PAD_X = 30
const FRAME_PAD_TOP = 12
const FRAME_PAD_BOTTOM = 16

// Deep-clone the parts of a RobotStep that the detail-panel inputs
// can mutate (the array fields). A shallow `{ ...step }` would leave
// every array as a shared reference between the node's data and the
// form, and v-model writes inside the panel would mutate the form
// directly — fired the deep `props.form` watcher and reset selection
// on every keystroke (closing the panel mid-edit).
function cloneStep(step: RobotStep): RobotStep {
  return {
    ...step,
    args: [...step.args],
    returnVars: [...step.returnVars],
    loopValues: [...step.loopValues],
    // _lineNumber is a primitive — covered by `...step`. Listed here
    // explicitly so a future contributor sees that DEBUG-3 metadata
    // intentionally rides through the clone.
    _lineNumber: step._lineNumber,
  }
}

// --- Node height estimation ---

const START_END_HEIGHT = 32
const NODE_BASE_HEIGHT = 44

export function estimateNodeHeight(step: RobotStep): number {
  const type = getNodeType(step.type)
  if (type === 'start' || type === 'end') return START_END_HEIGHT
  let h = NODE_BASE_HEIGHT
  if (type === 'keyword' || type === 'assignment') {
    if (step.args.length > 0) {
      // Story EDITOR-8 — one chip per row (KeywordNode now uses
      // `flex-direction: column` for args). The previous `ceil(n/3)`
      // estimate assumed 3 chips per row but long selector values
      // (e.g. recorded text= / xpath= selectors) take a full row
      // each, so the node grew taller than estimated and overlapped
      // the next one.
      h += 4 + step.args.length * 22
    }
    if (step.returnVars.length > 0) h += 20
  }
  if (type === 'control') {
    if (step.condition) h += 20
    if (step.type === 'for' || step.type === 'while') {
      if (step.loopVar && step.loopValues.length > 0) h += 20
    }
    if (step.exceptPattern) h += 20
  }
  return h
}

// --- Control block detection ---

const BLOCK_STARTERS = new Set<StepType>(['if', 'for', 'while', 'try'])

/** Find the matching END index for a block starter at startIdx. */
function findBlockEnd(steps: RobotStep[], startIdx: number): number {
  let depth = 1
  let i = startIdx + 1
  while (i < steps.length && depth > 0) {
    if (BLOCK_STARTERS.has(steps[i].type)) depth++
    if (steps[i].type === 'end') depth--
    i++
  }
  return i - 1 // index of the END step
}

const FRAME_COLORS: Record<string, { border: string; bg: string }> = {
  if:    { border: '#E8A838', bg: 'rgba(232, 168, 56, 0.06)' },
  for:   { border: '#7B61FF', bg: 'rgba(123, 97, 255, 0.06)' },
  while: { border: '#7B61FF', bg: 'rgba(123, 97, 255, 0.06)' },
  try:   { border: '#38B2AC', bg: 'rgba(56, 178, 172, 0.06)' },
}

/** Add visual frame nodes behind control blocks, recursively for nesting. */
function addControlFrames(steps: RobotStep[], nodes: Node[], prefix: string) {
  addFramesInRange(steps, nodes, prefix, 0, steps.length, 0)
}

function addFramesInRange(
  steps: RobotStep[], nodes: Node[], prefix: string,
  from: number, to: number, depth: number,
) {
  let i = from
  while (i < to) {
    if (BLOCK_STARTERS.has(steps[i].type)) {
      const endIdx = findBlockEnd(steps, i)

      // Collect rendered nodes within this block (header + body, excluding END)
      const blockNodes: Node[] = []
      for (let j = i; j < endIdx; j++) {
        if (steps[j].type === 'end') continue
        const node = nodes.find(n => n.id === `${prefix}-step-${j}`)
        if (node) blockNodes.push(node)
      }

      if (blockNodes.length > 0) {
        const minY = Math.min(...blockNodes.map(n => n.position.y))
        const maxY = Math.max(...blockNodes.map(n => n.position.y))
        const lastStep = blockNodes[blockNodes.length - 1].data as FlowNodeData
        const lastHeight = estimateNodeHeight(lastStep.step)
        const colors = FRAME_COLORS[steps[i].type] || { border: '#888', bg: 'rgba(0,0,0,0.03)' }

        // Indent nested frames so they don't overlap the parent border
        const inset = depth * 14

        nodes.push({
          id: `${prefix}-frame-${i}`,
          type: 'control-frame',
          position: { x: NODE_X - FRAME_PAD_X + inset, y: minY - FRAME_PAD_TOP },
          data: { stepType: steps[i].type, borderColor: colors.border, bgColor: colors.bg },
          style: {
            width: `${320 + (FRAME_PAD_X - inset) * 2}px`,
            height: `${maxY - minY + lastHeight + FRAME_PAD_TOP + FRAME_PAD_BOTTOM}px`,
          },
          zIndex: -1 - depth,
          selectable: false,
          draggable: false,
        })
      }

      // Recurse into the block body to find nested control blocks
      addFramesInRange(steps, nodes, prefix, i + 1, endIdx, depth + 1)

      i = endIdx + 1
    } else {
      i++
    }
  }
}

// --- Converter: Steps → Nodes + Edges ---

export function stepsToFlow(
  steps: RobotStep[],
  name: string,
  prefix: string,
  section: 'testcase' | 'keyword',
  sectionIndex: number,
  sidecar: RecordedFlow | null = null,
  signatures: SignatureMap | null = null,
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  // Start node — label comes from i18n inside StartEndNode.vue
  // ("Start" / "End"). The test-case name is already in the
  // section tab strip, so duplicating it on the canvas added no
  // information — and left fresh, unnamed test cases with a
  // visually empty box. `name` is still on the param list for
  // any future caller that wants to pin a custom label.
  nodes.push({
    id: `${prefix}-start`,
    type: 'start',
    position: { x: NODE_X, y: 0 },
    data: { label: name || undefined },
  })

  let prevId = `${prefix}-start`
  let y = START_END_HEIGHT + NODE_GAP

  for (let i = 0; i < steps.length; i++) {
    const step = steps[i]
    if (step.type === 'end') continue

    const nodeId = `${prefix}-step-${i}`
    const nodeType = getNodeType(step.type)
    const label = getStepLabel(step)
    const nodeHeight = estimateNodeHeight(step)

    nodes.push({
      id: nodeId,
      type: nodeType,
      position: { x: NODE_X, y },
      data: {
        label,
        stepType: step.type,
        // Deep-clone the step's arrays so v-model edits inside the
        // detail panel don't mutate the form's arrays directly. The
        // shallow spread `{ ...step }` previously left `args` /
        // `returnVars` / `loopValues` as SHARED REFERENCES, so each
        // keystroke fired the deep watcher on `props.form` — which
        // reset `selectedNode` and tore down the panel mid-edit.
        // `updateStepFromNode` replaces the form's arrays on blur via
        // `Object.assign`, so the round-trip still lands.
        step: cloneStep(step),
        section,
        sectionIndex,
        stepIndex: i,
        recording: matchStepToCommand(steps, sidecar, i),
        argSpecs: resolveArgSpecs(step, signatures),
      } as FlowNodeData,
    })

    const edgeLabel = getEdgeLabel(step, i > 0 ? steps[i - 1] : undefined)
    edges.push({
      id: `${prefix}-e-${prevId}-${nodeId}`,
      source: prevId,
      target: nodeId,
      animated: step.type === 'if' || step.type === 'for' || step.type === 'try',
      label: edgeLabel,
    })

    prevId = nodeId
    y += nodeHeight + NODE_GAP
  }

  // End node — label comes from i18n inside StartEndNode.vue.
  const endId = `${prefix}-end`
  nodes.push({
    id: endId,
    type: 'end',
    position: { x: NODE_X, y },
    data: {},
  })
  edges.push({
    id: `${prefix}-e-${prevId}-${endId}`,
    source: prevId,
    target: endId,
  })

  // Post-process: add visual frames behind control blocks
  addControlFrames(steps, nodes, prefix)

  return { nodes, edges }
}

/**
 * Settings that may attach to a test case or keyword as side-note
 * nodes on the canvas. Each kind corresponds to a Robot Framework
 * `[...]` setting and (for now) a string field on RobotTestCase /
 * RobotKeywordDef. Order here drives the vertical stacking order
 * to the LEFT of the Start node.
 *
 * `tags` and `arguments` store as string[] but the side-note
 * displays them comma-separated; the detail panel converts back.
 */
export type SettingMetaKind =
  | 'documentation'
  | 'tags'
  | 'arguments'
  | 'setup'
  | 'teardown'
  | 'template'
  | 'timeout'

const TC_SETTING_KINDS: SettingMetaKind[] = [
  'documentation', 'tags', 'setup', 'teardown', 'template', 'timeout',
]
const KW_SETTING_KINDS: SettingMetaKind[] = [
  'documentation', 'arguments', 'tags', 'setup', 'teardown', 'timeout',
]

const KIND_LABELS: Record<SettingMetaKind, string> = {
  documentation: '[Documentation]',
  tags: '[Tags]',
  arguments: '[Arguments]',
  setup: '[Setup]',
  teardown: '[Teardown]',
  template: '[Template]',
  timeout: '[Timeout]',
}

/** Read the raw value for a kind off the underlying form record.
 *  Returns the display text — may be empty when the setting is
 *  freshly added via the "+ [X]" affordance and the user hasn't
 *  typed anything yet. Use `settingPresent()` to decide whether the
 *  side note should render; this function only formats the text. */
function readSettingValue(
  source: RobotTestCase | RobotKeywordDef,
  kind: SettingMetaKind,
): string {
  switch (kind) {
    case 'documentation': return source.documentation
    case 'tags': return source.tags.join(', ')
    case 'arguments':
      return 'arguments' in source ? source.arguments.join(', ') : ''
    case 'setup': return source.setup
    case 'teardown': return source.teardown
    case 'template':
      return 'template' in source ? source.template : ''
    case 'timeout': return source.timeout
  }
}

/** Whether the kind has any user-attached data on the source. The
 *  side note renders as soon as this returns true, even if the
 *  current text is empty / whitespace — that's the case the moment
 *  after the user clicks "+ [X]" before they've typed the value.
 *
 *  The presence check is intentionally based on the underlying
 *  field (array length / truthiness), NOT on the formatted value,
 *  so a freshly-added empty setting still surfaces a visible side
 *  note for the user to click and edit. The matching write-side
 *  uses `[''] / ' '` placeholders in `addSetting()` (FlowEditor.vue)
 *  to flip the flag without polluting the saved .robot file with
 *  spurious chars. */
export function settingPresent(
  source: RobotTestCase | RobotKeywordDef,
  kind: SettingMetaKind,
): boolean {
  switch (kind) {
    case 'tags': return source.tags.length > 0
    case 'arguments':
      return 'arguments' in source && source.arguments.length > 0
    case 'template':
      return 'template' in source && source.template !== ''
    case 'documentation':
    case 'setup':
    case 'teardown':
    case 'timeout':
      return source[kind] !== ''
  }
}

/** Convert a single test case to flow graph. */
export function testCaseToFlow(
  tc: RobotTestCase, index: number,
  sidecar: RecordedFlow | null = null,
  signatures: SignatureMap | null = null,
): { nodes: Node[]; edges: Edge[] } {
  const out = stepsToFlow(tc.steps, tc.name, `tc${index}`, 'testcase', index, sidecar, signatures)
  appendSettingMetaNodes(out.nodes, out.edges, `tc${index}`, tc, 'testcase', index, TC_SETTING_KINDS)
  return out
}

/** Convert a single keyword definition to flow graph. */
export function keywordDefToFlow(
  kw: RobotKeywordDef, index: number,
  sidecar: RecordedFlow | null = null,
  signatures: SignatureMap | null = null,
): { nodes: Node[]; edges: Edge[] } {
  const out = stepsToFlow(kw.steps, kw.name, `kw${index}`, 'keyword', index, sidecar, signatures)
  appendSettingMetaNodes(out.nodes, out.edges, `kw${index}`, kw, 'keyword', index, KW_SETTING_KINDS)
  return out
}

/**
 * Append `[…]` meta-nodes to the flow for each non-empty setting on
 * the source (test case or keyword definition). The nodes stack
 * vertically to the LEFT of the Start node and each connects via a
 * dashed edge — visually they read as "side notes" attached to the
 * whole flow rather than as steps.
 *
 * The detail panel listens for clicks on `setting-meta` nodes and
 * switches into a kind-specific edit mode. Empty settings produce
 * no node — clutter-free for plain test cases.
 */
function appendSettingMetaNodes(
  nodes: Node[],
  edges: Edge[],
  prefix: string,
  source: RobotTestCase | RobotKeywordDef,
  section: 'testcase' | 'keyword',
  sectionIndex: number,
  kinds: SettingMetaKind[],
): void {
  const startNode = nodes.find((n) => n.id === `${prefix}-start`)
  if (!startNode) return
  let stackIdx = 0
  // Side-note pitch is wider than step pitch (80) to leave a clear
  // visual gap between consecutive side notes. The CSS clamps each
  // side-note body to two lines + a hard max-height so a long
  // [Documentation] preview can't grow into the [Tags] node below.
  const META_PITCH = 96
  for (const kind of kinds) {
    if (!settingPresent(source, kind)) continue
    const value = readSettingValue(source, kind)
    const id = `${prefix}-${kind}`
    // Position to the LEFT of the Start node, stacked vertically.
    // Each kind sits at a fixed row offset from the start.
    nodes.push({
      id,
      type: 'setting-meta',
      position: { x: NODE_X - 280, y: startNode.position.y + stackIdx * META_PITCH },
      data: {
        kind,
        label: KIND_LABELS[kind],
        text: value,
        section,
        sectionIndex,
      },
      selectable: true,
      draggable: false,
    })
    edges.push({
      id: `${prefix}-${kind}-edge`,
      source: id,
      target: `${prefix}-start`,
      // Connect side note's RIGHT handle → Start's LEFT handle so the
      // dashed edge runs horizontally between them rather than the
      // default Bottom→Top route (which crossed the whole canvas).
      sourceHandle: 'right',
      targetHandle: 'left',
      type: 'default',
      style: { strokeDasharray: '6 4', stroke: '#9AA5BF', strokeWidth: 1.5 },
      animated: false,
    })
    stackIdx++
  }
}

// --- Converter: Full RobotForm → Nodes + Edges ---

/**
 * The sidecar is a flat list of recorded commands. We apply it to test
 * case index 0 only — Recorder v2 always emits one test case per recording
 * (`Recording <session_id>`), so attaching the same command list to every
 * test case would mis-match anything but the first one. Hand-authored
 * additional test cases get no sidecar matching; that's the right answer.
 */
export function robotFormToFlow(
  form: RobotForm,
  sidecar: RecordedFlow | null = null,
  signatures: SignatureMap | null = null,
): { nodes: Node[]; edges: Edge[] } {
  const allNodes: Node[] = []
  const allEdges: Edge[] = []
  for (let i = 0; i < form.testCases.length; i++) {
    const sc = i === 0 ? sidecar : null
    const { nodes, edges } = testCaseToFlow(form.testCases[i], i, sc, signatures)
    const xOffset = i * 500
    for (const node of nodes) {
      node.position.x += xOffset
      allNodes.push(node)
    }
    allEdges.push(...edges)
  }
  return { nodes: allNodes, edges: allEdges }
}

/**
 * Convert all keyword definitions to flow. Sidecar entries are never bound
 * to user-defined keyword bodies (Recorder v2 targets test cases), so this
 * function intentionally takes no sidecar parameter.
 */
export function robotKeywordsToFlow(
  form: RobotForm,
  signatures: SignatureMap | null = null,
): { nodes: Node[]; edges: Edge[] } {
  const allNodes: Node[] = []
  const allEdges: Edge[] = []
  for (let i = 0; i < form.keywords.length; i++) {
    const { nodes, edges } = keywordDefToFlow(form.keywords[i], i, null, signatures)
    const xOffset = i * 500
    for (const node of nodes) {
      node.position.x += xOffset
      allNodes.push(node)
    }
    allEdges.push(...edges)
  }
  return { nodes: allNodes, edges: allEdges }
}

// --- Reverse: Update RobotForm step from edited node data ---

export function updateStepFromNode(form: RobotForm, nodeData: FlowNodeData): void {
  const list = nodeData.section === 'testcase'
    ? form.testCases[nodeData.sectionIndex]?.steps
    : form.keywords[nodeData.sectionIndex]?.steps
  if (!list) return
  const step = list[nodeData.stepIndex]
  if (!step) return
  Object.assign(step, nodeData.step)
}

// --- Helpers ---

function getNodeType(stepType: StepType): string {
  switch (stepType) {
    case 'if': case 'else_if': case 'else':
    case 'for': case 'while':
    case 'try': case 'except': case 'finally':
      return 'control'
    case 'assignment':
      return 'assignment'
    case 'comment':
      return 'comment'
    case 'return':
      // RETURN deserves a richer node than BREAK/CONTINUE — it's
      // the public surface of a `*** Keywords ***` definition. Each
      // arg is a return value and the visual makes that obvious.
      return 'return'
    case 'break': case 'continue':
      return 'flow-control'
    default:
      return 'keyword'
  }
}

export function getStepLabel(step: RobotStep): string {
  switch (step.type) {
    case 'keyword': return step.keyword || 'Keyword'
    case 'assignment': return `${step.returnVars.join(', ')} = ${step.keyword}`
    case 'if': return `IF  ${step.condition}`
    case 'else_if': return `ELSE IF  ${step.condition}`
    case 'else': return 'ELSE'
    case 'for': return `FOR ${step.loopVar} ${step.loopFlavor} ${step.loopValues.join('  ')}`
    case 'while': return `WHILE  ${step.condition}`
    case 'try': return 'TRY'
    case 'except': return step.exceptPattern ? `EXCEPT  ${step.exceptPattern}` : 'EXCEPT'
    case 'finally': return 'FINALLY'
    case 'return': return `RETURN  ${step.args.join('  ')}`
    case 'break': return 'BREAK'
    case 'continue': return 'CONTINUE'
    case 'comment': return `# ${step.comment}`
    case 'var': return `VAR ${step.keyword} = ${step.args.join('  ')}`
    default: return step.keyword || step.type
  }
}

function getEdgeLabel(step: RobotStep, prevStep?: RobotStep): string | undefined {
  if (step.type === 'else') return 'false'
  if (step.type === 'else_if') return 'false'
  if (prevStep?.type === 'if' || prevStep?.type === 'else_if') return 'true'
  return undefined
}

// ---------------------------------------------------------------------------
// DEBUG-3 follow-up: live step-line computation
// ---------------------------------------------------------------------------
//
// `parseRobotToForm` annotates `step._lineNumber` on the steps it just
// read from disk, but those numbers go stale the moment the user adds /
// removes / reorders a step in the Flow Editor — every step below the
// edit shifts, but its `_lineNumber` doesn't. The "Bis hier ausführen"
// button needs the LIVE line number of the clicked step, otherwise it
// asks the backend to break at the wrong line.
//
// `computeStepLine` mirrors `RobotEditor.vue::serializeFormToRobot`
// line-for-line so the result is identical to the line the step would
// occupy if the form were saved right now. Pure function, no side
// effects, easy to unit-test in isolation.

/** Number of source lines a multiline-`...`-continued setting occupies. */
function _multilineLineCount(value: string): number {
  if (!value) return 0
  return value.split('\n').length
}

/** True iff the running emit-buffer's last line is non-empty (so the
 *  serializer would prepend a blank before the next section header). */
function _trailingNonBlank(lastLine: string | undefined): boolean {
  return lastLine !== undefined && lastLine !== ''
}

/**
 * Returns the 1-based source line where `form.testCases[testCaseIndex]
 * .steps[stepIndex]` would land if the form were serialised right now,
 * or ``null`` when the indices are out of range or the file is
 * resource-only.
 *
 * Mirrors ``serializeFormToRobot`` exactly — every change to the
 * serializer must be reflected here, otherwise the "Run up to here"
 * button breaks at the wrong line. Pinned by tests in
 * ``components/FlowEditorComputeStepLine.spec.ts``.
 */
export function computeStepLine(
  form: RobotForm,
  isResource: boolean,
  testCaseIndex: number,
  stepIndex: number,
): number | null {
  if (isResource) return null
  if (testCaseIndex < 0 || testCaseIndex >= form.testCases.length) return null
  const tc = form.testCases[testCaseIndex]
  if (stepIndex < 0 || stepIndex >= tc.steps.length) return null

  // Walk the same emit pipeline as the serializer. We only track the
  // running line count + the last line's blank-ness; we don't need
  // the actual string content.
  let line = 0
  let lastLine: string | undefined

  // Preamble.
  for (const pl of form.preambleLines) {
    line += 1
    lastLine = pl
  }

  // Settings.
  if (form.settings.length > 0) {
    if (line > 0 && _trailingNonBlank(lastLine)) {
      line += 1
      lastLine = ''
    }
    line += 1
    lastLine = '*** Settings ***'
    for (const s of form.settings) {
      if (s.key === '#') {
        line += 1
        lastLine = s.value
        continue
      }
      const span = s.value && s.value.includes('\n')
        ? _multilineLineCount(s.value)
        : 1
      line += span
      lastLine = 'set'
    }
  }

  // Variables.
  if (form.variables.length > 0) {
    if (line > 0 && _trailingNonBlank(lastLine)) {
      line += 1
      lastLine = ''
    }
    line += 1
    lastLine = '*** Variables ***'
    for (const v of form.variables) {
      line += 1
      lastLine = v.name === '#' ? v.value : v.name
    }
  }

  // Test cases. (Resource files were rejected at the top.)
  if (form.testCases.length > 0) {
    if (line > 0 && _trailingNonBlank(lastLine)) {
      line += 1
      lastLine = ''
    }
    line += 1
    lastLine = '*** Test Cases ***'
    for (let tcIdx = 0; tcIdx < form.testCases.length; tcIdx++) {
      const cur = form.testCases[tcIdx]
      // test name
      line += 1
      // metadata lines emitted in the serializer order
      if (cur.documentation) line += _multilineLineCount(cur.documentation)
      if (cur.tags.length > 0) line += 1
      if (cur.setup) line += 1
      if (cur.teardown) line += 1
      if (cur.timeout) line += 1
      if (cur.template) line += 1

      // We're now at the line BEFORE the first step body. Steps fill
      // line+1 .. line+steps.length.
      if (tcIdx === testCaseIndex) {
        return line + stepIndex + 1
      }

      line += cur.steps.length
      // Trailing blank between test cases.
      line += 1
      lastLine = ''
    }
  }

  return null
}
