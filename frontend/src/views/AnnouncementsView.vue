<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NEmpty, NSpin, useMessage } from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import {
  getAnnouncement,
  listAnnouncements,
  markAllAnnouncementsRead,
} from '@/api/content'
import type { AnnouncementDetail, AnnouncementItem } from '@/types'

const message = useMessage()
const items = ref<AnnouncementItem[]>([])
const unread = ref(0)
const loading = ref(true)
const failed = ref(false)
const expandedId = ref<number | null>(null)
const details = ref<Record<number, AnnouncementDetail>>({})
const detailLoading = ref(false)
const marking = ref(false)

const categoryLabels: Record<string, string> = {
  notice: '通知',
  policy: '政策',
  activity: '活动',
}
const audienceLabels: Record<string, string> = {
  all: '全部成员',
  pet_owner: '宠物主',
  boarding_staff: '寄养员',
  admin: '管理员',
}

const hasUnread = computed(() => unread.value > 0)

function dateText(value?: string | null): string {
  if (!value) return ''
  return value.slice(0, 16).replace('T', ' ')
}

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const result = await listAnnouncements(30)
    items.value = result.items
    unread.value = result.unread
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function toggle(item: AnnouncementItem): Promise<void> {
  if (expandedId.value === item.id) {
    expandedId.value = null
    return
  }
  expandedId.value = item.id
  if (details.value[item.id]) return
  detailLoading.value = true
  try {
    const detail = await getAnnouncement(item.id)
    details.value = { ...details.value, [item.id]: detail }
    if (!item.is_read) {
      item.is_read = true
      unread.value = Math.max(0, unread.value - 1)
    }
  } catch {
    expandedId.value = null
  } finally {
    detailLoading.value = false
  }
}

async function markAll(): Promise<void> {
  marking.value = true
  try {
    await markAllAnnouncementsRead()
    items.value = items.value.map((item) => ({ ...item, is_read: true }))
    unread.value = 0
    message.success('已全部标记为已读')
  } finally {
    marking.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">公告</h1>
        <p class="page-subtitle">
          寄养须知、政策通知与活动信息，按你的角色推送
          <span v-if="hasUnread" class="pill amber">{{ unread }} 条未读</span>
        </p>
      </div>
      <div class="header-actions">
        <n-button :loading="loading" @click="load">刷新</n-button>
        <n-button v-if="hasUnread" type="primary" secondary :loading="marking" @click="markAll">
          全部标记已读
        </n-button>
      </div>
    </header>

    <n-spin :show="loading">
      <div v-if="failed" class="soft-card empty-panel" role="alert">
        <p>公告加载失败，请重试。</p>
        <n-button @click="load">重新加载</n-button>
      </div>
      <template v-else>
        <div v-if="items.length" class="notice-list">
          <article
            v-for="item in items"
            :key="item.id"
            class="soft-card notice-card"
            :class="{ unread: !item.is_read }"
          >
            <button type="button" class="notice-head" @click="toggle(item)">
              <span class="notice-title">
                <span v-if="!item.is_read" class="unread-dot" aria-label="未读" />
                <span v-if="item.is_pinned" class="pill sage">置顶</span>
                <span class="pill">{{ categoryLabels[item.category] ?? item.category }}</span>
                <strong>{{ item.title }}</strong>
              </span>
              <span class="notice-meta">
                <span>{{ audienceLabels[item.audience] ?? item.audience }}</span>
                <span class="dot">·</span>
                <span>{{ dateText(item.publish_at || item.create_time) }}</span>
                <AppIcon :name="expandedId === item.id ? 'chevronDown' : 'chevronRight'" :size="14" />
              </span>
            </button>
            <div v-if="expandedId === item.id" class="notice-body">
              <n-spin v-if="detailLoading && !details[item.id]" :show="true" />
              <template v-else-if="details[item.id]">
                <p class="notice-content">{{ details[item.id].content }}</p>
                <p v-if="details[item.id].attachment_url" class="notice-attach">
                  附件：<a :href="details[item.id].attachment_url!" target="_blank" rel="noopener">
                    下载附件
                  </a>
                </p>
                <p v-if="details[item.id].expire_at" class="muted">
                  有效期至 {{ dateText(details[item.id].expire_at) }}
                </p>
              </template>
            </div>
          </article>
        </div>
        <div v-else class="soft-card empty-panel">
          <n-empty description="暂无公告" />
        </div>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.header-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.notice-list { display: grid; gap: 12px; }
.notice-card { padding: 0; overflow: hidden; }
.notice-card.unread { border-color: var(--pc-primary); }
.notice-head {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px 18px;
  background: transparent;
  border: 0;
  cursor: pointer;
  text-align: left;
  color: var(--pc-ink);
  font: inherit;
}
.notice-head:focus-visible { outline: 2px solid var(--pc-primary); outline-offset: -2px; }
.notice-title { display: flex; align-items: center; gap: 8px; min-width: 0; flex-wrap: wrap; }
.notice-title strong { font-size: 14px; overflow-wrap: anywhere; }
.unread-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--pc-danger); flex: none; }
.notice-meta { display: flex; align-items: center; gap: 6px; color: var(--pc-ink-soft); font-size: 12px; white-space: nowrap; }
.notice-meta .dot { color: var(--pc-line-strong); }
.notice-body { padding: 0 18px 18px; border-top: 1px solid var(--pc-line); }
.notice-content { margin: 14px 0 0; font-size: 13px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }
.notice-attach { margin: 12px 0 0; font-size: 12px; }
.notice-attach a { color: var(--pc-primary); font-weight: 600; }
.empty-panel { padding: 40px; text-align: center; }
.muted { color: var(--pc-ink-soft); font-size: 12px; }
@media (max-width: 650px) {
  .notice-head { flex-direction: column; align-items: flex-start; }
  .notice-meta { white-space: normal; }
}
</style>
