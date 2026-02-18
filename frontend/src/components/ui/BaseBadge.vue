<script setup lang="ts">
defineProps<{
  status?: string
  variant?: 'success' | 'danger' | 'warning' | 'info' | 'default'
}>()
</script>

<template>
  <span
    class="status-badge"
    :class="status ? `status-${status.toLowerCase()}` : `badge-${variant || 'default'}`"
  >
    <slot>{{ status }}</slot>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.badge-success { background: #DCFCE7; color: #166534; }
.badge-danger { background: #FEE2E2; color: #991B1B; }
.badge-warning { background: #FEF3C7; color: #92400E; }
.badge-info { background: #E8F8F5; color: #1B6B5A; }
.badge-default { background: #EDF0F7; color: #5C688C; }
</style>
