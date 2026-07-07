import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import client from '../../api/client'
import { useProjectsStore } from '../projects'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
  API_BASE: 'http://test',
}))

describe('projects store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('fetches projects', async () => {
    client.get.mockResolvedValue({ data: [{ id: 1, name: 'A' }] })
    const store = useProjectsStore()
    await store.fetchProjects()
    expect(store.projects).toHaveLength(1)
    expect(store.loading).toBe(false)
  })

  it('createProject prepends the new project', async () => {
    client.post.mockResolvedValue({ data: { id: 2, name: 'B' } })
    const store = useProjectsStore()
    store.projects = [{ id: 1, name: 'A' }]
    await store.createProject('B')
    expect(store.projects[0].name).toBe('B')
  })

  it('deleteProject removes it locally', async () => {
    client.delete.mockResolvedValue({})
    const store = useProjectsStore()
    store.projects = [{ id: 1 }, { id: 2 }]
    await store.deleteProject(1)
    expect(store.projects.map((p) => p.id)).toEqual([2])
  })
})
