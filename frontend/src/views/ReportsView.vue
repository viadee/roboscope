<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReportsStore } from '@/stores/reports.store'
import { useAuthStore } from '@/stores/auth.store'
import { useToast } from '@/composables/useToast'
import BaseBadge from '@/components/ui/BaseBadge.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import { formatDateTime } from '@/utils/formatDate'
import { formatDuration } from '@/utils/formatDuration'
import { formatPercent } from '@/utils/formatDuration'

const reports = useReportsStore()
const auth = useAuthStore()
const toast = useToast()
const { t } = useI18n()
const deleting = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

onMounted(() => reports.fetchReports())

async function deleteAll() {
  if (!confirm(t('reports.confirmDeleteAll'))) return
  deleting.value = true
  try {
    const result = await reports.deleteAllReports()
    toast.success(t('reports.toasts.deleted'), t('reports.toasts.deletedMsg', { deleted: result.deleted, dirs: result.dirs_cleaned }))
  } catch {
    toast.error(t('common.error'), t('reports.toasts.deleteError'))
  } finally {
    deleting.value = false
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleFileUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = '' // reset so same file can be selected again

  if (!file.name.toLowerCase().endsWith('.zip')) {
    toast.error(t('common.error'), t('reports.upload.invalidFormat'))
    return
  }

  uploading.value = true
  try {
    const result = await reports.uploadArchive(file)
    toast.success(
      t('reports.upload.success'),
      t('reports.upload.successMsg', {
        name: file.name,
        tests: result.report.total_tests,
      }),
    )
  } catch (e: any) {
    toast.error(
      t('reports.upload.error'),
      e.response?.data?.detail || t('reports.upload.errorMsg'),
    )
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('reports.title') }}</h1>
      <div class="flex gap-2">
        <BaseButton
          variant="secondary"
          :loading="uploading"
          @click="triggerUpload"
        >
          {{ t('reports.upload.button') }}
        </BaseButton>
        <input
          ref="fileInput"
          type="file"
          accept=".zip"
          style="display: none"
          @change="handleFileUpload"
        />
        <BaseButton
          v-if="auth.hasMinRole('admin') && reports.reports.length > 0"
          variant="danger"
          :loading="deleting"
          @click="deleteAll"
        >
          {{ t('reports.deleteAll') }}
        </BaseButton>
      </div>
    </div>

    <BaseSpinner v-if="reports.loading" />

    <div v-else class="card">
      <table class="data-table" v-if="reports.reports.length">
        <thead>
          <tr>
            <th>{{ t('common.id') }}</th>
            <th>{{ t('reports.source') }}</th>
            <th>{{ t('reports.tests') }}</th>
            <th>{{ t('reports.passed') }}</th>
            <th>{{ t('reports.failed') }}</th>
            <th>{{ t('reports.successRate') }}</th>
            <th>{{ t('common.duration') }}</th>
            <th>{{ t('common.date') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="report in reports.reports"
            :key="report.id"
            class="clickable-row"
            @click="$router.push(`/reports/${report.id}`)"
          >
            <td>#{{ report.id }}</td>
            <td>
              <template v-if="report.archive_name">
                <BaseBadge variant="info">{{ t('reports.archive') }}</BaseBadge>
                <span class="text-sm" style="margin-left: 4px;">{{ report.archive_name }}</span>
              </template>
              <template v-else>
                {{ t('reports.run') }} #{{ report.execution_run_id }}
              </template>
            </td>
            <td>{{ report.total_tests }}</td>
            <td>
              <span class="text-success">{{ report.passed_tests }}</span>
            </td>
            <td>
              <span :class="report.failed_tests > 0 ? 'text-danger' : ''">{{ report.failed_tests }}</span>
            </td>
            <td>
              <BaseBadge
                :variant="report.total_tests > 0 && report.passed_tests === report.total_tests ? 'success' : 'danger'"
              >
                {{ report.total_tests > 0 ? formatPercent(report.passed_tests / report.total_tests * 100) : '-' }}
              </BaseBadge>
            </td>
            <td>{{ formatDuration(report.total_duration_seconds) }}</td>
            <td class="text-muted text-sm">{{ formatDateTime(report.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-muted text-center p-4">{{ t('reports.noReports') }}</p>
    </div>
  </div>
</template>

<style scoped>
.clickable-row { cursor: pointer; }
.clickable-row:hover { background: var(--color-border-light); }
.text-success { color: var(--color-success); font-weight: 500; }
.text-danger { color: var(--color-danger); font-weight: 500; }
</style>
