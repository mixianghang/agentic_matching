import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi, type User } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('accessToken'))
  const user = ref<User | null>(JSON.parse(localStorage.getItem('currentUser') || 'null'))

  async function login(username: string, password: string) {
    const res = await authApi.login(username, password)
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('accessToken', res.access_token)
    localStorage.setItem('currentUser', JSON.stringify(res.user))
  }

  async function register(username: string, password: string, email?: string) {
    const res = await authApi.register(username, password, email)
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('accessToken', res.access_token)
    localStorage.setItem('currentUser', JSON.stringify(res.user))
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('accessToken')
    localStorage.removeItem('currentUser')
  }

  return { token, user, login, register, logout }
})
