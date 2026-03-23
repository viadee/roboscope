<script setup lang="ts">
const props = defineProps<{
  data: { stepType: string; borderColor: string; bgColor: string }
}>()
</script>

<template>
  <div
    class="control-frame"
    :style="{
      borderColor: data.borderColor,
      background: data.bgColor,
      width: '100%',
      height: '100%',
    }"
  />
</template>

<style scoped>
.control-frame {
  border: 2px dashed #888;
  border-radius: 12px;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
