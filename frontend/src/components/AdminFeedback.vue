<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPagination,
  NSelect,
  NSpin,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import { listFeedback, replyFeedback } from '@/api/content'
import type { Feedback } from '@/types'

const message = useMessage()

const categoryLabels: Record<string, string> = {
  bug: '功能异常',
  suggestion: '功能建议',
  service: '服务体验',
  other: '其他',
}
const statusLabels: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  resolved: '已解决',
  closed: '已关闭',
}
const statusPill: Record<string, string> = {
  pending: 'pill amber',
  processing: 'pill amber',
  resolved: 'pill sage',
  closed: 'pill grey',
}
const statusOptions = Object.entries(statusLabels).map(([value, label]) => ({ value, label }))

const items = ref<Feedback[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const keyword = ref('')
const statusFilter = ref<string | null>('pending')
const loading = ref(false)

const showReply = ref(false)
const saving = ref(false)
const current = ref<Feedback | null>(null)
const form = reactive({ status: 'processing', reply: '' })

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await listFeedback({
      keyword: keyword.value.trim() || undefined,
      status: statusFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    items.value = result.items
    total.value = result.total
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function search(): void {
  page.value = 1
  void load()
}

function openReply(row: Feedback): void {
  current.value = row
  form.status = row.status === 'pending' ? 'processing' : row.status
  form.reply = row.reply ?? ''
  showReply.value = true
}

async function save(): Promise<void> {
  if (!current.value) return
  saving.value = true
  try {
    await replyFeedback(current.value.id, {
      status: form.status,
      reply: form.reply.trim() || null,
    })
    message.success('反馈已更新，提交人会收到站内通知')
    showReply.value = false
    await load()
  } finally {
    saving.value = false
  }
}

const columns: DataTableColumns<Feedback> = [
  {
    title: '提交人',
    key: 'user',
    width: 130,
    render: (row) =>
      h('div', { style: 'display:flex;flex-direction:column;gap:2px' }, [
        h('strong', { style: 'font-size:12.5px' }, row.nickname || row.username || '—'),
        h('span', { class: 'muted', style: 'font-size:11px' }, formatDateTime(row.create_time)),
      ]),
  },
  {
    title: '类型',
    key: 'category',
    width: 92,
    render: (row) => categoryLabels[row.category] ?? row.category,
  },
  {
    title: '内容',
    key: 'content',
    minWidth: 300,
    render: (row) =>
      h(
        'div',
        { style: 'display:flex;flex-direction:column;gap:4px;min-width:0' },
        [
          h('span', { style: 'font-size:12px;line-height:1.6' }, row.content),
          row.reply
            ? h(
                'span',
                { style: 'color:var(--pc-ink-soft);font-size:11.5px;line-height:1.6' },
                `回复：${row.reply}`,
              )
            : null,
        ],
      ),
  },
  {
    title: '联系方式',
    key: 'contact',
    width: 120,
    render: (row) => row.contact || '—',
  },
  {
    title: '状态',
    key: 'status',
    width: 88,
    render: (row) => h('span', { class: statusPill[row.status] }, statusLabels[row.status]),
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (row) =>
      h(
        NButton,
        { size: 'tiny', quaternary: true, onClick: () => openReply(row) },
        { default: () => (row.status === 'pending' ? '处理' : '查看') },
      ),
  },
]

onMounted(load)
</script>

<template>
  <section class="admin-block">
    <header class="block-head">
      <div>
        <h2 class="section-title">意见反馈</h2>
        <p class="muted">回复后会向提交人发送站内通知；状态只能向前推进，不能退回待处理。</p>
      </div>
    </header>

    <div class="toolbar">
      <n-input
        v-model:value="keyword"
        placeholder="搜索内容或账号"
        clearable
        style="width: 240px"
        @keyup.enter="search"
      />
      <n-select
        v-model:value="statusFilter"
        :options="statusOptions"
        placeholder="全部状态"
        clearable
        style="width: 150px"
        @update:value="search"
      />
      <n-button @click="search">查询</n-button>
    </div>

    <n-spin :show="loading">
      <n-data-table
        :columns="columns"
        :data="items"
        :row-key="(row: Feedback) => row.id"
        :pagination="false"
        size="small"
      />
    </n-spin>

    <div class="pager">
      <n-pagination
        v-model:page="page"
        :page-size="pageSize"
        :item-count="total"
        @update:page="load"
      />
    </div>

    <n-modal v-model:show="showReply" preset="card" title="处理反馈" style="max-width: 560px">
      <template v-if="current">
        <div class="feedback-quote">
          <p class="muted">{{ current.nickname || current.username }} · {{ formatDateTime(current.create_time) }}</p>
          <p>{{ current.content }}</p>
          <p v-if="current.contact" class="muted">联系方式：{{ current.contact }}</p>
        </div>
        <n-form label-placement="top">
          <n-form-item label="状态">
            <n-select v-model:value="form.status" :options="statusOptions" style="width: 180px" />
          </n-form-item>
          <n-form-item label="回复内容">
            <n-input
              v-model:value="form.reply"
              type="textarea"
              :autosize="{ minRows: 4, maxRows: 8 }"
              maxlength="1000"
              show-count
              placeholder="说明处理结果；提交人会在站内通知里看到这段回复"
            />
          </n-form-item>
        </n-form>
      </template>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="showReply = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">提交</n-button>
        </div>
      </template>
    </n-modal>
  </section>
</template>

<style scoped>
.admin-block { display: grid; gap: 16px; }
.block-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.pager { display: flex; justify-content: flex-end; }
.muted { color: var(--pc-ink-soft); font-size: 12px; }
.feedback-quote {
  margin-bottom: 16px;
  padding: 14px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-primary-soft);
}
.feedback-quote p { margin: 0; font-size: 12.5px; line-height: 1.7; }
.feedback-quote p + p { margin-top: 6px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; }
</style>
