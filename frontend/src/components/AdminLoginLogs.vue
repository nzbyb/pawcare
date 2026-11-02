<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NInput,
  NPagination,
  NSelect,
  NSpin,
  type DataTableColumns,
} from 'naive-ui'

import { listLoginLogs } from '@/api/system'
import type { LoginLog } from '@/types'

const reasonLabels: Record<string, string> = {
  success: '登录成功',
  wrong_password: '密码错误',
  no_user: '账号不存在',
  locked: '账号锁定',
  disabled: '账号停用',
}
const roleLabels: Record<string, string> = {
  pet_owner: '宠物主',
  boarding_staff: '寄养员',
  admin: '管理员',
}
const resultOptions = [
  { label: '全部结果', value: 'all' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
]

const items = ref<LoginLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const keyword = ref('')
const resultFilter = ref('all')
const loading = ref(false)

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await listLoginLogs({
      keyword: keyword.value.trim() || undefined,
      success:
        resultFilter.value === 'all' ? undefined : resultFilter.value === 'success',
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

const columns: DataTableColumns<LoginLog> = [
  {
    title: '时间',
    key: 'create_time',
    width: 132,
    render: (row) => formatDateTime(row.create_time),
  },
  {
    title: '账号',
    key: 'username',
    minWidth: 150,
    render: (row) =>
      h('div', { style: 'display:flex;flex-direction:column;gap:2px' }, [
        h('strong', { style: 'font-size:12.5px' }, row.nickname || row.username),
        h(
          'span',
          { style: 'color:var(--pc-ink-soft);font-size:11px' },
          `${row.username}${row.role ? ` · ${roleLabels[row.role] ?? row.role}` : ''}`,
        ),
      ]),
  },
  {
    title: '结果',
    key: 'success',
    width: 96,
    render: (row) =>
      h(
        'span',
        { class: row.success ? 'pill sage' : 'pill amber' },
        row.success ? '成功' : '失败',
      ),
  },
  {
    title: '原因',
    key: 'reason',
    width: 100,
    render: (row) => reasonLabels[row.reason] ?? row.reason,
  },
  {
    title: 'IP',
    key: 'ip',
    width: 120,
    render: (row) => row.ip || '—',
  },
  {
    title: '设备',
    key: 'user_agent',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => row.user_agent || '—',
  },
]

onMounted(load)
</script>

<template>
  <section class="admin-block">
    <header class="block-head">
      <div>
        <h2 class="section-title">登录日志</h2>
        <p class="muted">
          记录每次登录尝试，包括账号不存在、密码错误与被禁用账号；只读，不参与鉴权。
        </p>
      </div>
    </header>

    <div class="toolbar">
      <n-input
        v-model:value="keyword"
        placeholder="搜索账号或 IP"
        clearable
        style="width: 220px"
        @keyup.enter="search"
      />
      <n-select
        v-model:value="resultFilter"
        :options="resultOptions"
        style="width: 140px"
        @update:value="search"
      />
      <n-button @click="search">查询</n-button>
    </div>

    <n-spin :show="loading">
      <!-- scroll-x：列宽合计 798px，窄屏时表格内部横向滚动 -->
      <n-data-table
        :columns="columns"
        :data="items"
        :row-key="(row: LoginLog) => row.id"
        :pagination="false"
        :scroll-x="800"
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
  </section>
</template>

<style scoped>
.admin-block {
  display: grid;
  /* 表格 scroll-x 会撑出 800+ 的 min-content，不限住网格轨道的话整块会被撑宽，
     标题和工具栏跟着跑到屏幕外，看起来就是"不能左右滑动"。 */
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}
.block-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.pager { display: flex; justify-content: flex-end; }
.muted { color: var(--pc-ink-soft); font-size: 12px; line-height: 1.7; }
</style>
