<script setup lang="ts">
/**
 * Standalone "Detailbericht" pop-out — opened from the inline
 * RunDetailPanel via "↗ In neuem Tab öffnen". Renders ONLY the
 * keyword tree (`ReportXmlView`) full-width, without the rest of
 * the report KPIs / failed-tests / AI analysis sections.
 *
 * Used together with `MinimalLayout` (no sidebar / header) so the
 * pop-out window contains just the deep view the user wanted.
 */
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useReportsStore } from '@/stores/reports.store'
import BaseSpinner from '@/components/ui/BaseSpinner.vue'
import ReportXmlView from '@/components/report/ReportXmlView.vue'

const route = useRoute()
const reports = useReportsStore()
const { t } = useI18n()

const reportId = computed(() => Number(route.params.id))

onMounted(() => {
  if (reportId.value) {
    reports.fetchReport(reportId.value)
  }
  // Browser tab title for the popped-out window.
  document.title = `${t('reportDetail.tabs.detailedReport')} — RoboScope`
})
</script>

<template>
  <div class="detailed-view">
    <header class="detailed-header">
      <h1>
        {{ t('reportDetail.tabs.detailedReport') }}
        <span v-if="reports.activeReport" class="detailed-subtitle">
          — Run #{{ reports.activeReport.report.execution_run_id ?? reports.activeReport.report.id }}
        </span>
      </h1>
    </header>

    <BaseSpinner v-if="reports.loading" />
    <div v-else-if="reports.activeReport" class="detailed-body">
      <ReportXmlView :report-id="reportId" />
    </div>
    <p v-else class="text-muted">
      {{ t('reportDetail.notFound', { id: reportId }) }}
    </p>
  </div>
</template>

<style scoped>
.detailed-view {
  max-width: 1400px;
  margin: 0 auto;
}
.detailed-header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
}
.detailed-header h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-navy, #1A2D50);
}
.detailed-subtitle {
  font-weight: 400;
  color: var(--color-text-muted, #5A6380);
}
.detailed-body {
  background: var(--color-bg-card, #fff);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 8px;
  padding: 16px;
}
</style>
