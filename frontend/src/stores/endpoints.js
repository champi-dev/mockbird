import { defineStore } from 'pinia'
import client from '../api/client'

export const useEndpointsStore = defineStore('endpoints', {
  state: () => ({
    endpoints: [],
    logs: [],
    loading: false,
  }),

  actions: {
    async fetchEndpoints(projectId) {
      this.loading = true
      try {
        const { data } = await client.get(
          `/projects/${projectId}/endpoints/`,
        )
        this.endpoints = data
      } finally {
        this.loading = false
      }
    },

    async createEndpoint(projectId, payload) {
      const { data } = await client.post(
        `/projects/${projectId}/endpoints/`,
        payload,
      )
      this.endpoints.push(data)
      return data
    },

    async updateEndpoint(projectId, id, payload) {
      const { data } = await client.patch(
        `/projects/${projectId}/endpoints/${id}/`,
        payload,
      )
      const i = this.endpoints.findIndex((e) => e.id === id)
      if (i !== -1) this.endpoints[i] = data
      return data
    },

    async deleteEndpoint(projectId, id) {
      await client.delete(`/projects/${projectId}/endpoints/${id}/`)
      this.endpoints = this.endpoints.filter((e) => e.id !== id)
    },

    async fetchLogs(projectId) {
      const { data } = await client.get(`/projects/${projectId}/logs/`)
      this.logs = data
    },
  },
})
