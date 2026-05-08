import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
})

// Request interceptor: attach JWT token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle 401 and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Skip token refresh/redirect for login requests — 401 means invalid credentials
    const isLoginRequest = originalRequest.url?.includes('/auth/login')

    // Already on /login: clear any stale token but DO NOT reload — a
    // reload from /login back to /login is the redirect loop the
    // singleton composables (e.g. useBypassStatus) can trigger when
    // they fire on the brief DefaultLayout render before the router
    // resolves to AuthLayout. Always check the current path before
    // forcing navigation from inside an interceptor.
    const onLoginPage =
      typeof window !== 'undefined' && window.location.pathname === '/login'

    if (error.response?.status === 401 && !originalRequest._retry && !isLoginRequest) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const response = await axios.post(
            `${apiClient.defaults.baseURL}/auth/refresh`,
            { refresh_token: refreshToken }
          )
          const { access_token, refresh_token } = response.data
          localStorage.setItem('access_token', access_token)
          localStorage.setItem('refresh_token', refresh_token)
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return apiClient(originalRequest)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          if (!onLoginPage) window.location.href = '/login'
        }
      } else {
        localStorage.removeItem('access_token')
        if (!onLoginPage) window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
