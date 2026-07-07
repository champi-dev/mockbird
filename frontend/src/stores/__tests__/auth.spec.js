import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'
import { useAuthStore } from '../auth'

vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
    create: () => ({
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
      post: vi.fn(),
    }),
  },
}))

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('starts unauthenticated', () => {
    expect(useAuthStore().isAuthenticated).toBe(false)
  })

  it('login stores tokens and username', async () => {
    axios.post.mockResolvedValue({
      data: { access: 'A', refresh: 'R' },
    })
    const store = useAuthStore()
    await store.login('alice', 'pw')
    expect(store.isAuthenticated).toBe(true)
    expect(localStorage.getItem('access')).toBe('A')
    expect(localStorage.getItem('refresh')).toBe('R')
    expect(store.username).toBe('alice')
  })

  it('logout clears everything', async () => {
    axios.post.mockResolvedValue({
      data: { access: 'A', refresh: 'R' },
    })
    const store = useAuthStore()
    await store.login('alice', 'pw')
    store.logout()
    expect(store.isAuthenticated).toBe(false)
    expect(localStorage.getItem('access')).toBeNull()
  })
})
