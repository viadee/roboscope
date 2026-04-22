import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import TeamListView from '@/views/TeamListView.vue'
import en from '@/i18n/locales/en'
import de from '@/i18n/locales/de'
import { useTeamsStore } from '@/stores/teams.store'
import type { Team } from '@/types/domain.types'

const _routerPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: _routerPush }),
}))

vi.mock('@/api/teams.api', () => ({
  listTeams: vi.fn().mockResolvedValue([]),
  getTeam: vi.fn(),
  createTeam: vi.fn(),
  updateTeam: vi.fn(),
  deleteTeam: vi.fn().mockResolvedValue(undefined),
}))

import * as teamsApi from '@/api/teams.api'

function createTestI18n(locale: 'de' | 'en' = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { de, en },
  })
}

function mountView(locale: 'de' | 'en' = 'en') {
  return mount(TeamListView, {
    global: {
      plugins: [createTestI18n(locale)],
      stubs: {
        BaseButton: {
          template:
            '<button v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
          props: ['loading', 'size', 'variant'],
          inheritAttrs: false,
        },
        BaseModal: {
          template:
            '<div class="modal"><slot /><div class="modal-footer"><slot name="footer" /></div></div>',
          props: ['title'],
        },
        BaseSpinner: {
          template: '<div class="spinner" />',
        },
      },
    },
    attachTo: document.body,
  })
}

const SAMPLE: Team[] = [
  {
    id: 1,
    name: 'Engineering',
    description: 'Backend + Frontend',
    external_id: null,
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
  },
  {
    id: 2,
    name: 'Quality Assurance',
    description: null,
    external_id: 'az://qa',
    created_at: '2026-04-05T00:00:00Z',
    updated_at: '2026-04-05T00:00:00Z',
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('TeamListView', () => {
  describe('empty state (AC2)', () => {
    it('renders empty-state with two CTAs when no teams exist', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce([])
      const wrapper = mountView()
      await flushPromises()

      const empty = wrapper.find('[data-testid="empty-state"]')
      expect(empty.exists()).toBe(true)
      expect(empty.text()).toContain('No teams yet')
      // Both CTAs present (order doesn't matter; both are primary CTAs).
      const buttons = empty.findAll('button').map((b) => b.text())
      expect(buttons.some((t) => t.includes('New Team'))).toBe(true)
      expect(buttons.some((t) => t.includes('Import from IdP groups'))).toBe(true)
    })

    it('clicking empty-state [+ New Team] navigates to /admin/teams/new', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce([])
      const wrapper = mountView()
      await flushPromises()

      const btn = wrapper
        .findAll('button')
        .find((b) => b.text().includes('New Team'))!
      await btn.trigger('click')

      expect(_routerPush).toHaveBeenCalledWith('/admin/teams/new')
    })
  })

  describe('populated table (AC3, AC4)', () => {
    it('renders one row per team', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce(SAMPLE)
      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.findAll('.team-row')).toHaveLength(2)
    })

    it('shows header actions above the table', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce(SAMPLE)
      const wrapper = mountView()
      await flushPromises()

      const toolbar = wrapper.find('.toolbar')
      expect(toolbar.exists()).toBe(true)
      const buttons = toolbar.findAll('button').map((b) => b.text())
      expect(buttons.some((t) => t.includes('New Team'))).toBe(true)
      expect(buttons.some((t) => t.includes('Import from IdP groups'))).toBe(
        true,
      )
    })
  })

  describe('search (AC5)', () => {
    it('filters rows on debounced input', async () => {
      vi.useFakeTimers()
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce(SAMPLE)
      const wrapper = mountView()
      await flushPromises()

      const input = wrapper.find('[data-testid="search-input"]')
      await input.setValue('quality')
      // Before debounce fires, both rows still visible.
      expect(wrapper.findAll('.team-row')).toHaveLength(2)
      await vi.advanceTimersByTimeAsync(350)
      expect(wrapper.findAll('.team-row')).toHaveLength(1)
      expect(wrapper.find('.team-row').text()).toContain('Quality')
    })
  })

  describe('sort (AC5)', () => {
    it('toggles sort direction when clicking the Name header', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce(SAMPLE)
      const wrapper = mountView()
      await flushPromises()

      const firstRow = () => wrapper.findAll('.team-row')[0].text()
      expect(firstRow()).toContain('Engineering') // default asc

      const nameHeader = wrapper
        .findAll('th.sortable')
        .find((t) => t.text().includes('Name'))!
      await nameHeader.trigger('click')
      expect(firstRow()).toContain('Quality') // flipped desc
    })
  })

  describe('delete flow (AC6)', () => {
    it('opens modal and on confirm calls the store remove', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce(SAMPLE)
      const wrapper = mountView()
      await flushPromises()

      const rowDeleteBtn = wrapper.findAll('[data-testid="row-delete"]')[0]
      await rowDeleteBtn.trigger('click')

      const modal = wrapper.find('.modal')
      expect(modal.exists()).toBe(true)
      // Confirm button is in the modal footer.
      const confirm = modal
        .findAll('button')
        .find((b) => b.text().includes('Delete'))!
      await confirm.trigger('click')
      await flushPromises()

      expect(teamsApi.deleteTeam).toHaveBeenCalledWith(1)
    })
  })

  describe('i18n (AC7)', () => {
    it('renders German heading when locale is de', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce([])
      const wrapper = mountView('de')
      await flushPromises()
      expect(wrapper.find('h1').text()).toBe('Teams')
      expect(wrapper.text()).toContain('Neues Team')
    })
  })

  describe('row edit (AC3)', () => {
    it('clicking View/Edit navigates to /admin/teams/:id', async () => {
      vi.mocked(teamsApi.listTeams).mockResolvedValueOnce(SAMPLE)
      const wrapper = mountView()
      await flushPromises()

      const editBtn = wrapper.findAll('[data-testid="row-edit"]')[0]
      await editBtn.trigger('click')
      expect(_routerPush).toHaveBeenCalledWith('/admin/teams/1')
    })
  })
})
