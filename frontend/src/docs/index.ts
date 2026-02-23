import type { DocsContent } from './types'
import en from './content/en'
import de from './content/de'
import fr from './content/fr'
import es from './content/es'

const docsMap: Record<string, DocsContent> = { en, de, fr, es }

export function getDocsContent(locale: string): DocsContent {
  return docsMap[locale] || docsMap['en']
}
