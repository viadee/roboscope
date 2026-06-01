<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import AuthLayout from '@/layouts/AuthLayout.vue'
import MinimalLayout from '@/layouts/MinimalLayout.vue'
import RobotParade from '@/components/ui/RobotParade.vue'
import { useKonamiCode } from '@/composables/useKonamiCode'

const route = useRoute()
const layout = computed(() => {
  if (route.meta.layout === 'auth') return AuthLayout
  if (route.meta.layout === 'minimal') return MinimalLayout
  return DefaultLayout
})

const paradeActive = ref(false)
useKonamiCode(() => { paradeActive.value = true })
</script>

<template>
  <component :is="layout">
    <RouterView />
  </component>
  <RobotParade v-if="paradeActive" @done="paradeActive = false" />
</template>
