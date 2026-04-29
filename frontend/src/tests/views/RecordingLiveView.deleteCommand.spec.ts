/**
 * Regression guard for `deleteCommand`'s local-only contract
 * (RECORDER-PRUNE-1).
 *
 * The function is defined inside RecordingLiveView.vue's <script
 * setup> and not directly importable. We mirror its body here and
 * exercise the splice semantics that matter:
 *
 *   - Deleting a valid index removes exactly that one row.
 *   - Out-of-range indices are no-ops (defensive — the template
 *     binds `idx` from v-for so this can't fire in practice, but
 *     the guard exists in case a future caller invokes by other
 *     means).
 *   - The mutated commands array is what later gets POSTed to
 *     /recordings/save, so the deleted row really is gone from the
 *     persisted .robot / .rbs.json. (Save uses `commands.value`
 *     directly — no separate filter step.)
 */
import { describe, it, expect } from 'vitest'

import type { RecordedCommand } from '@/types/recorder.types'

function deleteCommand(commands: RecordedCommand[], cmdIndex: number): void {
  if (cmdIndex < 0 || cmdIndex >= commands.length) return
  commands.splice(cmdIndex, 1)
}

function _cmd(index: number, keyword: string): RecordedCommand {
  return {
    index,
    keyword,
    args: {},
    selector_candidates: [],
    active_candidate_index: 0,
  }
}

describe('deleteCommand — local-only prune (RECORDER-PRUNE-1)', () => {
  it('removes exactly the targeted row', () => {
    const commands = [
      _cmd(0, 'Click'),       // ad-iframe pixel the user wants gone
      _cmd(1, 'Type Text'),
      _cmd(2, 'Click'),
    ]
    deleteCommand(commands, 0)
    expect(commands.map((c) => c.keyword)).toEqual(['Type Text', 'Click'])
  })

  it('leaves the array untouched on negative index', () => {
    const commands = [_cmd(0, 'Click'), _cmd(1, 'Click')]
    deleteCommand(commands, -1)
    expect(commands).toHaveLength(2)
  })

  it('leaves the array untouched on out-of-range positive index', () => {
    const commands = [_cmd(0, 'Click'), _cmd(1, 'Click')]
    deleteCommand(commands, 99)
    expect(commands).toHaveLength(2)
  })

  it('handles deletion of the last element', () => {
    const commands = [_cmd(0, 'Click'), _cmd(1, 'Type Text')]
    deleteCommand(commands, 1)
    expect(commands.map((c) => c.keyword)).toEqual(['Click'])
  })

  it('preserves unrelated frame_url / fingerprint fields on remaining rows', () => {
    // Repro of the real use case: ad-iframe noise lives at index 0,
    // legitimate iframe consent click at index 1. After pruning the
    // ad row, the consent row's frame_url must still be there so the
    // emitter can wrap the selector with `iframe[src*=...] >>>`.
    const adRow: RecordedCommand = {
      ..._cmd(0, 'Click'),
      frame_url: 'https://googleads.g.doubleclick.net/banner',
    }
    const consentRow: RecordedCommand = {
      ..._cmd(1, 'Click'),
      frame_url: 'https://message-eu.sp-prod.net/i?id=xxx',
    }
    const commands = [adRow, consentRow]
    deleteCommand(commands, 0)
    expect(commands).toHaveLength(1)
    expect(commands[0].frame_url).toBe('https://message-eu.sp-prod.net/i?id=xxx')
  })
})
