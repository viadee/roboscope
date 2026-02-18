<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="page-content">
    <div class="page-header">
      <h1>{{ t('imprint.title') }}</h1>
    </div>

    <div class="card imprint-card">
      <div class="imprint-section">
        <h2>{{ t('imprint.provider') }}</h2>
        <p>
          <strong>viadee Unternehmensberatung AG</strong><br />
          Anton-Bruchausen-Str. 8<br />
          48147 Münster<br />
          {{ t('imprint.germany') }}
        </p>
      </div>

      <div class="imprint-section">
        <h2>{{ t('imprint.contact') }}</h2>
        <p>
          {{ t('imprint.phone') }}: +49 251 777770<br />
          {{ t('imprint.fax') }}: +49 251 77777888<br />
          {{ t('imprint.emailLabel') }}: <a href="mailto:kontakt@viadee.de">kontakt@viadee.de</a><br />
          Web: <a href="https://www.viadee.de" target="_blank" rel="noopener">www.viadee.de</a>
        </p>
      </div>

      <div class="imprint-section">
        <h2>{{ t('imprint.board') }}</h2>
        <p>
          {{ t('imprint.boardMembers') }}: Dr. Volker Oshege, Rita Helter<br />
          {{ t('imprint.supervisoryChair') }}: Carl-Josef Husken
        </p>
      </div>

      <div class="imprint-section">
        <h2>{{ t('imprint.register') }}</h2>
        <p>
          {{ t('imprint.court') }}: Amtsgericht Münster<br />
          {{ t('imprint.regNumber') }}: HRB 17380<br />
          {{ t('imprint.vatId') }}: DE170173068
        </p>
      </div>

      <div class="imprint-section">
        <h2>{{ t('imprint.product') }}</h2>
        <p>
          {{ t('imprint.productText') }}<br />
          <a href="https://www.mateo-automation.com" target="_blank" rel="noopener">www.mateo-automation.com</a>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.imprint-card {
  max-width: 720px;
  padding: 32px;
}

.imprint-section {
  margin-bottom: 24px;
}

.imprint-section:last-child {
  margin-bottom: 0;
}

.imprint-section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 8px;
}

.imprint-section p {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-muted);
  margin: 0;
}

.imprint-section a {
  color: var(--color-primary);
  text-decoration: none;
}

.imprint-section a:hover {
  text-decoration: underline;
}
</style>
