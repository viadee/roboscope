<script setup lang="ts">
defineProps<{
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}>()

defineEmits<{ click: [e: MouseEvent] }>()
</script>

<template>
  <button
    class="btn"
    :class="[`btn-${variant || 'primary'}`, `btn-${size || 'md'}`]"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="spinner"></span>
    <slot />
  </button>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  font-family: inherit;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm { padding: 5px 12px; font-size: 12px; }
.btn-md { padding: 8px 18px; font-size: 14px; }
.btn-lg { padding: 11px 22px; font-size: 15px; }

.btn-primary {
  background: var(--color-primary);
  color: white;
  box-shadow: 0 1px 3px rgba(60, 181, 161, 0.25);
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
  box-shadow: 0 2px 6px rgba(60, 181, 161, 0.35);
  transform: translateY(-1px);
}

.btn-secondary {
  background: white;
  color: var(--color-text);
  border-color: var(--color-border);
}
.btn-secondary:hover:not(:disabled) {
  background: var(--color-bg);
  border-color: var(--color-primary-light);
  color: var(--color-primary-dark);
}

.btn-danger {
  background: var(--color-danger);
  color: white;
  box-shadow: 0 1px 3px rgba(220, 53, 69, 0.2);
}
.btn-danger:hover:not(:disabled) {
  background: #c82333;
  box-shadow: 0 2px 6px rgba(220, 53, 69, 0.3);
  transform: translateY(-1px);
}

.btn-ghost {
  background: transparent;
  color: var(--color-text-muted);
}
.btn-ghost:hover:not(:disabled) {
  background: var(--color-border-light);
  color: var(--color-text);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
