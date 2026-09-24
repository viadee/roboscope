/**
 * V14.2 — EnvironmentsView Variables section: add / edit / delete call the
 * API, and a secret renders as a password input that never echoes the value.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import EnvironmentsView from '@/views/EnvironmentsView.vue'
import en from '@/i18n/locales/en'
import { useAuthStore } from '@/stores/auth.store'
import type { Environment, EnvironmentVariable } from '@/types/domain.types'

vi.mock('@/composables/useFeatureFlags', () => ({
  useFeatureFlags: () => ({ isEnabled: () => true }),
}))

const ENV = { id: 7, name: 'staging', python_version: '3.12', venv_kind: 'managed' } as Environment
const VARS: EnvironmentVariable[] = [
  { id: 1, environment_id: 7, key: 'BASE_URL', value: 'https://staging', is_secret: false },
  { id: 2, environment_id: 7, key: 'API_KEY', value: '********', is_secret: true },
]

vi.mock('@/api/environments.api', () => ({
  getEnvironments: vi.fn(async () => [ENV]),
  getPopularPackages: vi.fn(async () => []),
  getPackages: vi.fn(async () => []),
  getInstalledPackages: vi.fn(async () => []),
  getVariables: vi.fn(async () => VARS),
  createVariable: vi.fn(async () => VARS[0]),
  updateVariable: vi.fn(async () => VARS[1]),
  deleteVariable: vi.fn(async () => undefined),
}))

import * as envsApi from '@/api/environments.api'

async function mountOpen() {
  const auth = useAuthStore()
  vi.spyOn(auth, 'hasMinRole').mockReturnValue(true)
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en } })
  const w = mount(EnvironmentsView, { global: { plugins: [i18n] }, attachTo: document.body })
  await flushPromises()
  await w.find('.card-header').trigger('click')
  await flushPromises()
  return w
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('EnvironmentsView variables', () => {
  it('adds a variable via the API', async () => {
    const w = await mountOpen()
    expect(w.text()).toContain('%{NAME}') // escaped braces in the i18n hint
    await w.find('[data-testid="env-var-add"]').trigger('click')
    await w.find('[data-testid="env-var-key"]').setValue('TIMEOUT')
    await w.find('[data-testid="env-var-value"]').setValue('30')
    await w.find('[data-testid="env-var-form"]').trigger('submit')
    await flushPromises()
    expect(envsApi.createVariable).toHaveBeenCalledWith(7, { key: 'TIMEOUT', value: '30', is_secret: false })
    w.unmount()
  })

  it('edits a secret as a password input with an empty value', async () => {
    const w = await mountOpen()
    await w.findAll('[data-testid="env-var-edit"]')[1].trigger('click')
    const value = w.find('[data-testid="env-var-value"]')
    expect(value.attributes('type')).toBe('password')
    expect((value.element as HTMLInputElement).value).toBe('')
    expect(value.attributes('placeholder')).toBe('(unchanged)')
    await w.find('[data-testid="env-var-form"]').trigger('submit')
    await flushPromises()
    expect(envsApi.updateVariable).toHaveBeenCalledWith(7, 2, { key: 'API_KEY', value: '', is_secret: true })
    w.unmount()
  })

  it('deletes a variable after confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const w = await mountOpen()
    await w.findAll('[data-testid="env-var-delete"]')[0].trigger('click')
    await flushPromises()
    expect(envsApi.deleteVariable).toHaveBeenCalledWith(7, 1)
    w.unmount()
  })
})
