<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { formatDuration } from '@/utils/formatDuration'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import KeywordNode from '@/components/report/KeywordNode.vue'
import type { XmlSuite, XmlTest } from '@/types/domain.types'

const props = defineProps<{
  suite: XmlSuite
  path: string
  expandedNodes: Set<string>
  reportId: number
  statusFilter: 'all' | 'PASS' | 'FAIL'
}>()

const emit = defineEmits<{ toggle: [id: string] }>()
const { t } = useI18n()

function isExpanded(id: string) { return props.expandedNodes.has(id) }
function toggle(id: string) { emit('toggle', id) }

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

function filteredTests(tests: XmlTest[]): XmlTest[] {
  if (props.statusFilter === 'all') return tests
  return tests.filter(t => t.status === props.statusFilter)
}

function suiteHasMatchingTests(suite: XmlSuite): boolean {
  if (props.statusFilter === 'all') return true
  if (suite.tests.some(t => t.status === props.statusFilter)) return true
  return (suite.suites || []).some(s => suiteHasMatchingTests(s))
}
</script>

<template>
  <div class="tree-node">
    <div class="tree-header suite-header" @click="toggle(path)">
      <span class="tree-toggle">{{ isExpanded(path) ? '&#9660;' : '&#9654;' }}</span>
      <BaseBadge :status="suite.status" />
      <span class="tree-label">{{ suite.name }}</span>
      <span class="suite-stats">
        <span class="stat-pass">&#10003; {{ countTests(suite).pass }}</span>
        <span class="stat-fail">&#10007; {{ countTests(suite).fail }}</span>
      </span>
      <span class="tree-meta">{{ formatDuration(suite.duration) }}</span>
    </div>

    <div v-if="isExpanded(path)" class="tree-children">
      <p v-if="suite.doc" class="tree-doc">{{ suite.doc }}</p>

      <template v-for="(childSuite, csi) in suite.suites" :key="path + '-' + csi">
        <SuiteNode
          v-if="suiteHasMatchingTests(childSuite)"
          :suite="childSuite"
          :path="path + '-' + csi"
          :expanded-nodes="expandedNodes"
          :report-id="reportId"
          :status-filter="statusFilter"
          @toggle="toggle"
        />
      </template>

      <div v-for="(test, ti) in filteredTests(suite.tests)" :key="path + '-t-' + ti" class="tree-node">
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
            :report-id="reportId"
            @toggle="toggle"
          />
          <p v-if="!test.keywords.length" class="text-muted text-sm">{{ t('reportDetail.xmlView.noKeywords') }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
