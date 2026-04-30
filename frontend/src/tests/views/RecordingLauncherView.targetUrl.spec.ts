/**
 * RecordingLauncherView — target-URL field contract.
 *
 * The validation + stash logic lives inside the view's <script setup>
 * and isn't directly importable. Mirrors verbatim — same pattern as
 * RecordingLiveView.deleteCommand.spec.ts. The contract:
 *
 *   1. Validation message fires only for non-empty values that
 *      DON'T start with http:// or https://. Empty / whitespace-only
 *      counts as "no URL" and never errors.
 *   2. The Start button's `canStart` check requires
 *      targetUrlError === null, so a malformed URL disables the
 *      button instead of letting a 400 round-trip happen.
 *   3. On Start, the trimmed URL is stashed in sessionStorage at
 *      `recorder.url.<sessionId>`. Empty trims aren't stashed —
 *      the live view reads `null` and falls through to about:blank.
 *
 * If any of those drift, the security validation (commit d7c7f19)
 * still backstops the backend, but the UX message would point the
 * wrong way.
 */
import { describe, it, expect, beforeEach } from 'vitest'

// Mirror of RecordingLauncherView's `targetUrlError` computed.
const TARGET_URL_INVALID_MSG = 'URL must start with http:// or https://'

function targetUrlError(targetUrl: string): string | null {
  const v = targetUrl.trim()
  if (v === '') return null
  if (v.startsWith('http://') || v.startsWith('https://')) return null
  return TARGET_URL_INVALID_MSG
}

// Mirror of `canStart` (just the URL-related portion).
function canStart(opts: {
  transport: string
  repoId: number | null
  starting: boolean
  targetUrl: string
}): boolean {
  return (
    !!opts.transport
    && opts.repoId !== null
    && !opts.starting
    && targetUrlError(opts.targetUrl) === null
  )
}

// Mirror of the launch-time stash logic.
function stashTargetUrl(sessionId: number, targetUrl: string): string | null {
  const trimmed = targetUrl.trim()
  if (trimmed) {
    sessionStorage.setItem(`recorder.url.${sessionId}`, trimmed)
    return trimmed
  }
  return null
}

beforeEach(() => {
  sessionStorage.clear()
})

describe('targetUrlError — inline validation', () => {
  it('passes empty input', () => {
    expect(targetUrlError('')).toBeNull()
  })

  it('passes whitespace-only input as a no-op', () => {
    expect(targetUrlError('   \t\n  ')).toBeNull()
  })

  it('passes http:// URLs', () => {
    expect(targetUrlError('http://internal.example/')).toBeNull()
  })

  it('passes https:// URLs', () => {
    expect(targetUrlError('https://example.com/path?q=1')).toBeNull()
  })

  it('passes URLs with leading/trailing whitespace (trimmed first)', () => {
    expect(targetUrlError('  https://example.com  ')).toBeNull()
  })

  it.each([
    ['javascript:alert(1)'],
    ['file:///etc/passwd'],
    ['ftp://server/'],
    ['data:text/html,<p>x</p>'],
    ['mailto:user@example.com'],
    ['not-a-url'],
    ['//missing-scheme.example.com'],
    ['HTTP://example.com'],  // case-sensitive — matches backend's startswith()
  ])('flags %s as invalid', (bad) => {
    expect(targetUrlError(bad)).toBe(TARGET_URL_INVALID_MSG)
  })
})

describe('canStart — Start button gating', () => {
  const baseOpts = {
    transport: 'web_playwright',
    repoId: 1 as number | null,
    starting: false,
    targetUrl: '',
  }

  it('enables for a valid URL', () => {
    expect(canStart({ ...baseOpts, targetUrl: 'https://example.com' })).toBe(true)
  })

  it('enables for an empty URL', () => {
    expect(canStart({ ...baseOpts, targetUrl: '' })).toBe(true)
  })

  it('disables for an invalid URL', () => {
    expect(canStart({ ...baseOpts, targetUrl: 'javascript:foo' })).toBe(false)
  })

  it('still disables on missing repo even with a valid URL', () => {
    expect(canStart({ ...baseOpts, repoId: null, targetUrl: 'https://x' })).toBe(false)
  })

  it('disables while a request is in flight', () => {
    expect(canStart({ ...baseOpts, starting: true, targetUrl: 'https://x' })).toBe(false)
  })
})

describe('stashTargetUrl — sessionStorage hand-off to the live view', () => {
  it('stashes the trimmed URL under recorder.url.<id>', () => {
    stashTargetUrl(42, 'https://example.com/')
    expect(sessionStorage.getItem('recorder.url.42')).toBe('https://example.com/')
  })

  it('does NOT stash anything for an empty input', () => {
    stashTargetUrl(42, '')
    expect(sessionStorage.getItem('recorder.url.42')).toBeNull()
  })

  it('does NOT stash anything for a whitespace-only input', () => {
    stashTargetUrl(42, '   ')
    expect(sessionStorage.getItem('recorder.url.42')).toBeNull()
  })

  it('strips leading/trailing whitespace before stashing', () => {
    stashTargetUrl(42, '  https://example.com/  ')
    expect(sessionStorage.getItem('recorder.url.42')).toBe('https://example.com/')
  })

  it('keys by session id so two concurrent launches do not collide', () => {
    stashTargetUrl(42, 'https://a.example/')
    stashTargetUrl(43, 'https://b.example/')
    expect(sessionStorage.getItem('recorder.url.42')).toBe('https://a.example/')
    expect(sessionStorage.getItem('recorder.url.43')).toBe('https://b.example/')
  })
})
