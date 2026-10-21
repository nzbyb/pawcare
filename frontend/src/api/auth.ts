import { request } from './http'
import type { LoginResult, User } from '@/types'

export type VerificationChannel = 'email' | 'phone'
export type VerificationScene = 'register' | 'reset'

export interface RegisterPayload {
  username: string
  password: string
  nickname?: string
  email?: string
  phone?: string
  code: string
}

export interface SendCodeResult {
  cooldown: number
  expires_in: number
  debug_code?: string
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

export function sendVerificationCode(payload: {
  channel: VerificationChannel
  target: string
  scene: VerificationScene
}): Promise<SendCodeResult> {
  return request.post<SendCodeResult>('/auth/verification-code', payload)
}

export function resetPassword(payload: {
  channel: VerificationChannel
  target: string
  code: string
  new_password: string
}): Promise<{ username: string }> {
  return request.post<{ username: string }>('/auth/password/reset', payload)
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

export interface ProfilePayload {
  nickname: string
  email?: string | null
  phone?: string | null
}

export interface NotificationPrefsPayload {
  notify_health: boolean
  notify_order: boolean
  notify_system: boolean
}

export function updateProfile(payload: ProfilePayload): Promise<User> {
  return request.put<User>('/auth/me', payload)
}

export function updateNotificationPrefs(
  payload: NotificationPrefsPayload,
): Promise<User> {
  return request.put<User>('/auth/notification-prefs', payload)
}
