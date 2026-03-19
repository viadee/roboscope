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
  testCaseIndex: number
  stepIndex: number
}

// --- Layout constants ---

const NODE_SPACING_Y = 80
const NODE_START_Y = 60
const NODE_X = 250

// --- Converter: RobotTestCase → Nodes + Edges ---

export function testCaseToFlow(
  tc: RobotTestCase,
  testCaseIndex: number,
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []
  const prefix = `tc${testCaseIndex}`

  // Start node
  nodes.push({
    id: `${prefix}-start`,
    type: 'start',
    position: { x: NODE_X, y: 0 },
    data: { label: tc.name },
  })

  let prevId = `${prefix}-start`
  let y = NODE_START_Y

  for (let i = 0; i < tc.steps.length; i++) {
    const step = tc.steps[i]
    // Skip 'end' steps — they're implicit in the visual graph
    if (step.type === 'end') continue

    const nodeId = `${prefix}-step-${i}`
    const nodeType = getNodeType(step.type)
    const label = getStepLabel(step)

    nodes.push({
      id: nodeId,
      type: nodeType,
      position: { x: NODE_X, y },
      data: {
        label,
        stepType: step.type,
        step: { ...step },
        testCaseIndex,
        stepIndex: i,
      } as FlowNodeData,
    })

    // Edge from previous node
    const edgeLabel = getEdgeLabel(step, tc.steps[i - 1])
    edges.push({
      id: `${prefix}-e-${prevId}-${nodeId}`,
      source: prevId,
      target: nodeId,
      animated: step.type === 'if' || step.type === 'for' || step.type === 'try',
      label: edgeLabel,
    })

    prevId = nodeId
    y += NODE_SPACING_Y
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

  return { nodes, edges }
}

// --- Converter: Full RobotForm → Nodes + Edges (all test cases) ---

export function robotFormToFlow(form: RobotForm): { nodes: Node[]; edges: Edge[] } {
  const allNodes: Node[] = []
  const allEdges: Edge[] = []

  for (let i = 0; i < form.testCases.length; i++) {
    const { nodes, edges } = testCaseToFlow(form.testCases[i], i)
    // Offset X for multiple test cases side by side
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
  const tc = form.testCases[nodeData.testCaseIndex]
  if (!tc) return
  const step = tc.steps[nodeData.stepIndex]
  if (!step) return

  // Copy edited fields back
  Object.assign(step, nodeData.step)
}

// --- Helpers ---

function getNodeType(stepType: StepType): string {
  switch (stepType) {
    case 'if':
    case 'else_if':
    case 'else':
    case 'for':
    case 'while':
    case 'try':
    case 'except':
    case 'finally':
      return 'control'
    case 'assignment':
      return 'assignment'
    case 'comment':
      return 'comment'
    case 'return':
    case 'break':
    case 'continue':
      return 'flow-control'
    default:
      return 'keyword'
  }
}

function getStepLabel(step: RobotStep): string {
  switch (step.type) {
    case 'keyword':
      return step.keyword || 'Keyword'
    case 'assignment':
      return `${step.returnVars.join(', ')} = ${step.keyword}`
    case 'if':
      return `IF  ${step.condition}`
    case 'else_if':
      return `ELSE IF  ${step.condition}`
    case 'else':
      return 'ELSE'
    case 'for':
      return `FOR ${step.loopVar} ${step.loopFlavor} ${step.loopValues.join('  ')}`
    case 'while':
      return `WHILE  ${step.condition}`
    case 'try':
      return 'TRY'
    case 'except':
      return step.exceptPattern ? `EXCEPT  ${step.exceptPattern}` : 'EXCEPT'
    case 'finally':
      return 'FINALLY'
    case 'return':
      return `RETURN  ${step.args.join('  ')}`
    case 'break':
      return 'BREAK'
    case 'continue':
      return 'CONTINUE'
    case 'comment':
      return `# ${step.comment}`
    case 'var':
      return `VAR ${step.keyword} = ${step.args.join('  ')}`
    default:
      return step.keyword || step.type
  }
}

function getEdgeLabel(step: RobotStep, prevStep?: RobotStep): string | undefined {
  if (step.type === 'else') return 'false'
  if (step.type === 'else_if') return 'false'
  if (prevStep?.type === 'if' || prevStep?.type === 'else_if') return 'true'
  return undefined
}
