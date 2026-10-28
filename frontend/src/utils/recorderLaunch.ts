/**
 * Pure helpers of RecordingLauncherView — kept out of the SFC so the unit
 * spec tests the real code.
 */

/** Scheme guard mirrored from the backend's `v2_start_browser`: http(s) only, empty = about:blank. */
export function isValidTargetUrl(raw: string): boolean {
  const v = raw.trim()
  return v === '' || v.startsWith('http://') || v.startsWith('https://')
}

/** Hand the trimmed target URL to the live view via sessionStorage; returns what was stashed. */
export function stashTargetUrl(sessionId: number, raw: string): string | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  sessionStorage.setItem(`recorder.url.${sessionId}`, trimmed)
  return trimmed
}
