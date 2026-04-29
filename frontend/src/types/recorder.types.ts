/**
 * Story S.1 — Recorder v2 shared selector + command datamodel.
 *
 * Frontend-canonical TypeScript types. Must round-trip losslessly with
 * the Pydantic definitions in `backend/src/recording/selector_schema.py`.
 */

export type SelectorStrategy =
  | 'testid'
  | 'aria'
  | 'text'
  | 'css'
  | 'xpath'
  | 'pw_locator'
  | 'automation_id'
  | 'uia_name'
  | 'uia_class_name'

export type RecordingTransport =
  | 'chrome_extension'
  | 'web_playwright'
  | 'desktop_windows'
  | 'desktop_macos'

export const RECORDER_SCHEMA_VERSION = 1

export interface SelectorCandidate {
  strategy: SelectorStrategy
  value: string
  /** 0–100 — higher = more stable. See architecture doc AR-7 scoring rubric. */
  quality_score: number
  verified_unique: boolean
}

export interface RecordedCommand {
  /**
   * Story RECORDER-IDMAP — position-independent command id. The
   * emitter writes this as a trailing `# rbs:<id>` comment on the
   * `.robot` line so the FlowEditor can re-link selector groups to
   * their step even after reorder / insert / delete in the visual
   * editor. Optional for backwards compatibility with sidecars
   * recorded before the field shipped — the FlowEditor falls back
   * to positional matching when the id is missing.
   */
  id?: string
  index: number
  /** Robot Framework keyword name — e.g. "Click", "Type Text", "Get Element Value". */
  keyword: string
  /** Keyword-specific non-selector args (expected value, wait timeout, etc.). */
  args: Record<string, unknown>
  /**
   * Sorted by `(verified_unique DESC, quality_score DESC)`.
   * Empty list only for commands that target no element (e.g. `Go To <url>`).
   */
  selector_candidates: SelectorCandidate[]
  /** Index into selector_candidates; 0 by default. */
  active_candidate_index: number
  /**
   * Story SH-3 — element fingerprint captured at record-time for the
   * runtime self-healing fallback. Opaque shape used by the heal
   * library; the UI never reads it.
   */
  element_fingerprint?: Record<string, unknown> | null
  /**
   * Story RECORDER-FRAMES — origin frame URL for events captured in
   * a cross-origin iframe (Sourcepoint / OneTrust consent banners,
   * OAuth widgets). Top-frame events have this null. The .robot
   * emitter wraps the selector with `iframe[src*="<host>"] >>> …`
   * when set.
   */
  frame_url?: string | null
}

export interface RecordedFlow {
  schema_version: number
  transport: RecordingTransport
  session_id: string
  name?: string | null
  commands: RecordedCommand[]
}

/** Throw if `flow` was written by a newer (unknown) schema version. */
export function validateSchemaVersion(flow: { schema_version?: unknown }): void {
  const v = flow.schema_version
  if (v === undefined || v === null) {
    throw new Error('RecordedFlow missing schema_version')
  }
  if (typeof v !== 'number' || !Number.isInteger(v)) {
    throw new Error(`RecordedFlow schema_version must be integer, got ${typeof v}`)
  }
  if (v > RECORDER_SCHEMA_VERSION) {
    throw new Error(
      `RecordedFlow schema_version ${v} newer than supported ${RECORDER_SCHEMA_VERSION}. Upgrade RoboScope.`,
    )
  }
  if (v < 1) {
    throw new Error(`RecordedFlow schema_version must be >= 1, got ${v}`)
  }
}

/** Return the currently-selected locator string, or null for no-target commands. */
export function activeSelector(cmd: RecordedCommand): SelectorCandidate | null {
  if (cmd.selector_candidates.length === 0) return null
  return cmd.selector_candidates[cmd.active_candidate_index] ?? null
}
