import { request } from './http'
import type { LoginResult, User } from '@/types'

export interface RegisterPayload {
  username: string
  password: string
  nickname?: string
  phone?: string
}

export function login(payload: {
  username: string
  password: string
}): Promise<LoginResult> {
  return request.post<LoginResult>('/auth/login', payload)
}

export function register(payload: RegisterPayload): Promise<User> {
  return request.post<User>('/auth/register', payload)
}

export function getMe(): Promise<User> {
  return request.get<User>('/auth/me')
}

export function changePassword(payload: {
  old_password: string
  new_password: string
}): Promise<{ token: string }> {
  return request.put<{ token: string }>('/auth/password', payload)
}
