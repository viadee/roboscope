# Story EDITOR-13: Bugfix — Start/End nodes blank-page on click

Status: done

Epic: EDITOR — Visual Flow Editor usability
Story Key: `editor-13-start-end-node-blank-page`

## Reported

> Wenn ich im Flow Editor auf das Start oder End Element drücke, wechselt er auf eine neue Seite, die nur weiß ist.

## Root cause

Vue Flow emits `node-click` for every node, including the terminal Start / End nodes that `flowConverter.stepsToFlow()` synthesises with `data: { label }` only — no `step`, no `stepType`, no `argSpecs`. The detail panel template renders:

    <h4>{{ selectedNodeData.stepType.toUpperCase().replace('_', ' ') }}</h4>

`selectedNodeData.stepType` is `undefined` for terminal nodes; the `.toUpperCase()` throws a TypeError, Vue's render error propagates, and the FlowEditor sub-tree unmounts — which, inside the `RobotEditor` wrapper, manifests as a blank page until the user navigates back.

## Fix

`onNodeClick` short-circuits for `event.node.type === 'start' | 'end'` and clears `selectedNode` so the detail panel doesn't render at all. Terminal nodes are visual cues only, never editable.

## Acceptance Criteria

- [x] Clicking Start or End in the visual flow editor does NOT throw or unmount.
- [x] No detail panel opens for Start / End — they have nothing editable.
- [x] Existing keyword/control-node click behaviour is preserved.
- [x] 352 / 352 Vitest still green.

## Out of scope

- Showing read-only meta about the start node (testcase / keyword name) — could be a follow-up if useful.
