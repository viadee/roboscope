<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import * as idpApi from '@/api/idpProviders.api'
import { useIdpProvidersStore } from '@/stores/idpProviders.store'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import DryRunPanel from '@/components/idp/DryRunPanel.vue'
import type {
  DryRunProbeResponse,
  IdpProvider,
  IdpProviderCreate,
  IdpProviderType,
  IdpProviderUpdate,
} from '@/types/domain.types'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const store = useIdpProvidersStore()

// --- Mode detection ------------------------------------------------------

const routeId = computed(() => {
  const raw = route.params.id
  if (!raw) return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
})

const mode = ref<'create' | 'edit'>(routeId.value == null ? 'create' : 'edit')

// --- Form state ----------------------------------------------------------

type Form = {
  name: string
  provider_type: IdpProviderType
  issuer_url: string
  client_id: string
  client_secret: string
  scopes: string
  group_claim_name: string
}

const DEFAULT_FORM: Form = {
  name: '',
  provider_type: 'oidc_azure_ad',
  issuer_url: '',
  client_id: '',
  client_secret: '',
  scopes: 'openid profile email',
  group_claim_name: 'groups',
}

const form = reactive<Form>({ ...DEFAULT_FORM })
const initialForm = ref<Form>({ ...DEFAULT_FORM })
const lastDryRunAtForm = ref<Form | null>(null)

// client_secret handling in edit mode: placeholder displayed until user types
const secretVisible = ref(false)
const secretTouched = ref(false)

// --- Dry-run state -------------------------------------------------------

const dryRunResult = ref<DryRunProbeResponse | null>(null)
const dryRunLoading = ref(false)
const loadingEntity = ref(false)
const saving = ref(false)
const loadedDiscoveryCachedAt = ref<string | null>(null)

// --- Scope chips ---------------------------------------------------------

const scopeInput = ref('')
const scopeChips = computed(() =>
  form.scopes
    .split(/\s+/)
    .map((s) => s.trim())
    .filter(Boolean),
)

function addScope() {
  const raw = scopeInput.value.trim()
  if (!raw) return
  const existing = new Set(scopeChips.value)
  for (const token of raw.split(/\s+/)) {
    if (token) existing.add(token)
  }
  form.scopes = [...existing].join(' ')
  scopeInput.value = ''
}

function onScopeKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    addScope()
  }
}

function removeScope(chip: string) {
  form.scopes = scopeChips.value.filter((c) => c !== chip).join(' ')
}

// --- Redirect URI --------------------------------------------------------

const redirectUri = computed(() => `${window.location.origin}/auth/sso/callback`)

async function copyRedirect() {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(redirectUri.value)
    } else {
      const el = document.getElementById('redirect-uri-input') as HTMLInputElement | null
      if (el) { el.select(); document.execCommand('copy') }
    }
    toast.success(t('idpProviders.edit.toasts.copiedToClipboard'))
  } catch {
    toast.error(t('idpProviders.edit.toasts.copyFailed'))
  }
}

// --- Validation ----------------------------------------------------------

type Errors = Partial<Record<keyof Form, string>>
const errors = ref<Errors>({})

function validate(): boolean {
  const e: Errors = {}
  if (!form.name.trim()) e.name = t('idpProviders.edit.errors.required')
  else if (form.name.length > 100) e.name = t('idpProviders.edit.errors.tooLong', { max: 100 })

  if (!form.issuer_url.trim()) e.issuer_url = t('idpProviders.edit.errors.required')
  else if (!/^https?:\/\//i.test(form.issuer_url.trim())) {
    e.issuer_url = t('idpProviders.edit.errors.urlScheme')
  } else if (form.issuer_url.length > 500) {
    e.issuer_url = t('idpProviders.edit.errors.tooLong', { max: 500 })
  }

  if (!form.client_id.trim()) e.client_id = t('idpProviders.edit.errors.required')
  else if (form.client_id.length > 255) e.client_id = t('idpProviders.edit.errors.tooLong', { max: 255 })

  if (mode.value === 'create' && !form.client_secret) {
    e.client_secret = t('idpProviders.edit.errors.required')
  } else if (form.client_secret && form.client_secret.length > 500) {
    e.client_secret = t('idpProviders.edit.errors.tooLong', { max: 500 })
  }

  if (form.scopes.length > 500) e.scopes = t('idpProviders.edit.errors.tooLong', { max: 500 })
  if (form.group_claim_name.length > 100) {
    e.group_claim_name = t('idpProviders.edit.errors.tooLong', { max: 100 })
  }

  errors.value = e
  return Object.keys(e).length === 0
}

const formIsValid = computed(() => {
  // Pure computed — does not mutate errors (called by canRunDryRun)
  if (!form.name.trim() || form.name.length > 100) return false
  if (!form.issuer_url.trim() || !/^https?:\/\//i.test(form.issuer_url)) return false
  if (form.issuer_url.length > 500) return false
  if (!form.client_id.trim() || form.client_id.length > 255) return false
  if (mode.value === 'create' && !form.client_secret) return false
  if (form.client_secret.length > 500) return false
  if (form.scopes.length > 500) return false
  if (form.group_claim_name.length > 100) return false
  return true
})

// --- Dirty + stale tracking ---------------------------------------------

function formSnapshot(): Form {
  return {
    name: form.name,
    provider_type: form.provider_type,
    issuer_url: form.issuer_url,
    client_id: form.client_id,
    client_secret: form.client_secret,
    scopes: form.scopes,
    group_claim_name: form.group_claim_name,
  }
}

function sameForm(a: Form, b: Form): boolean {
  return (
    a.name === b.name &&
    a.provider_type === b.provider_type &&
    a.issuer_url === b.issuer_url &&
    a.client_id === b.client_id &&
    a.client_secret === b.client_secret &&
    a.scopes === b.scopes &&
    a.group_claim_name === b.group_claim_name
  )
}

const dryRunStale = computed(() => {
  return lastDryRunAtForm.value != null && !sameForm(formSnapshot(), lastDryRunAtForm.value)
})

const canSave = computed(() => {
  return (
    dryRunResult.value?.overall_status === 'passed' &&
    !dryRunStale.value &&
    formIsValid.value &&
    !saving.value
  )
})

// --- Loaders -------------------------------------------------------------

async function loadExisting() {
  if (routeId.value == null) return
  loadingEntity.value = true
  try {
    let idp: IdpProvider | undefined = store.providers.find((p) => p.id === routeId.value)
    if (!idp) idp = await idpApi.getIdp(routeId.value)
    if (!idp) return
    form.name = idp.name
    form.provider_type = idp.provider_type
    form.issuer_url = idp.issuer_url
    form.client_id = idp.client_id
    form.client_secret = ''
    form.scopes = idp.scopes
    form.group_claim_name = idp.group_claim_name
    initialForm.value = formSnapshot()
    loadedDiscoveryCachedAt.value = idp.discovery_cached_at ?? null
    if (idp.last_dry_run_status === 'passed') {
      // Treat last-saved config as the baseline for "stale" tracking
      lastDryRunAtForm.value = formSnapshot()
    }
  } finally {
    loadingEntity.value = false
  }
}

function isDiscoveryCacheStale(cachedAt: string | null | undefined): boolean {
  if (!cachedAt) return true
  return Date.now() - new Date(cachedAt).getTime() > 24 * 3600 * 1000
}

onMounted(async () => {
  if (mode.value === 'edit') {
    await loadExisting()
  }
})

watch(
  () => route.params.id,
  async () => {
    dryRunResult.value = null
    lastDryRunAtForm.value = null
    mode.value = routeId.value == null ? 'create' : 'edit'
    if (mode.value === 'edit') await loadExisting()
  },
)

// --- Actions -------------------------------------------------------------

function sanitizeDetail(detail: string): string {
  return detail.replace(/[{}@|]/g, ' ').trim()
}

async function runDryRun() {
  if (!validate()) return
  dryRunLoading.value = true
  dryRunResult.value = null
  try {
    let idpId: number
    if (mode.value === 'create') {
      const payload: IdpProviderCreate = {
        name: form.name,
        provider_type: form.provider_type,
        issuer_url: form.issuer_url,
        client_id: form.client_id,
        client_secret: form.client_secret,
        scopes: form.scopes,
        group_claim_name: form.group_claim_name,
      }
      const created = await store.create(payload)
      idpId = created.id
      initialForm.value = formSnapshot()
      // Silently transition to edit URL so subsequent dry-runs hit PATCH
      mode.value = 'edit'
      await router.replace(`/admin/identity-providers/${idpId}`)
    } else {
      idpId = routeId.value!
      const patch: IdpProviderUpdate = buildPatch()
      if (Object.keys(patch).length > 0) {
        await store.update(idpId, patch)
        initialForm.value = formSnapshot()
      }
    }
    const result = await store.runDryRun(idpId)
    dryRunResult.value = result
    lastDryRunAtForm.value = formSnapshot()
    // Reset secretTouched so future edits are tracked freshly
    if (secretTouched.value) secretTouched.value = false
    if (result.overall_status === 'passed') {
      toast.success(t('idpProviders.toasts.dryRunPassed'))
    } else {
      const failed = result.checks.find((c) => c.status === 'failed')
      toast.error(
        t('idpProviders.toasts.dryRunFailed', {
          detail: sanitizeDetail(failed?.detail ?? ''),
        }),
      )
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : ''
    toast.error(t('idpProviders.edit.toasts.dryRunError', { detail: sanitizeDetail(msg) }))
  } finally {
    dryRunLoading.value = false
  }
}

function buildPatch(): IdpProviderUpdate {
  const patch: IdpProviderUpdate = {}
  const i = initialForm.value
  if (form.name !== i.name) patch.name = form.name
  if (form.provider_type !== i.provider_type) patch.provider_type = form.provider_type
  if (form.issuer_url !== i.issuer_url) patch.issuer_url = form.issuer_url
  if (form.client_id !== i.client_id) patch.client_id = form.client_id
  if (secretTouched.value && form.client_secret) {
    patch.client_secret = form.client_secret
  }
  if (form.scopes !== i.scopes) patch.scopes = form.scopes
  if (form.group_claim_name !== i.group_claim_name) patch.group_claim_name = form.group_claim_name
  return patch
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  try {
    if (mode.value === 'edit' && routeId.value != null) {
      const patch = buildPatch()
      if (Object.keys(patch).length > 0) {
        await store.update(routeId.value, patch)
        initialForm.value = formSnapshot()
      }
    }
    toast.success(t('idpProviders.edit.toasts.saved'))
    await nextTick()
    router.push('/admin/identity-providers')
  } catch (e) {
    const msg = e instanceof Error ? e.message : ''
    toast.error(
      t('idpProviders.edit.toasts.saveFailed', { detail: sanitizeDetail(msg) }),
    )
  } finally {
    saving.value = false
  }
}

function cancel() {
  router.push('/admin/identity-providers')
}

// --- Handoff artifact download -------------------------------------------

const handoffDownloading = ref<'pdf' | 'md' | null>(null)

async function downloadHandoffFile(format: 'pdf' | 'md') {
  const id = routeId.value
  if (!id) return
  handoffDownloading.value = format
  try {
    const blob = await idpApi.downloadHandoff(id, format, locale.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `idp-handoff-${form.name || id}-${locale.value}.${format}`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    toast.error(t('idpProviders.edit.handoff.error'))
  } finally {
    handoffDownloading.value = null
  }
}

function onSecretInput(value: string) {
  secretTouched.value = true
  form.client_secret = value
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <div>
        <h1>
          {{ mode === 'create'
            ? t('idpProviders.edit.title.create')
            : t('idpProviders.edit.title.edit') }}
        </h1>
        <span
          v-if="mode === 'edit' && isDiscoveryCacheStale(loadedDiscoveryCachedAt)"
          class="stale-cache-badge"
          data-testid="discovery-cache-stale-badge"
        >
          {{ loadedDiscoveryCachedAt ? t('idpProviders.staleCacheBadge') : t('idpProviders.neverCached') }}
        </span>
      </div>
    </div>

    <BaseSpinner v-if="loadingEntity" />

    <form
      v-else
      class="idp-form card"
      @submit.prevent="save"
      data-testid="idp-edit-form"
    >
      <div class="grid-2 form-grid">
        <div class="form-group">
          <label class="form-label" for="idp-name">{{ t('idpProviders.edit.fields.name.label') }} *</label>
          <input
            id="idp-name"
            v-model="form.name"
            class="form-input"
            :placeholder="t('idpProviders.edit.fields.name.placeholder')"
            maxlength="100"
            required
          />
          <div v-if="errors.name" class="field-error">{{ errors.name }}</div>
        </div>

        <div class="form-group">
          <label class="form-label" for="idp-provider-type">{{ t('idpProviders.edit.fields.providerType.label') }} *</label>
          <select id="idp-provider-type" v-model="form.provider_type" class="form-input" required>
            <option value="oidc_azure_ad">{{ t('idpProviders.types.azureAd') }}</option>
            <option value="oidc_google">{{ t('idpProviders.types.google') }}</option>
            <option value="oidc_github">{{ t('idpProviders.types.github') }}</option>
            <option value="oidc_generic">{{ t('idpProviders.types.generic') }}</option>
          </select>
        </div>

        <div class="form-group grid-span-2">
          <label class="form-label" for="idp-issuer-url">{{ t('idpProviders.edit.fields.issuerUrl.label') }} *</label>
          <input
            id="idp-issuer-url"
            v-model="form.issuer_url"
            type="url"
            class="form-input"
            :placeholder="t('idpProviders.edit.fields.issuerUrl.placeholder')"
            maxlength="500"
            required
          />
          <div class="field-help">{{ t('idpProviders.edit.fields.issuerUrl.help') }}</div>
          <div v-if="errors.issuer_url" class="field-error">{{ errors.issuer_url }}</div>
        </div>

        <div class="form-group">
          <label class="form-label" for="idp-client-id">{{ t('idpProviders.edit.fields.clientId.label') }} *</label>
          <input
            id="idp-client-id"
            v-model="form.client_id"
            class="form-input"
            maxlength="255"
            required
          />
          <div v-if="errors.client_id" class="field-error">{{ errors.client_id }}</div>
        </div>

        <div class="form-group">
          <label class="form-label" for="idp-client-secret">
            {{ t('idpProviders.edit.fields.clientSecret.label') }}
            <template v-if="mode === 'create'">*</template>
          </label>
          <div class="secret-wrap">
            <input
              id="idp-client-secret"
              :value="form.client_secret"
              :type="secretVisible ? 'text' : 'password'"
              class="form-input"
              :placeholder="mode === 'create'
                ? t('idpProviders.edit.fields.clientSecret.placeholderCreate')
                : t('idpProviders.edit.fields.clientSecret.placeholderEdit')"
              maxlength="500"
              :required="mode === 'create'"
              autocomplete="off"
              data-testid="client-secret-input"
              @input="(e) => onSecretInput((e.target as HTMLInputElement).value)"
            />
            <button
              type="button"
              class="secret-toggle"
              :aria-label="secretVisible
                ? t('idpProviders.edit.fields.clientSecret.hide')
                : t('idpProviders.edit.fields.clientSecret.show')"
              @click="secretVisible = !secretVisible"
            >
              {{ secretVisible ? '\u{1F441}' : '\u{1F441}\u200D\u{1F5E8}' }}
            </button>
          </div>
          <div class="field-help">{{ t('idpProviders.edit.fields.clientSecret.help') }}</div>
          <div v-if="errors.client_secret" class="field-error">{{ errors.client_secret }}</div>
        </div>

        <div class="form-group grid-span-2">
          <label class="form-label" for="idp-scopes-input">{{ t('idpProviders.edit.fields.scopes.label') }}</label>
          <div class="chip-input">
            <span
              v-for="chip in scopeChips"
              :key="chip"
              class="chip"
              data-testid="scope-chip"
            >
              {{ chip }}
              <button
                type="button"
                class="chip-remove"
                :aria-label="`Remove ${chip}`"
                @click="removeScope(chip)"
              >&times;</button>
            </span>
            <input
              id="idp-scopes-input"
              v-model="scopeInput"
              class="chip-input-field"
              :placeholder="t('idpProviders.edit.fields.scopes.placeholder')"
              @keydown="onScopeKeydown"
              @blur="addScope"
            />
          </div>
          <div class="field-help">{{ t('idpProviders.edit.fields.scopes.help') }}</div>
        </div>

        <div class="form-group">
          <label class="form-label" for="idp-group-claim">{{ t('idpProviders.edit.fields.groupClaim.label') }}</label>
          <input
            id="idp-group-claim"
            v-model="form.group_claim_name"
            class="form-input"
            maxlength="100"
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="redirect-uri-input">{{ t('idpProviders.edit.fields.redirectUri.label') }}</label>
          <div class="redirect-wrap">
            <input
              id="redirect-uri-input"
              :value="redirectUri"
              class="form-input"
              readonly
            />
            <button
              type="button"
              class="copy-btn"
              :aria-label="t('idpProviders.edit.buttons.copy')"
              @click="copyRedirect"
            >&#128203;</button>
          </div>
          <div class="field-help">{{ t('idpProviders.edit.fields.redirectUri.help') }}</div>
        </div>
      </div>

      <div class="form-actions">
        <BaseButton variant="ghost" type="button" @click="cancel">
          {{ t('idpProviders.edit.buttons.cancel') }}
        </BaseButton>
        <BaseButton
          variant="secondary"
          type="button"
          :loading="dryRunLoading"
          :disabled="!formIsValid || dryRunLoading"
          data-testid="run-dry-run-btn"
          @click="runDryRun"
        >
          {{ t('idpProviders.edit.buttons.runDryRun') }}
        </BaseButton>
        <BaseButton
          variant="primary"
          type="submit"
          :loading="saving"
          :disabled="!canSave"
          :title="!canSave ? t('idpProviders.edit.tooltips.saveDisabled') : undefined"
          data-testid="save-btn"
        >
          {{ t('idpProviders.edit.buttons.save') }}
        </BaseButton>
      </div>
    </form>

    <div v-if="mode === 'edit'" class="card handoff-section" data-testid="handoff-section">
      <h3 class="handoff-title">{{ t('idpProviders.edit.handoff.title') }}</h3>
      <p class="handoff-description">{{ t('idpProviders.edit.handoff.description') }}</p>
      <div class="handoff-buttons">
        <BaseButton
          variant="secondary"
          type="button"
          :loading="handoffDownloading === 'pdf'"
          :disabled="handoffDownloading !== null"
          data-testid="handoff-pdf-btn"
          @click="downloadHandoffFile('pdf')"
        >
          {{ t('idpProviders.edit.handoff.downloadPdf') }}
        </BaseButton>
        <BaseButton
          variant="secondary"
          type="button"
          :loading="handoffDownloading === 'md'"
          :disabled="handoffDownloading !== null"
          data-testid="handoff-md-btn"
          @click="downloadHandoffFile('md')"
        >
          {{ t('idpProviders.edit.handoff.downloadMarkdown') }}
        </BaseButton>
      </div>
    </div>

    <DryRunPanel
      v-if="dryRunLoading || dryRunResult || dryRunStale"
      :result="dryRunResult"
      :loading="dryRunLoading"
      :stale="dryRunStale"
      class="panel-spacer"
    />
  </div>
</template>

<style scoped>
.idp-form {
  padding: 24px;
}

.form-grid {
  gap: 16px 20px;
}

.grid-span-2 {
  grid-column: span 2;
}

.field-help {
  font-size: 12px;
  color: var(--color-text-muted, #5C688C);
  margin-top: 4px;
}

.field-error {
  font-size: 12px;
  color: var(--color-danger, #DC3545);
  margin-top: 4px;
}

.secret-wrap,
.redirect-wrap {
  display: flex;
  gap: 6px;
  align-items: stretch;
}

.secret-wrap .form-input,
.redirect-wrap .form-input {
  flex: 1;
}

.secret-toggle,
.copy-btn {
  background: var(--color-bg, #F4F7FA);
  border: 1px solid var(--color-border, #D6DCE5);
  border-radius: 4px;
  padding: 0 10px;
  cursor: pointer;
  font-size: 16px;
}

.secret-toggle:hover,
.copy-btn:hover {
  background: var(--color-border-light, #E4E9F0);
}

.chip-input {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 10px;
  border: 1px solid var(--color-border, #D6DCE5);
  border-radius: 4px;
  background: white;
  min-height: 38px;
  align-items: center;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--color-bg, #F4F7FA);
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text, #1A2D50);
}

.chip-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
  color: var(--color-text-muted, #5C688C);
}

.chip-remove:hover {
  color: var(--color-danger, #DC3545);
}

.chip-input-field {
  flex: 1;
  min-width: 120px;
  border: none;
  outline: none;
  font-size: 13px;
  font-family: inherit;
  background: transparent;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border, #D6DCE5);
}

.panel-spacer {
  margin-top: 20px;
}

.handoff-section {
  margin-top: 20px;
  padding: 16px 20px;
}

.handoff-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-navy);
  margin: 0 0 6px;
}

.handoff-description {
  font-size: 13px;
  color: var(--color-text-secondary, #666);
  margin: 0 0 12px;
}

.handoff-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.stale-cache-badge {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  background-color: var(--color-accent, #D4883E);
  color: #fff;
  vertical-align: middle;
}

@media (max-width: 1023px) {
  .form-grid {
    grid-template-columns: 1fr !important;
  }
  .grid-span-2 {
    grid-column: span 1;
  }
}
</style>
