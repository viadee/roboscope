<script setup lang="ts">
import type { Toast } from '@/stores/ui.store'

defineProps<{ toast: Toast }>()
defineEmits<{ close: [] }>()

const icons: Record<string, string> = {
  success: '\u2713',
  error: '\u2717',
  warning: '!',
  info: 'i',
}
</script>

<template>
  <div class="toast" :class="`toast-${toast.type}`">
    <span class="toast-icon">{{ icons[toast.type] || 'i' }}</span>
    <div class="toast-content">
      <strong>{{ toast.title }}</strong>
      <p v-if="toast.message">{{ toast.message }}</p>
    </div>
    <button class="toast-close" @click="$emit('close')">&times;</button>
  </div>
</template>

<style scoped>
.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  background: white;
  border-left: 4px solid;
  min-width: 300px;
}

.toast-success { border-color: var(--color-success); }
.toast-error { border-color: var(--color-danger); }
.toast-warning { border-color: var(--color-warning); }
.toast-info { border-color: var(--color-primary); }

.toast-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.toast-success .toast-icon { background: var(--color-success); }
.toast-error .toast-icon { background: var(--color-danger); }
.toast-warning .toast-icon { background: var(--color-warning); }
.toast-info .toast-icon { background: var(--color-primary); }

.toast-content { flex: 1; }
.toast-content strong { display: block; font-size: 13px; color: var(--color-text); }
.toast-content p { font-size: 12px; color: var(--color-text-muted); margin-top: 2px; }

.toast-close {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: var(--color-text-light);
  line-height: 1;
  transition: color 0.15s;
}

.toast-close:hover {
  color: var(--color-text);
}
</style>
