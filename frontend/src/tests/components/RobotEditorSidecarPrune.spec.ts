/**
 * RECORDER-IDMAP follow-up — sidecar pruning on save.
 *
 * When the user deletes a step in the visual editor, its
 * `# rbs:<id>` comment leaves the .robot but its candidate group
 * stays in the sidecar. `saveSidecarIfDirty(robotContent)` now
 * scans the about-to-save text for live ids and drops sidecar
 * commands that no longer reference any step. Without the prune
 * the runtime heal library's `_lookup_command_id` could match a
 * dead command's selector by value and stamp the audit with an
 * `rbs:<id>` chip that points to a row the user removed.
 *
 * The scanner regex lives inside RobotEditor.vue's `<script setup>`
 * block. We mirror it here (same pattern as
 * RobotEditorEscapeRoundTrip.spec.ts).
 */
import { describe, it, expect } from 'vitest'

// Mirror of `RobotEditor.vue::_collectRbsIdsFromContent`.
function collectRbsIdsFromContent(content: string): Set<string> {
  const ids = new Set<string>()
  const re = /\s+# rbs:([a-f0-9]{8,32})\s*$/gm
  let m: RegExpExecArray | null
  while ((m = re.exec(content)) !== null) ids.add(m[1])
  return ids
}

describe('collectRbsIdsFromContent — scan .robot for live rbs ids', () => {
  it('finds a single id on a Click line', () => {
    const content =
      '*** Test Cases ***\n' +
      'T1\n' +
      '    Click    id=submit    # rbs:abc123def456\n'
    expect(collectRbsIdsFromContent(content)).toEqual(new Set(['abc123def456']))
  })

  it('finds multiple ids across multiple lines', () => {
    const content =
      '    Click    id=submit    # rbs:aaaaaaaa1111\n' +
      '    Type Text    id=user    Alice    # rbs:bbbbbbbb2222\n' +
      '    Click    id=login    # rbs:cccccccc3333\n'
    expect(collectRbsIdsFromContent(content)).toEqual(
      new Set(['aaaaaaaa1111', 'bbbbbbbb2222', 'cccccccc3333']),
    )
  })

  it('returns an empty set for legacy / hand-written .robot files', () => {
    const content =
      '*** Test Cases ***\n' +
      'Legacy\n' +
      '    Click    id=submit\n' +
      '    Type Text    id=user    Alice\n'
    expect(collectRbsIdsFromContent(content).size).toBe(0)
  })

  it('ignores `# rbs:` tokens inside the middle of a line', () => {
    // Only the trailing comment shape counts; an embedded mention
    // (e.g. inside a comment about the feature) must not be picked up.
    const content = '    # See # rbs:notatag for details\n'
    expect(collectRbsIdsFromContent(content).size).toBe(0)
  })

  it('rejects malformed ids (too short, wrong charset)', () => {
    const content =
      '    Click    id=a    # rbs:short\n' +
      '    Click    id=b    # rbs:UPPER1234567\n'
    expect(collectRbsIdsFromContent(content).size).toBe(0)
  })
})

describe('sidecar prune — drop commands whose id is gone from the file', () => {
  type Cmd = { id?: string; index: number; keyword: string }
  type Sidecar = { commands: Cmd[] }

  function pruneSidecar(sidecar: Sidecar, robotContent: string): {
    sidecar: Sidecar
    pruned: number
  } {
    const liveIds = collectRbsIdsFromContent(robotContent)
    const before = sidecar.commands.length
    const kept = sidecar.commands.filter(c => !c.id || liveIds.has(c.id))
    return {
      sidecar: { ...sidecar, commands: kept },
      pruned: before - kept.length,
    }
  }

  it('drops the deleted step and keeps the survivors', () => {
    const sidecar: Sidecar = {
      commands: [
        { id: 'aaaaaaaa1111', index: 0, keyword: 'Click' },
        { id: 'bbbbbbbb2222', index: 1, keyword: 'Type Text' }, // deleted from .robot
        { id: 'cccccccc3333', index: 2, keyword: 'Click' },
      ],
    }
    const robot =
      '    Click    id=submit    # rbs:aaaaaaaa1111\n' +
      '    Click    id=login    # rbs:cccccccc3333\n'
    const { sidecar: result, pruned } = pruneSidecar(sidecar, robot)
    expect(pruned).toBe(1)
    expect(result.commands.map(c => c.id)).toEqual([
      'aaaaaaaa1111',
      'cccccccc3333',
    ])
  })

  it('keeps legacy commands without an id (pre-RECORDER-IDMAP)', () => {
    // Sidecars from before the id field shipped have commands with no
    // `id` attribute. Pruning must not drop them, otherwise loading
    // an old recording then saving silently empties the sidecar.
    const sidecar: Sidecar = {
      commands: [
        { index: 0, keyword: 'Click' },
        { index: 1, keyword: 'Type Text' },
      ],
    }
    const robot = '    Click    id=submit\n    Type Text    id=user    Alice\n'
    const { sidecar: result, pruned } = pruneSidecar(sidecar, robot)
    expect(pruned).toBe(0)
    expect(result.commands.length).toBe(2)
  })

  it('no-op when every id is still present', () => {
    const sidecar: Sidecar = {
      commands: [
        { id: 'aaaaaaaa1111', index: 0, keyword: 'Click' },
        { id: 'bbbbbbbb2222', index: 1, keyword: 'Click' },
      ],
    }
    const robot =
      '    Click    id=a    # rbs:aaaaaaaa1111\n' +
      '    Click    id=b    # rbs:bbbbbbbb2222\n'
    const { pruned } = pruneSidecar(sidecar, robot)
    expect(pruned).toBe(0)
  })
})
