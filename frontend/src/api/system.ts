import { request } from '@/api/http'
import type {
  LoginLogPage,
  SearchResult,
  SystemSettingItem,
  SystemSettings,
} from '@/types'

export function getPublicSettings(): Promise<SystemSettings> {
  return request.get('/settings')
}

export function getAdminSettings(): Promise<SystemSettingItem[]> {
  return request.get('/admin/settings')
}

export function updateAdminSettings(
  items: { key: string; value: string }[],
): Promise<SystemSettingItem[]> {
  return request.put('/admin/settings', { items })
}

export interface LoginLogQuery {
  keyword?: string
  success?: boolean
  page?: number
  page_size?: number
}

export function listLoginLogs(params: LoginLogQuery = {}): Promise<LoginLogPage> {
  return request.get('/admin/login-logs', { params })
}

export function searchSite(q: string, limit = 5): Promise<SearchResult> {
  return request.get('/search', { params: { q, limit } })
}
