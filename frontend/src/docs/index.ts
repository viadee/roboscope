import type { DocsContent } from './types'
import en from './content/en'
import de from './content/de'

const docsMap: Record<string, DocsContent> = { en, de }

export function getDocsContent(locale: string): DocsContent {
  return docsMap[locale] || docsMap['en']
}
