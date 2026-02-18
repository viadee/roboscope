import { config } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Global test setup
beforeEach(() => {
  setActivePinia(createPinia())
})

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}

Object.defineProperty(window, 'localStorage', { value: localStorageMock })
