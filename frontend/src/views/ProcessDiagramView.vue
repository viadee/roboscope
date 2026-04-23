<script setup lang="ts">
/**
 * Story DOCS-1 — BPMN 2.0 viewer for the RoboScope core process.
 *
 * Heavyweight bpmn-js is loaded via dynamic import so it never lands
 * in the critical bundle; the route itself is also code-split at the
 * router level. The hand-authored BPMN XML lives as a static asset
 * under `public/diagrams/` so maintainers can open it in any BPMN
 * modeler without a build step.
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const canvas = ref<HTMLDivElement | null>(null)
const error = ref<string | null>(null)
const loading = ref(true)

// bpmn-js module type is not exposed in package.json so we keep this
// `any` — the alternative is a module-augmentation file that costs
// more than it buys in a single-callsite view.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let viewer: any = null

async function boot() {
  try {
    const [{ default: NavigatedViewer }, bpmnXml] = await Promise.all([
      import('bpmn-js/lib/NavigatedViewer'),
      fetch('/diagrams/roboscope-core-process.bpmn').then((r) => {
        if (!r.ok) throw new Error(`Failed to fetch BPMN asset: HTTP ${r.status}`)
        return r.text()
      }),
    ])
    // bpmn-js CSS gets imported here so it's included only when this
    // lazy chunk is actually fetched.
    await import('bpmn-js/dist/assets/diagram-js.css')
    await import('bpmn-js/dist/assets/bpmn-js.css')
    await import('bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css')

    if (!canvas.value) return
    viewer = new NavigatedViewer({ container: canvas.value })
    await viewer.importXML(bpmnXml)
    // Fit-to-viewport on initial render.
    viewer.get('canvas').zoom('fit-viewport', 'auto')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    error.value = t('process.loadError', { reason: msg })
  } finally {
    loading.value = false
  }
}

onMounted(boot)
onBeforeUnmount(() => {
  if (viewer) {
    viewer.destroy()
    viewer = null
  }
})
</script>

<template>
  <section class="process-diagram">
    <header class="process-diagram__header">
      <h1>{{ t('process.heading') }}</h1>
      <p class="process-diagram__hint">{{ t('process.hint') }}</p>
    </header>

    <p v-if="loading" class="process-diagram__loading">{{ t('process.loading') }}</p>
    <p v-if="error" class="process-diagram__error" role="alert">{{ error }}</p>

    <div class="process-diagram__canvas-wrapper">
      <div ref="canvas" class="process-diagram__canvas" aria-label="BPMN diagram"></div>
    </div>

    <footer class="process-diagram__footer">
      <span>{{ t('process.credits') }}</span>
    </footer>
  </section>
</template>

<style scoped>
.process-diagram {
  padding: 1rem 1.5rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  height: calc(100vh - var(--app-header-height, 60px));
  min-height: 600px;
}

.process-diagram__header h1 {
  margin: 0 0 0.3rem;
}

.process-diagram__hint {
  color: var(--color-text-secondary, #555);
  margin: 0;
}

.process-diagram__loading {
  color: var(--color-text-secondary, #777);
  font-style: italic;
}

.process-diagram__error {
  padding: 0.6rem 0.85rem;
  background: #fee2e2;
  border: 1px solid #f87171;
  color: #7f1d1d;
  border-radius: 4px;
}

.process-diagram__canvas-wrapper {
  flex: 1;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
  min-height: 420px;
}

.process-diagram__canvas {
  width: 100%;
  height: 100%;
}

.process-diagram__footer {
  font-size: 0.8rem;
  color: var(--color-text-secondary, #777);
}
</style>
