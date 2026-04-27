# Story EDITOR-8: Bugfix — flow node overlaps next node when arg count grows

Status: done

Epic: EDITOR — Visual Flow Editor usability for non-developers
Story Key: `editor-8-flow-node-overlap-on-many-args`

## Reported

> Wenn ich im Flow-Editor zu viele Argumente habe, wird das Element so groß, dass es über das Folgeelement geht. Es soll immer der gleiche vertikale Abstand zwischen dem unteren Rand des vorherigen Keyword zum oberen Rand des folgenden Keyword bestehen.

## Root cause

`flowConverter.ts:estimateNodeHeight()` computed `rows = Math.ceil(step.args.length / 3)` — assuming three arg chips fit per visual row. The actual `KeywordNode.vue` rendered chips with `flex-wrap: wrap` and a per-chip `max-width: 200px`. Long selector values (`text=de‪Deutsch‬…`, `xpath=/html/body/…`) take a full row each, so the rendered height was up to 3× the estimate. Vue Flow uses our pre-computed `node.position.y` values literally — there's no post-render re-layout — so taller-than-estimated nodes overflowed into the gap meant for the next node.

## Fix

Two coordinated changes so the layout estimator always matches reality:

1. **`KeywordNode.vue`** — `.flow-node-args` switched from `flex-wrap: wrap` (multi-chip rows) to `flex-direction: column` (one chip per row). Predictable 22px per arg, regardless of value width.
2. **`flowConverter.ts:estimateNodeHeight`** — `rows = step.args.length` (was `ceil(args/3)`).

The vertical gap between every two consecutive keyword nodes is now constant (`NODE_GAP = 50px` between the bottom of one node and the top of the next) and independent of either node's arg count.

## Trade-off

Single-arg and double-arg nodes now use 1 / 2 stacked rows instead of 1 / 1 wrapped row. Slightly taller for the common case, but visually clearer (the eye reads "selector / button" easier than "selector button"). The total canvas height for typical recordings goes up by ~20px per multi-arg node — negligible against the canvas's auto-fit zoom.

## Verification

- 297-case Vitest suite still green.
- Manual smoke: open `recording.robot` in the flow tab → all four nodes render with consistent gaps; bumping a step's args list to 5+ entries no longer overlaps the next node.
- vue-tsc: no new errors.

## Out of scope

- Post-render measurement (using ResizeObserver or `node:dimensions-changed` to true-up positions from actual DOM heights). That's the proper long-term solution; the current fix avoids the failure mode without the complexity of an observer-driven re-layout pass.
