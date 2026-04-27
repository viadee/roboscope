/**
 * Story EDITOR-2 — single-source-of-truth for keyword argument signatures
 * across the visual flow editor and the keyword palette.
 *
 * Combines, in priority order:
 *   1. Dynamic library introspection from the backend (exposed as
 *      `useExplorerStore().keywords` — populated when the user opens a
 *      repo) — these carry the libdoc-style `name: type = default` shape.
 *   2. The static `RF_KEYWORD_SIGNATURES` fallback for the Robot
 *      Framework standard libraries (BuiltIn, Collections, …) so the
 *      editor still has labels before the dynamic fetch resolves.
 *
 * Lookup is case-insensitive (Robot Framework treats keyword names that
 * way) and returns `null` for unknown keywords so the caller can fall
 * back to the generic "arg N" label.
 */
import { computed } from 'vue'
import { useExplorerStore } from '@/stores/explorer.store'
import {
  RF_KEYWORD_SIGNATURES,
  parseArgSignature,
  type ParsedArg,
} from '@/utils/robotKeywordSignatures'

export function useKeywordSignatures() {
  const explorer = useExplorerStore()

  const argsByName = computed<Map<string, string[]>>(() => {
    const m = new Map<string, string[]>()
    // Built-in fallback first so dynamic entries can override it.
    for (const [k, v] of RF_KEYWORD_SIGNATURES) m.set(k.toLowerCase(), v)
    // TODO(EDITOR-2 follow-up): project-resource keywords (loaded by
    // KeywordPalette via `getProjectKeywords`) are not merged here. A
    // user-defined keyword with the same name as a BuiltIn would be
    // shadowed by the BuiltIn unless the dynamic library cache also
    // returns it. Promote project keywords once the palette stops
    // owning that fetch.
    for (const kw of explorer.keywords) {
      if (kw.args && kw.args.length) m.set(kw.name.toLowerCase(), kw.args)
    }
    return m
  })

  function getArgs(keywordName: string): string[] | null {
    if (!keywordName) return null
    return argsByName.value.get(keywordName.toLowerCase()) ?? null
  }

  function getParsedArgs(keywordName: string): ParsedArg[] | null {
    const raw = getArgs(keywordName)
    if (!raw) return null
    return raw.map(parseArgSignature)
  }

  return { argsByName, getArgs, getParsedArgs }
}
