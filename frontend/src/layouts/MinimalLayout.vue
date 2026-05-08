<script setup lang="ts">
/**
 * MinimalLayout — used for routes that pop out a single component
 * into its own browser tab (currently /reports/:id/detailed for the
 * keyword-tree deep view). Renders the slot in a centered narrow
 * column without the app sidebar / header so the user can scan the
 * one piece of content full-width without UI chrome competing.
 *
 * Auth is still enforced via the route's `meta.requiresAuth` —
 * this layout makes no assumption about the user being signed in.
 */
</script>

<template>
  <div class="minimal-layout">
    <slot />
  </div>
</template>

<style scoped>
.minimal-layout {
  min-height: 100vh;
  background: var(--color-bg, #F4F7FA);
  padding: 16px 24px;
}
</style>
