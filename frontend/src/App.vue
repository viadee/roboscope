<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import MinimalLayout from '@/layouts/MinimalLayout.vue'

const route = useRoute()
const layout = computed(() => {
  if (route.meta.layout === 'auth') return AuthLayout
  if (route.meta.layout === 'minimal') return MinimalLayout
  return DefaultLayout
})
</script>

<template>
  <component :is="layout">
    <RouterView />
  </component>
</template>
