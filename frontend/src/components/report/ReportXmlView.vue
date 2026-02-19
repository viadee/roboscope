<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getReportXmlData } from '@/api/reports.api'
import { formatDuration } from '@/utils/formatDuration'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import type { XmlReportData, XmlSuite, XmlTest, XmlKeyword } from '@/types/domain.types'

const props = defineProps<{ reportId: number }>()
const { t } = useI18n()

const xmlData = ref<XmlReportData | null>(null)
const loading = ref(false)
const error = ref('')

// Track expanded nodes
const expandedNodes = ref<Set<string>>(new Set())

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

onMounted(async () => {
  loading.value = true
  try {
    xmlData.value = await getReportXmlData(props.reportId)
    // Auto-expand top-level suites
    if (xmlData.value?.suites) {
      xmlData.value.suites.forEach((s, i) => {
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

    <div v-else class="xml-tree">
      <!-- Suites -->
      <div v-for="(suite, si) in xmlData.suites" :key="`suite-${si}`" class="tree-node">
        <div class="tree-header suite-header" @click="toggleNode(`suite-${si}`)">
          <span class="tree-toggle">{{ isExpanded(`suite-${si}`) ? '&#9660;' : '&#9654;' }}</span>
          <BaseBadge :status="suite.status" />
          <span class="tree-label">{{ suite.name }}</span>
          <span class="tree-meta">{{ formatDuration(suite.duration) }}</span>
        </div>

        <div v-if="isExpanded(`suite-${si}`)" class="tree-children">
          <p v-if="suite.doc" class="tree-doc">{{ suite.doc }}</p>

          <!-- Nested suites -->
          <template v-for="(childSuite, csi) in suite.suites" :key="`suite-${si}-${csi}`">
            <SuiteNode
              :suite="childSuite"
              :path="`suite-${si}-${csi}`"
              :expanded-nodes="expandedNodes"
              @toggle="toggleNode"
            />
          </template>

          <!-- Tests -->
          <div v-for="(test, ti) in suite.tests" :key="`test-${si}-${ti}`" class="tree-node">
            <div class="tree-header test-header" @click="toggleNode(`test-${si}-${ti}`)">
              <span class="tree-toggle">{{ isExpanded(`test-${si}-${ti}`) ? '&#9660;' : '&#9654;' }}</span>
              <BaseBadge :status="test.status" />
              <span class="tree-label">{{ test.name }}</span>
              <span v-if="test.tags.length" class="tree-tags">
                <span v-for="tag in test.tags" :key="tag" class="tag-chip">{{ tag }}</span>
              </span>
              <span class="tree-meta">{{ formatDuration(test.duration) }}</span>
            </div>

            <div v-if="isExpanded(`test-${si}-${ti}`)" class="tree-children">
              <p v-if="test.doc" class="tree-doc">{{ test.doc }}</p>
              <p v-if="test.error_message" class="tree-error">{{ test.error_message }}</p>

              <!-- Keywords -->
              <template v-for="(kw, ki) in test.keywords" :key="`kw-${si}-${ti}-${ki}`">
                <KeywordNode
                  :keyword="kw"
                  :path="`kw-${si}-${ti}-${ki}`"
                  :expanded-nodes="expandedNodes"
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
</template>

<!-- Recursive SuiteNode component (defined inline via script) -->
<script lang="ts">
import { defineComponent, type PropType } from 'vue'

const KeywordNode = defineComponent({
  name: 'KeywordNode',
  components: { BaseBadge },
  props: {
    keyword: { type: Object as PropType<XmlKeyword>, required: true },
    path: { type: String, required: true },
    expandedNodes: { type: Object as PropType<Set<string>>, required: true },
  },
  emits: ['toggle'],
  setup(props, { emit }) {
    const { t } = useI18n()

    function isExpanded(id: string) { return props.expandedNodes.has(id) }
    function toggle(id: string) { emit('toggle', id) }

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

    return { isExpanded, toggle, msgLevelClass, kwTypeLabel, t, formatDuration }
  },
  template: `
    <div class="tree-node">
      <div class="tree-header kw-header" @click="toggle(path)">
        <span class="tree-toggle">{{ isExpanded(path) ? '&#9660;' : '&#9654;' }}</span>
        <BaseBadge :status="keyword.status" />
        <span v-if="kwTypeLabel(keyword)" class="kw-type">{{ kwTypeLabel(keyword) }}</span>
        <span class="tree-label">
          <span v-if="keyword.library" class="kw-library">{{ keyword.library }}.</span>{{ keyword.name }}
        </span>
        <span class="tree-meta">{{ formatDuration(keyword.duration) }}</span>
      </div>

      <div v-if="isExpanded(path)" class="tree-children">
        <p v-if="keyword.doc" class="tree-doc">{{ keyword.doc }}</p>

        <div v-if="keyword.arguments.length" class="kw-args">
          <span class="args-label">{{ t('reportDetail.xmlView.arguments') }}:</span>
          <span v-for="(arg, i) in keyword.arguments" :key="i" class="arg-chip">{{ arg }}</span>
        </div>

        <!-- Messages -->
        <div v-for="(msg, mi) in keyword.messages" :key="mi" class="kw-message" :class="msgLevelClass(msg.level)">
          <span class="msg-level">{{ msg.level }}</span>
          <span class="msg-text">{{ msg.text }}</span>
        </div>

        <!-- Nested keywords -->
        <KeywordNode
          v-for="(childKw, cki) in keyword.keywords"
          :key="path + '-' + cki"
          :keyword="childKw"
          :path="path + '-' + cki"
          :expanded-nodes="expandedNodes"
          @toggle="toggle"
        />
      </div>
    </div>
  `,
})

const SuiteNode = defineComponent({
  name: 'SuiteNode',
  components: { BaseBadge, KeywordNode },
  props: {
    suite: { type: Object as PropType<XmlSuite>, required: true },
    path: { type: String, required: true },
    expandedNodes: { type: Object as PropType<Set<string>>, required: true },
  },
  emits: ['toggle'],
  setup(props, { emit }) {
    const { t } = useI18n()

    function isExpanded(id: string) { return props.expandedNodes.has(id) }
    function toggle(id: string) { emit('toggle', id) }

    return { isExpanded, toggle, t, formatDuration }
  },
  template: `
    <div class="tree-node">
      <div class="tree-header suite-header" @click="toggle(path)">
        <span class="tree-toggle">{{ isExpanded(path) ? '&#9660;' : '&#9654;' }}</span>
        <BaseBadge :status="suite.status" />
        <span class="tree-label">{{ suite.name }}</span>
        <span class="tree-meta">{{ formatDuration(suite.duration) }}</span>
      </div>

      <div v-if="isExpanded(path)" class="tree-children">
        <p v-if="suite.doc" class="tree-doc">{{ suite.doc }}</p>

        <SuiteNode
          v-for="(childSuite, csi) in suite.suites"
          :key="path + '-' + csi"
          :suite="childSuite"
          :path="path + '-' + csi"
          :expanded-nodes="expandedNodes"
          @toggle="toggle"
        />

        <div v-for="(test, ti) in suite.tests" :key="path + '-t-' + ti" class="tree-node">
          <div class="tree-header test-header" @click="toggle(path + '-t-' + ti)">
            <span class="tree-toggle">{{ isExpanded(path + '-t-' + ti) ? '&#9660;' : '&#9654;' }}</span>
            <BaseBadge :status="test.status" />
            <span class="tree-label">{{ test.name }}</span>
            <span v-if="test.tags.length" class="tree-tags">
              <span v-for="tag in test.tags" :key="tag" class="tag-chip">{{ tag }}</span>
            </span>
            <span class="tree-meta">{{ formatDuration(test.duration) }}</span>
          </div>

          <div v-if="isExpanded(path + '-t-' + ti)" class="tree-children">
            <p v-if="test.doc" class="tree-doc">{{ test.doc }}</p>
            <p v-if="test.error_message" class="tree-error">{{ test.error_message }}</p>

            <KeywordNode
              v-for="(kw, ki) in test.keywords"
              :key="path + '-t-' + ti + '-kw-' + ki"
              :keyword="kw"
              :path="path + '-t-' + ti + '-kw-' + ki"
              :expanded-nodes="expandedNodes"
              @toggle="toggle"
            />
            <p v-if="!test.keywords.length" class="text-muted text-sm">{{ t('reportDetail.xmlView.noKeywords') }}</p>
          </div>
        </div>
      </div>
    </div>
  `,
})

export default {
  components: { SuiteNode, KeywordNode },
}
</script>

<style scoped>
.xml-view { padding: 0; }

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--color-text-muted);
}

.xml-tree {
  font-size: 13px;
}

.tree-node {
  border-left: 2px solid var(--color-border, #e2e8f0);
  margin-left: 8px;
}

.tree-node:first-child {
  border-left: none;
  margin-left: 0;
}

.tree-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.15s;
}

.tree-header:hover {
  background-color: var(--color-bg-hover, #f1f5f9);
}

.tree-toggle {
  font-size: 10px;
  width: 14px;
  flex-shrink: 0;
  color: var(--color-text-muted);
  user-select: none;
}

.tree-label {
  font-weight: 500;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-meta {
  font-size: 11px;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.tree-children {
  padding-left: 16px;
}

.tree-doc {
  font-size: 12px;
  color: var(--color-text-muted);
  font-style: italic;
  margin: 2px 0 4px 30px;
}

.tree-error {
  font-size: 12px;
  color: var(--color-danger);
  margin: 2px 0 4px 30px;
  background: rgba(220, 38, 38, 0.05);
  padding: 4px 8px;
  border-radius: 4px;
  border-left: 3px solid var(--color-danger);
}

.suite-header .tree-label { color: var(--color-navy, #1A2D50); }
.test-header .tree-label { color: var(--color-text); }
.kw-header .tree-label { color: var(--color-text-muted); font-weight: 400; }

.kw-type {
  font-size: 10px;
  color: var(--color-accent, #D4883E);
  font-weight: 600;
  text-transform: uppercase;
  flex-shrink: 0;
}

.kw-library {
  color: var(--color-text-muted);
  font-weight: 400;
}

.tree-tags {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.tag-chip {
  font-size: 10px;
  background: var(--color-primary, #3B7DD8);
  color: white;
  padding: 1px 6px;
  border-radius: 8px;
}

.kw-args {
  font-size: 12px;
  margin: 2px 0 4px 30px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.args-label {
  color: var(--color-text-muted);
  font-weight: 500;
}

.arg-chip {
  background: var(--color-bg, #f4f7fa);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 11px;
}

.kw-message {
  font-size: 12px;
  margin: 1px 0 1px 30px;
  padding: 2px 8px;
  border-radius: 3px;
  display: flex;
  gap: 8px;
  font-family: monospace;
}

.msg-level {
  font-weight: 600;
  flex-shrink: 0;
  width: 40px;
  font-size: 10px;
  text-transform: uppercase;
}

.msg-text {
  word-break: break-word;
}

.msg-info { color: var(--color-text-muted); }
.msg-info .msg-level { color: var(--color-text-muted); }

.msg-warn { color: #b45309; background: rgba(217, 119, 6, 0.05); }
.msg-warn .msg-level { color: #d97706; }

.msg-fail { color: var(--color-danger); background: rgba(220, 38, 38, 0.05); }
.msg-fail .msg-level { color: var(--color-danger); }

.msg-debug { color: #6b7280; }
.msg-debug .msg-level { color: #9ca3af; }
</style>
