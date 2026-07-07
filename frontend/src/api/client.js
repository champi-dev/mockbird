import axios from 'axios'

export const API_BASE =
  import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

const client = axios.create({ baseURL: `${API_BASE}/api` })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const refresh = localStorage.getItem('refresh')
    if (error.response?.status === 401 && refresh && !original._retried) {
      original._retried = true
      try {
        const { data } = await axios.post(
          `${API_BASE}/api/auth/token/refresh/`,
          { refresh },
        )
        localStorage.setItem('access', data.access)
        return client(original)
      } catch {
        localStorage.removeItem('access')
        localStorage.removeItem('refresh')
      }
    }
    return Promise.reject(error)
  },
)

export default client
