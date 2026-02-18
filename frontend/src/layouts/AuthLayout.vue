<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import mateoLogo from '@/assets/mateo-logo.png'

const { t } = useI18n()
</script>

<template>
  <div class="auth-layout">
    <div class="auth-container">
      <div class="auth-logo">
        <img :src="mateoLogo" alt="mateo" class="auth-logo-img" />
        <p>{{ t('auth.tagline') }}</p>
      </div>
      <slot />
    </div>

    <!-- Decorative background elements -->
    <div class="bg-decoration bg-circle-1"></div>
    <div class="bg-decoration bg-circle-2"></div>
  </div>
</template>

<style scoped>
.auth-layout {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #101933 0%, #203166 50%, #162044 100%);
  position: relative;
  overflow: hidden;
}

.auth-container {
  width: 100%;
  max-width: 400px;
  padding: 24px;
  position: relative;
  z-index: 2;
}

.auth-logo {
  text-align: center;
  margin-bottom: 32px;
}

.auth-logo-img {
  height: 64px;
  width: auto;
  margin-bottom: 12px;
}

.auth-logo p {
  color: var(--color-text-sidebar);
  font-size: 14px;
  margin-top: 4px;
}

/* Decorative circles */
.bg-decoration {
  position: absolute;
  border-radius: 50%;
  z-index: 1;
}

.bg-circle-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(60, 181, 161, 0.08) 0%, transparent 70%);
  top: -150px;
  right: -100px;
}

.bg-circle-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(223, 170, 64, 0.06) 0%, transparent 70%);
  bottom: -100px;
  left: -100px;
}
</style>
