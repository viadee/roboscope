<script setup lang="ts">
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAiStore } from '@/stores/ai.store'
import { extractErrorDetail } from '@/utils/errors'
import type { SuggestedPatch } from '@/types/domain.types'

const props = defineProps<{
  patches: SuggestedPatch[]
  /** Repo the patched files belong to (from the analysis job). When null the
   *  auto-apply button is hidden — we can't resolve the file without it. */
  repositoryId: number | null
}>()

const emit = defineEmits<{ applied: [filePath: string] }>()

const { t } = useI18n()
const aiStore = useAiStore()

type PatchState = { status: 'idle' | 'applying' | 'applied' | 'error'; error: string }
// Keyed by patch index — survives re-render of the list.
const states = reactive<Record<number, PatchState>>({})

function stateFor(idx: number): PatchState {
  if (!states[idx]) states[idx] = { status: 'idle', error: '' }
  return states[idx]
}

async function copyPatch(unifiedDiff: string) {
  try {
    await navigator.clipboard.writeText(unifiedDiff)
  } catch {
    // Clipboard API may be blocked (HTTP on non-localhost, iframe policies);
    // the diff is visible inline, so a silent no-op beats an error toast.
  }
}

async function applyPatch(idx: number, patch: SuggestedPatch) {
  if (props.repositoryId == null) return
  const s = stateFor(idx)
  s.status = 'applying'
  s.error = ''
  try {
    await aiStore.applyPatch(props.repositoryId, patch.file_path, patch.unified_diff)
    s.status = 'applied'
    emit('applied', patch.file_path)
  } catch (e: unknown) {
    s.status = 'error'
    // 422 from the backend means the hunks no longer match — surface the
    // localized "apply manually" guidance rather than the raw detail.
    s.error = extractErrorDetail(e, t('reportDetail.analysis.patches.applyError'))
  }
}
</script>

<template>
  <section v-if="patches.length" class="analysis-patches">
    <h4 class="analysis-patches__heading">🩹 {{ t('reportDetail.analysis.patches.heading') }}</h4>
    <p class="analysis-patches__hint">{{ t('reportDetail.analysis.patches.hint') }}</p>

    <div
      v-for="(patch, idx) in patches"
      :key="`${patch.file_path}-${idx}`"
      class="analysis-patch"
    >
      <div class="analysis-patch__head">
        <code class="analysis-patch__file">{{ patch.file_path }}</code>
        <div class="analysis-patch__actions">
          <button
            v-if="repositoryId != null"
            type="button"
            class="analysis-patch__apply"
            :disabled="stateFor(idx).status === 'applying' || stateFor(idx).status === 'applied'"
            @click="applyPatch(idx, patch)"
          >
            <template v-if="stateFor(idx).status === 'applying'">{{ t('reportDetail.analysis.patches.applying') }}</template>
            <template v-else-if="stateFor(idx).status === 'applied'">{{ t('reportDetail.analysis.patches.applied') }}</template>
            <template v-else>{{ t('reportDetail.analysis.patches.apply') }}</template>
          </button>
          <button type="button" class="analysis-patch__copy" @click="copyPatch(patch.unified_diff)">
            {{ t('reportDetail.analysis.patches.copy') }}
          </button>
        </div>
      </div>
      <p v-if="stateFor(idx).status === 'error'" class="analysis-patch__error">{{ stateFor(idx).error }}</p>
      <pre class="analysis-patch__diff"><code>{{ patch.unified_diff }}</code></pre>
    </div>
  </section>
</template>

<style scoped>
.analysis-patches { margin-top: 16px; }
.analysis-patches__heading { margin: 0 0 4px; font-size: 14px; font-weight: 700; }
.analysis-patches__hint { margin: 0 0 10px; font-size: 12px; color: var(--color-text-muted); }
.analysis-patch { border: 1px solid var(--color-border, #e2e8f0); border-radius: 6px; margin-bottom: 10px; overflow: hidden; }
.analysis-patch__head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 6px 10px; background: var(--color-bg, #F4F7FA);
}
.analysis-patch__file { font-size: 12px; word-break: break-all; }
.analysis-patch__actions { display: flex; gap: 6px; flex-shrink: 0; }
.analysis-patch__apply, .analysis-patch__copy {
  border: 1px solid var(--color-border, #cbd5e1); background: #fff; border-radius: 4px;
  padding: 3px 8px; font-size: 12px; cursor: pointer; white-space: nowrap;
}
.analysis-patch__apply { border-color: var(--color-primary, #3B7DD8); color: var(--color-primary, #3B7DD8); }
.analysis-patch__apply:disabled { opacity: 0.6; cursor: default; }
.analysis-patch__copy:hover, .analysis-patch__apply:not(:disabled):hover { background: #EBF4FF; }
.analysis-patch__error { margin: 0; padding: 6px 10px; font-size: 12px; color: var(--color-danger, #d33); }
.analysis-patch__diff { margin: 0; padding: 8px 10px; overflow-x: auto; font-size: 12px; background: #fff; }
</style>
