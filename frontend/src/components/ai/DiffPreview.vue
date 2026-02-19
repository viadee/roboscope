<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  before: string
  after: string
  fileName: string
}>()

const { t } = useI18n()
const viewMode = ref<'split' | 'unified' | 'raw'>('raw')

const beforeLines = computed(() => props.before.split('\n'))
const afterLines = computed(() => props.after.split('\n'))

const diffLines = computed(() => {
  // Simple line-by-line diff
  const result: Array<{ type: 'same' | 'add' | 'remove'; line: string; lineNum: number }> = []
  const maxLen = Math.max(beforeLines.value.length, afterLines.value.length)

  if (!props.before) {
    // All new
    afterLines.value.forEach((line, i) => {
      result.push({ type: 'add', line, lineNum: i + 1 })
    })
    return result
  }

  // LCS-based diff is complex; use simple sequential comparison
  const bSet = new Set(beforeLines.value)
  const aSet = new Set(afterLines.value)

  // Removed lines (in before but not in after)
  beforeLines.value.forEach((line, i) => {
    if (!aSet.has(line)) {
      result.push({ type: 'remove', line, lineNum: i + 1 })
    }
  })

  // Show after with markers
  afterLines.value.forEach((line, i) => {
    if (!bSet.has(line)) {
      result.push({ type: 'add', line, lineNum: i + 1 })
    } else {
      result.push({ type: 'same', line, lineNum: i + 1 })
    }
  })

  return result
})
</script>

<template>
  <div class="diff-preview">
    <div class="diff-toolbar">
      <span class="diff-filename">{{ fileName }}</span>
      <div class="diff-tabs">
        <button :class="{ active: viewMode === 'raw' }" @click="viewMode = 'raw'">
          {{ t('ai.rawOutput') }}
        </button>
        <button :class="{ active: viewMode === 'unified' }" @click="viewMode = 'unified'">
          {{ t('ai.diffView') }}
        </button>
      </div>
    </div>

    <!-- Raw output -->
    <div v-if="viewMode === 'raw'" class="diff-content">
      <pre class="code-block"><code>{{ after }}</code></pre>
    </div>

    <!-- Unified diff -->
    <div v-else class="diff-content">
      <div class="diff-lines">
        <div
          v-for="(d, i) in diffLines"
          :key="i"
          class="diff-line"
          :class="{
            'diff-add': d.type === 'add',
            'diff-remove': d.type === 'remove',
          }"
        >
          <span class="diff-marker">{{ d.type === 'add' ? '+' : d.type === 'remove' ? '-' : ' ' }}</span>
          <span class="diff-num">{{ d.lineNum }}</span>
          <span class="diff-text">{{ d.line }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diff-preview {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.diff-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--color-bg);
  border-bottom: 1px solid var(--color-border);
}

.diff-filename {
  font-family: monospace;
  font-size: 12px;
  color: var(--color-text-muted);
}

.diff-tabs {
  display: flex;
  gap: 4px;
}

.diff-tabs button {
  background: none;
  border: 1px solid var(--color-border);
  padding: 3px 10px;
  font-size: 11px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--color-text-muted);
  transition: all 0.15s;
}

.diff-tabs button.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.diff-content {
  max-height: 400px;
  overflow: auto;
}

.code-block {
  margin: 0;
  padding: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--color-text);
}

.diff-lines {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.diff-line {
  display: flex;
  padding: 0 12px;
}

.diff-marker {
  width: 16px;
  text-align: center;
  flex-shrink: 0;
  color: var(--color-text-muted);
  user-select: none;
}

.diff-num {
  width: 40px;
  text-align: right;
  padding-right: 8px;
  color: var(--color-text-light);
  flex-shrink: 0;
  user-select: none;
}

.diff-text {
  white-space: pre-wrap;
  word-break: break-all;
}

.diff-add {
  background: #e6ffec;
}

.diff-add .diff-marker {
  color: var(--color-success);
}

.diff-remove {
  background: #ffeef0;
}

.diff-remove .diff-marker {
  color: var(--color-danger);
}
</style>
