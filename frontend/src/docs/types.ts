export interface DocSection {
  id: string
  title: string
  icon: string
  subsections: DocSubsection[]
}

export interface DocSubsection {
  id: string
  title: string
  content: string
  tip?: string
}

export type DocsContent = DocSection[]
