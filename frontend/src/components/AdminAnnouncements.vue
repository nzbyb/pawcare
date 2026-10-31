<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPagination,
  NSelect,
  NSpin,
  NSwitch,
  useDialog,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import {
  announcementReadStats,
  createAnnouncement,
  deleteAnnouncement,
  listAdminAnnouncements,
  updateAnnouncement,
  type AdminAnnouncementPayload,
} from '@/api/content'
import type { AnnouncementDetail, AnnouncementReadStats } from '@/types'

const dialog = useDialog()
const message = useMessage()

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
const statusLabels: Record<string, string> = {
  draft: '草稿',
  published: '已发布',
  archived: '已归档',
}
const statusPill: Record<string, string> = {
  draft: 'pill grey',
  published: 'pill sage',
  archived: 'pill amber',
}

const categoryOptions = Object.entries(categoryLabels).map(([value, label]) => ({ value, label }))
const audienceOptions = Object.entries(audienceLabels).map(([value, label]) => ({ value, label }))
const statusOptions = Object.entries(statusLabels).map(([value, label]) => ({ value, label }))

const items = ref<AnnouncementDetail[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const keyword = ref('')
const statusFilter = ref<string | null>(null)
const loading = ref(false)

const showForm = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  title: '',
  category: 'notice',
  audience: 'all',
  status: 'draft',
  is_pinned: false,
  attachment_url: '',
  content: '',
  expire: null as number | null,
})

const showReads = ref(false)
const readsLoading = ref(false)
const reads = ref<AnnouncementReadStats | null>(null)
const readsTitle = ref('')

const formTitle = computed(() => (editingId.value ? '编辑公告' : '新建公告'))

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await listAdminAnnouncements({
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

function openCreate(): void {
  editingId.value = null
  Object.assign(form, {
    title: '',
    category: 'notice',
    audience: 'all',
    status: 'draft',
    is_pinned: false,
    attachment_url: '',
    content: '',
    expire: null,
  })
  showForm.value = true
}

function openEdit(row: AnnouncementDetail): void {
  editingId.value = row.id
  Object.assign(form, {
    title: row.title,
    category: row.category,
    audience: row.audience,
    status: row.status,
    is_pinned: row.is_pinned,
    attachment_url: row.attachment_url ?? '',
    content: row.content,
    expire: row.expire_at ? new Date(row.expire_at).getTime() : null,
  })
  showForm.value = true
}

async function save(): Promise<void> {
  if (form.title.trim().length < 2) {
    message.warning('标题至少 2 个字')
    return
  }
  if (form.content.trim().length < 2) {
    message.warning('正文不能为空')
    return
  }
  const payload: AdminAnnouncementPayload = {
    title: form.title.trim(),
    category: form.category,
    audience: form.audience,
    status: form.status,
    is_pinned: form.is_pinned,
    attachment_url: form.attachment_url.trim() || null,
    content: form.content.trim(),
    expire_at: form.expire ? new Date(form.expire).toISOString() : null,
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateAnnouncement(editingId.value, payload)
      message.success('公告已更新')
    } else {
      await createAnnouncement(payload)
      message.success('公告已保存')
    }
    showForm.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function remove(row: AnnouncementDetail): void {
  dialog.warning({
    title: '删除公告',
    content: `确认删除「${row.title}」？已读记录会一并删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteAnnouncement(row.id)
        message.success('公告已删除')
        await load()
      } catch {
        // 拦截器已提示
      }
    },
  })
}

async function showReaders(row: AnnouncementDetail): Promise<void> {
  readsTitle.value = row.title
  reads.value = null
  showReads.value = true
  readsLoading.value = true
  try {
    reads.value = await announcementReadStats(row.id)
  } finally {
    readsLoading.value = false
  }
}

const columns: DataTableColumns<AnnouncementDetail> = [
  {
    title: '公告',
    key: 'title',
    minWidth: 260,
    render: (row) =>
      h('div', { style: 'display:flex;flex-direction:column;gap:3px;min-width:0' }, [
        h('div', { style: 'display:flex;align-items:center;gap:6px;flex-wrap:wrap' }, [
          row.is_pinned ? h('span', { class: 'pill sage' }, '置顶') : null,
          h('span', { class: 'pill' }, categoryLabels[row.category] ?? row.category),
          h('strong', { style: 'font-size:12.5px' }, row.title),
        ]),
        h(
          'span',
          { style: 'color:var(--pc-ink-faint);font-size:11px' },
          row.content.length > 40 ? `${row.content.slice(0, 40)}…` : row.content,
        ),
      ]),
  },
  {
    title: '推送对象',
    key: 'audience',
    width: 96,
    render: (row) => audienceLabels[row.audience] ?? row.audience,
  },
  {
    title: '状态',
    key: 'status',
    width: 82,
    render: (row) => h('span', { class: statusPill[row.status] }, statusLabels[row.status]),
  },
  {
    title: '上线时间',
    key: 'publish_at',
    width: 132,
    render: (row) => formatDateTime(row.publish_at),
  },
  {
    title: '已读',
    key: 'read_count',
    width: 70,
    render: (row) => `${row.read_count ?? 0} 人`,
  },
  {
    title: '操作',
    key: 'actions',
    width: 190,
    render: (row) =>
      h('div', { style: 'display:flex;gap:4px;flex-wrap:wrap' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => openEdit(row) },
          { default: () => '编辑' },
        ),
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => void showReaders(row) },
          { default: () => '已读' },
        ),
        row.status === 'published'
          ? h(
              NButton,
              {
                size: 'tiny',
                quaternary: true,
                onClick: async () => {
                  try {
                    await updateAnnouncement(row.id, {
                      title: row.title,
                      category: row.category,
                      audience: row.audience,
                      status: 'archived',
                      is_pinned: row.is_pinned,
                      attachment_url: row.attachment_url ?? null,
                      content: row.content,
                      expire_at: row.expire_at ?? null,
                    })
                    message.success('公告已归档')
                    await load()
                  } catch {
                    // 拦截器已提示
                  }
                },
              },
              { default: () => '归档' },
            )
          : h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'error', onClick: () => remove(row) },
              { default: () => '删除' },
            ),
      ]),
  },
]

onMounted(load)
</script>

<template>
  <section class="admin-block">
    <header class="block-head">
      <div>
        <h2 class="section-title">公告管理</h2>
        <p class="muted">发布后会按推送对象出现在对应角色的公告页，已读按用户去重统计。</p>
      </div>
      <n-button type="primary" @click="openCreate">新建公告</n-button>
    </header>

    <div class="toolbar">
      <n-input
        v-model:value="keyword"
        placeholder="搜索标题或正文"
        clearable
        style="width: 240px"
        @keyup.enter="search"
      />
      <n-select
        v-model:value="statusFilter"
        :options="statusOptions"
        placeholder="全部状态"
        clearable
        style="width: 140px"
        @update:value="search"
      />
      <n-button @click="search">查询</n-button>
    </div>

    <n-spin :show="loading">
      <n-data-table
        :columns="columns"
        :data="items"
        :row-key="(row: AnnouncementDetail) => row.id"
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

    <n-modal v-model:show="showForm" preset="card" :title="formTitle" style="max-width: 640px">
      <n-form label-placement="top">
        <n-form-item label="标题">
          <n-input v-model:value="form.title" maxlength="120" show-count placeholder="例如：国庆期间寄养预约须知" />
        </n-form-item>
        <div class="form-grid">
          <n-form-item label="分类">
            <n-select v-model:value="form.category" :options="categoryOptions" />
          </n-form-item>
          <n-form-item label="推送对象">
            <n-select v-model:value="form.audience" :options="audienceOptions" />
          </n-form-item>
          <n-form-item label="状态">
            <n-select v-model:value="form.status" :options="statusOptions" />
          </n-form-item>
        </div>
        <n-form-item label="正文">
          <n-input
            v-model:value="form.content"
            type="textarea"
            :autosize="{ minRows: 6, maxRows: 12 }"
            maxlength="5000"
            show-count
          />
        </n-form-item>
        <div class="form-grid">
          <n-form-item label="附件地址（选填）">
            <n-input v-model:value="form.attachment_url" maxlength="255" placeholder="https://" />
          </n-form-item>
          <n-form-item label="过期时间（选填）">
            <n-date-picker v-model:value="form.expire" type="datetime" clearable style="width: 100%" />
          </n-form-item>
        </div>
        <n-form-item label="置顶">
          <n-switch v-model:value="form.is_pinned" />
          <span class="muted switch-hint">置顶公告排在列表最前</span>
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="showReads" preset="card" :title="`已读统计 · ${readsTitle}`" style="max-width: 520px">
      <n-spin :show="readsLoading">
        <template v-if="reads">
          <div class="read-metrics">
            <div><span>可推送人数</span><strong>{{ reads.target }}</strong></div>
            <div><span>已读</span><strong>{{ reads.read }}</strong></div>
            <div><span>未读</span><strong>{{ reads.unread }}</strong></div>
          </div>
          <ul class="readers">
            <li v-for="reader in reads.readers" :key="reader.user_id">
              <span>{{ reader.nickname || reader.username }}</span>
              <span class="muted">{{ formatDateTime(reader.read_at) }}</span>
            </li>
          </ul>
          <p v-if="!reads.readers.length" class="muted">还没有人读过这条公告。</p>
        </template>
      </n-spin>
    </n-modal>
  </section>
</template>

<style scoped>
.admin-block { display: grid; gap: 16px; }
.block-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.pager { display: flex; justify-content: flex-end; }
.form-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 16px; }
.form-grid:last-of-type { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; }
.switch-hint { margin-left: 10px; font-size: 12px; }
.read-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.read-metrics div { display: flex; flex-direction: column; gap: 4px; }
.read-metrics span, .muted { color: var(--pc-ink-soft); font-size: 12px; }
.read-metrics strong { font-size: 20px; }
.readers { list-style: none; margin: 0; padding: 0; max-height: 260px; overflow: auto; }
.readers li { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px solid var(--pc-line); font-size: 12px; }
@media (max-width: 640px) {
  .form-grid, .form-grid:last-of-type { grid-template-columns: 1fr; }
}
</style>
