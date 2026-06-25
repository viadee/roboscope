import { describe, it, expect, vi, beforeEach } from 'vitest'

const { getFeatures } = vi.hoisted(() => ({ getFeatures: vi.fn() }))
vi.mock('@/api/governance.api', () => ({ getFeatures }))

import { useFeatureFlags } from '@/composables/useFeatureFlags'

// localStorage is a vi.fn() mock in src/tests/setup.ts — drive getItem directly.
function setToken(token: string | null) {
  vi.mocked(localStorage.getItem).mockReturnValue(token)
}

describe('useFeatureFlags', () => {
  beforeEach(() => {
    getFeatures.mockReset()
    setToken(null)
  })

  it('does NOT fetch when there is no access token (redirect-loop guard)', async () => {
    setToken(null)
    const ff = useFeatureFlags()
    await ff.refresh()
    expect(getFeatures).not.toHaveBeenCalled()
  })

  it('reflects disabled + locked flags after refresh', async () => {
    setToken('x')
    getFeatures.mockResolvedValue({
      flags: { packageManagement: false },
      locked: { packageManagement: true },
    })
    const ff = useFeatureFlags()
    await ff.refresh()
    expect(getFeatures).toHaveBeenCalled()
    expect(ff.isEnabled('packageManagement')).toBe(false)
    expect(ff.isLocked('packageManagement')).toBe(true)
  })

  it('defaults to enabled for an unknown flag', async () => {
    setToken('x')
    getFeatures.mockResolvedValue({ flags: { packageManagement: true }, locked: {} })
    const ff = useFeatureFlags()
    await ff.refresh()
    expect(ff.isEnabled('someUnknownFlag')).toBe(true)
  })

  it('degrades to enabled when the fetch fails (server still enforces)', async () => {
    setToken('x')
    getFeatures.mockRejectedValue(new Error('500'))
    const ff = useFeatureFlags()
    await ff.refresh()
    expect(ff.isEnabled('aFreshFlagName')).toBe(true)
  })
})
