<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useIdpProvidersStore } from '@/stores/idpProviders.store'
import { useToast } from '@/composables/useToast'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import type { IdpProvider, IdpProviderType } from '@/types/domain.types'

const { t } = useI18n()
const router = useRouter()
const toast = useToast()
const store = useIdpProvidersStore()

const showDeleteModal = ref(false)
const pendingDelete = ref<IdpProvider | null>(null)

onMounted(async () => {
  try {
    await store.fetch()
  } catch {
    toast.error(t('idpProviders.toasts.loadFailed'))
  }
})

function providerStatus(idp: IdpProvider): 'enabled' | 'draft' | 'disabled' {
  if (idp.is_enabled) return 'enabled'
  if (idp.last_dry_run_status === 'passed') return 'disabled'
  return 'draft'
}

function badgeVariant(
  s: 'enabled' | 'draft' | 'disabled',
): 'success' | 'default' | 'danger' {
  if (s === 'enabled') return 'success'
  if (s === 'disabled') return 'danger'
  return 'default'
}

function showBrokenWarning(idp: IdpProvider): boolean {
  return idp.is_enabled && idp.last_dry_run_status === 'failed'
}

const typeLabelKey: Record<IdpProviderType, string> = {
  oidc_azure_ad: 'idpProviders.types.azureAd',
  oidc_google: 'idpProviders.types.google',
  oidc_github: 'idpProviders.types.github',
  oidc_generic: 'idpProviders.types.generic',
}

function typeLabel(idp: IdpProvider): string {
  const key = typeLabelKey[idp.provider_type]
  return key ? t(key) : idp.provider_type
}

function formatRelative(iso: string | null): string {
  if (!iso) return t('idpProviders.relative.never')
  const diffMs = Date.now() - new Date(iso).getTime()
  if (diffMs < 0) return t('idpProviders.relative.justNow')
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 1) return t('idpProviders.relative.justNow')
  if (mins < 60) return t('idpProviders.relative.minutesAgo', { n: mins })
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return t('idpProviders.relative.hoursAgo', { n: hrs })
  const days = Math.floor(hrs / 24)
  return t('idpProviders.relative.daysAgo', { n: days })
}

const hasProviders = computed(() => store.providers.length > 0)

function onNew() {
  router.push('/admin/identity-providers/new')
}

function onEdit(idp: IdpProvider) {
  router.push(`/admin/identity-providers/${idp.id}`)
}

// vue-i18n treats `@`, `|`, `{`, `}` as template-reserved chars when
// interpolating into a translation string; sanitize server-provided detail
// before handing it to t() to avoid parser warnings and mangled output.
function sanitizeDetail(detail: string): string {
  return detail.replace(/[{}@|]/g, ' ').trim()
}

async function onDryRun(idp: IdpProvider) {
  try {
    const result = await store.runDryRun(idp.id)
    if (result.overall_status === 'passed') {
      toast.success(t('idpProviders.toasts.dryRunPassed'))
    } else {
      const failed = result.checks.find((c) => c.status === 'failed')
      toast.error(t('idpProviders.toasts.dryRunFailed', {
        detail: sanitizeDetail(failed?.detail ?? ''),
      }))
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : ''
    toast.error(t('idpProviders.toasts.dryRunFailed', {
      detail: sanitizeDetail(msg),
    }))
  }
}

function onDeleteClick(idp: IdpProvider) {
  pendingDelete.value = idp
  showDeleteModal.value = true
}

async function confirmDelete() {
  if (!pendingDelete.value) return
  const target = pendingDelete.value
  try {
    await store.remove(target.id)
    toast.success(t('idpProviders.toasts.deleted'))
  } catch {
    toast.error(t('idpProviders.toasts.deleteFailed'))
  } finally {
    showDeleteModal.value = false
    pendingDelete.value = null
  }
}

function cancelDelete() {
  showDeleteModal.value = false
  pendingDelete.value = null
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <div>
        <h1>{{ t('idpProviders.title') }}</h1>
        <p class="page-subtitle">{{ t('idpProviders.subtitle') }}</p>
      </div>
      <BaseButton v-if="hasProviders" variant="primary" @click="onNew">
        {{ t('idpProviders.addProvider') }}
      </BaseButton>
    </div>

    <BaseSpinner v-if="store.loading && !hasProviders" />

    <div v-else-if="!hasProviders" class="card empty-state" data-testid="empty-state">
      <div class="empty-illustration" aria-hidden="true">&#128274;</div>
      <h2>{{ t('idpProviders.emptyState.title') }}</h2>
      <p>{{ t('idpProviders.emptyState.description') }}</p>
      <BaseButton variant="primary" @click="onNew">
        {{ t('idpProviders.emptyState.cta') }}
      </BaseButton>
    </div>

    <div v-else class="table-wrapper">
      <table class="data-table" data-testid="providers-table">
        <thead>
          <tr>
            <th scope="col">{{ t('idpProviders.columns.name') }}</th>
            <th scope="col">{{ t('idpProviders.columns.type') }}</th>
            <th scope="col">{{ t('idpProviders.columns.status') }}</th>
            <th scope="col">{{ t('idpProviders.columns.lastDryRun') }}</th>
            <th scope="col" class="col-actions">{{ t('idpProviders.columns.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="idp in store.providers" :key="idp.id" :data-testid="`provider-row-${idp.id}`">
            <td>
              <button class="link-button" @click="onEdit(idp)">{{ idp.name }}</button>
            </td>
            <td>{{ typeLabel(idp) }}</td>
            <td>
              <BaseBadge :variant="badgeVariant(providerStatus(idp))">
                {{ t(`idpProviders.status.${providerStatus(idp)}`) }}
              </BaseBadge>
              <span
                v-if="showBrokenWarning(idp)"
                class="broken-warning"
                :title="t('idpProviders.brokenWarning')"
                :aria-label="t('idpProviders.brokenWarning')"
              >&#9888;</span>
            </td>
            <td>{{ formatRelative(idp.last_dry_run_at) }}</td>
            <td class="col-actions">
              <BaseButton
                variant="ghost"
                size="sm"
                :aria-label="t('idpProviders.actions.edit')"
                @click="onEdit(idp)"
              >
                {{ t('idpProviders.actions.edit') }}
              </BaseButton>
              <BaseButton
                variant="ghost"
                size="sm"
                :loading="store.isDryRunInFlight(idp.id)"
                :aria-label="t('idpProviders.actions.dryRun')"
                @click="onDryRun(idp)"
              >
                {{ t('idpProviders.actions.dryRun') }}
              </BaseButton>
              <BaseButton
                variant="danger"
                size="sm"
                :aria-label="t('idpProviders.actions.delete')"
                @click="onDeleteClick(idp)"
              >
                {{ t('idpProviders.actions.delete') }}
              </BaseButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <BaseModal v-model="showDeleteModal" :title="t('idpProviders.confirmDelete.title')">
      <p>{{ t('idpProviders.confirmDelete.message', { name: pendingDelete?.name ?? '' }) }}</p>
      <template #footer>
        <BaseButton variant="ghost" @click="cancelDelete">
          {{ t('idpProviders.confirmDelete.cancel') }}
        </BaseButton>
        <BaseButton variant="danger" @click="confirmDelete">
          {{ t('idpProviders.confirmDelete.confirm') }}
        </BaseButton>
      </template>
    </BaseModal>
  </div>
</template>

<style scoped>
.page-subtitle {
  margin: 4px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.empty-state {
  padding: 48px 32px;
  text-align: center;
}

.empty-illustration {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-state h2 {
  margin: 0 0 8px;
  font-size: 18px;
  color: var(--color-navy);
}

.empty-state p {
  margin: 0 0 20px;
  color: var(--color-text-muted);
}

.table-wrapper {
  overflow-x: auto;
}

.link-button {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  color: var(--color-primary);
  font-weight: 600;
  font-family: inherit;
  font-size: inherit;
  text-align: left;
}

.link-button:hover {
  text-decoration: underline;
}

.link-button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  border-radius: 2px;
}

.col-actions {
  white-space: nowrap;
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  align-items: center;
}

th.col-actions {
  text-align: right;
}

.broken-warning {
  margin-left: 6px;
  color: var(--color-accent, #D4883E);
  font-size: 14px;
  cursor: help;
}
</style>
