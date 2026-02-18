import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import LoginView from '@/views/LoginView.vue'
import { useAuthStore } from '@/stores/auth.store'

// Mock vue-router
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  useRoute: () => ({
    query: {},
  }),
}))

// Mock auth API so the store doesn't make real calls
vi.mock('@/api/auth.api', () => ({
  login: vi.fn(),
  getMe: vi.fn(),
}))

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mountLoginView = () => {
    return mount(LoginView, {
      global: {
        stubs: {
          BaseButton: {
            template: '<button :disabled="$attrs.disabled || loading" @click="$emit(\'click\', $event)"><slot /></button>',
            props: ['loading', 'size', 'variant'],
          },
        },
      },
    })
  }

  describe('rendering', () => {
    it('renders login form with email input', () => {
      const wrapper = mountLoginView()
      const emailInput = wrapper.find('input[type="text"]')
      expect(emailInput.exists()).toBe(true)
      expect(emailInput.attributes('placeholder')).toBe('admin@mateox.local')
    })

    it('renders login form with password input', () => {
      const wrapper = mountLoginView()
      const passwordInput = wrapper.find('input[type="password"]')
      expect(passwordInput.exists()).toBe(true)
      expect(passwordInput.attributes('placeholder')).toBe('Passwort')
    })

    it('renders the submit button with Anmelden text', () => {
      const wrapper = mountLoginView()
      const button = wrapper.find('button')
      expect(button.exists()).toBe(true)
      expect(button.text()).toContain('Anmelden')
    })

    it('renders the heading', () => {
      const wrapper = mountLoginView()
      expect(wrapper.find('h2').text()).toBe('Anmelden')
    })
  })

  describe('error handling', () => {
    it('shows error message on failed login', async () => {
      const wrapper = mountLoginView()
      const auth = useAuthStore()

      // Make auth.login reject
      vi.spyOn(auth, 'login').mockRejectedValue({
        response: { data: { detail: 'Ungueltige Anmeldedaten' } },
      })

      await wrapper.find('input[type="text"]').setValue('bad@email.com')
      await wrapper.find('input[type="password"]').setValue('wrong')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.find('.error-text').exists()).toBe(true)
      expect(wrapper.find('.error-text').text()).toBe('Ungueltige Anmeldedaten')
    })

    it('shows default error message when no detail is returned', async () => {
      const wrapper = mountLoginView()
      const auth = useAuthStore()

      vi.spyOn(auth, 'login').mockRejectedValue(new Error('Network Error'))

      await wrapper.find('input[type="text"]').setValue('bad@email.com')
      await wrapper.find('input[type="password"]').setValue('wrong')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.find('.error-text').text()).toBe('Anmeldung fehlgeschlagen')
    })
  })

  describe('login flow', () => {
    it('calls auth store login with email and password on submit', async () => {
      const wrapper = mountLoginView()
      const auth = useAuthStore()

      vi.spyOn(auth, 'login').mockResolvedValue(undefined)

      await wrapper.find('input[type="text"]').setValue('admin@mateox.local')
      await wrapper.find('input[type="password"]').setValue('admin')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(auth.login).toHaveBeenCalledWith('admin@mateox.local', 'admin')
    })

    it('does not show error text before form submission', () => {
      const wrapper = mountLoginView()
      expect(wrapper.find('.error-text').exists()).toBe(false)
    })
  })
})
