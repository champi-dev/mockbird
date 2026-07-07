import { defineStore } from 'pinia'
import client from '../api/client'

export const useProjectsStore = defineStore('projects', {
  state: () => ({
    projects: [],
    loading: false,
  }),

  actions: {
    async fetchProjects() {
      this.loading = true
      try {
        const { data } = await client.get('/projects/')
        this.projects = data
      } finally {
        this.loading = false
      }
    },

    async createProject(name) {
      const { data } = await client.post('/projects/', { name })
      this.projects.unshift(data)
      return data
    },

    async deleteProject(id) {
      await client.delete(`/projects/${id}/`)
      this.projects = this.projects.filter((p) => p.id !== id)
    },
  },
})
