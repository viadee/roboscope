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
    }
  },
  { immediate: true },
)

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
  border-color: var(--color-primary, #2D63B0);
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
