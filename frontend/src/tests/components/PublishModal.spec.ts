/**
 * Story REPO-1 — Vitest specs for the Save-to-repository modal.
 *
 * Covers:
 *   - happy-path publish
 *   - empty-tree empty state
 *   - 409 conflict path renders the recovery view
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'

vi.mock('@/api/repos.api', () => ({
  publishRepo: vi.fn(),
  pushRepo: vi.fn(),
  syncRepo: vi.fn(),
  getRepoStatus: vi.fn(async () => ({
    current_branch: 'main',
    ahead: 0, behind: 0,
    modified: [], staged: [], untracked: [], deleted: [],
    is_dirty: false,
  })),
}))

import PublishModal from '@/components/repos/PublishModal.vue'
import { publishRepo, pushRepo, syncRepo } from '@/api/repos.api'

const mockedPublish = publishRepo as unknown as ReturnType<typeof vi.fn>
const mockedPush = pushRepo as unknown as ReturnType<typeof vi.fn>
const mockedSync = syncRepo as unknown as ReturnType<typeof vi.fn>

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  pluralRules: {},
  // For tests we just route the keys through identity so we can assert
  // on stable strings.
  fallbackLocale: 'en',
  silentTranslationWarn: true,
  silentFallbackWarn: true,
  messages: {
    en: {
      common: { cancel: 'Cancel' },
      repos: {
        publish: {
          badgeLabel: 'Save {n} changes',
          badgeTitle: '{n} unsaved',
          title: 'Save changes',
          messageLabel: 'Message',
          messagePlaceholder: 'What did you change?',
          save: 'Save {n}',
          empty: 'Nothing to save',
          tagModified: 'modified',
          tagNew: 'new',
          tagDeleted: 'deleted',
          conflictHeader: 'Remote moved on',
          conflictBody: 'committed locally as {hash}',
          conflictHint: 'Pull and retry',
          pullAndRetry: 'Pull latest and retry',
          toastSaved: 'Saved {n} ({hash})',
          toastResolved: 'Resolved {hash}',
          toastError: 'Error: {detail}',
          toastResolveFailed: 'Resolve failed: {detail}',
        },
      },
    },
  },
})

const dirtyStatus = {
  current_branch: 'main',
  ahead: 0, behind: 0,
  modified: ['a.robot'],
  staged: [],
  untracked: ['b.robot'],
  deleted: [],
  is_dirty: true,
}

function mountModal(propsOverride: Record<string, unknown> = {}) {
  return mount(PublishModal, {
    props: {
      modelValue: true,
      repoId: 7,
      status: dirtyStatus,
      ...propsOverride,
    },
    global: {
      plugins: [createPinia(), i18n],
      stubs: {
        BaseModal: {
          name: 'BaseModal',
          props: ['modelValue', 'title', 'size'],
          template: '<div class="base-modal"><slot /><slot name="footer" /></div>',
        },
        BaseButton: {
          name: 'BaseButton',
          props: ['variant', 'loading', 'disabled'],
          template: '<button :disabled="disabled" v-bind="$attrs"><slot /></button>',
        },
      },
    },
  })
}

describe('PublishModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedPublish.mockReset()
    mockedPush.mockReset()
    mockedSync.mockReset()
  })

  it('lists every modified, untracked, and deleted path', () => {
    const w = mountModal({
      status: { ...dirtyStatus, deleted: ['old.robot'] },
    })
    const items = w.findAll('.publish-path')
    expect(items.map((i) => i.text())).toEqual(
      expect.arrayContaining([
        expect.stringContaining('a.robot'),
        expect.stringContaining('b.robot'),
        expect.stringContaining('old.robot'),
      ]),
    )
  })

  it('disables the submit button until a message is typed', async () => {
    const w = mountModal()
    const btn = w.get('[data-testid="publish-submit"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
    await w.get('[data-testid="publish-message"]').setValue('add tests')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('calls publishRepo with the trimmed message + checked paths', async () => {
    mockedPublish.mockResolvedValue({
      commit_hash: 'abc1234567', message: 'add tests',
      files: ['a.robot', 'b.robot'],
      pushed: true, conflict: false, remote_ref: 'origin/main',
    })
    const w = mountModal()
    await w.get('[data-testid="publish-message"]').setValue('  add tests  ')
    await w.get('[data-testid="publish-submit"]').trigger('click')
    await flushPromises()
    expect(mockedPublish).toHaveBeenCalledTimes(1)
    const [repoId, body] = mockedPublish.mock.calls[0]
    expect(repoId).toBe(7)
    expect(body.message).toBe('add tests')
    expect(body.paths).toEqual(expect.arrayContaining(['a.robot', 'b.robot']))
  })

  it('renders the empty state when there is nothing to publish', () => {
    const w = mountModal({
      status: {
        current_branch: 'main', ahead: 0, behind: 0,
        modified: [], staged: [], untracked: [], deleted: [],
        is_dirty: false,
      },
    })
    expect(w.find('.publish-empty').exists()).toBe(true)
    expect(w.find('.publish-paths').exists()).toBe(false)
  })

  it('switches to the conflict view on HTTP 409', async () => {
    mockedPublish.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: {
            commit_hash: 'def4567890',
            message: 'add tests',
            files: ['a.robot'],
            pushed: false,
            conflict: true,
            reason: 'updates were rejected because the tip of your current branch is behind',
          },
        },
      },
    })
    const w = mountModal()
    await w.get('[data-testid="publish-message"]').setValue('add tests')
    await w.get('[data-testid="publish-submit"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-testid="publish-conflict"]').exists()).toBe(true)
    expect(w.find('[data-testid="publish-form"]').exists()).toBe(false)
    // Conflict body interpolates the short hash.
    expect(w.find('.publish-conflict').text()).toContain('def4567')
    // Pull-and-retry button is shown.
    expect(w.find('[data-testid="publish-pull-retry"]').exists()).toBe(true)
  })

  it('pull-and-retry runs syncRepo + pushRepo and closes the modal on success', async () => {
    mockedPublish.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: {
            commit_hash: 'def4567890',
            message: 'add tests',
            files: ['a.robot'],
            pushed: false, conflict: true,
            reason: 'rejected',
          },
        },
      },
    })
    mockedSync.mockResolvedValue({ status: 'syncing', message: 'ok', task_id: 't1' })
    mockedPush.mockResolvedValue({ branch: 'main', remote_ref: 'origin/main', ahead_after: 0 })

    const w = mountModal()
    await w.get('[data-testid="publish-message"]').setValue('add tests')
    await w.get('[data-testid="publish-submit"]').trigger('click')
    await flushPromises()

    await w.get('[data-testid="publish-pull-retry"]').trigger('click')
    await flushPromises()

    expect(mockedSync).toHaveBeenCalledWith(7)
    expect(mockedPush).toHaveBeenCalledWith(7)
    // Modal asks the parent to close after success.
    const events = w.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events![events!.length - 1]).toEqual([false])
  })
})
