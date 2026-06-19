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

// Quiet/cached keyword loading (spec-keyword-loading-quiet-and-cached) — a plain
// file switch must NOT refetch; keyword data is repo-scoped and idempotent.
describe('explorer.store preloadKeywords — repo-scoped idempotency', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedSearch.mockReset()
    mockedEnvKw.mockReset()
  })

  it('does not refetch when keywords are already loaded for the same repo', async () => {
    seedDefaultEnv(5)
    mockedEnvKw.mockResolvedValue({
      status: 'ready', source_hash: 'h', updated_at: null,
      keywords: [{ name: 'Click', library: 'Browser', args: ['selector'], shortdoc: '' }],
    })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    expect(explorer.keywordsRepoId).toBe(1)
    expect(mockedEnvKw).toHaveBeenCalledTimes(1)

    // Simulate file switches within the same repo — must be a no-op.
    await explorer.preloadKeywords(1)
    await explorer.preloadKeywords(1)
    expect(mockedEnvKw).toHaveBeenCalledTimes(1)
    expect(mockedSearch).not.toHaveBeenCalled()
  })

  it('does load again when switching to a different repo', async () => {
    seedDefaultEnv(5)
    mockedEnvKw.mockResolvedValue({
      status: 'ready', source_hash: 'h', updated_at: null,
      keywords: [{ name: 'Click', library: 'Browser', args: [], shortdoc: '' }],
    })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    await explorer.preloadKeywords(2)
    expect(mockedEnvKw).toHaveBeenCalledTimes(2)
    expect(explorer.keywordsRepoId).toBe(2)
  })

  it('refreshKeywords forces a reload even for the same repo', async () => {
    seedDefaultEnv(5)
    mockedEnvKw.mockResolvedValue({
      status: 'ready', source_hash: 'h', updated_at: null,
      keywords: [{ name: 'Click', library: 'Browser', args: [], shortdoc: '' }],
    })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    expect(mockedEnvKw).toHaveBeenCalledTimes(1)
    await explorer.refreshKeywords(1)
    expect(mockedEnvKw).toHaveBeenCalledTimes(2)
  })

  it('services the latest repo when switched mid-load (no dropped repo)', async () => {
    seedDefaultEnv(5)
    let resolveA!: (v: unknown) => void
    const aPending = new Promise((r) => { resolveA = r })
    mockedEnvKw
      .mockReturnValueOnce(aPending) // repo 1 — stays in-flight
      .mockResolvedValue({
        status: 'ready', source_hash: 'h', updated_at: null,
        keywords: [{ name: 'FromRepoTwo', library: 'L', args: [], shortdoc: '' }],
      })
    const explorer = useExplorerStore()
    const p1 = explorer.preloadKeywords(1) // in-flight
    explorer.preloadKeywords(2)            // queued as pending (not dropped)
    resolveA({
      status: 'ready', source_hash: 'h', updated_at: null,
      keywords: [{ name: 'FromRepoOne', library: 'L', args: [], shortdoc: '' }],
    })
    await p1
    await new Promise((r) => setTimeout(r, 0)) // let the re-run settle
    expect(explorer.keywordsRepoId).toBe(2)
    expect(explorer.keywords[0].name).toBe('FromRepoTwo')
  })

  it('clears the repo anchor when a load fails', async () => {
    seedDefaultEnv(5)
    mockedEnvKw.mockResolvedValueOnce({
      status: 'ready', source_hash: 'h', updated_at: null,
      keywords: [{ name: 'Click', library: 'Browser', args: [], shortdoc: '' }],
    })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    expect(explorer.keywordsRepoId).toBe(1)
    // Switch to repo 2; both env + rf-knowledge fail → anchor must not lie.
    mockedEnvKw.mockRejectedValueOnce(new Error('boom'))
    mockedSearch.mockRejectedValueOnce(new Error('boom2'))
    await explorer.preloadKeywords(2)
    expect(explorer.keywordsRepoId).toBe(null)
    expect(explorer.keywords).toEqual([])
  })

  it('clearAll resets the repo anchor so the next preload reloads', async () => {
    seedDefaultEnv(5)
    mockedEnvKw.mockResolvedValue({
      status: 'ready', source_hash: 'h', updated_at: null,
      keywords: [{ name: 'Click', library: 'Browser', args: [], shortdoc: '' }],
    })
    const explorer = useExplorerStore()
    await explorer.preloadKeywords(1)
    explorer.clearAll()
    expect(explorer.keywordsRepoId).toBe(null)
    await explorer.preloadKeywords(1)
    expect(mockedEnvKw).toHaveBeenCalledTimes(2)
  })
})
