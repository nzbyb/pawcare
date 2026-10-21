import { request } from './http'
import type { NotificationPage } from '@/types'

export function listNotifications(limit = 10): Promise<NotificationPage> {
  return request.get<NotificationPage>('/notifications', {
    params: { limit },
    silent: true,
  })
}

export function getUnreadCount(): Promise<{ unread: number }> {
  return request.get<{ unread: number }>('/notifications/unread-count', {
    silent: true,
  })
}

export function markNotificationRead(id: number): Promise<{ unread: number }> {
  return request.post<{ unread: number }>(`/notifications/${id}/read`)
}

export function markAllNotificationsRead(): Promise<{ unread: number }> {
  return request.post<{ unread: number }>('/notifications/read-all')
}
