import { request } from './http'
import type {
  AnnouncementDetail,
  AnnouncementItem,
  AnnouncementReadStats,
  Feedback,
  FeedbackPage,
} from '@/types'

export function listAnnouncements(limit = 20): Promise<{ items: AnnouncementItem[]; unread: number }> {
  return request.get('/announcements', { params: { limit } })
}

export function getAnnouncement(id: number): Promise<AnnouncementDetail> {
  return request.get(`/announcements/${id}`)
}

export function markAllAnnouncementsRead(): Promise<{ unread: number }> {
  return request.post('/announcements/read-all')
}

export function unreadAnnouncementCount(): Promise<{ unread: number }> {
  return request.get('/announcements/unread-count', { silent: true })
}

export interface AdminAnnouncementPayload {
  title: string
  category: string
  content: string
  audience: string
  status: string
  is_pinned: boolean
  attachment_url?: string | null
  publish_at?: string | null
  expire_at?: string | null
}

export interface AdminAnnouncementQuery {
  keyword?: string
  status?: string
  page?: number
  page_size?: number
}

export function listAdminAnnouncements(
  params: AdminAnnouncementQuery,
): Promise<{ items: AnnouncementDetail[]; total: number; page: number; page_size: number }> {
  return request.get('/admin/announcements', { params })
}

export function createAnnouncement(data: AdminAnnouncementPayload): Promise<{ id: number }> {
  return request.post('/admin/announcements', data)
}

export function updateAnnouncement(
  id: number,
  data: AdminAnnouncementPayload,
): Promise<{ id: number }> {
  return request.put(`/admin/announcements/${id}`, data)
}

export function deleteAnnouncement(id: number): Promise<void> {
  return request.delete(`/admin/announcements/${id}`)
}

export function announcementReadStats(id: number): Promise<AnnouncementReadStats> {
  return request.get(`/admin/announcements/${id}/reads`)
}

export function submitFeedback(data: {
  category: string
  content: string
  contact?: string | null
}): Promise<Feedback> {
  return request.post('/feedback', data)
}

export function listMyFeedback(): Promise<{ items: Feedback[] }> {
  return request.get('/feedback')
}

export function listFeedback(params: {
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}): Promise<FeedbackPage> {
  return request.get('/admin/feedbacks', { params })
}

export function replyFeedback(
  id: number,
  data: { status: string; reply?: string | null },
): Promise<{ id: number; status: string }> {
  return request.put(`/admin/feedbacks/${id}`, data)
}
