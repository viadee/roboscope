<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { changePassword } from '@/api/auth.api'
import { useAuthStore } from '@/stores/auth.store'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

// Story SECURITY-1 (revised): this modal is OPT-IN. The user opens it
// from the default-password banner (or, in the future, a profile menu).
// It is NOT forced by `password_change_required`.

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const open = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const { t } = useI18n()
const auth = useAuthStore()

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

const canSubmit = computed(
  () =>
    currentPassword.value.length > 0 &&
    newPassword.value.length >= 8 &&
    newPassword.value === confirmPassword.value &&
    !submitting.value,
)

function reset() {
  currentPassword.value = ''
  newPassword.value = ''
  confirmPassword.value = ''
  error.value = null
}

async function submit() {
  if (!canSubmit.value) return
  if (newPassword.value === currentPassword.value) {
    error.value = t('auth.pwChange.sameAsCurrent')
    return
  }
  submitting.value = true
  error.value = null
  try {
    await changePassword({
      current_password: currentPassword.value,
      new_password: newPassword.value,
    })
    await auth.fetchCurrentUser()
    reset()
    open.value = false
  } catch (e: any) {
    if (e?.response?.status === 401) {
      error.value = t('auth.pwChange.wrongCurrent')
    } else if (e?.response?.status === 422) {
      error.value = e?.response?.data?.detail || t('auth.pwChange.invalid')
    } else {
      error.value = t('common.error')
    }
  } finally {
    submitting.value = false
  }
}

function cancel() {
  reset()
  open.value = false
}
</script>

<template>
  <BaseModal v-model="open" :title="t('auth.pwChange.title')" size="sm">
    <p class="intro">{{ t('auth.pwChange.intro') }}</p>
    <form class="pw-form" @submit.prevent="submit">
      <label>
        {{ t('auth.pwChange.current') }}
        <input
          v-model="currentPassword"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <label>
        {{ t('auth.pwChange.newPw') }}
        <input
          v-model="newPassword"
          type="password"
          autocomplete="new-password"
          minlength="8"
          required
        />
        <small>{{ t('auth.pwChange.minLength') }}</small>
      </label>
      <label>
        {{ t('auth.pwChange.confirm') }}
        <input
          v-model="confirmPassword"
          type="password"
          autocomplete="new-password"
          required
        />
        <small
          v-if="confirmPassword.length > 0 && confirmPassword !== newPassword"
          class="mismatch"
        >
          {{ t('auth.pwChange.mismatch') }}
        </small>
      </label>
      <div v-if="error" class="error">{{ error }}</div>
    </form>
    <template #footer>
      <BaseButton variant="secondary" @click="cancel">
        {{ t('common.cancel') }}
      </BaseButton>
      <BaseButton variant="primary" :disabled="!canSubmit" @click="submit">
        {{ submitting ? t('common.loading') : t('auth.pwChange.submit') }}
      </BaseButton>
    </template>
  </BaseModal>
</template>

<style scoped>
.intro {
  margin: 0 0 16px;
  color: var(--color-text-muted);
  font-size: 14px;
}
.pw-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.pw-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--color-text-muted);
}
.pw-form input {
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 14px;
}
.pw-form small {
  font-size: 11px;
  color: var(--color-text-muted);
}
.mismatch {
  color: var(--color-danger, #c0392b);
}
.error {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(192, 57, 43, 0.08);
  border: 1px solid var(--color-danger, #c0392b);
  border-radius: 4px;
  color: var(--color-danger, #c0392b);
  font-size: 13px;
}
</style>
