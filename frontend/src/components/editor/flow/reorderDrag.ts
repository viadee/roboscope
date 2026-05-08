/**
 * Shared constants for the FlowEditor reorder drag-and-drop UX.
 *
 * Why a shared module: KeywordNode and ControlNode both gate the
 * native HTML5 `draggable` attribute on a hold timer so a brief click
 * on the drag handle doesn't accidentally start a reorder. Both
 * components agree on the timer length here so the UX feels uniform
 * across keyword and control-flow steps.
 */

/**
 * Time the user has to hold the drag handle before native drag arms.
 * Tap-and-release before this elapses cancels — no reorder is started.
 *
 * 200 ms is comfortably above the typical accidental-click duration
 * (60–120 ms) and well below the threshold at which "press-and-hold"
 * starts to feel slow to a deliberate user.
 */
export const DRAG_ARM_DELAY_MS = 200
