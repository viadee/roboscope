/**
 * Mirror of `backend/src/recording/robot_emit.py::_emit_command`'s
 * selector composition so the Live recorder view can show what the
 * .robot file is ACTUALLY going to contain, not just the raw inner
 * candidate the picker is sitting on.
 *
 * User pain point: the live view shows `text="Zustimmen"` next to
 * a `⇣ cmp.heise.de` chip, but the saved .robot is
 * `Click  iframe#sp_message_… >>> text="Zustimmen" >> nth=0`.
 * Two different mental models. This util produces the composed form
 * so what-you-see matches what-gets-saved.
 *
 * Kept narrow + pure so a vitest can pin the equivalence against
 * the Python emitter via the schema fixtures.
 */
import type { RecordedCommand, SelectorCandidate } from '@/types/recorder.types'

const RISKY_UNVERIFIED_STRATEGIES = new Set(['text', 'css', 'role', 'aria'])

function isAlreadyDisambiguated(value: string): boolean {
  return (
    value.includes('>> nth=')
    || value.includes(':nth-match(')
    || value.includes(':nth-of-type(')
    || value.includes('>>>')
    || value.includes('>>')
  )
}

/**
 * Render the on-disk form of one selector candidate, mirroring the
 * emitter's `_render_selector`:
 *   - `xpath` → `xpath=<value>`
 *   - `text` → `text=<value>` if not already prefixed
 *   - everything else (css, testid, aria, pw_locator) → verbatim
 * Then apply defensive disambiguation `>> nth=0` for unverified
 * risky-strategy candidates (text / generic css without `#` /
 * role / aria). Mirrors the Python `_RISKY_UNVERIFIED_STRATEGIES`
 * + `_is_already_disambiguated` logic exactly.
 */
export function renderSelector(cand: SelectorCandidate): string {
  let out: string
  if (cand.strategy === 'xpath') {
    out = `xpath=${cand.value}`
  } else if (cand.strategy === 'text') {
    out = cand.value.startsWith('text=') ? cand.value : `text=${cand.value}`
  } else {
    out = cand.value
  }
  if (
    !cand.verified_unique
    && RISKY_UNVERIFIED_STRATEGIES.has(cand.strategy)
    && !isAlreadyDisambiguated(out)
    // CSS selectors with an id are unique enough that wrapping is
    // overkill (`#login-form` rarely matches multiple elements).
    && !(cand.strategy === 'css' && cand.value.includes('#'))
  ) {
    out = `${out} >> nth=0`
  }
  return out
}

function iframeLocatorFromUrl(frameUrl: string): string | null {
  try {
    const u = new URL(frameUrl)
    const host = u.host
    if (!host) return null
    return `iframe[src*="${host}"]`
  } catch {
    return null
  }
}

/**
 * Compose the iframe-wrapper portion of a cross-frame Browser-library
 * locator from `cmd.frame_chain`. Picks each rung's
 * `selector_candidates[0]` (which is already pre-sorted by
 * verified_unique DESC + qs DESC on the server side). Empty rungs
 * fall back to their own URL's `iframe[src*="<host>"]`.
 *
 * Returns `null` when there's no chain — caller falls back to
 * `iframeLocatorFromUrl(cmd.frame_url)` for legacy sidecars.
 */
export function iframeChainPrefix(cmd: RecordedCommand): string | null {
  if (!cmd.frame_chain || cmd.frame_chain.length === 0) return null
  const pieces: string[] = []
  for (const rung of cmd.frame_chain) {
    if (rung.selector_candidates && rung.selector_candidates.length > 0) {
      pieces.push(rung.selector_candidates[0].value)
    } else {
      const fallback = rung.url ? iframeLocatorFromUrl(rung.url) : null
      if (fallback === null) {
        // No URL either — can't safely compose a partial chain.
        return null
      }
      pieces.push(fallback)
    }
  }
  return pieces.join(' >>> ')
}

/**
 * Compose the effective selector for ONE specific candidate within
 * a command's iframe context. Inner half = `renderSelector(cand)`
 * (with defensive disambiguation); outer half = the command's
 * iframe chain prefix or its URL-derived fallback. The picker uses
 * this to show "if I picked THIS row, what'd the .robot say" for
 * each alternative — otherwise the user only sees the raw inner
 * value and can't compare which alternative will actually run
 * cleanly under Browser library's strict mode.
 */
export function effectiveSelectorForCandidate(
  cmd: RecordedCommand,
  cand: SelectorCandidate,
): string {
  // User-supplied verbatim override — short-circuit BEFORE any
  // composition so the picker display, the swap-write into
  // `step.args[0]`, the custom-value detector and the Python
  // emitter all agree on the same string. Empty-string override
  // is treated as "no override" (cleared via the edit form).
  if (cand.effective_override != null && cand.effective_override.trim() !== '') {
    return cand.effective_override
  }
  const inner = renderSelector(cand)
  const chainPrefix = iframeChainPrefix(cmd)
  if (chainPrefix !== null) {
    return `${chainPrefix} >>> ${inner}`
  }
  if (cmd.frame_url) {
    const legacy = iframeLocatorFromUrl(cmd.frame_url)
    if (legacy !== null) {
      return `${legacy} >>> ${inner}`
    }
  }
  return inner
}

/**
 * Return the full effective selector string for one recorded command
 * — the exact text the emitter writes into the .robot file as the
 * keyword's first argument. Used by the live view to show
 * what-you-get instead of just the raw inner candidate.
 */
export function effectiveSelector(cmd: RecordedCommand): string {
  const cands = cmd.selector_candidates ?? []
  if (cands.length === 0) return ''
  const idx = cmd.active_candidate_index ?? 0
  const active = cands[idx] ?? cands[0]
  return effectiveSelectorForCandidate(cmd, active)
}
