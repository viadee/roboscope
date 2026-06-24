<script setup lang="ts">
/**
 * EXEC.3 + EXEC.10 — advanced execution config for the run dialog.
 *
 * Curated, governed levers only — never a deny-list override:
 *  - a variables key/value editor and a freeform `robot` args field (EXEC.3);
 *  - curated pre-/post-execution modifier pickers fed by the server registry
 *    (EXEC.10) — the user picks vetted entries by key, never types a class path;
 *  - repo-confined `--pythonpath` / `--variablefile` levers, each shown only
 *    when its ADMIN-gated feature flag is on, behind an explicit code-loading
 *    consent (EXEC.10).
 *
 * Rendered ONLY when `executionAdvancedArgs` is on (the caller gates with
 * `v-if`). Server-authoritative validation happens on submit; this component
 * only collects input.
 */
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getRunModifiers, type RunModifier } from '@/api/execution.api'

const { t } = useI18n()

const props = defineProps<{
  argsText: string
  variablesText: string
  showPythonPath?: boolean
  showVariableFile?: boolean
}>()

const emit = defineEmits<{
  'update:argsText': [value: string]
  'update:variablesText': [value: string]
  'update:modifiers': [value: Array<{ key: string; kind: string; args: string[] }>]
  'update:pythonPaths': [value: string[]]
  'update:variableFiles': [value: string[]]
}>()

const modifiers = ref<RunModifier[]>([])
// per-key selection state: { checked, args: { name: value } }
const selection = ref<Record<string, { checked: boolean; args: Record<string, string> }>>({})

const pythonPathsText = ref('')
const variableFilesText = ref('')
const consentPython = ref(false)
const consentVarFile = ref(false)

onMounted(async () => {
  try {
    modifiers.value = await getRunModifiers()
  } catch {
    modifiers.value = []
  }
})

function ensureState(key: string) {
  if (!selection.value[key]) selection.value[key] = { checked: false, args: {} }
  return selection.value[key]
}

function emitModifiers() {
  const out: Array<{ key: string; kind: string; args: string[] }> = []
  for (const m of modifiers.value) {
    const st = selection.value[m.key]
    if (!st?.checked) continue
    const args = (m.args_schema || []).map((f) => st.args[f.name] ?? '')
    // trim trailing empty optional args
    while (args.length && args[args.length - 1] === '') args.pop()
    out.push({ key: m.key, kind: m.kind, args })
  }
  emit('update:modifiers', out)
}

function toggleModifier(key: string, checked: boolean) {
  ensureState(key).checked = checked
  emitModifiers()
}

function setModifierArg(key: string, name: string, value: string) {
  ensureState(key).args[name] = value
  emitModifiers()
}

function splitLines(text: string): string[] {
  return text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
}

function onPythonPaths(text: string) {
  pythonPathsText.value = text
  emit('update:pythonPaths', consentPython.value ? splitLines(text) : [])
}
function onConsentPython(checked: boolean) {
  consentPython.value = checked
  emit('update:pythonPaths', checked ? splitLines(pythonPathsText.value) : [])
}
function onVariableFiles(text: string) {
  variableFilesText.value = text
  emit('update:variableFiles', consentVarFile.value ? splitLines(text) : [])
}
function onConsentVarFile(checked: boolean) {
  consentVarFile.value = checked
  emit('update:variableFiles', checked ? splitLines(variableFilesText.value) : [])
}

function modifiersOfKind(kind: string) {
  return modifiers.value.filter((m) => m.kind === kind)
}
</script>

<template>
  <div class="advanced-run-config" data-testid="advanced-section">
    <h4 class="advanced-title">{{ t('execution.advanced.title') }}</h4>

    <div class="form-group">
      <label class="form-label">{{ t('execution.advanced.variables') }}</label>
      <textarea
        :value="variablesText"
        class="form-input"
        rows="3"
        :placeholder="t('execution.advanced.variablesPlaceholder')"
        data-testid="advanced-vars-input"
        @input="emit('update:variablesText', ($event.target as HTMLTextAreaElement).value)"
      ></textarea>
      <span class="text-muted text-sm">{{ t('execution.advanced.variablesHint') }}</span>
    </div>

    <div class="form-group">
      <label class="form-label">{{ t('execution.advanced.args') }}</label>
      <textarea
        :value="argsText"
        class="form-input"
        rows="2"
        :placeholder="t('execution.advanced.argsPlaceholder')"
        data-testid="advanced-args-input"
        @input="emit('update:argsText', ($event.target as HTMLTextAreaElement).value)"
      ></textarea>
      <span class="text-muted text-sm">{{ t('execution.advanced.argsHint') }}</span>
    </div>

    <!-- EXEC.10: curated modifier pickers (only render a group with entries) -->
    <div
      v-for="kind in ['prerun', 'prerebot']"
      :key="kind"
      v-show="modifiersOfKind(kind).length"
      class="form-group"
    >
      <label class="form-label">{{ t(`execution.advanced.modifiers.${kind}`) }}</label>
      <div
        v-for="m in modifiersOfKind(kind)"
        :key="m.key"
        class="modifier-row"
        :data-testid="`modifier-${m.key}`"
      >
        <label class="modifier-check">
          <input
            type="checkbox"
            :checked="selection[m.key]?.checked || false"
            @change="toggleModifier(m.key, ($event.target as HTMLInputElement).checked)"
          />
          <span>{{ m.label }}</span>
          <span class="modifier-tier" :class="`tier-${m.tier}`">{{
            t(`execution.advanced.modifiers.tier.${m.tier}`)
          }}</span>
        </label>
        <span v-if="m.description" class="text-muted text-sm modifier-desc">{{ m.description }}</span>
        <div v-if="selection[m.key]?.checked && m.args_schema?.length" class="modifier-args">
          <input
            v-for="f in m.args_schema"
            :key="f.name"
            type="text"
            class="form-input modifier-arg-input"
            :placeholder="f.label || f.name"
            :value="selection[m.key]?.args[f.name] || ''"
            @input="setModifierArg(m.key, f.name, ($event.target as HTMLInputElement).value)"
          />
        </div>
      </div>
    </div>

    <!-- EXEC.10: repo-confined code-loading levers (ADMIN flag-gated) -->
    <div v-if="props.showPythonPath" class="form-group" data-testid="pythonpath-lever">
      <label class="form-label">{{ t('execution.advanced.pythonPath') }}</label>
      <textarea
        :value="pythonPathsText"
        class="form-input"
        rows="2"
        :disabled="!consentPython"
        :placeholder="t('execution.advanced.pythonPathPlaceholder')"
        data-testid="advanced-pythonpath-input"
        @input="onPythonPaths(($event.target as HTMLTextAreaElement).value)"
      ></textarea>
      <label class="consent-check">
        <input
          type="checkbox"
          :checked="consentPython"
          data-testid="pythonpath-consent"
          @change="onConsentPython(($event.target as HTMLInputElement).checked)"
        />
        <span>{{ t('execution.advanced.codeLoadConsent') }}</span>
      </label>
      <span class="text-muted text-sm">{{ t('execution.advanced.pythonPathHint') }}</span>
    </div>

    <div v-if="props.showVariableFile" class="form-group" data-testid="variablefile-lever">
      <label class="form-label">{{ t('execution.advanced.variableFile') }}</label>
      <textarea
        :value="variableFilesText"
        class="form-input"
        rows="2"
        :disabled="!consentVarFile"
        :placeholder="t('execution.advanced.variableFilePlaceholder')"
        data-testid="advanced-variablefile-input"
        @input="onVariableFiles(($event.target as HTMLTextAreaElement).value)"
      ></textarea>
      <label class="consent-check">
        <input
          type="checkbox"
          :checked="consentVarFile"
          data-testid="variablefile-consent"
          @change="onConsentVarFile(($event.target as HTMLInputElement).checked)"
        />
        <span>{{ t('execution.advanced.codeLoadConsent') }}</span>
      </label>
      <span class="text-muted text-sm">{{ t('execution.advanced.variableFileHint') }}</span>
    </div>
  </div>
</template>

<style scoped>
.advanced-run-config {
  border-top: 1px solid var(--color-border, #e2e8f0);
  margin-top: 0.75rem;
  padding-top: 0.75rem;
}
.advanced-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-navy, #1a2d50);
  margin: 0 0 0.5rem;
}
.modifier-row {
  margin-bottom: 0.4rem;
}
.modifier-check {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
}
.modifier-tier {
  font-size: 0.7rem;
  padding: 0 0.35rem;
  border-radius: 4px;
  background: var(--color-border, #e2e8f0);
  color: var(--color-navy, #1a2d50);
}
.modifier-tier.tier-org {
  background: var(--color-accent, #d4883e);
  color: #fff;
}
.modifier-desc {
  display: block;
  margin-left: 1.4rem;
}
.modifier-args {
  margin: 0.25rem 0 0 1.4rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.modifier-arg-input {
  max-width: 12rem;
}
.consent-check {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.8rem;
  margin: 0.3rem 0;
}
</style>
