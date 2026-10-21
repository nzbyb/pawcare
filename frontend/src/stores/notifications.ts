import { ref } from 'vue'
import { defineStore } from 'pinia'

import {
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/notifications'
import type { NotificationItem } from '@/types'

const POLL_INTERVAL = 60_000

export const useNotificationStore = defineStore('notifications', () => {
  const items = ref<NotificationItem[]>([])
  const unread = ref(0)
  const loading = ref(false)

  let pollTimer: number | null = null
  let visibilityBound = false
  let inFlight = false

  function onVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      void refreshUnread()
    }
  }

  async function fetchList(): Promise<void> {
    if (inFlight) return
    inFlight = true
    loading.value = true
    try {
      const page = await listNotifications()
      items.value = page.items
      unread.value = page.unread
    } catch {
      // 通知是辅助信息，拉取失败不打断当前操作。
    } finally {
      inFlight = false
      loading.value = false
    }
  }

  async function refreshUnread(): Promise<void> {
    if (document.visibilityState === 'hidden') return
    try {
      const result = await getUnreadCount()
      unread.value = result.unread
    } catch {
      // 静默失败，下一轮再试。
    }
  }

  async function markRead(id: number): Promise<void> {
    const item = items.value.find((entry) => entry.id === id)
    if (item?.is_read) return
    try {
      const result = await markNotificationRead(id)
      if (item) item.is_read = true
      unread.value = result.unread
    } catch {
      // 标记失败时保留未读状态，用户下次打开还会看到。
    }
  }

  async function markAllRead(): Promise<void> {
    if (unread.value === 0) return
    try {
      await markAllNotificationsRead()
      items.value.forEach((entry) => {
        entry.is_read = true
      })
      unread.value = 0
    } catch {
      // 同上，保持原状态。
    }
  }

  function ensurePolling(): void {
    if (pollTimer === null) {
      pollTimer = window.setInterval(() => {
        void refreshUnread()
      }, POLL_INTERVAL)
    }
    if (!visibilityBound) {
      document.addEventListener('visibilitychange', onVisibilityChange)
      visibilityBound = true
    }
  }

  function stopPolling(): void {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
    if (visibilityBound) {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      visibilityBound = false
    }
  }

  return {
    items,
    unread,
    loading,
    fetchList,
    refreshUnread,
    markRead,
    markAllRead,
    ensurePolling,
    stopPolling,
  }
})
