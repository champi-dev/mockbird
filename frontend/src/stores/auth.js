import { defineStore } from 'pinia'
import axios from 'axios'
import client, { API_BASE } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    username: localStorage.getItem('username') || '',
    access: localStorage.getItem('access') || '',
  }),

  getters: {
    isAuthenticated: (state) => Boolean(state.access),
  },

  actions: {
    async login(username, password) {
      const { data } = await axios.post(`${API_BASE}/api/auth/token/`, {
        username,
        password,
      })
      this.access = data.access
      this.username = username
      localStorage.setItem('access', data.access)
      localStorage.setItem('refresh', data.refresh)
      localStorage.setItem('username', username)
    },

    async register(username, password) {
      await client.post('/auth/register/', { username, password })
      await this.login(username, password)
    },

    logout() {
      this.access = ''
      this.username = ''
      localStorage.removeItem('access')
      localStorage.removeItem('refresh')
      localStorage.removeItem('username')
    },
  },
})
