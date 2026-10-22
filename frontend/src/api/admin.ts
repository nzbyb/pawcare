import { request } from './http'
import type {
  AdminOverview,
  AdminUserPage,
  AuditLogPage,
  KennelOccupancy,
  KnowledgePage,
  UserRole,
} from '@/types'

export interface AdminUserQuery {
  keyword?: string
  role?: UserRole
  status?: number
  page?: number
  page_size?: number
}

export interface AuditLogQuery {
  action?: string
  page?: number
  page_size?: number
}

export function listUsers(params: AdminUserQuery): Promise<AdminUserPage> {
  return request.get<AdminUserPage>('/admin/users', { params })
}

export function updateUserStatus(
  userId: number,
  status: number,
): Promise<{ id: number; username: string; status: number }> {
  return request.put(`/admin/users/${userId}/status`, { status })
}

export function getKennelOccupancy(day?: string): Promise<KennelOccupancy> {
  return request.get<KennelOccupancy>('/admin/kennels/occupancy', {
    params: { day },
  })
}

export function listAuditLogs(params: AuditLogQuery): Promise<AuditLogPage> {
  return request.get<AuditLogPage>('/admin/audit-logs', { params })
}

export function getAdminOverview(): Promise<AdminOverview> {
  return request.get<AdminOverview>('/admin/overview')
}

export function listKnowledge(params: {
  keyword?: string
  page?: number
  page_size?: number
}): Promise<KnowledgePage> {
  return request.get<KnowledgePage>('/admin/knowledge', { params })
}
