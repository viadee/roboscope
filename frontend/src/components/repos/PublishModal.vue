<script setup lang="ts">
/**
 * Story REPO-1 — "Save to repository" modal for non-Git users.
 *
 * Shows the current `git status` snapshot, a commit-message input,
 * and a Save button that fires `POST /repos/{id}/publish` (commit +
 * push). On HTTP 409 (push rejected because the remote moved) it
 * switches to a recovery state offering a "Pull latest and retry"
 * action — the local commit stays in place so the user never loses
 * their work.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import {
  publishRepo,
  pushRepo,
  syncRepo,
  getFileDiff,
  type FileDiff,
  type RepoStatus,
  type PublishConflict,
} from '@/api/repos.api'
import { useRepoStatusStore } from '@/stores/repoStatus.store'
import { useToast } from '@/composables/useToast'

const props = defineProps<{
  modelValue: boolean
  repoId: number
  status: RepoStatus | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  /** Fires after a successful publish so the parent can refetch the
   *  file tree / clear the dirty indicator. */
  (e: 'published', commit: string): void
}>()

const { t } = useI18n()
const toast = useToast()
const repoStatus = useRepoStatusStore()

// All paths the user could publish, default-checked.
const allPaths = computed(() => {
  const s = props.status
  if (!s) return []
  return [...s.modified, ...s.untracked, ...s.deleted]
})

const selected = ref<Set<string>>(new Set())
const message = ref('')
const submitting = ref(false)
const conflict = ref<PublishConflict | null>(null)
const pulling = ref(false)
type DiffState = FileDiff | 'loading' | { error: string }
const diffs = ref<Record<string, DiffState>>({})
const openDiffs = ref<Set<string>>(new Set())

// Reset selection + error state on every re-open / status update.
// `immediate: true` so the initial render also seeds `selected` —
// otherwise the modal opens with every checkbox unchecked.
watch(
  () => [props.modelValue, props.status] as const,
  () => {
    if (props.modelValue) {
      selected.value = new Set(allPaths.value)
      message.value = ''
      conflict.value = null
      diffs.value = {}
      openDiffs.value = new Set()
    }
  },
  { immediate: true },
)

// Story V14.5 — lazy per-file diff preview (state declared above the
// watcher). Fetched once per open; rendered as escaped text (never
// v-html) with +/- line colouring.
async function toggleDiff(path: string) {
  const open = new Set(openDiffs.value)
  if (open.has(path)) open.delete(path)
  else open.add(path)
  openDiffs.value = open
  // Cached after the first successful load; a failed load retries on re-open.
  if (!open.has(path) || (diffs.value[path] && diffError(path) === null)) return
  diffs.value = { ...diffs.value, [path]: 'loading' }
  try {
    diffs.value = { ...diffs.value, [path]: await getFileDiff(props.repoId, path) }
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    diffs.value = {
      ...diffs.value,
      [path]: { error: typeof detail === 'string' ? detail : (e as Error).message ?? '' },
    }
  }
}

function loadedDiff(path: string): FileDiff | null {
  const d = diffs.value[path]
  return d && typeof d === 'object' && 'status' in d ? d : null
}

function diffError(path: string): string | null {
  const d = diffs.value[path]
  return d && typeof d === 'object' && 'error' in d ? d.error : null
}

function diffLineClass(line: string): string {
  if (line.startsWith('+++') || line.startsWith('---')) return 'diff-meta'
  if (line.startsWith('+')) return 'diff-add'
  if (line.startsWith('-')) return 'diff-del'
  if (line.startsWith('@@')) return 'diff-hunk'
  return ''
}

const canSubmit = computed(() =>
  !submitting.value
  && !conflict.value
  && message.value.trim().length > 0
  && selected.value.size > 0,
)

function togglePath(path: string) {
  if (selected.value.has(path)) selected.value.delete(path)
  else selected.value.add(path)
  selected.value = new Set(selected.value)
}

async function onSubmit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const out = await publishRepo(props.repoId, {
      message: message.value.trim(),
      paths: [...selected.value],
    })
    toast.success(t('repos.publish.toastSaved', {
      n: out.files.length,
      hash: out.commit_hash.slice(0, 7),
    }))
    emit('published', out.commit_hash)
    emit('update:modelValue', false)
    repoStatus.refresh(props.repoId)
  } catch (e: unknown) {
    // Axios error shape: e.response.data.detail = PublishConflict for 409.
    const status = (e as { response?: { status?: number } })?.response?.status
    const detail = (e as { response?: { data?: { detail?: PublishConflict | string } } })
      ?.response?.data?.detail
    if (status === 409 && detail && typeof detail === 'object' && 'commit_hash' in detail) {
      conflict.value = detail
    } else {
      toast.error(t('repos.publish.toastError', {
        detail: typeof detail === 'string' ? detail : (e as Error).message ?? '',
      }))
    }
  } finally {
    submitting.value = false
  }
}

async function onPullAndRetry() {
  if (!conflict.value) return
  pulling.value = true
  try {
    await syncRepo(props.repoId)
    // After the pull, push the local commit (which is still HEAD).
    await pushRepo(props.repoId)
    toast.success(t('repos.publish.toastResolved', {
      hash: conflict.value.commit_hash.slice(0, 7),
    }))
    emit('published', conflict.value.commit_hash)
    emit('update:modelValue', false)
    conflict.value = null
    repoStatus.refresh(props.repoId)
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })
      ?.response?.data?.detail
    toast.error(t('repos.publish.toastResolveFailed', {
      detail: typeof detail === 'string' ? detail : (e as Error).message ?? '',
    }))
  } finally {
    pulling.value = false
  }
}

function onCancel() {
  emit('update:modelValue', false)
}
</script>

<template>
  <BaseModal
    :model-value="modelValue"
    :title="t('repos.publish.title')"
    size="md"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <!-- ─── Conflict-recovery state ─────────────────────────── -->
    <div v-if="conflict" class="publish-conflict" data-testid="publish-conflict">
      <h4>{{ t('repos.publish.conflictHeader') }}</h4>
      <p>{{ t('repos.publish.conflictBody', { hash: conflict.commit_hash.slice(0, 7) }) }}</p>
      <pre class="publish-conflict-detail">{{ conflict.reason }}</pre>
      <p class="publish-conflict-hint">{{ t('repos.publish.conflictHint') }}</p>
    </div>

    <!-- ─── Default state: list + message + actions ─────────── -->
    <div v-else class="publish-form" data-testid="publish-form">
      <p v-if="allPaths.length === 0" class="publish-empty">
        {{ t('repos.publish.empty') }}
      </p>

      <ul v-else class="publish-paths" data-testid="publish-paths">
        <li v-for="path in allPaths" :key="path" class="publish-path">
          <label>
            <input
              type="checkbox"
              :checked="selected.has(path)"
              @change="togglePath(path)"
            />
            <code>{{ path }}</code>
            <span class="publish-path-tag">
              {{
                status?.deleted.includes(path) ? t('repos.publish.tagDeleted')
                  : status?.untracked.includes(path) ? t('repos.publish.tagNew')
                  : t('repos.publish.tagModified')
              }}
            </span>
          </label>
          <button
            type="button"
            class="publish-diff-toggle"
            :aria-expanded="openDiffs.has(path)"
            data-testid="publish-diff-toggle"
            @click="toggleDiff(path)"
          >
            {{ openDiffs.has(path) ? t('repos.publish.hideChanges') : t('repos.publish.showChanges') }}
          </button>
          <div v-if="openDiffs.has(path)" class="publish-diff" data-testid="publish-diff">
            <p v-if="diffs[path] === 'loading'" class="publish-diff-note">{{ t('common.loading') }}</p>
            <p v-else-if="diffError(path) !== null" class="publish-diff-note">
              {{ t('repos.publish.diffError', { detail: diffError(path) }) }}
            </p>
            <template v-else-if="loadedDiff(path)">
              <p v-if="loadedDiff(path)!.status === 'binary'" class="publish-diff-note">
                {{ t('repos.publish.binaryFile') }}
              </p>
              <p v-else-if="!loadedDiff(path)!.diff" class="publish-diff-note">
                {{ t('repos.publish.noChanges') }}
              </p>
              <pre v-else class="publish-diff-pre"><span
                v-for="(line, i) in loadedDiff(path)!.diff!.split('\n')"
                :key="i"
                :class="diffLineClass(line)"
              >{{ line || ' ' }}</span></pre>
              <p v-if="loadedDiff(path)!.truncated" class="publish-diff-note">
                {{ t('repos.publish.diffTruncated') }}
              </p>
            </template>
          </div>
        </li>
      </ul>

      <label class="publish-message-label">
        {{ t('repos.publish.messageLabel') }}
        <input
          v-model="message"
          type="text"
          maxlength="200"
          class="publish-message-input"
          :placeholder="t('repos.publish.messagePlaceholder')"
          data-testid="publish-message"
          :disabled="allPaths.length === 0"
        />
      </label>
    </div>

    <template #footer>
      <BaseButton variant="ghost" @click="onCancel">
        {{ t('common.cancel') }}
      </BaseButton>
      <BaseButton
        v-if="conflict"
        variant="primary"
        :loading="pulling"
        @click="onPullAndRetry"
        data-testid="publish-pull-retry"
      >
        {{ t('repos.publish.pullAndRetry') }}
      </BaseButton>
      <BaseButton
        v-else
        variant="primary"
        :loading="submitting"
        :disabled="!canSubmit"
        data-testid="publish-submit"
        @click="onSubmit"
      >
        {{ t('repos.publish.save', { n: selected.size }) }}
      </BaseButton>
    </template>
  </BaseModal>
</template>

<style scoped>
.publish-form { display: flex; flex-direction: column; gap: 14px; }
.publish-empty { color: var(--color-text-muted, #5A6380); font-style: italic; }
.publish-paths { list-style: none; padding: 0; margin: 0; max-height: 220px; overflow-y: auto; }
.publish-path label {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 6px; border-radius: 4px; cursor: pointer;
}
.publish-path label:hover { background: var(--color-bg, #F4F7FA); }
.publish-path code {
  flex: 1; font-size: 12px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.publish-path-tag {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
  padding: 1px 6px; border-radius: 8px;
  background: var(--color-bg, #F4F7FA);
  color: var(--color-text-muted, #5A6380);
  flex-shrink: 0;
}
.publish-path { display: flex; flex-wrap: wrap; align-items: center; }
.publish-path label { flex: 1; min-width: 0; }
.publish-diff-toggle {
  flex-shrink: 0; font-size: 11px; padding: 2px 6px;
  background: none; border: none; cursor: pointer;
  color: var(--color-primary, #3B7DD8);
}
.publish-diff { flex-basis: 100%; margin: 2px 0 6px; }
.publish-diff-note { margin: 2px 6px; font-size: 11px; color: var(--color-text-muted, #5A6380); }
.publish-diff-pre {
  margin: 0; max-height: 260px; overflow: auto;
  background: var(--color-bg, #F4F7FA);
  border: 1px solid var(--color-border, #D8DDE8);
  border-radius: 4px; font-size: 11px; line-height: 1.4;
}
.publish-diff-pre span { display: block; padding: 0 6px; white-space: pre; }
.publish-diff-pre .diff-add { background: var(--color-success-bg, #DCFCE7); color: var(--color-success, #37996E); }
.publish-diff-pre .diff-del { background: var(--color-danger-bg, #FEE2E2); color: var(--color-danger, #DC3545); }
.publish-diff-pre .diff-hunk { color: var(--color-primary, #3B7DD8); }
.publish-diff-pre .diff-meta { color: var(--color-text-muted, #5A6380); }
.publish-message-label {
  display: flex; flex-direction: column; gap: 4px;
  font-size: 12px; font-weight: 600;
  color: var(--color-text-muted, #5A6380);
}
.publish-message-input {
  padding: 6px 10px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 5px;
  font-size: 13px; font-family: inherit;
}
.publish-message-input:focus {
  outline: none;
  border-color: var(--color-primary, #3B7DD8);
}
.publish-conflict { display: flex; flex-direction: column; gap: 10px; }
.publish-conflict h4 { margin: 0; color: var(--color-accent, #D4883E); }
.publish-conflict-detail {
  background: var(--color-bg, #F4F7FA);
  padding: 8px 10px;
  border-radius: 4px;
  font-size: 11px;
  white-space: pre-wrap; word-break: break-word;
  margin: 0;
}
.publish-conflict-hint {
  font-size: 12px;
  color: var(--color-text-muted, #5A6380);
}
</style>
