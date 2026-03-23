/**
 * Converts between RobotForm AST and Vue Flow graph (nodes + edges).
 *
 * RobotForm → { nodes, edges }  (for rendering)
 * User edits graph → updated nodes/edges → RobotForm  (for serialization back to .robot)
 */

import type { Node, Edge } from '@vue-flow/core'

// --- Types matching RobotEditor.vue ---

export type StepType =
  | 'keyword' | 'assignment' | 'var' | 'for' | 'end' | 'if' | 'else_if' | 'else'
  | 'while' | 'try' | 'except' | 'finally' | 'break' | 'continue' | 'return' | 'comment'

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
}

// --- Layout constants ---

export const NODE_GAP = 50
export const NODE_START_Y = 60
export const NODE_X = 0
export const NODE_SPACING_Y = 80 // backward compat
const FRAME_PAD_X = 30
const FRAME_PAD_TOP = 12
const FRAME_PAD_BOTTOM = 16

// --- Node height estimation ---

const START_END_HEIGHT = 32
const NODE_BASE_HEIGHT = 44

function estimateNodeHeight(step: RobotStep): number {
  const type = getNodeType(step.type)
  if (type === 'start' || type === 'end') return START_END_HEIGHT
  let h = NODE_BASE_HEIGHT
  if (type === 'keyword' || type === 'assignment') {
    if (step.args.length > 0) {
      const rows = Math.ceil(step.args.length / 3)
      h += 4 + rows * 22
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
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  // Start node
  nodes.push({
    id: `${prefix}-start`,
    type: 'start',
    position: { x: NODE_X, y: 0 },
    data: { label: name },
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
        step: { ...step },
        section,
        sectionIndex,
        stepIndex: i,
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

  // End node
  const endId = `${prefix}-end`
  nodes.push({
    id: endId,
    type: 'end',
    position: { x: NODE_X, y },
    data: { label: 'END' },
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

/** Convert a single test case to flow graph. */
export function testCaseToFlow(
  tc: RobotTestCase, index: number,
): { nodes: Node[]; edges: Edge[] } {
  return stepsToFlow(tc.steps, tc.name, `tc${index}`, 'testcase', index)
}

/** Convert a single keyword definition to flow graph. */
export function keywordDefToFlow(
  kw: RobotKeywordDef, index: number,
): { nodes: Node[]; edges: Edge[] } {
  return stepsToFlow(kw.steps, kw.name, `kw${index}`, 'keyword', index)
}

// --- Converter: Full RobotForm → Nodes + Edges ---

export function robotFormToFlow(form: RobotForm): { nodes: Node[]; edges: Edge[] } {
  const allNodes: Node[] = []
  const allEdges: Edge[] = []
  for (let i = 0; i < form.testCases.length; i++) {
    const { nodes, edges } = testCaseToFlow(form.testCases[i], i)
    const xOffset = i * 500
    for (const node of nodes) {
      node.position.x += xOffset
      allNodes.push(node)
    }
    allEdges.push(...edges)
  }
  return { nodes: allNodes, edges: allEdges }
}

/** Convert all keyword definitions to flow. */
export function robotKeywordsToFlow(form: RobotForm): { nodes: Node[]; edges: Edge[] } {
  const allNodes: Node[] = []
  const allEdges: Edge[] = []
  for (let i = 0; i < form.keywords.length; i++) {
    const { nodes, edges } = keywordDefToFlow(form.keywords[i], i)
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
    case 'return': case 'break': case 'continue':
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
