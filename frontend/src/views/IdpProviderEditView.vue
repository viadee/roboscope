<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('idpProviders.placeholder.title') }}</h1>
    </div>
    <div class="card" style="padding: 32px; text-align: center;">
      <p style="font-size: 16px; color: var(--color-text-muted); margin-bottom: 16px;">
        {{ t('idpProviders.placeholder.comingSoon') }}
      </p>
      <BaseButton @click="router.push('/admin/identity-providers')">
        {{ t('idpProviders.placeholder.backToList') }}
      </BaseButton>
    </div>
  </div>
</template>
