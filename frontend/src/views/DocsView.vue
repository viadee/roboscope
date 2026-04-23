<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { getDocsContent } from '@/docs/index'
import type { DocSection } from '@/docs/types'

const { t, locale } = useI18n()

const searchQuery = ref('')
const activeId = ref('')
const tocCollapsed = ref<Set<string>>(new Set())
const observer = ref<IntersectionObserver | null>(null)

const docs = computed(() => getDocsContent(locale.value))

const filteredDocs = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return docs.value
  return docs.value
    .map((section: DocSection) => {
      const subs = section.subsections.filter(
        (sub) =>
          sub.title.toLowerCase().includes(q) ||
          sub.content.toLowerCase().includes(q)
      )
      if (subs.length || section.title.toLowerCase().includes(q)) {
        return { ...section, subsections: subs.length ? subs : section.subsections }
      }
      return null
    })
    .filter(Boolean) as DocSection[]
})

function toggleSection(id: string) {
  if (tocCollapsed.value.has(id)) {
    tocCollapsed.value.delete(id)
  } else {
    tocCollapsed.value.add(id)
  }
}

function scrollTo(id: string) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    history.replaceState(null, '', `#${id}`)
  }
}

function printDocs() {
  window.print()
}

function setupObserver() {
  if (observer.value) observer.value.disconnect()
  observer.value = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activeId.value = entry.target.id
          break
        }
      }
    },
    { rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }
  )
  nextTick(() => {
    document.querySelectorAll('.doc-subsection[id]').forEach((el) => {
      observer.value?.observe(el)
    })
  })
}

function scrollToHash() {
  const hash = window.location.hash.slice(1)
  if (hash) {
    nextTick(() => {
      const el = document.getElementById(hash)
      if (el) el.scrollIntoView({ block: 'start' })
    })
  }
}

onMounted(() => {
  setupObserver()
  scrollToHash()
})

watch(locale, () => {
  nextTick(() => setupObserver())
})

watch(filteredDocs, () => {
  nextTick(() => setupObserver())
})

onUnmounted(() => {
  observer.value?.disconnect()
})
</script>

<template>
  <div class="docs-page">
    <!-- Sidebar TOC -->
    <aside class="docs-toc">
      <div class="toc-header">
        <h3>{{ t('docs.tableOfContents') }}</h3>
      </div>

      <div class="toc-search">
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="t('docs.searchPlaceholder')"
          class="toc-search-input"
        />
      </div>

      <nav class="toc-nav" v-if="filteredDocs.length">
        <div v-for="section in filteredDocs" :key="section.id" class="toc-section">
          <div
            class="toc-section-title"
            :class="{ active: activeId.startsWith(section.id) }"
            @click="toggleSection(section.id)"
          >
            <span class="toc-icon">{{ section.icon }}</span>
            <span class="toc-label">{{ section.title }}</span>
            <span class="toc-chevron" :class="{ collapsed: tocCollapsed.has(section.id) }">&#9662;</span>
          </div>
          <div class="toc-subsections" v-if="!tocCollapsed.has(section.id)">
            <a
              v-for="sub in section.subsections"
              :key="sub.id"
              class="toc-sub-link"
              :class="{ active: activeId === sub.id }"
              @click.prevent="scrollTo(sub.id)"
              :href="`#${sub.id}`"
            >
              {{ sub.title }}
            </a>
          </div>
        </div>
      </nav>

      <div class="toc-empty" v-else>
        <p>{{ t('docs.noResults') }}</p>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="docs-content">
      <div class="docs-header">
        <h1>{{ t('docs.title') }}</h1>
        <button class="print-btn" @click="printDocs">
          🖨️ {{ t('docs.printVersion') }}
        </button>
      </div>

      <div v-if="filteredDocs.length" class="docs-sections">
        <section v-for="section in filteredDocs" :key="section.id" class="doc-section">
          <h2 :id="section.id" class="section-heading">
            <span class="section-icon">{{ section.icon }}</span>
            {{ section.title }}
          </h2>

          <div
            v-for="sub in section.subsections"
            :key="sub.id"
            :id="sub.id"
            class="doc-subsection"
          >
            <h3 class="subsection-heading">{{ sub.title }}</h3>
            <div class="subsection-content" v-html="sub.content"></div>
            <div v-if="sub.tip" class="doc-tip">
              <strong>{{ t('docs.tip') }}:</strong> {{ sub.tip }}
            </div>
          </div>
        </section>
      </div>

      <div v-else class="docs-empty">
        <p>{{ t('docs.noResults') }}</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.docs-page {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* --- TOC Sidebar --- */
.docs-toc {
  width: 280px;
  min-width: 280px;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.toc-header {
  padding: 20px 16px 12px;
  border-bottom: 1px solid var(--color-border);
}

.toc-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.toc-search {
  padding: 12px 16px;
}

.toc-search-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--color-bg);
  color: var(--color-text);
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.toc-search-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(60, 181, 161, 0.15);
}

.toc-nav {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0 16px;
}

.toc-section {
  margin-bottom: 2px;
}

.toc-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
  transition: background 0.15s;
  user-select: none;
}

.toc-section-title:hover {
  background: var(--color-bg);
}

.toc-section-title.active {
  color: var(--color-primary);
}

.toc-icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.toc-label {
  flex: 1;
}

.toc-chevron {
  font-size: 10px;
  color: var(--color-text-muted);
  transition: transform 0.15s;
}

.toc-chevron.collapsed {
  transform: rotate(-90deg);
}

.toc-subsections {
  padding: 2px 0 4px;
}

.toc-sub-link {
  display: block;
  padding: 5px 16px 5px 44px;
  font-size: 12.5px;
  color: var(--color-text-muted);
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s;
  border-left: 2px solid transparent;
}

.toc-sub-link:hover {
  color: var(--color-text);
  background: var(--color-bg);
}

.toc-sub-link.active {
  color: var(--color-primary);
  border-left-color: var(--color-primary);
  background: rgba(60, 181, 161, 0.06);
}

.toc-empty {
  padding: 24px 16px;
  text-align: center;
  color: var(--color-text-muted);
  font-size: 13px;
}

/* --- Main Content --- */
.docs-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px 40px 60px;
  background: var(--color-bg);
}

.docs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 32px;
}

.docs-header h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: var(--color-text);
}

.print-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg-card);
  color: var(--color-text);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.print-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* Sections */
.doc-section {
  margin-bottom: 40px;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 24px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--color-primary);
  scroll-margin-top: 20px;
}

.section-icon {
  font-size: 22px;
}

.doc-subsection {
  margin-bottom: 28px;
  scroll-margin-top: 80px;
}

.subsection-heading {
  font-size: 17px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 12px;
}

.subsection-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text);
}

.subsection-content :deep(p) {
  margin: 0 0 12px;
}

.subsection-content :deep(ul),
.subsection-content :deep(ol) {
  margin: 0 0 12px;
  padding-left: 24px;
}

.subsection-content :deep(li) {
  margin-bottom: 4px;
}

.subsection-content :deep(code) {
  background: rgba(60, 181, 161, 0.1);
  color: var(--color-primary-dark, #2a9485);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

.subsection-content :deep(h4) {
  font-size: 15px;
  font-weight: 600;
  margin: 16px 0 8px;
  color: var(--color-text);
}

.subsection-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

.subsection-content :deep(th) {
  text-align: left;
  padding: 8px 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.5px;
  color: var(--color-text-muted);
}

.subsection-content :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  color: var(--color-text);
}

.subsection-content :deep(strong) {
  font-weight: 600;
}

.doc-tip {
  background: rgba(223, 170, 64, 0.1);
  border-left: 3px solid var(--color-accent);
  padding: 10px 14px;
  border-radius: 0 6px 6px 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text);
  margin-top: 8px;
}

.docs-empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--color-text-muted);
  font-size: 15px;
}

/* --- Print Styles --- */
@media print {
  .docs-page {
    display: block;
    height: auto;
    overflow: visible;
  }

  .docs-toc {
    display: none;
  }

  .docs-content {
    overflow: visible;
    padding: 0;
  }

  .docs-header {
    margin-bottom: 20px;
  }

  .print-btn {
    display: none;
  }

  .doc-section {
    page-break-inside: avoid;
  }

  .doc-subsection {
    page-break-inside: avoid;
  }

  .section-heading {
    border-bottom-color: #333;
  }
}
</style>
