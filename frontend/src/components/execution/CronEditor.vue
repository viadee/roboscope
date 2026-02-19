<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const { t } = useI18n()

type Preset = 'custom' | 'every5m' | 'every15m' | 'every30m' | 'hourly' | 'daily' | 'weekly' | 'monthly'

const presets: Record<Exclude<Preset, 'custom'>, string> = {
  every5m: '*/5 * * * *',
  every15m: '*/15 * * * *',
  every30m: '*/30 * * * *',
  hourly: '0 * * * *',
  daily: '0 8 * * *',
  weekly: '0 8 * * 1',
  monthly: '0 8 1 * *',
}

const minute = ref('*')
const hour = ref('*')
const dayOfMonth = ref('*')
const month = ref('*')
const dayOfWeek = ref('*')
const activePreset = ref<Preset>('custom')

// Parse initial value
function parseCron(expr: string) {
  const parts = expr.trim().split(/\s+/)
  if (parts.length >= 5) {
    minute.value = parts[0]
    hour.value = parts[1]
    dayOfMonth.value = parts[2]
    month.value = parts[3]
    dayOfWeek.value = parts[4]
  }
  // Detect preset
  activePreset.value = 'custom'
  for (const [key, val] of Object.entries(presets)) {
    if (expr.trim() === val) {
      activePreset.value = key as Preset
      break
    }
  }
}

parseCron(props.modelValue || '0 8 * * *')

const cronExpression = computed(() => {
  return `${minute.value} ${hour.value} ${dayOfMonth.value} ${month.value} ${dayOfWeek.value}`
})

watch(cronExpression, (val) => {
  emit('update:modelValue', val)
})

watch(() => props.modelValue, (val) => {
  if (val && val !== cronExpression.value) {
    parseCron(val)
  }
})

function selectPreset(key: Preset) {
  if (key === 'custom') {
    activePreset.value = 'custom'
    return
  }
  activePreset.value = key
  parseCron(presets[key])
}

function onFieldChange() {
  // When user edits a field, switch to custom
  activePreset.value = 'custom'
  for (const [key, val] of Object.entries(presets)) {
    if (cronExpression.value === val) {
      activePreset.value = key as Preset
      break
    }
  }
}

const humanReadable = computed(() => {
  const m = minute.value
  const h = hour.value
  const dom = dayOfMonth.value
  const mo = month.value
  const dow = dayOfWeek.value

  if (m.startsWith('*/') && h === '*' && dom === '*' && mo === '*' && dow === '*') {
    return t('schedule.cron.everyMinutes', { n: m.slice(2) })
  }
  if (m !== '*' && h === '*' && dom === '*' && mo === '*' && dow === '*') {
    return t('schedule.cron.everyHourAt', { m })
  }
  if (m !== '*' && h !== '*' && dom === '*' && mo === '*' && dow === '*') {
    return t('schedule.cron.dailyAt', { h: h.padStart(2, '0'), m: m.padStart(2, '0') })
  }
  if (m !== '*' && h !== '*' && dom === '*' && mo === '*' && dow !== '*') {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const d = days[Number(dow)] || dow
    return t('schedule.cron.weeklyOn', { day: d, h: h.padStart(2, '0'), m: m.padStart(2, '0') })
  }
  if (m !== '*' && h !== '*' && dom !== '*' && mo === '*' && dow === '*') {
    return t('schedule.cron.monthlyOn', { dom, h: h.padStart(2, '0'), m: m.padStart(2, '0') })
  }
  return cronExpression.value
})

const minuteOptions = [
  { value: '*', label: t('schedule.cron.every') },
  ...['0', '5', '10', '15', '20', '30', '45'].map(v => ({ value: v, label: `:${v.padStart(2, '0')}` })),
  { value: '*/5', label: t('schedule.cron.step', { n: 5 }) },
  { value: '*/10', label: t('schedule.cron.step', { n: 10 }) },
  { value: '*/15', label: t('schedule.cron.step', { n: 15 }) },
  { value: '*/30', label: t('schedule.cron.step', { n: 30 }) },
]

const hourOptions = [
  { value: '*', label: t('schedule.cron.every') },
  ...Array.from({ length: 24 }, (_, i) => ({ value: String(i), label: `${String(i).padStart(2, '0')}:00` })),
]

const dayOfMonthOptions = [
  { value: '*', label: t('schedule.cron.every') },
  ...Array.from({ length: 31 }, (_, i) => ({ value: String(i + 1), label: String(i + 1) })),
]

const monthOptions = [
  { value: '*', label: t('schedule.cron.every') },
  ...['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    .map((name, i) => ({ value: String(i + 1), label: name })),
]

const dayOfWeekOptions = [
  { value: '*', label: t('schedule.cron.every') },
  ...['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    .map((name, i) => ({ value: String(i), label: name })),
]
</script>

<template>
  <div class="cron-editor">
    <!-- Presets -->
    <div class="cron-presets">
      <button
        v-for="(_, key) in presets"
        :key="key"
        class="preset-btn"
        :class="{ active: activePreset === key }"
        type="button"
        @click="selectPreset(key as Preset)"
      >
        {{ t(`schedule.cron.preset.${key}`) }}
      </button>
    </div>

    <!-- Field editors -->
    <div class="cron-fields">
      <div class="cron-field">
        <label>{{ t('schedule.cron.minute') }}</label>
        <select v-model="minute" class="form-select" @change="onFieldChange">
          <option v-for="opt in minuteOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="cron-field">
        <label>{{ t('schedule.cron.hour') }}</label>
        <select v-model="hour" class="form-select" @change="onFieldChange">
          <option v-for="opt in hourOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="cron-field">
        <label>{{ t('schedule.cron.dayOfMonth') }}</label>
        <select v-model="dayOfMonth" class="form-select" @change="onFieldChange">
          <option v-for="opt in dayOfMonthOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="cron-field">
        <label>{{ t('schedule.cron.month') }}</label>
        <select v-model="month" class="form-select" @change="onFieldChange">
          <option v-for="opt in monthOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
      <div class="cron-field">
        <label>{{ t('schedule.cron.dayOfWeek') }}</label>
        <select v-model="dayOfWeek" class="form-select" @change="onFieldChange">
          <option v-for="opt in dayOfWeekOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>
    </div>

    <!-- Expression preview -->
    <div class="cron-preview">
      <code class="cron-raw">{{ cronExpression }}</code>
      <span class="cron-human">{{ humanReadable }}</span>
    </div>
  </div>
</template>

<style scoped>
.cron-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cron-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preset-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 20px;
  background: none;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.preset-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.preset-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

.cron-fields {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}

.cron-field label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--color-text-muted);
  margin-bottom: 4px;
}

.cron-field .form-select {
  width: 100%;
  padding: 6px 8px;
  font-size: 13px;
}

.cron-preview {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--color-bg, #f4f7fa);
  border-radius: var(--radius-sm, 6px);
  border: 1px solid var(--color-border-light, #edf2f7);
}

.cron-raw {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary);
  white-space: nowrap;
}

.cron-human {
  font-size: 12px;
  color: var(--color-text-muted);
}

@media (max-width: 768px) {
  .cron-fields {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
