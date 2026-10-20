import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getMe, login as loginApi, register as registerApi } from '@/api/auth'
import type { RegisterPayload } from '@/api/auth'
import type { User } from '@/types'
import {
  clearToken,
  getStoredUser,
  getToken,
  setStoredUser,
  setToken,
} from '@/utils/storage'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(getStoredUser())

  const isLoggedIn = computed(() => Boolean(token.value))
  const displayName = computed(
    () => user.value?.nickname || user.value?.username || '铲屎官',
  )
  const initial = computed(() => displayName.value.slice(0, 1).toUpperCase())

  async function login(username: string, password: string): Promise<void> {
    const result = await loginApi({ username, password })
    token.value = result.token
    user.value = result.user
    setToken(result.token)
    setStoredUser(result.user)
  }

  async function register(payload: RegisterPayload): Promise<void> {
    await registerApi(payload)
    await login(payload.username, payload.password)
  }

  async function refreshMe(): Promise<void> {
    if (!token.value) return
    try {
      const me = await getMe()
      user.value = me
      setStoredUser(me)
    } catch {
      logout()
    }
  }

  function logout(): void {
    token.value = null
    user.value = null
    clearToken()
  }

  return {
    token,
    user,
    isLoggedIn,
    displayName,
    initial,
    login,
    register,
    refreshMe,
    logout,
  }
})
