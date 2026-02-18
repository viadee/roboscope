<script setup lang="ts">
defineProps<{ size?: 'sm' | 'md' | 'lg' }>()
</script>

<template>
  <div class="spinner-container">
    <div class="spinner" :class="`spinner-${size || 'md'}`"></div>
  </div>
</template>

<style scoped>
.spinner-container { display: flex; align-items: center; justify-content: center; padding: 20px; }
.spinner {
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.spinner-sm { width: 16px; height: 16px; border-width: 2px; }
.spinner-md { width: 32px; height: 32px; }
.spinner-lg { width: 48px; height: 48px; border-width: 4px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
