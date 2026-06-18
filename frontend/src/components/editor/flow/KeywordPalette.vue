<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExplorerStore } from '@/stores/explorer.store'
import { searchKeywords, type RfKeywordResult } from '@/api/ai.api'
import { getProjectKeywords, type ProjectKeyword } from '@/api/explorer.api'
import { resourceImportPath } from './resourcePath'
import {
  type PaletteFilter,
  type PaletteSort,
  PALETTE_FILTER_LS_KEY,
  PALETTE_SORT_LS_KEY,
  adaptiveDefaultFilter,
  parseStoredFilter,
  parseStoredSort,
  applyFilter,
  hiddenCount,
  sortLibraries,
  type CatLike,
} from './paletteView'
import type { StepType, RobotStep } from './flowConverter'

// Story TYPE-2 + UX D1: discriminated union for the palette categories.
//   - keyword categories (resources, BuiltIn, project libs, dynamic libs)
//   - the control category (IF / FOR / VAR …)
// A `kind` discriminator ('resource' | 'library' | 'control') drives the
// D1 "Your resources" sectioning + D5/D6 sort/filter, independent of the
// display name (resources now show the bare file basename, not a
// "Project: <file>" shouty prefix).
type ControlItem = { label: string; type: StepType }
type KeywordCategory = {
  name: string
  keywords: string[]
  kind: 'resource' | 'library'
  /** Curated static-fallback subset (no env / lib not installed). */
  isExamples?: boolean
  /** The resource file the user has open right now (pinned + tinted). */
  isCurrentFile?: boolean
  /** Repo-relative directory of a resource file (D1 path subtitle). */
  relPath?: string
  /** `.resource` (vs `.robot`) — picks the file glyph. */
  isResourceFile?: boolean
  /** Owning library imported in the open file (drives D5 importedFirst). */
  imported?: boolean
}
type ControlCategory = { name: string; items: ControlItem[]; kind: 'control' }
type PaletteCategory = KeywordCategory | ControlCategory

const props = defineProps<{
  repoId?: number
  /** Repo-relative path of the file the user is currently editing. */
  filePath?: string
  /** Lower-cased names of libraries currently imported in the file. */
  importedLibraries?: Set<string>
  /** Library → keyword-usage tally for the currently-open file. */
  usageCounts?: Map<string, number>
  /** UX D6 — Library + Resource import count of the open file (heuristic). */
  fileImportCount?: number
  /** UX D6 — total step count across the open file (heuristic). */
  fileStepCount?: number
}>()

const { t } = useI18n()
const explorer = useExplorerStore()

const emit = defineEmits<{
  /** Add a step to the active section. `library` is the auto-import hint:
   *  a Library name, or an open-file-relative `.resource`/`.robot` path
   *  for project keywords sourced from another file; `undefined` for
   *  Control items, BuiltIn, and same-file project keywords. */
  (e: 'add-node', step: RobotStep, library?: string): void
}>()

/** Decide if a category's keywords render as "imported" (full opacity)
 *  or "not imported" (dimmed + auto-import on pick). True for BuiltIn,
 *  Control, and resources (in-repo keywords are always usable). */
function isCategoryImported(cat: PaletteCategory): boolean {
  if (cat.kind === 'control') return true
  if (cat.kind === 'resource') return true
  if (cat.name === 'BuiltIn') return true
  if (!props.importedLibraries) return true // no signal → don't dim
  return props.importedLibraries.has(cat.name.toLowerCase())
}

// Dynamic keywords from environment + project .resource files
const dynamicLibraries = ref<Map<string, RfKeywordResult[]>>(new Map())
const projectKeywords = ref<ProjectKeyword[]>([])
const loadingKeywords = ref(false)

// Keyword args lookup: name → args[]
const keywordArgsMap = ref<Map<string, string[]>>(new Map())

function buildFromCache() {
  const argsMap = new Map<string, string[]>()
  const grouped = new Map<string, RfKeywordResult[]>()
  for (const kw of explorer.keywords) {
    const lib = kw.library || 'Unknown'
    if (!grouped.has(lib)) grouped.set(lib, [])
    grouped.get(lib)!.push({ name: kw.name, library: kw.library, doc: kw.doc, args: kw.args || [] })
    if (kw.args && kw.args.length > 0) {
      argsMap.set(kw.name, kw.args)
    }
  }
  dynamicLibraries.value = grouped
  keywordArgsMap.value = argsMap
}

async function loadDynamicKeywords() {
  if (!props.repoId) return
  loadingKeywords.value = true
  try {
    // Use preloaded keywords from explorer store if available
    if (explorer.keywordsLoaded && explorer.keywords.length > 0) {
      buildFromCache()
    } else {
      // Fallback: load directly
      const rfResult = await searchKeywords('*', props.repoId)
      const argsMap = new Map<string, string[]>()
      const grouped = new Map<string, RfKeywordResult[]>()
      for (const kw of rfResult.results) {
        const lib = kw.library || 'Unknown'
        if (!grouped.has(lib)) grouped.set(lib, [])
        grouped.get(lib)!.push(kw)
        if (kw.args && kw.args.length > 0) {
          argsMap.set(kw.name, kw.args)
        }
      }
      dynamicLibraries.value = grouped
      keywordArgsMap.value = argsMap
    }

    // Also load project-specific keywords from .robot/.resource files.
    const projKws = await getProjectKeywords(props.repoId).catch(() => [])
    projectKeywords.value = projKws
    explorer.setProjectKeywords(projKws)
    for (const kw of projKws) {
      if (kw.arguments && kw.arguments.length > 0) {
        keywordArgsMap.value.set(kw.name, kw.arguments)
      }
    }
  } finally {
    loadingKeywords.value = false
  }
}

onMounted(() => loadDynamicKeywords())
watch(() => props.repoId, () => loadDynamicKeywords())
// Rebuild when explorer store keywords are refreshed
watch(() => explorer.keywordsLoaded, (loaded) => {
  if (loaded && explorer.keywords.length > 0) buildFromCache()
})

const searchQuery = ref('')
// Track only EXPANDED categories — default collapsed.
const expandedCategories = ref<Set<string>>(new Set())
const selectedKeyword = ref<{ name: string; type?: StepType; library?: string } | null>(null)

function toggleCategory(name: string) {
  if (expandedCategories.value.has(name)) {
    expandedCategories.value.delete(name)
  } else {
    expandedCategories.value.add(name)
  }
}
function isCategoryOpen(name: string): boolean {
  if (searchQuery.value) return true
  return expandedCategories.value.has(name)
}
function expandAll() {
  for (const cat of allCategories.value) {
    expandedCategories.value.add(cat.name)
  }
}
function collapseAll() {
  expandedCategories.value.clear()
}

function getKeywordArgs(name: string): string[] {
  return keywordArgsMap.value.get(name) || []
}

// RES — keyword name → source file path (repo-relative) for project keywords.
const projectKeywordSource = computed(() => {
  const m = new Map<string, string>()
  for (const kw of projectKeywords.value) m.set(kw.name, kw.file_path)
  return m
})

/** Auto-import hint passed as the `add-node` `library` arg. For a Library
 *  category it's the library name (BuiltIn excluded — RF auto-imports it);
 *  for a resource keyword sourced from another file it's the open-file-
 *  relative path (so FlowEditor's addLibrary creates the `Resource`
 *  import). Same-file resource keywords and BuiltIn return undefined. */
function importHintFor(cat: PaletteCategory, keyword: string): string | undefined {
  if (cat.kind === 'resource') {
    const src = projectKeywordSource.value.get(keyword)
    if (src && src !== props.filePath) {
      return resourceImportPath(props.filePath || '', src)
    }
    return undefined
  }
  if (cat.kind === 'control') return undefined
  if (cat.name === 'BuiltIn') return undefined
  return cat.name
}

function selectKeyword(name: string, type?: StepType, library?: string) {
  selectedKeyword.value = { name, type, library }
}
function isSelected(name: string): boolean {
  return selectedKeyword.value?.name === name
}
function addSelectedKeyword() {
  if (!selectedKeyword.value) return
  if (selectedKeyword.value.type) {
    addControlNode(selectedKeyword.value.type)
  } else {
    addKeywordNode(selectedKeyword.value.name, selectedKeyword.value.library)
  }
  selectedKeyword.value = null
}

// Built-in keyword categories (curated, ~10 each) used to fill gaps in
// the dynamic libdoc data. See `allCategories`.
const categories: { name: string; keywords: string[] }[] = [
  {
    name: 'BuiltIn',
    keywords: [
      'Log', 'Log To Console', 'Set Variable', 'Should Be Equal',
      'Should Contain', 'Should Not Be Empty', 'Should Be True',
      'Sleep', 'Run Keyword If', 'Run Keyword And Return Status',
      'Fail', 'Pass Execution', 'Set Test Variable', 'Set Suite Variable',
      'Set Global Variable', 'Get Length', 'Convert To String',
      'Convert To Integer', 'Evaluate', 'Catenate',
    ],
  },
  {
    name: 'Collections',
    keywords: [
      'Create List', 'Create Dictionary', 'Append To List',
      'Get From Dictionary', 'Set To Dictionary', 'List Should Contain Value',
      'Dictionary Should Contain Key', 'Get Length', 'Remove From List',
    ],
  },
  {
    name: 'String',
    keywords: [
      'Replace String', 'Split String', 'Get Substring',
      'Should Match Regexp', 'Convert To Lower Case', 'Convert To Upper Case',
      'Strip String', 'Get Line Count',
    ],
  },
  {
    name: 'DateTime',
    keywords: [
      'Get Current Date', 'Convert Date', 'Convert Time',
      'Subtract Date From Date', 'Add Time To Date', 'Get Time',
    ],
  },
  {
    name: 'OperatingSystem',
    keywords: [
      'Run', 'Run And Return Rc', 'File Should Exist', 'Directory Should Exist',
      'Create File', 'Remove File', 'Copy File', 'Move File',
      'List Directory', 'Get Environment Variable',
    ],
  },
  {
    name: 'Process',
    keywords: [
      'Run Process', 'Start Process', 'Wait For Process', 'Terminate Process',
      'Get Process Result', 'Process Should Be Running',
    ],
  },
  {
    name: 'XML',
    keywords: [
      'Parse XML', 'Get Element', 'Get Element Text',
      'Get Element Attribute', 'Element Should Exist',
    ],
  },
  {
    name: 'Browser',
    keywords: [
      'New Browser', 'New Page', 'Click', 'Fill Text', 'Get Text',
      'Wait For Elements State', 'Take Screenshot', 'Go To',
      'Get Url', 'Close Browser',
    ],
  },
  {
    name: 'SeleniumLibrary',
    keywords: [
      'Open Browser', 'Close Browser', 'Click Element', 'Input Text',
      'Get Text', 'Wait Until Element Is Visible', 'Page Should Contain',
      'Capture Page Screenshot', 'Get Title', 'Go To',
    ],
  },
  {
    name: 'RequestsLibrary',
    keywords: [
      'Create Session', 'GET', 'POST', 'PUT', 'DELETE', 'PATCH',
      'Status Should Be', 'Should Be Equal As Strings',
    ],
  },
  {
    name: 'DatabaseLibrary',
    keywords: [
      'Connect To Database', 'Disconnect From Database', 'Execute Sql String',
      'Query', 'Row Count Is Equal To', 'Check If Exists In Database',
    ],
  },
]

const controlCategory: ControlCategory = {
  name: 'Control',
  kind: 'control',
  items: [
    { label: 'IF / ELSE', type: 'if' },
    { label: 'ELSE IF', type: 'else_if' },
    { label: 'ELSE', type: 'else' },
    { label: 'FOR Loop', type: 'for' },
    { label: 'WHILE Loop', type: 'while' },
    { label: 'TRY / EXCEPT', type: 'try' },
    { label: 'EXCEPT', type: 'except' },
    { label: 'FINALLY', type: 'finally' },
    { label: 'VAR', type: 'var' },
    { label: 'RETURN', type: 'return' },
    { label: 'BREAK', type: 'break' },
    { label: 'CONTINUE', type: 'continue' },
    { label: 'Comment', type: 'comment' },
  ],
}

const _ALWAYS_VISIBLE_LIBS = [
  'BuiltIn',
  'Collections', 'String', 'DateTime', 'OperatingSystem', 'Process', 'XML',
  'Browser', 'SeleniumLibrary', 'RequestsLibrary', 'DatabaseLibrary',
]

// --- D1: resource categories (project .robot/.resource files) ---------------
const resourceCategories = computed<KeywordCategory[]>(() => {
  if (projectKeywords.value.length === 0) return []
  // Group by full file_path (unique) so two files sharing a basename in
  // different folders don't merge; the relative directory is the subtitle.
  const byPath = new Map<string, string[]>()
  for (const kw of projectKeywords.value) {
    const arr = byPath.get(kw.file_path) ?? []
    arr.push(kw.name)
    byPath.set(kw.file_path, arr)
  }
  const cats: KeywordCategory[] = []
  for (const [path, keywords] of byPath) {
    const slash = path.lastIndexOf('/')
    const base = slash >= 0 ? path.slice(slash + 1) : path
    const dir = slash >= 0 ? path.slice(0, slash) : ''
    cats.push({
      name: base,
      keywords,
      kind: 'resource',
      relPath: dir,
      isResourceFile: base.toLowerCase().endsWith('.resource'),
      isCurrentFile: path === props.filePath,
    })
  }
  // Current file pinned first, then alphabetical for stable scanning.
  cats.sort((a, b) => {
    const c = Number(b.isCurrentFile) - Number(a.isCurrentFile)
    if (c !== 0) return c
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })
  return cats
})

// --- library categories (dynamic libdoc + static-fallback examples) ---------
const libraryCategories = computed<KeywordCategory[]>(() => {
  const libCats: KeywordCategory[] = []
  const dynamicLibNames = new Set<string>()
  for (const [lib, keywords] of dynamicLibraries.value) {
    libCats.push({
      name: lib,
      keywords: keywords.map(kw => kw.name),
      kind: 'library',
      imported: props.importedLibraries?.has(lib.toLowerCase()) ?? false,
    })
    dynamicLibNames.add(lib)
  }
  for (const libName of _ALWAYS_VISIBLE_LIBS) {
    if (dynamicLibNames.has(libName)) continue
    const staticCat = categories.find(c => c.name === libName)
    if (staticCat) {
      libCats.push({
        name: staticCat.name,
        keywords: staticCat.keywords,
        kind: 'library',
        isExamples: libName !== 'BuiltIn',
        imported: props.importedLibraries?.has(libName.toLowerCase()) ?? (libName === 'BuiltIn'),
      })
    }
  }
  return libCats
})

// True when the env-backed libdoc returned data — a proxy for "the repo
// has an environment configured" (D6 adaptive default).
const hasEnvData = computed(() => dynamicLibraries.value.size > 0)

// --- D5 sort + D6 filter state (persisted manual overrides) -----------------
const sortMode = ref<PaletteSort>(
  parseStoredSort(localStorage.getItem(PALETTE_SORT_LS_KEY)) ?? 'mostUsed',
)
const sortMenuOpen = ref(false)
function setSort(mode: PaletteSort) {
  sortMode.value = mode
  localStorage.setItem(PALETTE_SORT_LS_KEY, mode)
  sortMenuOpen.value = false
}

// A persisted filter override (null → use the adaptive default).
const filterOverride = ref<PaletteFilter | null>(
  parseStoredFilter(localStorage.getItem(PALETTE_FILTER_LS_KEY)),
)
const filterMenuOpen = ref(false)
const effectiveFilter = computed<PaletteFilter>(() =>
  filterOverride.value ?? adaptiveDefaultFilter({
    hasEnvData: hasEnvData.value,
    file: { importCount: props.fileImportCount ?? 0, stepCount: props.fileStepCount ?? 0 },
  }),
)
function toggleFilter(key: keyof PaletteFilter) {
  const next: PaletteFilter = { ...effectiveFilter.value, [key]: !effectiveFilter.value[key] }
  filterOverride.value = next
  localStorage.setItem(PALETTE_FILTER_LS_KEY, JSON.stringify(next))
}
function showAllCategories() {
  const next: PaletteFilter = { resources: true, importedLibs: true, exampleLibs: true, builtin: true }
  filterOverride.value = next
  localStorage.setItem(PALETTE_FILTER_LS_KEY, JSON.stringify(next))
}

// --- assembled categories (sort → combine → filter) -------------------------
const allCategories = computed<PaletteCategory[]>(() => {
  const usage = props.usageCounts ?? new Map<string, number>()
  const libs = sortLibraries(libraryCategories.value, sortMode.value, usage)
  const resources = sortMode.value === 'alpha'
    ? [...resourceCategories.value].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
    : resourceCategories.value
  return [...resources, ...libs, controlCategory]
})

// Categories after the D6 filter (search applied separately below).
const visibleCategories = computed<PaletteCategory[]>(() =>
  applyFilter(allCategories.value as CatLike[], effectiveFilter.value) as PaletteCategory[],
)

// How many categories the filter is hiding (for the "{n} hidden" affordance).
const hiddenCategoryCount = computed(() =>
  hiddenCount(allCategories.value as CatLike[], effectiveFilter.value),
)

function collapseAllNow() {
  expandedCategories.value.clear()
}

// Re-collapse on file switch.
watch(() => props.filePath, (next, prev) => {
  if (!next || next === prev) return
  collapseAllNow()
})
// Re-collapse on explorer keyword refresh.
watch(() => explorer.keywordsLoaded, (loaded, wasLoaded) => {
  if (loaded && wasLoaded === false) collapseAllNow()
})

const filteredCategories = computed<PaletteCategory[]>(() => {
  const q = searchQuery.value.toLowerCase()
  if (!q) return visibleCategories.value
  return visibleCategories.value
    .map((cat): PaletteCategory | null => {
      if ('keywords' in cat) {
        const kws = cat.keywords.filter(kw => kw.toLowerCase().includes(q))
        return kws.length ? { ...cat, keywords: kws } : null
      }
      const items = cat.items.filter(it => it.label.toLowerCase().includes(q))
      return items.length ? { ...cat, items } : null
    })
    .filter((cat): cat is PaletteCategory => cat !== null)
})

// D1 — split the rendered list into the pinned "Your resources" section and
// the rest (libraries + control), so the template can draw the section
// header + divider without per-row bookkeeping.
const resourceDisplay = computed(() =>
  filteredCategories.value.filter((c): c is KeywordCategory => c.kind === 'resource'),
)
const nonResourceDisplay = computed(() =>
  filteredCategories.value.filter(c => c.kind !== 'resource'),
)

function makeStep(type: StepType = 'keyword'): RobotStep {
  return {
    type, keyword: '', args: [], returnVars: [],
    condition: '', loopVar: '${item}', loopFlavor: 'IN', loopValues: [],
    exceptPattern: '', exceptVar: '', varScope: '', comment: '',
  }
}

function addKeywordNode(keyword: string, library?: string) {
  const step = makeStep('keyword')
  step.keyword = keyword
  emit('add-node', step, library)
}

function addControlNode(type: StepType) {
  const step = makeStep(type)
  if (type === 'if') step.condition = '${condition}'
  if (type === 'for') {
    step.loopVar = '${item}'
    step.loopFlavor = 'IN'
    step.loopValues = ['@{list}']
  }
  if (type === 'while') step.condition = '${condition}'
  emit('add-node', step)
}

function onDragStart(event: DragEvent, keyword: string, library?: string) {
  event.dataTransfer?.setData('application/rf-keyword', keyword)
  if (library) event.dataTransfer?.setData('application/rf-library', library)
  event.dataTransfer!.effectAllowed = 'copy'
}

function onControlDragStart(event: DragEvent, type: StepType) {
  event.dataTransfer?.setData('application/rf-control', type)
  event.dataTransfer!.effectAllowed = 'copy'
}
</script>

<template>
  <div class="keyword-palette">
    <div class="palette-header">
      <h4>{{ t('flowEditor.palette') || 'Keywords' }}</h4>
      <div class="palette-actions">
        <!-- D5 sort control -->
        <div class="palette-menu-wrap">
          <button
            class="palette-action-btn"
            :title="t('flowEditor.sort.title')"
            data-testid="palette-sort-btn"
            @click="sortMenuOpen = !sortMenuOpen; filterMenuOpen = false"
          >&#x21C5;</button>
          <div v-if="sortMenuOpen" class="palette-menu" data-testid="palette-sort-menu">
            <button
              v-for="mode in (['mostUsed', 'alpha', 'importedFirst'] as const)"
              :key="mode"
              class="palette-menu-item"
              :class="{ 'palette-menu-item--active': sortMode === mode }"
              @click="setSort(mode)"
            >
              <span class="palette-menu-check">{{ sortMode === mode ? '✓' : '' }}</span>
              {{ t(`flowEditor.sort.${mode}`) }}
            </button>
          </div>
        </div>
        <!-- D6 filter control -->
        <div class="palette-menu-wrap">
          <button
            class="palette-action-btn"
            :class="{ 'palette-action-btn--on': hiddenCategoryCount > 0 }"
            :title="t('flowEditor.filter.title')"
            data-testid="palette-filter-btn"
            @click="filterMenuOpen = !filterMenuOpen; sortMenuOpen = false"
          >&#x25BC;</button>
          <div v-if="filterMenuOpen" class="palette-menu palette-menu--wide" data-testid="palette-filter-menu">
            <label
              v-for="key in (['resources', 'importedLibs', 'exampleLibs', 'builtin'] as const)"
              :key="key"
              class="palette-menu-item palette-menu-item--check"
            >
              <input type="checkbox" :checked="effectiveFilter[key]" @change="toggleFilter(key)" />
              {{ t(`flowEditor.filter.${key}`) }}
            </label>
          </div>
        </div>
        <button class="palette-action-btn" @click="expandAll" title="Expand all">&#x229E;</button>
        <button class="palette-action-btn" @click="collapseAll" title="Collapse all">&#x229F;</button>
      </div>
    </div>
    <input
      v-model="searchQuery"
      class="palette-search"
      :placeholder="t('flowEditor.searchKeywords') || 'Search keywords...'"
    />
    <!-- D6 "hiding N" affordance -->
    <div v-if="hiddenCategoryCount > 0 && !searchQuery" class="palette-hiding-hint" data-testid="palette-hiding-hint">
      <span>{{ t('flowEditor.filter.hidingCategories', { count: hiddenCategoryCount }) }}</span>
      <button class="palette-hiding-clear" @click="showAllCategories">{{ t('flowEditor.filter.clear') }}</button>
    </div>
    <!-- Add selected keyword button + args preview -->
    <div v-if="selectedKeyword" class="palette-add-bar">
      <div class="palette-add-info">
        <span class="palette-add-label" :title="selectedKeyword.name">{{ selectedKeyword.name }}</span>
        <div v-if="!selectedKeyword.type && getKeywordArgs(selectedKeyword.name).length" class="palette-args-preview">
          <span
            v-for="(arg, i) in getKeywordArgs(selectedKeyword.name)"
            :key="i"
            class="palette-arg-tag"
          >{{ arg }}</span>
        </div>
      </div>
      <button class="palette-add-btn" @click="addSelectedKeyword">+</button>
    </div>
    <div class="palette-categories">
      <!-- D1: pinned "Your resources" section -->
      <template v-if="resourceDisplay.length">
        <div class="palette-section-label" data-testid="palette-resources-label">
          <span class="palette-section-glyph">&#x1F4C4;</span>
          <span>{{ t('flowEditor.resourcesSectionLabel') }}</span>
          <span class="palette-section-info" :title="t('flowEditor.resourcesSectionHint')">&#x24D8;</span>
        </div>
        <div
          v-for="cat in resourceDisplay"
          :key="cat.name + (cat.relPath || '')"
          class="palette-category palette-category--resource"
          :class="{ 'palette-category--current': cat.isCurrentFile }"
        >
          <div class="category-header" @click="toggleCategory(cat.name)">
            <span class="collapse-icon">{{ isCategoryOpen(cat.name) ? '▼' : '▶' }}</span>
            <span class="category-file-glyph">{{ cat.isResourceFile ? '\u{1F4C4}' : '\u{1F916}' }}</span>
            <span class="category-file">
              <span class="category-file-name" :title="(cat.relPath ? cat.relPath + '/' : '') + cat.name">{{ cat.name }}</span>
              <span v-if="cat.relPath" class="category-file-path">{{ cat.relPath }}/</span>
            </span>
            <span
              v-if="cat.isCurrentFile"
              class="category-current-badge"
              :title="t('flowEditor.currentFileCategoryHint')"
            >{{ t('flowEditor.currentFileCategoryBadge') }}</span>
            <span class="category-count">{{ cat.keywords.length }}</span>
          </div>
          <template v-if="isCategoryOpen(cat.name)">
            <div
              v-for="kw in cat.keywords"
              :key="kw"
              class="palette-item palette-item-keyword"
              :class="{ selected: isSelected(kw) }"
              :title="kw"
              draggable="true"
              @dragstart="onDragStart($event, kw, importHintFor(cat, kw))"
              @click="selectKeyword(kw, undefined, importHintFor(cat, kw))"
              @dblclick="addKeywordNode(kw, importHintFor(cat, kw))"
            >
              <span class="palette-icon">&#x2699;</span>
              <div class="palette-item-content">
                <span class="palette-item-name">{{ kw }}</span>
                <span v-if="getKeywordArgs(kw).length" class="palette-item-argcount">({{ getKeywordArgs(kw).length }})</span>
              </div>
            </div>
          </template>
        </div>
        <div class="palette-section-divider"></div>
      </template>

      <!-- Libraries + Control -->
      <div
        v-for="cat in nonResourceDisplay"
        :key="cat.name"
        class="palette-category"
      >
        <div class="category-header" @click="toggleCategory(cat.name)">
          <span class="collapse-icon">{{ isCategoryOpen(cat.name) ? '▼' : '▶' }}</span>
          <span class="category-name">{{ cat.name }}</span>
          <span
            v-if="'isExamples' in cat && cat.isExamples"
            class="category-examples-badge"
            :title="t('flowEditor.examplesCategoryHint')"
          >{{ t('flowEditor.examplesCategoryBadge') }}</span>
          <span class="category-count">
            {{ 'keywords' in cat ? cat.keywords.length : cat.items.length }}
          </span>
        </div>

        <template v-if="isCategoryOpen(cat.name)">
          <!-- Keyword items -->
          <template v-if="'keywords' in cat">
            <div
              v-for="kw in cat.keywords"
              :key="kw"
              :class="[
                'palette-item',
                'palette-item-keyword',
                { selected: isSelected(kw),
                  'palette-item--not-imported': !isCategoryImported(cat) },
              ]"
              :title="!isCategoryImported(cat)
                ? t('flowEditor.keywordNotImportedHint', { library: cat.name })
                : kw"
              draggable="true"
              @dragstart="onDragStart($event, kw, importHintFor(cat, kw))"
              @click="selectKeyword(kw, undefined, importHintFor(cat, kw))"
              @dblclick="addKeywordNode(kw, importHintFor(cat, kw))"
            >
              <span class="palette-icon">&#x2699;</span>
              <div class="palette-item-content">
                <span class="palette-item-name">{{ kw }}</span>
                <span v-if="getKeywordArgs(kw).length" class="palette-item-argcount">({{ getKeywordArgs(kw).length }})</span>
                <span
                  v-if="!isCategoryImported(cat)"
                  class="palette-item-import-badge"
                  :title="t('flowEditor.keywordNotImportedBadgeTitle')"
                >+ lib</span>
              </div>
            </div>
          </template>

          <!-- Control items -->
          <template v-if="'items' in cat">
            <div
              v-for="item in cat.items"
              :key="item.label"
              :class="['palette-item', 'palette-item-control', { selected: isSelected(item.label) }]"
              :title="item.label"
              draggable="true"
              @dragstart="onControlDragStart($event, item.type)"
              @click="selectKeyword(item.label, item.type)"
              @dblclick="addControlNode(item.type)"
            >
              <span class="palette-icon">&#x25C6;</span>
              <span class="palette-item-name">{{ item.label }}</span>
            </div>
          </template>
        </template>
      </div>
      <div v-if="!filteredCategories.length" class="palette-empty">
        {{ t('flowEditor.noResults') || 'No matching keywords.' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.keyword-palette {
  width: 220px;
  border-right: 1px solid var(--color-border, #e2e8f0);
  background: var(--color-bg, #F4F7FA);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.palette-header {
  padding: 10px 12px 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.palette-header h4 {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
}
.palette-actions {
  display: flex;
  gap: 2px;
}
.palette-action-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 4px;
  border-radius: 4px;
  color: var(--color-text-muted, #5A6380);
}
.palette-action-btn:hover {
  background: #e2e8f0;
}
.palette-action-btn--on {
  color: var(--color-primary, #3B7DD8);
}
.palette-menu-wrap {
  position: relative;
}
.palette-menu {
  position: absolute;
  top: 100%;
  right: 0;
  z-index: 20;
  margin-top: 2px;
  min-width: 150px;
  background: #fff;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  padding: 4px;
}
.palette-menu--wide {
  min-width: 210px;
}
.palette-menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  padding: 5px 6px;
  border-radius: 4px;
  color: var(--color-text, #1A2D50);
}
.palette-menu-item:hover {
  background: #EBF4FF;
}
.palette-menu-item--active {
  font-weight: 600;
  color: var(--color-primary, #3B7DD8);
}
.palette-menu-item--check {
  cursor: pointer;
}
.palette-menu-item--check input {
  margin: 0;
}
.palette-menu-check {
  width: 12px;
  color: var(--color-primary, #3B7DD8);
}
.palette-hiding-hint {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin: 0 10px 8px;
  padding: 4px 8px;
  font-size: 11px;
  color: var(--color-text-muted, #5A6380);
  background: #eef2f7;
  border-radius: 6px;
}
.palette-hiding-clear {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary, #3B7DD8);
  padding: 0;
}
.palette-hiding-clear:hover {
  text-decoration: underline;
}
.palette-add-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 10px 8px;
  padding: 5px 8px;
  background: #EBF4FF;
  border: 1px solid var(--color-primary, #3B7DD8);
  border-radius: 6px;
}
.palette-add-info {
  flex: 1;
  min-width: 0;
}
.palette-add-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary, #3B7DD8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}
.palette-args-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}
.palette-arg-tag {
  background: #fff;
  border: 1px solid var(--color-primary, #3B7DD8);
  color: var(--color-text-muted, #5A6380);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  font-family: monospace;
  white-space: nowrap;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.palette-add-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: var(--color-primary, #3B7DD8);
  color: #fff;
  border-radius: 50%;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.palette-add-btn:hover {
  background: var(--color-navy, #1A2D50);
}
.palette-search {
  margin: 0 10px 8px;
  padding: 6px 10px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  font-size: 12px;
  outline: none;
}
.palette-search:focus {
  border-color: var(--color-primary, #3B7DD8);
}
.palette-categories {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 12px;
}
/* D1 — "Your resources" section header */
.palette-section-label {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 6px 4px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-navy, #1A2D50);
}
.palette-section-glyph {
  font-size: 12px;
}
.palette-section-info {
  margin-left: auto;
  color: var(--color-text-muted, #5A6380);
  cursor: help;
  font-style: normal;
}
.palette-section-divider {
  height: 1px;
  background: var(--color-border, #e2e8f0);
  margin: 6px 4px 4px;
}
.category-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 6px 4px;
  cursor: pointer;
  user-select: none;
  border-radius: 4px;
}
.category-header:hover {
  background: #e8ecf0;
}
.collapse-icon {
  font-size: 8px;
  color: var(--color-text-muted, #5A6380);
  width: 12px;
  text-align: center;
  flex-shrink: 0;
}
.category-name {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted, #5A6380);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* D1 — resource file header: NOT shouty, basename + path subtitle */
.category-file-glyph {
  font-size: 12px;
  flex-shrink: 0;
}
.category-file {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}
.category-file-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-navy, #1A2D50);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.category-file-path {
  font-size: 9px;
  color: var(--color-text-muted, #5A6380);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.category-count {
  font-size: 9px;
  color: var(--color-text-muted, #5A6380);
  background: #e2e8f0;
  padding: 1px 5px;
  border-radius: 8px;
  flex-shrink: 0;
}
.category-examples-badge {
  font-size: 9px;
  font-style: italic;
  color: var(--color-accent, #D4883E);
  margin-right: 4px;
  flex-shrink: 0;
}
.palette-category--current .category-header {
  background: color-mix(in srgb, var(--color-primary, #3B7DD8) 8%, transparent);
}
.palette-category--current .category-file-name {
  color: var(--color-primary, #3B7DD8);
}
.category-current-badge {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--color-primary, #3B7DD8);
  background: color-mix(in srgb, var(--color-primary, #3B7DD8) 14%, transparent);
  padding: 1px 6px;
  border-radius: 8px;
  margin-right: 4px;
  flex-shrink: 0;
}
.palette-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: grab;
  user-select: none;
  transition: background 0.15s;
}
.palette-item:hover {
  background: #e2e8f0;
}
.palette-item.selected {
  background: #EBF4FF;
  border: 1px solid var(--color-primary, #3B7DD8);
  margin: -1px 0;
}
.palette-item-content {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  min-width: 0;
}
.palette-item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}
.palette-item-argcount {
  font-size: 10px;
  color: var(--color-text-muted, #5A6380);
  flex-shrink: 0;
}
.palette-item--not-imported {
  opacity: 0.55;
  border-style: dashed;
}
.palette-item--not-imported:hover {
  opacity: 1;
  border-style: solid;
}
.palette-item-import-badge {
  flex-shrink: 0;
  margin-left: 4px;
  padding: 1px 5px;
  border: 1px solid var(--color-accent, #D4883E);
  border-radius: 3px;
  background: rgba(212, 136, 62, 0.10);
  color: var(--color-accent, #D4883E);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.palette-item:active {
  cursor: grabbing;
}
.palette-item-keyword .palette-icon {
  color: var(--color-primary, #3B7DD8);
}
.palette-item-control .palette-icon {
  color: #E8A838;
}
.palette-icon {
  flex-shrink: 0;
}
.palette-empty {
  padding: 16px 12px;
  color: var(--color-text-muted, #5A6380);
  font-size: 12px;
  text-align: center;
}
</style>
