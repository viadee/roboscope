<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getReportXmlData, getReportAssetUrl } from '@/api/reports.api'
import { formatDuration } from '@/utils/formatDuration'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import SuiteNode from '@/components/report/SuiteNode.vue'
import KeywordNode from '@/components/report/KeywordNode.vue'
import type { XmlReportData, XmlSuite, XmlTest, XmlKeyword } from '@/types/domain.types'

const props = defineProps<{ reportId: number }>()
const { t } = useI18n()

const xmlData = ref<XmlReportData | null>(null)
const loading = ref(false)
const error = ref('')

// Track expanded nodes
const expandedNodes = ref<Set<string>>(new Set())

// Status filter
const statusFilter = ref<'all' | 'PASS' | 'FAIL'>('all')

function toggleNode(id: string) {
  if (expandedNodes.value.has(id)) {
    expandedNodes.value.delete(id)
  } else {
    expandedNodes.value.add(id)
  }
}

function isExpanded(id: string): boolean {
  return expandedNodes.value.has(id)
}

// Expand all: recursively collect all node IDs
function collectAllNodeIds(suites: XmlSuite[], prefix: string): string[] {
  const ids: string[] = []
  suites.forEach((suite, si) => {
    const suitePath = `${prefix}${si}`
    ids.push(suitePath)
    // Nested suites
    if (suite.suites) {
      ids.push(...collectAllNodeIds(suite.suites, `${suitePath}-`))
    }
    // Tests
    suite.tests.forEach((test, ti) => {
      const testPath = `${suitePath}-t-${ti}`
      ids.push(testPath)
      // Keywords in tests
      test.keywords.forEach((_kw, ki) => {
        ids.push(...collectKeywordIds(`${testPath}-kw-${ki}`, _kw))
      })
    })
  })
  return ids
}

function collectKeywordIds(path: string, kw: XmlKeyword): string[] {
  const ids = [path]
  kw.keywords.forEach((child, ci) => {
    ids.push(...collectKeywordIds(`${path}-${ci}`, child))
  })
  return ids
}

function expandAll() {
  if (!xmlData.value) return
  const ids = collectAllNodeIds(xmlData.value.suites, 'suite-')
  expandedNodes.value = new Set(ids)
}

function collapseAll() {
  expandedNodes.value = new Set()
}

// Count tests recursively in a suite
function countTests(suite: XmlSuite): { pass: number; fail: number } {
  let pass = 0
  let fail = 0
  for (const test of suite.tests) {
    if (test.status === 'PASS') pass++
    else fail++
  }
  for (const child of suite.suites || []) {
    const c = countTests(child)
    pass += c.pass
    fail += c.fail
  }
  return { pass, fail }
}

// Filter tests by status
function filteredTests(tests: XmlTest[]): XmlTest[] {
  if (statusFilter.value === 'all') return tests
  return tests.filter(t => t.status === statusFilter.value)
}

// Check if a suite has any matching tests (recursively)
function suiteHasMatchingTests(suite: XmlSuite): boolean {
  if (statusFilter.value === 'all') return true
  if (suite.tests.some(t => t.status === statusFilter.value)) return true
  return (suite.suites || []).some(s => suiteHasMatchingTests(s))
}

// Format timestamp from RF format "20240101 12:00:00.000" -> "12:00:00.000"
function formatTimestamp(ts: string): string {
  if (!ts) return ''
  const spaceIdx = ts.indexOf(' ')
  if (spaceIdx >= 0) return ts.substring(spaceIdx + 1)
  return ts
}

function msgLevelClass(level: string): string {
  switch (level.toUpperCase()) {
    case 'FAIL': return 'msg-fail'
    case 'WARN': return 'msg-warn'
    case 'ERROR': return 'msg-fail'
    case 'DEBUG': return 'msg-debug'
    default: return 'msg-info'
  }
}

function kwTypeLabel(kw: XmlKeyword): string {
  switch (kw.type) {
    case 'setup': return `[${t('reportDetail.xmlView.setup')}]`
    case 'teardown': return `[${t('reportDetail.xmlView.teardown')}]`
    default: return ''
  }
}

// Check if message text contains HTML img tags
function hasHtml(text: string): boolean {
  return /<img\s/i.test(text)
}

// Rewrite img src attributes to use asset endpoint
function renderMessageHtml(text: string): string {
  return text.replace(
    /(<img\s[^>]*src=")([^"]+)(")/gi,
    (_match, prefix, src, suffix) => {
      if (src.startsWith('http')) return _match
      return prefix + getReportAssetUrl(props.reportId, src) + suffix
    }
  )
}

// Filtered top-level suites
const filteredSuites = computed(() => {
  if (!xmlData.value) return []
  if (statusFilter.value === 'all') return xmlData.value.suites
  return xmlData.value.suites.filter(s => suiteHasMatchingTests(s))
})

onMounted(async () => {
  loading.value = true
  try {
    xmlData.value = await getReportXmlData(props.reportId)
    // Auto-expand top-level suites
    if (xmlData.value?.suites) {
      xmlData.value.suites.forEach((_s, i) => {
        expandedNodes.value.add(`suite-${i}`)
      })
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load XML data'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="xml-view">
    <BaseSpinner v-if="loading" />

    <div v-else-if="error" class="empty-state">
      <p class="text-danger">{{ error }}</p>
    </div>

    <div v-else-if="!xmlData || !xmlData.suites.length" class="empty-state">
      <p class="text-muted">{{ t('reportDetail.noXmlData') }}</p>
    </div>

    <div v-else>
      <!-- Toolbar -->
      <div class="xml-toolbar">
        <button class="toolbar-btn" @click="expandAll">{{ t('reportDetail.xmlView.expandAll') }}</button>
        <button class="toolbar-btn" @click="collapseAll">{{ t('reportDetail.xmlView.collapseAll') }}</button>
        <select v-model="statusFilter" class="toolbar-select">
          <option value="all">{{ t('reportDetail.xmlView.filterAll') }}</option>
          <option value="PASS">{{ t('reportDetail.xmlView.filterPassed') }}</option>
          <option value="FAIL">{{ t('reportDetail.xmlView.filterFailed') }}</option>
        </select>
      </div>

      <div class="xml-tree">
        <!-- Suites -->
        <div v-for="(suite, si) in filteredSuites" :key="`suite-${si}`" class="tree-node">
          <div class="tree-header suite-header" @click="toggleNode(`suite-${si}`)">
            <span class="tree-toggle">{{ isExpanded(`suite-${si}`) ? '&#9660;' : '&#9654;' }}</span>
            <BaseBadge :status="suite.status" />
            <span class="tree-label">{{ suite.name }}</span>
            <span class="suite-stats">
              <span class="stat-pass">&#10003; {{ countTests(suite).pass }}</span>
              <span class="stat-fail">&#10007; {{ countTests(suite).fail }}</span>
            </span>
            <span class="tree-meta">{{ formatDuration(suite.duration) }}</span>
          </div>

          <div v-if="isExpanded(`suite-${si}`)" class="tree-children">
            <p v-if="suite.doc" class="tree-doc">{{ suite.doc }}</p>

            <!-- Nested suites -->
            <template v-for="(childSuite, csi) in suite.suites" :key="`suite-${si}-${csi}`">
              <SuiteNode
                v-if="suiteHasMatchingTests(childSuite)"
                :suite="childSuite"
                :path="`suite-${si}-${csi}`"
                :expanded-nodes="expandedNodes"
                :report-id="reportId"
                :status-filter="statusFilter"
                @toggle="toggleNode"
              />
            </template>

            <!-- Tests -->
            <div v-for="(test, ti) in filteredTests(suite.tests)" :key="`suite-${si}-t-${ti}`" class="tree-node">
              <div class="tree-header test-header" @click="toggleNode(`suite-${si}-t-${ti}`)">
                <span class="tree-toggle">{{ isExpanded(`suite-${si}-t-${ti}`) ? '&#9660;' : '&#9654;' }}</span>
                <BaseBadge :status="test.status" />
                <span class="tree-label">{{ test.name }}</span>
                <span v-if="test.tags.length" class="tree-tags">
                  <span v-for="tag in test.tags" :key="tag" class="tag-chip">{{ tag }}</span>
                </span>
                <span class="tree-meta">{{ formatDuration(test.duration) }}</span>
              </div>

              <div v-if="isExpanded(`suite-${si}-t-${ti}`)" class="tree-children">
                <p v-if="test.doc" class="tree-doc">{{ test.doc }}</p>
                <p v-if="test.error_message" class="tree-error">{{ test.error_message }}</p>

                <!-- Keywords -->
                <template v-for="(kw, ki) in test.keywords" :key="`suite-${si}-t-${ti}-kw-${ki}`">
                  <KeywordNode
                    :keyword="kw"
                    :path="`suite-${si}-t-${ti}-kw-${ki}`"
                    :expanded-nodes="expandedNodes"
                    :report-id="reportId"
                    @toggle="toggleNode"
                  />
                </template>
                <p v-if="!test.keywords.length" class="text-muted text-sm">{{ t('reportDetail.xmlView.noKeywords') }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.xml-view { padding: 0; }

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--color-text-muted);
}

/* Toolbar */
.xml-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
}

.toolbar-btn {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px;
  background: var(--color-bg-card, #ffffff);
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.15s;
}

.toolbar-btn:hover {
  background: var(--color-bg-hover, #f1f5f9);
  border-color: var(--color-primary, #3B7DD8);
  color: var(--color-primary, #3B7DD8);
}

.toolbar-select {
  padding: 4px 8px;
  font-size: 12px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px;
  background: var(--color-bg-card, #ffffff);
  color: var(--color-text);
  cursor: pointer;
  margin-left: auto;
}

.xml-tree {
  font-size: 13px;
}
</style>

<style>
/* Shared tree styles (not scoped — used by child components SuiteNode, KeywordNode) */
.xml-view .tree-node {
  border-left: 2px solid var(--color-border, #e2e8f0);
  margin-left: 8px;
}

.xml-view .tree-node:first-child {
  border-left: none;
  margin-left: 0;
}

.xml-view .tree-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.15s;
}

.xml-view .tree-header:hover {
  background-color: var(--color-bg-hover, #f1f5f9);
}

.xml-view .tree-toggle {
  font-size: 10px;
  width: 14px;
  flex-shrink: 0;
  color: var(--color-text-muted);
  user-select: none;
}

.xml-view .tree-label {
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xml-view .tree-meta {
  font-size: 11px;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.xml-view .tree-timestamp {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: monospace;
  flex-shrink: 0;
}

.xml-view .tree-children {
  padding-left: 16px;
}

.xml-view .tree-doc {
  font-size: 12px;
  color: var(--color-text-muted);
  font-style: italic;
  margin: 2px 0 4px 30px;
}

.xml-view .tree-error {
  font-size: 12px;
  color: var(--color-danger);
  margin: 2px 0 4px 30px;
  background: rgba(220, 38, 38, 0.05);
  padding: 4px 8px;
  border-radius: 4px;
  border-left: 3px solid var(--color-danger);
}

.xml-view .suite-header .tree-label { color: var(--color-navy, #1A2D50); }
.xml-view .test-header .tree-label { color: var(--color-text); }
.xml-view .kw-header .tree-label { color: var(--color-text-muted); font-weight: 400; }

/* Suite stats */
.xml-view .suite-stats {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
}

.xml-view .stat-pass {
  color: var(--color-success, #16a34a);
}

.xml-view .stat-fail {
  color: var(--color-danger, #dc2626);
}

.xml-view .kw-type {
  font-size: 10px;
  color: var(--color-accent, #D4883E);
  font-weight: 600;
  text-transform: uppercase;
  flex-shrink: 0;
}

.xml-view .kw-library {
  color: var(--color-text-muted);
  font-weight: 400;
}

.xml-view .tree-tags {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.xml-view .tag-chip {
  font-size: 10px;
  background: var(--color-primary, #3B7DD8);
  color: white;
  padding: 1px 6px;
  border-radius: 8px;
}

.xml-view .kw-args {
  font-size: 12px;
  margin: 2px 0 4px 30px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.xml-view .args-label {
  color: var(--color-text-muted);
  font-weight: 500;
}

.xml-view .arg-chip {
  background: var(--color-bg, #f4f7fa);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 11px;
}

.xml-view .kw-message {
  font-size: 12px;
  margin: 1px 0 1px 30px;
  padding: 2px 8px;
  border-radius: 3px;
  display: flex;
  gap: 8px;
  font-family: monospace;
  align-items: flex-start;
}

.xml-view .msg-timestamp {
  font-size: 10px;
  color: var(--color-text-muted);
  font-family: monospace;
  flex-shrink: 0;
  min-width: 80px;
}

.xml-view .msg-level {
  font-weight: 600;
  flex-shrink: 0;
  width: 40px;
  font-size: 10px;
  text-transform: uppercase;
}

.xml-view .msg-text {
  word-break: break-word;
}

/* Screenshot images rendered via v-html */
.xml-view .msg-text img {
  max-width: 600px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 6px;
  margin: 8px 0;
  display: block;
  cursor: pointer;
}

.xml-view .msg-text img:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.xml-view .msg-info { color: var(--color-text-muted); }
.xml-view .msg-info .msg-level { color: var(--color-text-muted); }

.xml-view .msg-warn { color: #b45309; background: rgba(217, 119, 6, 0.05); }
.xml-view .msg-warn .msg-level { color: #d97706; }

.xml-view .msg-fail { color: var(--color-danger); background: rgba(220, 38, 38, 0.05); }
.xml-view .msg-fail .msg-level { color: var(--color-danger); }

.xml-view .msg-debug { color: #6b7280; }
.xml-view .msg-debug .msg-level { color: #9ca3af; }
</style>
