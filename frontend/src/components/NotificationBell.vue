<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppIcon from '@/components/AppIcon.vue'
import { useNotificationStore } from '@/stores/notifications'
import type { NotificationCategory, NotificationItem } from '@/types'

const router = useRouter()
const store = useNotificationStore()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const badgeText = computed(() => (store.unread > 99 ? '99+' : String(store.unread)))

const categoryIcons: Record<NotificationCategory, string> = {
  health: 'clock',
  order: 'clipboard',
  system: 'bell',
}

function iconFor(category: NotificationCategory): string {
  return categoryIcons[category] ?? 'bell'
}

function relativeTime(value?: string | null): string {
  if (!value) return ''
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return ''

  const diff = Date.now() - timestamp
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)} 天前`
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  }).format(timestamp)
}

function toggle(): void {
  open.value = !open.value
  if (open.value) {
    void store.fetchList()
  }
}

function close(): void {
  open.value = false
}

async function openItem(item: NotificationItem): Promise<void> {
  close()
  await store.markRead(item.id)
  if (item.link) {
    void router.push(item.link)
  }
}

function onDocumentClick(event: MouseEvent): void {
  if (!open.value) return
  if (rootRef.value?.contains(event.target as Node)) return
  close()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  void store.fetchList()
  store.ensurePolling()
  document.addEventListener('mousedown', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
  store.stopPolling()
})
</script>

<template>
  <div ref="rootRef" class="notice">
    <button
      class="bell-button"
      type="button"
      aria-label="通知"
      :aria-expanded="open"
      @click="toggle"
    >
      <AppIcon name="bell" :size="16" />
      <span v-if="store.unread > 0" class="badge">{{ badgeText }}</span>
    </button>

    <div v-if="open" class="panel" role="dialog" aria-label="通知中心">
      <div class="panel-head">
        <span class="panel-title">通知</span>
        <button
          v-if="store.unread > 0"
          class="read-all"
          type="button"
          @click="store.markAllRead()"
        >
          全部已读
        </button>
      </div>

      <div v-if="store.loading && store.items.length === 0" class="panel-empty">
        <span class="empty-text">加载中…</span>
      </div>

      <div v-else-if="store.items.length === 0" class="panel-empty">
        <AppIcon name="bell" :size="20" />
        <span class="empty-text">暂无通知</span>
        <span class="empty-hint">订单状态变化和健康提醒会出现在这里</span>
      </div>

      <ul v-else class="notice-list">
        <li v-for="item in store.items" :key="item.id">
          <button
            class="notice-item"
            :class="{ unread: !item.is_read }"
            type="button"
            @click="openItem(item)"
          >
            <span class="notice-icon" :class="item.category">
              <AppIcon :name="iconFor(item.category)" :size="14" />
            </span>
            <span class="notice-body">
              <span class="notice-title">{{ item.title }}</span>
              <span class="notice-text">{{ item.content }}</span>
              <span class="notice-time">{{ relativeTime(item.create_time) }}</span>
            </span>
            <span v-if="!item.is_read" class="unread-dot" aria-label="未读" />
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.notice {
  position: relative;
}

.bell-button {
  position: relative;
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid var(--pc-line-strong);
  border-radius: var(--pc-radius-sm);
  background: var(--pc-surface);
  color: var(--pc-ink-soft);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    color 0.15s ease,
    background 0.15s ease;
}

.bell-button:hover,
.bell-button[aria-expanded='true'] {
  border-color: var(--pc-primary);
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
}

.badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border: 1.5px solid var(--pc-surface);
  border-radius: 999px;
  background: var(--pc-accent);
  color: #fff;
  font-size: 9.5px;
  font-weight: 700;
  line-height: 13px;
  text-align: center;
}

.panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 60;
  width: min(340px, calc(100vw - 24px));
  border: 1px solid var(--pc-line-strong);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
  text-align: left;
}

.panel-head {
  display: flex;
  height: 42px;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  border-bottom: 1px solid var(--pc-line);
}

.panel-title {
  font-size: 13px;
  font-weight: 650;
}

.read-all {
  padding: 2px 0;
  border: 0;
  background: transparent;
  color: var(--pc-primary);
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
}

.read-all:hover {
  text-decoration: underline;
}

.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 34px 20px 36px;
  color: var(--pc-ink-faint);
}

.empty-text {
  font-size: 12.5px;
  font-weight: 550;
}

.empty-hint {
  font-size: 11px;
  text-align: center;
}

.notice-list {
  max-height: 380px;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.notice-list li + li {
  border-top: 1px solid var(--pc-line);
}

.notice-item {
  display: flex;
  width: 100%;
  gap: 10px;
  padding: 11px 14px;
  border: 0;
  background: transparent;
  color: inherit;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
}

.notice-item:hover {
  background: var(--pc-surface-muted);
}

.notice-item.unread {
  background: var(--pc-primary-soft);
}

.notice-item.unread:hover {
  background: #e2ece7;
}

.notice-icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  border-radius: var(--pc-radius-sm);
}

.notice-icon.health {
  background: var(--pc-ok-soft);
  color: var(--pc-ok);
}

.notice-icon.order {
  background: var(--pc-accent-soft);
  color: var(--pc-accent);
}

.notice-icon.system {
  background: var(--pc-surface-muted);
  color: var(--pc-ink-soft);
}

.notice-body {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.notice-title {
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1.4;
}

.notice-item.unread .notice-title {
  font-weight: 700;
}

.notice-text {
  display: -webkit-box;
  overflow: hidden;
  color: var(--pc-ink-soft);
  font-size: 11.5px;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.notice-time {
  margin-top: 1px;
  color: var(--pc-ink-faint);
  font-size: 10.5px;
}

.unread-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  margin-top: 5px;
  border-radius: 50%;
  background: var(--pc-accent);
}

@media (max-width: 900px) {
  .panel {
    position: fixed;
    top: 58px;
    right: 12px;
    left: 12px;
    width: auto;
  }

  .notice-list {
    max-height: calc(100vh - 160px);
  }
}
</style>
