/**
 * Story: Flow Editor — Verification & Hardening (libdoc-per-environment).
 * preloadKeywords must be offline-first: prefer the env libdoc endpoint, fall
 * back to rf-knowledge when it's unavailable / still building.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/ai.api', () => ({
  searchKeywords: vi.fn(),
  invalidateKeywordCache: vi.fn(),
}))
vi.mock('@/api/environments.api', () => ({
  getEnvironmentKeywords: vi.fn(),
}))

import { searchKeywords } from '@/api/ai.api'
import { getEnvironmentKeywords } from '@/api/environments.api'
import { useExplorerStore } from '@/stores/explorer.store'
import { useEnvironmentsStore } from '@/stores/environments.store'

const mockedSearch = searchKeywords as unknown as ReturnType<typeof vi.fn>
const mockedEnvKw = getEnvironmentKeywords as unknown as ReturnType<typeof vi.fn>

function seedDefaultEnv(id = 5) {
  const envs = useEnvironmentsStore()
  // Only the fields resolveEnvironmentId reads matter.
  envs.environments.push({ id, is_default: true } as never)
}

describe('explorer.store preloadKeywords — offline-first', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedSearch.mockReset()
    mockedEnvKw.mockReset()
  })

  it('uses libdoc-per-environment keywords when the endpoint is ready', async () => {
    seedDefaultEnv(5)
    mockedEnvKw.mockResolvedValue({
      status: 'ready', source_hash: 'h', updated_at: null,
      keywords: [{ name: 'Click', library: 'Browser', args: ['selector'], shortdoc: 'Click it' }],
    })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    expect(mockedEnvKw).toHaveBeenCalledWith(5)
    expect(mockedSearch).not.toHaveBeenCalled()
    expect(explorer.keywords[0]).toMatchObject({ name: 'Click', library: 'Browser', args: ['selector'] })
    expect(explorer.keywordsLoaded).toBe(true)
  })

  it('falls back to rf-knowledge when the env cache is still building/empty', async () => {
    seedDefaultEnv(5)
    mockedEnvKw.mockResolvedValue({ status: 'building', source_hash: '', updated_at: null, keywords: [] })
    mockedSearch.mockResolvedValue({ results: [{ name: 'Log', library: 'BuiltIn', args: ['message'] }] })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    expect(mockedSearch).toHaveBeenCalledWith('*', 1)
    expect(explorer.keywords[0]).toMatchObject({ name: 'Log', library: 'BuiltIn' })
  })

  it('falls back to rf-knowledge when no environment is resolvable', async () => {
    // no default env seeded → resolveEnvironmentId returns null
    mockedSearch.mockResolvedValue({ results: [{ name: 'Sleep', library: 'BuiltIn', args: ['time'] }] })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    expect(mockedEnvKw).not.toHaveBeenCalled()
    expect(mockedSearch).toHaveBeenCalledWith('*', 1)
    expect(explorer.keywords[0].name).toBe('Sleep')
  })

  it('falls back to rf-knowledge when the env endpoint throws', async () => {
    seedDefaultEnv(7)
    mockedEnvKw.mockRejectedValue(new Error('503'))
    mockedSearch.mockResolvedValue({ results: [{ name: 'Log', library: 'BuiltIn', args: [] }] })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    expect(mockedSearch).toHaveBeenCalled()
    expect(explorer.keywords[0].name).toBe('Log')
  })
})
