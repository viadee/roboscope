<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { searchKeywords, type RfKeywordResult } from '@/api/ai.api'
import type { StepType, RobotStep } from './flowConverter'

const props = defineProps<{
  repoId?: number
}>()

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'add-node', step: RobotStep): void
}>()

// Dynamic keywords from rf-mcp
const dynamicLibraries = ref<Map<string, RfKeywordResult[]>>(new Map())
const loadingKeywords = ref(false)

async function loadDynamicKeywords() {
  if (!props.repoId) return
  loadingKeywords.value = true
  try {
    // Search with empty query returns all available keywords
    const result = await searchKeywords('*', props.repoId)
    // Group by library
    const grouped = new Map<string, RfKeywordResult[]>()
    for (const kw of result.results) {
      const lib = kw.library || 'Unknown'
      if (!grouped.has(lib)) grouped.set(lib, [])
      grouped.get(lib)!.push(kw)
    }
    dynamicLibraries.value = grouped
  } catch {
    // rf-mcp might not be running — fall back to static list
  } finally {
    loadingKeywords.value = false
  }
}

onMounted(() => loadDynamicKeywords())
watch(() => props.repoId, () => loadDynamicKeywords())

const searchQuery = ref('')
const collapsedCategories = ref<Set<string>>(new Set())
const selectedKeyword = ref<{ name: string; type?: StepType } | null>(null)

function toggleCategory(name: string) {
  if (collapsedCategories.value.has(name)) {
    collapsedCategories.value.delete(name)
  } else {
    collapsedCategories.value.add(name)
  }
}
function isCategoryOpen(name: string): boolean {
  if (searchQuery.value) return true
  return !collapsedCategories.value.has(name)
}
function expandAll() {
  collapsedCategories.value.clear()
}
function collapseAll() {
  for (const cat of allCategories.value) {
    collapsedCategories.value.add(cat.name)
  }
}

function selectKeyword(name: string, type?: StepType) {
  selectedKeyword.value = { name, type }
}
function isSelected(name: string): boolean {
  return selectedKeyword.value?.name === name
}
function addSelectedKeyword() {
  if (!selectedKeyword.value) return
  if (selectedKeyword.value.type) {
    addControlNode(selectedKeyword.value.type)
  } else {
    addKeywordNode(selectedKeyword.value.name)
  }
  selectedKeyword.value = null
}

// Built-in keyword categories
const categories = [
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
    name: 'Browser',
    keywords: [
      'New Browser', 'New Page', 'Click', 'Fill Text', 'Get Text',
      'Wait For Elements State', 'Take Screenshot', 'Go To',
      'Get Url', 'Close Browser',
    ],
  },
  {
    name: 'Control',
    items: [
      { label: 'IF / ELSE', type: 'if' as StepType },
      { label: 'ELSE IF', type: 'else_if' as StepType },
      { label: 'ELSE', type: 'else' as StepType },
      { label: 'FOR Loop', type: 'for' as StepType },
      { label: 'WHILE Loop', type: 'while' as StepType },
      { label: 'TRY / EXCEPT', type: 'try' as StepType },
      { label: 'VAR', type: 'var' as StepType },
      { label: 'RETURN', type: 'return' as StepType },
      { label: 'BREAK', type: 'break' as StepType },
      { label: 'CONTINUE', type: 'continue' as StepType },
      { label: 'Comment', type: 'comment' as StepType },
    ],
  },
]

// Build categories: dynamic (from rf-mcp) + static fallbacks + control
const allCategories = computed(() => {
  const cats: typeof categories = []

  // Dynamic library keywords (from rf-mcp, if available)
  for (const [lib, keywords] of dynamicLibraries.value) {
    cats.push({
      name: lib,
      keywords: keywords.map(kw => kw.name),
    } as any)
  }

  // If no dynamic keywords loaded, use static fallbacks
  if (cats.length === 0) {
    cats.push(...categories.filter(c => c.name !== 'Control'))
  }

  // Always add Control category at the end
  const controlCat = categories.find(c => c.name === 'Control')
  if (controlCat) cats.push(controlCat)

  return cats
})

const filteredCategories = computed(() => {
  const q = searchQuery.value.toLowerCase()
  if (!q) return allCategories.value
  return allCategories.value
    .map(cat => {
      if ('keywords' in cat && cat.keywords) {
        const kws = cat.keywords.filter((kw: string) => kw.toLowerCase().includes(q))
        return kws.length ? { ...cat, keywords: kws } : null
      }
      if ('items' in cat && cat.items) {
        const items = cat.items.filter((it: { label: string }) => it.label.toLowerCase().includes(q))
        return items.length ? { ...cat, items } : null
      }
      return null
    })
    .filter(Boolean)
})

function makeStep(type: StepType = 'keyword'): RobotStep {
  return {
    type, keyword: '', args: [], returnVars: [],
    condition: '', loopVar: '${item}', loopFlavor: 'IN', loopValues: [],
    exceptPattern: '', exceptVar: '', varScope: '', comment: '',
  }
}

function addKeywordNode(keyword: string) {
  const step = makeStep('keyword')
  step.keyword = keyword
  emit('add-node', step)
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

function onDragStart(event: DragEvent, keyword: string) {
  event.dataTransfer?.setData('application/rf-keyword', keyword)
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
    <!-- Add selected keyword button -->
    <div v-if="selectedKeyword" class="palette-add-bar">
      <span class="palette-add-label">{{ selectedKeyword.name }}</span>
      <button class="palette-add-btn" @click="addSelectedKeyword">+</button>
    </div>
    <div class="palette-categories">
      <div v-for="cat in filteredCategories" :key="cat!.name" class="palette-category">
        <div class="category-header" @click="toggleCategory(cat!.name)">
          <span class="collapse-icon">{{ isCategoryOpen(cat!.name) ? '\u25BC' : '\u25B6' }}</span>
          <span class="category-name">{{ cat!.name }}</span>
          <span class="category-count">
            {{ 'keywords' in cat! ? (cat as any).keywords?.length : (cat as any).items?.length }}
          </span>
        </div>

        <template v-if="isCategoryOpen(cat!.name)">
          <!-- Keyword items -->
          <template v-if="'keywords' in cat!">
            <div
              v-for="kw in (cat as any).keywords"
              :key="kw"
              :class="['palette-item', 'palette-item-keyword', { selected: isSelected(kw) }]"
              draggable="true"
              @dragstart="onDragStart($event, kw)"
              @click="selectKeyword(kw)"
              @dblclick="addKeywordNode(kw)"
            >
              <span class="palette-icon">&#x2699;</span>
              <span class="palette-item-name">{{ kw }}</span>
            </div>
          </template>

          <!-- Control items -->
          <template v-if="'items' in cat!">
            <div
              v-for="item in (cat as any).items"
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
.palette-add-label {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary, #3B7DD8);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.palette-item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
