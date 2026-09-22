import { api, setToken, clearToken } from './client'

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: string
  email: string
  role: string
}

export interface MeResponse {
  user_id: string
  email: string
  role: string
  is_active: boolean
}

export const authApi = {
  login: (email: string, password: string) =>
    api.post<LoginResponse>('/auth/login', { email, password }),

  me: () => api.get<MeResponse>('/users/me'),

  logout: () => {
    clearToken()
  },

  googleAuthUrl: () =>
    api.get<{ url: string }>('/auth/google'),

  samlMetadata: () =>
    fetch('/api/v1/auth/saml/metadata').then(r => r.text()),
}

export async function loginAndStore(email: string, password: string): Promise<LoginResponse> {
  const result = await authApi.login(email, password)
  setToken(result.access_token)
  return result
}
