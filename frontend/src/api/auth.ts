import api from './index'

export interface User {
  id: string
  username: string
  email?: string
  created_at: string
}

export interface AuthResponse {
  user: User
  access_token: string
  token_type: string
}

export const authApi = {
  login(username: string, password: string) {
    return api.post<never, AuthResponse>('/auth/login', { username, password })
  },
  register(username: string, password: string, email?: string) {
    return api.post<never, AuthResponse>('/auth/register', { username, password, email })
  },
}
