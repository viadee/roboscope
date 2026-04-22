import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import TeamDetailView from '@/views/TeamDetailView.vue'
import en from '@/i18n/locales/en'
import de from '@/i18n/locales/de'
import type { GroupMapping, TeamDetail } from '@/types/domain.types'

let _routeParams: Record<string, string> = {}
const _routerPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: _routerPush }),
  useRoute: () => ({ params: _routeParams }),
}))

vi.mock('@/api/teams.api', () => ({
  listTeams: vi.fn().mockResolvedValue([]),
  getTeam: vi.fn(),
  createTeam: vi.fn(),
  updateTeam: vi.fn(),
  deleteTeam: vi.fn(),
  addMember: vi.fn(),
  removeMember: vi.fn(),
  listGroupMappings: vi.fn().mockResolvedValue([]),
  createGroupMapping: vi.fn(),
  deleteGroupMapping: vi.fn(),
  listAvailableGroups: vi.fn().mockResolvedValue([]),
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
  return mount(TeamDetailView, {
    global: {
      plugins: [createTestI18n(locale)],
      stubs: {
        BaseButton: {
          template:
            '<button v-bind="$attrs" @click="$emit(\'click\', $event)"><slot /></button>',
          props: ['loading', 'size', 'variant', 'type'],
          inheritAttrs: false,
        },
        BaseSpinner: { template: '<div class="spinner" />' },
      },
    },
    attachTo: document.body,
  })
}

const SAMPLE_DETAIL: TeamDetail = {
  id: 5,
  name: 'Engineering',
  description: 'Backend + Frontend',
  external_id: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
  members: [
    {
      id: 11,
      user_id: 101,
      email: 'alice@test.com',
      role: 'editor',
      source: 'manual',
    },
  ],
}

const SAMPLE_MAPPINGS: GroupMapping[] = [
  {
    id: 201,
    idp_id: 1,
    team_id: 5,
    group_claim_value: 'engineering',
    role: 'editor',
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  _routeParams = {}
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('TeamDetailView', () => {
  describe('create mode (AC2)', () => {
    it('renders the new-team form (no tabs) when id=new', async () => {
      _routeParams = { id: 'new' }
      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.find('[data-testid="new-team-name"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="tablist"]').exists()).toBe(false)
    })

    it('submits the form and navigates to /admin/teams/:id', async () => {
      _routeParams = { id: 'new' }
      vi.mocked(teamsApi.createTeam).mockResolvedValueOnce({
        id: 42,
        name: 'Rockets',
        description: null,
        external_id: null,
        created_at: '2026-04-22T00:00:00Z',
        updated_at: '2026-04-22T00:00:00Z',
      })
      const wrapper = mountView()
      await flushPromises()

      await wrapper.find('[data-testid="new-team-name"]').setValue('Rockets')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(teamsApi.createTeam).toHaveBeenCalledWith({
        name: 'Rockets',
        description: null,
      })
      expect(_routerPush).toHaveBeenCalledWith('/admin/teams/42')
    })
  })

  describe('detail mode (AC1, AC3, AC4)', () => {
    async function mountDetail() {
      _routeParams = { id: '5' }
      vi.mocked(teamsApi.getTeam).mockResolvedValueOnce(SAMPLE_DETAIL)
      vi.mocked(teamsApi.listGroupMappings).mockResolvedValueOnce(
        SAMPLE_MAPPINGS,
      )
      const wrapper = mountView()
      await flushPromises()
      return wrapper
    }

    it('renders three tabs', async () => {
      const wrapper = await mountDetail()
      expect(wrapper.find('[data-testid="tab-members"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="tab-mappings"]').exists()).toBe(true)
      expect(wrapper.find('[data-testid="tab-repos"]').exists()).toBe(true)
    })

    it('renders members list when present', async () => {
      const wrapper = await mountDetail()
      const list = wrapper.find('[data-testid="member-list"]')
      expect(list.exists()).toBe(true)
      expect(list.text()).toContain('alice@test.com')
    })

    it('add member calls the API and reloads', async () => {
      const wrapper = await mountDetail()
      vi.mocked(teamsApi.addMember).mockResolvedValueOnce({
        id: 12,
        user_id: 202,
        email: 'bob@test.com',
        role: 'viewer',
        source: 'manual',
      })
      // After add, loadDetail is called again → stub fresh return.
      vi.mocked(teamsApi.getTeam).mockResolvedValueOnce({
        ...SAMPLE_DETAIL,
        members: [
          ...SAMPLE_DETAIL.members,
          {
            id: 12,
            user_id: 202,
            email: 'bob@test.com',
            role: 'viewer',
            source: 'manual',
          },
        ],
      })
      vi.mocked(teamsApi.listGroupMappings).mockResolvedValueOnce(
        SAMPLE_MAPPINGS,
      )

      await wrapper
        .find('[data-testid="add-member-user-id"]')
        .setValue('202')
      await wrapper.find('[data-testid="add-member-role"]').setValue('viewer')
      await wrapper.findAll('form')[0].trigger('submit')
      await flushPromises()

      expect(teamsApi.addMember).toHaveBeenCalledWith(5, {
        user_id: 202,
        role: 'viewer',
      })
    })

    it('add member rejects invalid user id', async () => {
      const wrapper = await mountDetail()
      await wrapper
        .find('[data-testid="add-member-user-id"]')
        .setValue('0')
      await wrapper.findAll('form')[0].trigger('submit')
      await flushPromises()

      expect(teamsApi.addMember).not.toHaveBeenCalled()
      expect(wrapper.text()).toContain('valid user ID')
    })
  })

  describe('group mappings tab (AC5)', () => {
    async function mountAndSwitchToMappings() {
      _routeParams = { id: '5' }
      vi.mocked(teamsApi.getTeam).mockResolvedValueOnce(SAMPLE_DETAIL)
      vi.mocked(teamsApi.listGroupMappings).mockResolvedValueOnce(
        SAMPLE_MAPPINGS,
      )
      const wrapper = mountView()
      await flushPromises()
      await wrapper.find('[data-testid="tab-mappings"]').trigger('click')
      await flushPromises()
      return wrapper
    }

    it('renders mapping list', async () => {
      const wrapper = await mountAndSwitchToMappings()
      const list = wrapper.find('[data-testid="mapping-list"]')
      expect(list.exists()).toBe(true)
      expect(list.text()).toContain('engineering')
    })

    it('submits add-mapping form', async () => {
      const wrapper = await mountAndSwitchToMappings()
      vi.mocked(teamsApi.createGroupMapping).mockResolvedValueOnce({
        id: 202,
        idp_id: 1,
        team_id: 5,
        group_claim_value: 'qa',
        role: 'viewer',
      })

      await wrapper.find('[data-testid="mapping-idp-id"]').setValue('1')
      await wrapper.find('[data-testid="mapping-group"]').setValue('qa')
      await wrapper.find('[data-testid="mapping-role"]').setValue('viewer')
      // The mapping-tab form is the second form on the page (after member form).
      await wrapper.findAll('form')[1].trigger('submit')
      await flushPromises()

      expect(teamsApi.createGroupMapping).toHaveBeenCalledWith(5, {
        idp_id: 1,
        group_name: 'qa',
        role: 'viewer',
      })
    })

    it('surfaces duplicate error code with localized copy', async () => {
      const wrapper = await mountAndSwitchToMappings()
      vi.mocked(teamsApi.createGroupMapping).mockRejectedValueOnce({
        response: { data: { detail: 'group_mapping.duplicate' } },
      })

      await wrapper.find('[data-testid="mapping-idp-id"]').setValue('1')
      await wrapper.find('[data-testid="mapping-group"]').setValue('dup')
      await wrapper.findAll('form')[1].trigger('submit')
      await flushPromises()

      expect(wrapper.text()).toContain('already mapped')
    })
  })

  describe('keyboard navigation (AC7)', () => {
    it('Arrow Right moves from Members to Group Mappings', async () => {
      _routeParams = { id: '5' }
      vi.mocked(teamsApi.getTeam).mockResolvedValueOnce(SAMPLE_DETAIL)
      vi.mocked(teamsApi.listGroupMappings).mockResolvedValueOnce([])
      const wrapper = mountView()
      await flushPromises()

      const tablist = wrapper.find('[data-testid="tablist"]')
      await tablist.trigger('keydown', { key: 'ArrowRight' })

      const mappingsTab = wrapper.find('[data-testid="tab-mappings"]')
      expect(mappingsTab.attributes('aria-selected')).toBe('true')
    })
  })

  describe('i18n (AC8)', () => {
    it('renders German tab labels when locale is de', async () => {
      _routeParams = { id: '5' }
      vi.mocked(teamsApi.getTeam).mockResolvedValueOnce(SAMPLE_DETAIL)
      vi.mocked(teamsApi.listGroupMappings).mockResolvedValueOnce([])
      const wrapper = mountView('de')
      await flushPromises()
      expect(wrapper.find('[data-testid="tab-members"]').text()).toBe(
        'Mitglieder',
      )
    })
  })
})
