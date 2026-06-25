import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAiStore } from '@/stores/ai.store'
import type { AiJob } from '@/types/domain.types'

vi.mock('@/api/ai.api', () => ({
  analyzeFailures: vi.fn(),
  getJobStatus: vi.fn(),
}))

import * as aiApi from '@/api/ai.api'

function job(overrides: Partial<AiJob> = {}): AiJob {
  return {
    id: 1,
    job_type: 'analyze',
    status: 'running',
    repository_id: 1,
    provider_id: 1,
    report_id: 42,
    spec_path: '',
    target_path: null,
    result_preview: null,
    error_message: null,
    token_usage: null,
    triggered_by: 1,
    started_at: null,
    completed_at: null,
    created_at: '2026-06-17T00:00:00Z',
    ...overrides,
  }
}

describe('ai.store — analysis lifecycle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('analyzeFailures stores the job keyed by report_id and starts polling', async () => {
    vi.mocked(aiApi.analyzeFailures).mockResolvedValue(job({ report_id: 42 }))
    vi.mocked(aiApi.getJobStatus).mockResolvedValue(job({ report_id: 42, status: 'running' }))
    const store = useAiStore()

    await store.analyzeFailures(42)
    expect(store.analysisJob?.report_id).toBe(42)

    // Poll tick keeps refreshing while running.
    await vi.advanceTimersByTimeAsync(2000)
    expect(aiApi.getJobStatus).toHaveBeenCalled()
  })

  it('clearAnalysis drops the job and stops the poll', async () => {
    vi.mocked(aiApi.analyzeFailures).mockResolvedValue(job({ report_id: 42 }))
    vi.mocked(aiApi.getJobStatus).mockResolvedValue(job({ report_id: 42, status: 'running' }))
    const store = useAiStore()
    await store.analyzeFailures(42)

    store.clearAnalysis()
    expect(store.analysisJob).toBeNull()

    // No further polling after clear.
    vi.mocked(aiApi.getJobStatus).mockClear()
    await vi.advanceTimersByTimeAsync(6000)
    expect(aiApi.getJobStatus).not.toHaveBeenCalled()
  })

  it('completed/failed status stops polling on its own', async () => {
    vi.mocked(aiApi.analyzeFailures).mockResolvedValue(job({ report_id: 7 }))
    vi.mocked(aiApi.getJobStatus).mockResolvedValue(job({ report_id: 7, status: 'completed', result_preview: 'done' }))
    const store = useAiStore()
    await store.analyzeFailures(7)

    await vi.advanceTimersByTimeAsync(2000)
    expect(store.analysisJob?.status).toBe('completed')

    vi.mocked(aiApi.getJobStatus).mockClear()
    await vi.advanceTimersByTimeAsync(6000)
    expect(aiApi.getJobStatus).not.toHaveBeenCalled()
  })
})
