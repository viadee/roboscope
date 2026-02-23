<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { getReportAssetUrl } from '@/api/reports.api'
import { formatDuration } from '@/utils/formatDuration'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import type { XmlKeyword } from '@/types/domain.types'

const props = defineProps<{
  keyword: XmlKeyword
  path: string
  expandedNodes: Set<string>
  reportId: number
}>()

const emit = defineEmits<{ toggle: [id: string] }>()
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

function formatTimestamp(ts: string): string {
  if (!ts) return ''
  const spaceIdx = ts.indexOf(' ')
  if (spaceIdx >= 0) return ts.substring(spaceIdx + 1)
  return ts
}

function hasHtml(text: string): boolean {
  return /<img\s/i.test(text)
}

function renderMessageHtml(text: string): string {
  return text.replace(
    /(<img\s[^>]*src=")([^"]+)(")/gi,
    (_match, prefix, src, suffix) => {
      if (src.startsWith('http')) return _match
      return prefix + getReportAssetUrl(props.reportId, src) + suffix
    }
  )
}
</script>

<template>
  <div class="tree-node">
    <div class="tree-header kw-header" @click="toggle(path)">
      <span class="tree-toggle">{{ isExpanded(path) ? '&#9660;' : '&#9654;' }}</span>
      <BaseBadge :status="keyword.status" />
      <span v-if="kwTypeLabel(keyword)" class="kw-type">{{ kwTypeLabel(keyword) }}</span>
      <span class="tree-label">
        <span v-if="keyword.library" class="kw-library">{{ keyword.library }}.</span>{{ keyword.name }}
      </span>
      <span v-if="keyword.start_time" class="tree-timestamp">{{ formatTimestamp(keyword.start_time) }}</span>
      <span class="tree-meta">{{ formatDuration(keyword.duration) }}</span>
    </div>

    <div v-if="isExpanded(path)" class="tree-children">
      <p v-if="keyword.doc" class="tree-doc">{{ keyword.doc }}</p>

      <div v-if="keyword.arguments.length" class="kw-args">
        <span class="args-label">{{ t('reportDetail.xmlView.arguments') }}:</span>
        <span v-for="(arg, i) in keyword.arguments" :key="i" class="arg-chip">{{ arg }}</span>
      </div>

      <!-- Messages -->
      <template v-for="(msg, mi) in keyword.messages" :key="mi">
        <div v-if="hasHtml(msg.text)" class="kw-message" :class="msgLevelClass(msg.level)">
          <span class="msg-timestamp">{{ formatTimestamp(msg.timestamp) }}</span>
          <span class="msg-level">{{ msg.level }}</span>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <span class="msg-text" v-html="renderMessageHtml(msg.text)"></span>
        </div>
        <div v-else class="kw-message" :class="msgLevelClass(msg.level)">
          <span class="msg-timestamp">{{ formatTimestamp(msg.timestamp) }}</span>
          <span class="msg-level">{{ msg.level }}</span>
          <span class="msg-text">{{ msg.text }}</span>
        </div>
      </template>

      <!-- Nested keywords -->
      <KeywordNode
        v-for="(childKw, cki) in keyword.keywords"
        :key="path + '-' + cki"
        :keyword="childKw"
        :path="path + '-' + cki"
        :expanded-nodes="expandedNodes"
        :report-id="reportId"
        @toggle="toggle"
      />
    </div>
  </div>
</template>
