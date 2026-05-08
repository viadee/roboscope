<!--
  GroupMappingRow (Story 3-14).

  Display/Edit modes for inline role editing on a single group-mapping row.
  Keyboard contract:
    - In Display: Enter (on the focused role badge) or click on the badge → Edit
    - In Edit: Enter on the select → submit; Escape → discard
    - Arrow keys in the native <select> cycle options
    - Tab still flows through row → role badge → delete link
-->
<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { GroupMapping } from '@/types/domain.types'

const props = defineProps<{
  mapping: GroupMapping
}>()

const emit = defineEmits<{
  (e: 'update-role', id: number, role: string): void
  (e: 'delete', id: number): void
}>()

const { t } = useI18n()

const editing = ref(false)
const draftRole = ref(props.mapping.role)
const selectRef = ref<HTMLSelectElement | null>(null)
const saving = ref(false)
const error = ref<string | null>(null)

async function enterEdit() {
  draftRole.value = props.mapping.role
  error.value = null
  editing.value = true
  await nextTick()
  selectRef.value?.focus()
}

function cancelEdit() {
  editing.value = false
  draftRole.value = props.mapping.role
  error.value = null
}

async function submit() {
  if (draftRole.value === props.mapping.role) {
    editing.value = false
    return
  }
  saving.value = true
  error.value = null
  try {
    emit('update-role', props.mapping.id, draftRole.value)
    editing.value = false
  } catch (err: unknown) {
    error.value =
      (err as Error)?.message || t('teams.detail.mappings.updateFailed')
  } finally {
    saving.value = false
  }
}

function onBadgeKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Enter' || ev.key === ' ') {
    ev.preventDefault()
    enterEdit()
  }
}

function onSelectKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Enter') {
    ev.preventDefault()
    submit()
  } else if (ev.key === 'Escape') {
    ev.preventDefault()
    cancelEdit()
  }
}
</script>

<template>
  <li class="mapping-row" :data-mapping-id="mapping.id">
    <span class="mapping-idp">IdP {{ mapping.idp_id }}</span>
    <span class="mapping-group">{{ mapping.group_claim_value }}</span>

    <template v-if="!editing">
      <button
        type="button"
        class="role-badge"
        :aria-label="
          t('teams.detail.mappings.editRoleAriaLabel', {
            role: mapping.role,
            group: mapping.group_claim_value,
          })
        "
        data-testid="role-badge"
        @click="enterEdit"
        @keydown="onBadgeKeydown"
      >
        {{ mapping.role }}
      </button>
      <button
        type="button"
        class="action-link danger"
        data-testid="row-delete"
        @click="emit('delete', mapping.id)"
      >
        {{ t('teams.detail.mappings.remove') }}
      </button>
    </template>

    <template v-else>
      <select
        ref="selectRef"
        v-model="draftRole"
        class="role-select"
        data-testid="role-select"
        :disabled="saving"
        @keydown="onSelectKeydown"
      >
        <option value="viewer">viewer</option>
        <option value="runner">runner</option>
        <option value="editor">editor</option>
        <option value="admin">admin</option>
      </select>
      <div class="edit-actions">
        <button
          type="button"
          class="action-link"
          data-testid="save-role"
          :disabled="saving"
          @click="submit"
        >
          {{ t('teams.detail.mappings.save') }}
        </button>
        <button
          type="button"
          class="action-link"
          data-testid="cancel-role"
          :disabled="saving"
          @click="cancelEdit"
        >
          {{ t('teams.detail.mappings.cancel') }}
        </button>
      </div>
    </template>

    <p v-if="error" class="error-text">{{ error }}</p>
  </li>
</template>

<style scoped>
.mapping-row {
  display: grid;
  grid-template-columns: 80px 1fr 120px auto;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border);
  align-items: center;
}
.mapping-idp {
  color: var(--color-text-muted);
  font-size: 13px;
}
.mapping-group {
  font-weight: 500;
}
.role-badge {
  background: var(--color-bg);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  text-align: center;
  min-width: 80px;
}
.role-badge:hover,
.role-badge:focus-visible {
  border-color: var(--color-primary);
  color: var(--color-primary);
  outline: none;
}
.role-select {
  padding: 4px 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
}
.edit-actions {
  display: flex;
  gap: 8px;
}
.action-link {
  background: none;
  border: none;
  padding: 4px 8px;
  color: var(--color-primary);
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  text-decoration: underline;
}
.action-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.action-link.danger {
  color: var(--color-danger);
}
.error-text {
  grid-column: 1 / -1;
  color: var(--color-danger);
  margin: 4px 0 0;
  font-size: 12px;
}
</style>
