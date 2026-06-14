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
import { searchKeywords } from '@/api/ai.api'
import {
  RF_KEYWORD_SIGNATURES,
  parseArgSignature,
  type ParsedArg,
} from '@/utils/robotKeywordSignatures'

export function useKeywordSignatures() {
  const explorer = useExplorerStore()

  const argsByName = computed<Map<string, string[]>>(() => {
    const m = new Map<string, string[]>()
    // Resolution order mirrors Robot Framework's own keyword search order:
    // project/resource keywords > library keywords > BuiltIn. We build the
    // map LOWEST-precedence first so higher tiers overwrite on a name clash.
    //
    //   1. static BuiltIn fallback (lowest)
    for (const [k, v] of RF_KEYWORD_SIGNATURES) m.set(k.toLowerCase(), v)
    //   2. dynamic library introspection (libdoc / rf-knowledge cache)
    for (const kw of explorer.keywords) {
      if (kw.args && kw.args.length) m.set(kw.name.toLowerCase(), kw.args)
    }
    //   3. the repo's OWN user-defined keywords (highest) — fixes the
    //      shadowing bug where a project keyword sharing a BuiltIn name
    //      showed the BuiltIn's signature. Empty-arg user keywords still
    //      register (overwrite) so we don't fall back to a library spec.
    for (const kw of explorer.projectKeywords) {
      if (kw.name) m.set(kw.name.toLowerCase(), kw.arguments ?? [])
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

  /**
   * Story EDITOR-7 — return everything we know about a keyword for the
   * doc modal. `doc` and `library` are only available for dynamic-
   * library introspection entries; the static `RF_KEYWORD_SIGNATURES`
   * map carries args only.
   */
  function getKeywordInfo(keywordName: string): {
    display: string
    library: string
    doc: string
    docFormat: string
    args: string[]
  } | null {
    if (!keywordName) return null
    const lower = keywordName.toLowerCase()
    const args = argsByName.value.get(lower)
    if (!args) return null
    const dynamic = explorer.keywords.find((k) => k.name.toLowerCase() === lower)
    return {
      display: dynamic?.name ?? keywordName,
      library: dynamic?.library ?? 'BuiltIn',
      doc: dynamic?.doc ?? '',
      docFormat: dynamic?.doc_format ?? 'text',
      args,
    }
  }

  /**
   * Story EDITOR-7 follow-up — async fetch of full keyword info
   * (including the doc string) for keywords that aren't yet in the
   * explorer cache. The wildcard `searchKeywords('*')` call that
   * `KeywordPalette` runs at mount time SKIPS BuiltIn (the backend
   * lists only third-party libraries to keep the response size sane),
   * so static-fallback BuiltIn keywords land in the modal without a
   * doc. A targeted `searchKeywords(name, repoId)` does return the
   * BuiltIn match, so we lazy-load on demand and fold the result into
   * `explorer.keywords` for caching.
   */
  async function fetchKeywordInfo(
    keywordName: string,
    repoId?: number,
  ): Promise<{
    display: string
    library: string
    doc: string
    docFormat: string
    args: string[]
  } | null> {
    if (!keywordName) return null
    try {
      const response = await searchKeywords(keywordName, repoId)
      const lower = keywordName.toLowerCase()
      const hit = response.results.find((r) => r.name.toLowerCase() === lower)
        ?? response.results[0]
      if (!hit) return getKeywordInfo(keywordName)
      // Cache it so subsequent reads are synchronous.
      const exists = explorer.keywords.some((k) => k.name.toLowerCase() === hit.name.toLowerCase())
      if (!exists) {
        explorer.keywords.push({
          name: hit.name,
          library: hit.library || '',
          doc: hit.doc || '',
          doc_format: hit.doc_format || 'text',
          args: hit.args || [],
        })
      }
      return {
        display: hit.name,
        library: hit.library || 'BuiltIn',
        doc: hit.doc || '',
        docFormat: hit.doc_format || 'text',
        args: hit.args ?? getArgs(keywordName) ?? [],
      }
    } catch {
      return getKeywordInfo(keywordName)
    }
  }

  return { argsByName, getArgs, getParsedArgs, getKeywordInfo, fetchKeywordInfo }
}
