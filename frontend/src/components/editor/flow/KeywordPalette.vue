<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useExplorerStore } from '@/stores/explorer.store'
import { searchKeywords, type RfKeywordResult } from '@/api/ai.api'
import { getProjectKeywords, type ProjectKeyword } from '@/api/explorer.api'
import type { StepType, RobotStep } from './flowConverter'

// Story TYPE-2: discriminated union for the palette categories.
// Two shapes flow through `allCategories`:
//   - keyword categories (BuiltIn, project libs, dynamic libs)
//   - the control category (IF / FOR / VAR …)
// Tagging by which key is present lets TS narrow inside the
// `'keywords' in cat` / `'items' in cat` template branches without
// `as any`.
type ControlItem = { label: string; type: StepType }
type KeywordCategory = {
  name: string
  keywords: string[]
  /** True when this category comes from the hand-curated static
   *  fallback list (`Browser`, `BuiltIn`, … with ~10 keywords
   *  each), used when the dynamic libdoc introspection returns
   *  nothing — typically because the repo has no environment
   *  configured or the library isn't installed. The header gets a
   *  small "(examples)" suffix so users don't mistake the curated
   *  subset for the full library surface. */
  isExamples?: boolean
  /** True when this Project: category corresponds to the file the
   *  user has open right now. Pinned to the top of the palette and
   *  visually marked so the user can scan to "their own" keywords
   *  faster than reading every Project: header. */
  isCurrentFile?: boolean
}
type ControlCategory = { name: string; items: ControlItem[] }
type PaletteCategory = KeywordCategory | ControlCategory

const props = defineProps<{
  repoId?: number
  /** Repo-relative path of the file the user is currently editing.
   *  Used as a re-collapse signal — every time the user switches
   *  files we clear `expandedCategories` so the palette opens
   *  in the same condensed view, regardless of how the user had
   *  expanded categories on the previous file. */
  filePath?: string
  /** Lower-cased names of libraries currently imported in the file
   *  (`Library    Browser` → `'browser'`). `BuiltIn` is always
   *  considered imported because RF auto-imports it. The palette
   *  uses this to visually dim non-imported keywords and signal
   *  that picking one will trigger an auto-import. */
  importedLibraries?: Set<string>
}>()

const { t } = useI18n()
const explorer = useExplorerStore()

const emit = defineEmits<{
  /** Add a step to the active section. `library` is the source
   *  Library name when the keyword came from one (so the parent can
   *  auto-import it if missing); `undefined` for Control items and
   *  Project / Resource keywords. */
  (e: 'add-node', step: RobotStep, library?: string): void
}>()

/** Decide if a category's keywords should render as "imported"
 *  (full opacity) or "not imported" (dimmed + auto-import on pick).
 *  Always-true for BuiltIn (RF auto-imports it), Control (not a
 *  library), and Project / Resource categories (in-repo keywords
 *  are always usable from the same repo). Everything else is
 *  gated on `props.importedLibraries`. */
function isCategoryImported(catName: string): boolean {
  if (catName === 'BuiltIn' || catName === 'Control') return true
  if (catName.startsWith('Project: ')) return true
  if (!props.importedLibraries) return true  // no signal → don't dim
  return props.importedLibraries.has(catName.toLowerCase())
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

    // Also load project-specific keywords from .robot/.resource files
    const projKws = await getProjectKeywords(props.repoId).catch(() => [])
    projectKeywords.value = projKws
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
// Track only EXPANDED categories — the palette can list 100+
// keywords across BuiltIn / Project / dynamic libs and an expanded
// state buries the search box and "(examples)" hints. With the
// default being "collapsed unless in the set", new categories that
// pop in mid-load (e.g. libdoc finishing after the initial render)
// stay collapsed automatically — no seed pass needed.
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

/** Map a category name to a library name suitable for the
 *  auto-import hint, or undefined when no auto-import should
 *  happen. Skips BuiltIn (RF auto-imports it implicitly) and
 *  Project: ... categories (those are .resource files, would need
 *  a Resource import — out of scope for the auto-import quick
 *  path; users can still add Resource manually via the library
 *  panel). Everything else passes through verbatim — for both
 *  dynamic categories (the lib name from libdoc) and static-
 *  fallback categories (Browser, Collections, String). */
function libraryHintFor(catName: string): string | undefined {
  if (catName === 'BuiltIn' || catName === 'Control') return undefined
  if (catName.startsWith('Project: ')) return undefined
  return catName
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

// Built-in keyword categories. The list is curated, not exhaustive
// — about 10 popular keywords per library — and is used to fill
// gaps in what the dynamic libdoc returned (BuiltIn is always
// stripped backend-side; common third-party libs may not be
// installed in the env yet). See `allCategories` for how these
// are merged with the dynamic data.
const categories: PaletteCategory[] = [
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
  {
    name: 'Control',
    items: [
      { label: 'IF / ELSE', type: 'if' },
      { label: 'ELSE IF', type: 'else_if' },
      { label: 'ELSE', type: 'else' },
      { label: 'FOR Loop', type: 'for' },
      { label: 'WHILE Loop', type: 'while' },
      { label: 'TRY / EXCEPT', type: 'try' },
      { label: 'VAR', type: 'var' },
      { label: 'RETURN', type: 'return' },
      { label: 'BREAK', type: 'break' },
      { label: 'CONTINUE', type: 'continue' },
      { label: 'Comment', type: 'comment' },
    ],
  },
]

/** Common library names we ALWAYS surface in the palette via the
 *  static curated subset when the dynamic libdoc didn't return
 *  them. RF-bundled libs (Collections, String, …) are shipped
 *  with `robotframework` itself but still need an explicit
 *  `Library    X` import to use; common third-party libs
 *  (Browser, SeleniumLibrary, …) need pip install + import.
 *  Either way, showing the curated subset gives the user
 *  discovery + the auto-import / install path on click.
 *  BuiltIn is the special case: always shown, never marked
 *  examples (RF auto-imports it).
 */
const _ALWAYS_VISIBLE_LIBS = [
  'BuiltIn',
  // RF-bundled (no pip install needed, only `Library    X`):
  'Collections', 'String', 'DateTime', 'OperatingSystem', 'Process', 'XML',
  // Common third-party (pip install + Library import):
  'Browser', 'SeleniumLibrary', 'RequestsLibrary', 'DatabaseLibrary',
]

// Build categories: project keywords + dynamic (from rf-mcp)
// + static curated examples for any always-visible lib not
// covered by dynamic + control. Per-library mix instead of the
// old all-or-nothing fallback so that an env with e.g. Selenium
// installed still gets the curated Browser/Requests/DB examples
// for discovery + auto-install.
const allCategories = computed(() => {
  const cats: PaletteCategory[] = []

  // Project keywords from .robot/.resource files (grouped by file).
  // The category for the file the user has currently open is pinned
  // to the top of the palette and flagged via `isCurrentFile` so the
  // template can render a "current" badge — saves the user from
  // scanning every Project: header to find their own keywords.
  if (projectKeywords.value.length > 0) {
    const currentBase = props.filePath?.split('/').pop() || ''
    const byFile = new Map<string, { paths: Set<string>; keywords: string[] }>()
    for (const kw of projectKeywords.value) {
      const file = kw.file_path.split('/').pop() || kw.file_path
      const entry = byFile.get(file) ?? { paths: new Set<string>(), keywords: [] }
      entry.paths.add(kw.file_path)
      entry.keywords.push(kw.name)
      byFile.set(file, entry)
    }
    const projCats: KeywordCategory[] = []
    for (const [file, entry] of byFile) {
      // Match basenames first; if multiple files in different folders
      // share a basename, only flag the one whose full path matches.
      const isCurrent = file === currentBase
        && (props.filePath ? entry.paths.has(props.filePath) || entry.paths.size === 1 : false)
      projCats.push({ name: `Project: ${file}`, keywords: entry.keywords, isCurrentFile: isCurrent })
    }
    projCats.sort((a, b) => Number(b.isCurrentFile) - Number(a.isCurrentFile))
    cats.push(...projCats)
  }

  // Dynamic library keywords (from rf-mcp). These show as fully-
  // available (not "examples") because the libdoc introspection
  // confirmed they're installed.
  const dynamicLibNames = new Set<string>()
  for (const [lib, keywords] of dynamicLibraries.value) {
    cats.push({
      name: lib,
      keywords: keywords.map(kw => kw.name),
    })
    dynamicLibNames.add(lib)
  }

  // Always-visible curated subsets for libs not covered by
  // dynamic. BuiltIn is special: never tagged isExamples (RF
  // auto-imports it so the "configure an environment" hint
  // doesn't apply). The rest get the (examples) badge.
  for (const libName of _ALWAYS_VISIBLE_LIBS) {
    if (dynamicLibNames.has(libName)) continue
    const staticCat = categories.find(c => c.name === libName)
    if (staticCat && 'keywords' in staticCat) {
      cats.push({
        name: staticCat.name,
        keywords: staticCat.keywords,
        isExamples: libName !== 'BuiltIn',
      })
    }
  }

  // Always add Control category at the end
  const controlCat = categories.find(c => c.name === 'Control')
  if (controlCat) cats.push(controlCat)

  return cats
})

function collapseAllNow() {
  expandedCategories.value.clear()
}

// Re-collapse on file switch — opening a different test file
// shouldn't expose the expanded view from the previous file.
watch(() => props.filePath, (next, prev) => {
  if (!next || next === prev) return
  collapseAllNow()
})

// Re-collapse on explorer keyword refresh — a fresh ExplorerView
// load (page reload, repo switch, manual refresh) flips
// `keywordsLoaded` from false to true and we want the palette to
// open condensed every time, even if the user had categories
// expanded before the refresh.
watch(() => explorer.keywordsLoaded, (loaded, wasLoaded) => {
  if (loaded && wasLoaded === false) collapseAllNow()
})

const filteredCategories = computed<PaletteCategory[]>(() => {
  const q = searchQuery.value.toLowerCase()
  if (!q) return allCategories.value
  return allCategories.value
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
  // Tag with the source library so the canvas drop handler can
  // auto-import it if missing. The caller (template) passes the
  // category name when applicable; `libraryHintFor` already
  // filtered out Project / Control / BuiltIn upstream so we can
  // trust the value and write it verbatim.
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
        <button class="palette-action-btn" @click="expandAll" title="Expand all">&#x229E;</button>
        <button class="palette-action-btn" @click="collapseAll" title="Collapse all">&#x229F;</button>
      </div>
    </div>
    <input
      v-model="searchQuery"
      class="palette-search"
      :placeholder="t('flowEditor.searchKeywords') || 'Search keywords...'"
    />
    <!-- Add selected keyword button + args preview -->
    <div v-if="selectedKeyword" class="palette-add-bar">
      <div class="palette-add-info">
        <span class="palette-add-label">{{ selectedKeyword.name }}</span>
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
      <div
        v-for="cat in filteredCategories"
        :key="cat.name"
        class="palette-category"
        :class="{ 'palette-category--current': 'isCurrentFile' in cat && cat.isCurrentFile }"
      >
        <div class="category-header" @click="toggleCategory(cat.name)">
          <span class="collapse-icon">{{ isCategoryOpen(cat.name) ? '\u25BC' : '\u25B6' }}</span>
          <span class="category-name">{{ cat.name }}</span>
          <span
            v-if="'isCurrentFile' in cat && cat.isCurrentFile"
            class="category-current-badge"
            :title="t('flowEditor.currentFileCategoryHint')"
          >{{ t('flowEditor.currentFileCategoryBadge') }}</span>
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
                  'palette-item--not-imported': !isCategoryImported(cat.name) },
              ]"
              :title="!isCategoryImported(cat.name)
                ? t('flowEditor.keywordNotImportedHint', { library: cat.name })
                : undefined"
              draggable="true"
              @dragstart="onDragStart($event, kw, libraryHintFor(cat.name))"
              @click="selectKeyword(kw, undefined, libraryHintFor(cat.name))"
              @dblclick="addKeywordNode(kw, libraryHintFor(cat.name))"
            >
              <span class="palette-icon">&#x2699;</span>
              <div class="palette-item-content">
                <span class="palette-item-name">{{ kw }}</span>
                <span v-if="getKeywordArgs(kw).length" class="palette-item-argcount">({{ getKeywordArgs(kw).length }})</span>
                <span
                  v-if="!isCategoryImported(cat.name)"
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
}
.palette-header {
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
}
.category-name {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted, #5A6380);
  flex: 1;
}
.category-count {
  font-size: 9px;
  color: var(--color-text-muted, #5A6380);
  background: #e2e8f0;
  padding: 1px 5px;
  border-radius: 8px;
}
/* Static-fallback hint: "BuiltIn (examples)", "Browser (examples)".
   Signals that the listed keywords are a curated subset, not the
   full library — kicks in when the dynamic libdoc introspection
   returned nothing (no env, library not installed, rf-mcp off). */
.category-examples-badge {
  font-size: 9px;
  font-style: italic;
  color: var(--color-accent, #D4883E);
  margin-right: 4px;
}
/* Highlights the Project: category for the file the user has open
   right now — pinned to the top of the palette and tinted so it
   stands out from the other Project: entries. */
.palette-category--current .category-header {
  background: color-mix(in srgb, var(--color-primary, #3B7DD8) 8%, transparent);
}
.palette-category--current .category-name {
  font-weight: 700;
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
}
.palette-item-argcount {
  font-size: 10px;
  color: var(--color-text-muted, #5A6380);
  flex-shrink: 0;
}

/* Dimmed appearance for keywords whose owning library isn't
   imported in the file yet. Hover restores opacity so the user can
   read the name; the "+ lib" badge signals what will happen on
   pick. The auto-import itself runs in FlowEditor. */
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
.palette-empty {
  padding: 16px 12px;
  color: var(--color-text-muted, #5A6380);
  font-size: 12px;
  text-align: center;
}
</style>
