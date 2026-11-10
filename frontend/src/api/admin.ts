import { request } from './http'
import type {
  AdminOverview,
  AgentOverview,
  AgentToolCallPage,
  AgentTrace,
  AdminUserPage,
  AuditLogPage,
  KennelOccupancy,
  KnowledgeCreatePayload,
  KnowledgeDocumentDetail,
  KnowledgeDocumentPayload,
  KnowledgeHitTest,
  KnowledgePage,
  KnowledgeStatus,
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

export interface KnowledgeQuery {
  keyword?: string
  category?: string
  status?: KnowledgeStatus
  page?: number
  page_size?: number
}

export function listKnowledge(params: KnowledgeQuery): Promise<KnowledgePage> {
  return request.get<KnowledgePage>('/admin/knowledge', { params })
}

export function getKnowledgeCategories(): Promise<string[]> {
  return request.get<string[]>('/admin/knowledge/categories')
}

export function getKnowledge(
  docId: string,
): Promise<KnowledgeDocumentDetail> {
  return request.get<KnowledgeDocumentDetail>(`/admin/knowledge/${docId}`)
}

export function createKnowledge(
  payload: KnowledgeCreatePayload,
): Promise<{ doc_id: string; chunk_count: number }> {
  return request.post('/admin/knowledge', payload)
}

export function updateKnowledge(
  docId: string,
  payload: KnowledgeDocumentPayload,
): Promise<{ doc_id: string; chunk_count: number }> {
  return request.put(`/admin/knowledge/${docId}`, payload)
}

export function updateKnowledgeStatus(
  docId: string,
  status: KnowledgeStatus,
): Promise<{ doc_id: string; status: KnowledgeStatus }> {
  return request.put(`/admin/knowledge/${docId}/status`, { status })
}

export function reindexKnowledge(
  docId: string,
): Promise<{
  doc_id: string
  chunk_count: number
  embedded: number
  mode: string
  error?: string | null
}> {
  return request.post(`/admin/knowledge/${docId}/reindex`)
}

export function deleteKnowledge(docId: string): Promise<null> {
  return request.delete(`/admin/knowledge/${docId}`)
}

export function hitTestKnowledge(payload: {
  query: string
  top_k?: number
  category?: string
}): Promise<KnowledgeHitTest> {
  return request.post<KnowledgeHitTest>('/admin/knowledge/test', payload)
}

export interface AgentToolCallQuery {
  status?: 'ok' | 'error'
  tool_name?: string
  keyword?: string
  days?: number
  page?: number
  page_size?: number
}

export function getAgentOverview(days: number): Promise<AgentOverview> {
  return request.get<AgentOverview>('/admin/agent/overview', { params: { days } })
}

export function listAgentToolCalls(
  params: AgentToolCallQuery,
): Promise<AgentToolCallPage> {
  return request.get<AgentToolCallPage>('/admin/agent/tool-calls', { params })
}

export function getAgentTrace(traceId: string): Promise<AgentTrace> {
  return request.get<AgentTrace>(`/admin/agent/traces/${traceId}`)
}
