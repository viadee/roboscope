<script setup lang="ts">
const emit = defineEmits<{ done: [] }>()

function onAnimationEnd(event: AnimationEvent) {
  if (event.animationName === 'parade-march') emit('done')
}
</script>

<template>
  <div class="parade" aria-hidden="true" @animationend="onAnimationEnd">
    <svg viewBox="0 0 40 48" width="40" height="48">
      <line x1="20" y1="2" x2="20" y2="8" stroke="currentColor" stroke-width="2" />
      <circle cx="20" cy="2" r="2" fill="currentColor" />
      <rect x="10" y="8" width="20" height="14" rx="2" fill="currentColor" />
      <circle cx="16" cy="15" r="1.5" fill="white" />
      <circle cx="24" cy="15" r="1.5" fill="white" />
      <rect x="8" y="22" width="24" height="14" rx="1" fill="currentColor" />
      <rect class="leg leg-l" x="12" y="36" width="5" height="10" fill="currentColor" />
      <rect class="leg leg-r" x="23" y="36" width="5" height="10" fill="currentColor" />
    </svg>
  </div>
</template>

<style scoped>
.parade {
  position: fixed;
  bottom: 8px;
  left: -80px;
  z-index: 9999;
  pointer-events: none;
  color: var(--color-primary);
  animation: parade-march 4s linear forwards, parade-bob 0.4s ease-in-out infinite alternate;
}

.leg {
  transform-origin: center top;
  animation: leg-shuffle 0.4s ease-in-out infinite alternate;
}
.leg-r {
  animation-delay: -0.2s;
}

@keyframes parade-march {
  from { transform: translateX(0); }
  to   { transform: translateX(calc(100vw + 80px)); }
}

@keyframes parade-bob {
  from { margin-bottom: 0; }
  to   { margin-bottom: 4px; }
}

@keyframes leg-shuffle {
  from { transform: scaleY(1); }
  to   { transform: scaleY(0.7); }
}
</style>
