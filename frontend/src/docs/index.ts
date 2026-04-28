import type { DocsContent } from './types'

// Story PERF-1: lazy-load each locale's content as its own bundler
// chunk. Rollup splits the four ~2300-line content files into separate
// chunks; only the active locale ships on initial DocsView load.
const loaders: Record<string, () => Promise<{ default: DocsContent }>> = {
  en: () => import('./content/en'),
  de: () => import('./content/de'),
  fr: () => import('./content/fr'),
  es: () => import('./content/es'),
}

const cache: Record<string, DocsContent> = {}

export async function getDocsContent(locale: string): Promise<DocsContent> {
  const key = loaders[locale] ? locale : 'en'
  if (cache[key]) return cache[key]
  const mod = await loaders[key]()
  cache[key] = mod.default
  return cache[key]
}
