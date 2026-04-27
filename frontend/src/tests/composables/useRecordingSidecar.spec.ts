import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the explorer API before importing the composable
vi.mock('@/api/explorer.api', () => ({
  getFile: vi.fn(),
  saveFile: vi.fn(),
}))

import { getFile, saveFile } from '@/api/explorer.api'
import {
  loadSidecar,
  saveSidecar,
  sidecarPathFor,
} from '@/composables/useRecordingSidecar'

const mockedGet = getFile as unknown as ReturnType<typeof vi.fn>
const mockedSave = saveFile as unknown as ReturnType<typeof vi.fn>

const validSidecar = {
  schema_version: 1,
  transport: 'web_playwright',
  session_id: 'abc',
  name: null,
  commands: [
    {
      index: 0,
      keyword: 'Click',
      args: {},
      selector_candidates: [
        { strategy: 'text', value: 'text=Hello', quality_score: 70, verified_unique: false },
      ],
      active_candidate_index: 0,
    },
  ],
}

describe('sidecarPathFor', () => {
  it('replaces .robot with .rbs.json', () => {
    expect(sidecarPathFor('a/b/c.robot')).toBe('a/b/c.rbs.json')
    expect(sidecarPathFor('foo.ROBOT')).toBe('foo.rbs.json')
  })

  it('returns the input unchanged when extension is not .robot', () => {
    expect(sidecarPathFor('foo.txt')).toBe('foo.txt')
  })
})

describe('loadSidecar', () => {
  beforeEach(() => {
    mockedGet.mockReset()
  })

  it('returns the parsed sidecar when getFile succeeds with valid JSON', async () => {
    mockedGet.mockResolvedValue({ content: JSON.stringify(validSidecar) })
    const result = await loadSidecar(7, 'flows/recording.robot')
    expect(result).not.toBeNull()
    expect(result!.commands).toHaveLength(1)
    expect(result!.commands[0].keyword).toBe('Click')
    expect(mockedGet).toHaveBeenCalledWith(7, 'flows/recording.rbs.json')
  })

  it('returns null when the sidecar file is missing (getFile rejects)', async () => {
    mockedGet.mockRejectedValue(new Error('404'))
    const result = await loadSidecar(7, 'flows/missing.robot')
    expect(result).toBeNull()
  })

  it('returns null when JSON is malformed', async () => {
    mockedGet.mockResolvedValue({ content: '{"oops":' })
    const result = await loadSidecar(7, 'flows/broken.robot')
    expect(result).toBeNull()
  })

  it('returns null when the schema version is unsupported (newer than known)', async () => {
    mockedGet.mockResolvedValue({
      content: JSON.stringify({ ...validSidecar, schema_version: 99 }),
    })
    const result = await loadSidecar(7, 'flows/future.robot')
    expect(result).toBeNull()
  })

  it('returns null when commands is not an array', async () => {
    mockedGet.mockResolvedValue({
      content: JSON.stringify({ ...validSidecar, commands: 'oops' }),
    })
    const result = await loadSidecar(7, 'flows/bad.robot')
    expect(result).toBeNull()
  })
})

describe('saveSidecar', () => {
  beforeEach(() => {
    mockedSave.mockReset()
  })

  it('serialises the sidecar to JSON and writes the .rbs.json sibling', async () => {
    mockedSave.mockResolvedValue({})
    await saveSidecar(3, 'flows/recording.robot', validSidecar as never)
    expect(mockedSave).toHaveBeenCalledTimes(1)
    const [repo, path, content] = mockedSave.mock.calls[0]
    expect(repo).toBe(3)
    expect(path).toBe('flows/recording.rbs.json')
    expect(content).toContain('"schema_version": 1')
    expect(content.endsWith('\n')).toBe(true)
  })
})
