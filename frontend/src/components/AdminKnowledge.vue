<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPagination,
  NSelect,
  NSpin,
  useDialog,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import {
  createKnowledge,
  deleteKnowledge,
  getKnowledge,
  getKnowledgeCategories,
  hitTestKnowledge,
  listKnowledge,
  reindexKnowledge,
  updateKnowledge,
  updateKnowledgeStatus,
  type KnowledgeQuery,
} from '@/api/admin'
import type {
  KnowledgeDocumentItem,
  KnowledgeHitTest,
  KnowledgeStatus,
} from '@/types'

const dialog = useDialog()
const message = useMessage()

const categoryLabels: Record<string, string> = {
  boarding: '寄养',
  vaccine: '疫苗',
  deworm: '驱虫',
  nutrition: '营养',
  medication: '用药',
  emergency: '急症',
  senior: '老年',
  allergy: '过敏',
  cat: '猫咪',
}
const statusLabels: Record<KnowledgeStatus, string> = {
  published: '已发布',
  archived: '已归档',
}
const statusPill: Record<KnowledgeStatus, string> = {
  published: 'pill sage',
  archived: 'pill amber',
}

const categories = ref<string[]>([])
const categoryOptions = computed(() =>
  categories.value.map((value) => ({
    value,
    label: categoryLabels[value] ?? value,
  })),
)
const statusOptions = [
  { value: 'published', label: '已发布' },
  { value: 'archived', label: '已归档' },
]

const items = ref<KnowledgeDocumentItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const keyword = ref('')
const categoryFilter = ref<string | null>(null)
const statusFilter = ref<KnowledgeStatus | null>(null)
const loading = ref(false)

const showForm = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = reactive({
  doc_id: '',
  category: 'boarding',
  title: '',
  source: 'PawCare 护理知识库',
  content: '',
  status: 'published' as KnowledgeStatus,
})

const showHit = ref(false)
const hitLoading = ref(false)
const hitForm = reactive({
  query: '',
  category: null as string | null,
  top_k: 5,
})
const hitResult = ref<KnowledgeHitTest | null>(null)

const formTitle = computed(() => (editingId.value ? '编辑知识文档' : '新建知识文档'))

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

function categoryLabel(value?: string | null): string {
  if (!value) return '—'
  return categoryLabels[value] ?? value
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const params: KnowledgeQuery = {
      keyword: keyword.value.trim() || undefined,
      category: categoryFilter.value || undefined,
      status: statusFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    }
    const result = await listKnowledge(params)
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
    doc_id: '',
    category: categories.value[0] ?? 'boarding',
    title: '',
    source: 'PawCare 护理知识库',
    content: '',
    status: 'published',
  })
  showForm.value = true
}

async function openEdit(row: KnowledgeDocumentItem): Promise<void> {
  editingId.value = row.doc_id
  try {
    const detail = await getKnowledge(row.doc_id)
    Object.assign(form, {
      doc_id: detail.doc_id,
      category: detail.category,
      title: detail.title,
      source: detail.source,
      content: detail.content,
      status: detail.status,
    })
    showForm.value = true
  } catch {
    // 拦截器已提示
  }
}

async function save(): Promise<void> {
  if (form.title.trim().length < 2) {
    message.warning('标题至少 2 个字')
    return
  }
  if (form.content.trim().length < 10) {
    message.warning('正文至少 10 个字')
    return
  }
  const payload = {
    category: form.category,
    title: form.title.trim(),
    content: form.content.trim(),
    source: form.source.trim() || null,
  }
  saving.value = true
  try {
    if (editingId.value) {
      const result = await updateKnowledge(editingId.value, payload)
      message.success(`文档已更新，共 ${result.chunk_count} 片切片`)
    } else {
      const result = await createKnowledge({
        ...payload,
        doc_id: form.doc_id.trim() || null,
        status: form.status,
      })
      message.success(`文档已创建，共 ${result.chunk_count} 片切片`)
    }
    showForm.value = false
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function archive(row: KnowledgeDocumentItem): void {
  const next: KnowledgeStatus = row.status === 'archived' ? 'published' : 'archived'
  dialog.warning({
    title: next === 'archived' ? '归档文档' : '重新发布',
    content:
      next === 'archived'
        ? `归档后「${row.title}」不再参与助手检索和站内搜索，内容仍保留。`
        : `重新发布后「${row.title}」会立刻回到检索范围。`,
    positiveText: '确认',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await updateKnowledgeStatus(row.doc_id, next)
        message.success(next === 'archived' ? '文档已归档' : '文档已发布')
        await load()
      } catch {
        // 拦截器已提示
      }
    },
  })
}

function reindex(row: KnowledgeDocumentItem): void {
  dialog.info({
    title: '重建索引',
    content: `将按当前正文重新切片并生成向量：「${row.title}」。正文较长时需要几秒。`,
    positiveText: '开始',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        const result = await reindexKnowledge(row.doc_id)
        if (result.mode === 'hybrid') {
          message.success(`已重建 ${result.chunk_count} 片切片，生成 ${result.embedded} 条向量`)
        } else {
          message.warning(result.error || '切片已重建，向量未生成')
        }
        await load()
      } catch {
        // 拦截器已提示
      }
    },
  })
}

function remove(row: KnowledgeDocumentItem): void {
  dialog.warning({
    title: '删除文档',
    content: `确认删除「${row.title}」？切片和向量会一并删除，无法恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteKnowledge(row.doc_id)
        message.success('文档已删除')
        await load()
      } catch {
        // 拦截器已提示
      }
    },
  })
}

function openHitTest(): void {
  hitResult.value = null
  showHit.value = true
}

async function runHitTest(): Promise<void> {
  if (!hitForm.query.trim()) {
    message.warning('请输入测试问题')
    return
  }
  hitLoading.value = true
  try {
    hitResult.value = await hitTestKnowledge({
      query: hitForm.query.trim(),
      top_k: hitForm.top_k,
      category: hitForm.category || undefined,
    })
  } catch {
    hitResult.value = null
  } finally {
    hitLoading.value = false
  }
}

function scoreWidth(score: number): string {
  return `${Math.max(1, Math.min(100, Math.round(score * 100)))}%`
}

const columns: DataTableColumns<KnowledgeDocumentItem> = [
  {
    title: '文档',
    key: 'title',
    minWidth: 240,
    render: (row) =>
      h('div', { style: 'display:flex;flex-direction:column;gap:3px;min-width:0' }, [
        h('strong', { style: 'font-size:12.5px' }, row.title),
        h('span', { style: 'color:var(--pc-ink-faint);font-size:11px' }, row.doc_id),
      ]),
  },
  {
    title: '分类',
    key: 'category',
    width: 84,
    render: (row) => categoryLabel(row.category),
  },
  {
    title: '切片',
    key: 'chunk_count',
    width: 70,
    render: (row) => `${row.chunk_count} 片`,
  },
  {
    title: '向量',
    key: 'missing_embedding',
    width: 96,
    render: (row) =>
      h(
        'span',
        { class: row.missing_embedding ? 'pill amber' : 'pill sage' },
        row.missing_embedding ? `待生成 ${row.missing_embedding}` : '已生成',
      ),
  },
  {
    title: '索引',
    key: 'needs_reindex',
    width: 88,
    render: (row) =>
      h(
        'span',
        { class: row.needs_reindex ? 'pill amber' : 'pill grey' },
        row.needs_reindex ? '待重建' : '已同步',
      ),
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render: (row) => h('span', { class: statusPill[row.status] }, statusLabels[row.status]),
  },
  {
    title: '更新时间',
    key: 'update_time',
    width: 132,
    render: (row) => formatDateTime(row.update_time),
  },
  {
    title: '操作',
    key: 'actions',
    width: 224,
    render: (row) =>
      h('div', { style: 'display:flex;gap:2px;flex-wrap:wrap' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => void openEdit(row) },
          { default: () => '编辑' },
        ),
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => reindex(row) },
          { default: () => '重建' },
        ),
        h(
          NButton,
          { size: 'tiny', quaternary: true, onClick: () => archive(row) },
          { default: () => (row.status === 'archived' ? '发布' : '归档') },
        ),
        row.status === 'archived'
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'error', onClick: () => remove(row) },
              { default: () => '删除' },
            )
          : null,
      ]),
  },
]

onMounted(async () => {
  void load()
  try {
    categories.value = await getKnowledgeCategories()
  } catch {
    categories.value = Object.keys(categoryLabels)
  }
})
</script>

<template>
  <section class="admin-block">
    <header class="block-head">
      <div>
        <h2 class="section-title">护理知识库</h2>
        <p class="muted">
          文档是维护单位，切片是检索单位。改正文后旧切片作废、向量置空，
          可在这里重建索引或直接测试一句提问的命中情况。
        </p>
      </div>
      <div class="head-actions">
        <n-button @click="openHitTest">命中测试</n-button>
        <n-button type="primary" @click="openCreate">新建文档</n-button>
      </div>
    </header>

    <div class="toolbar">
      <n-input
        v-model:value="keyword"
        placeholder="搜索标题 / 正文 / 文档编号"
        clearable
        style="width: 260px"
        @keyup.enter="search"
        @clear="search"
      />
      <n-select
        v-model:value="categoryFilter"
        :options="categoryOptions"
        placeholder="全部分类"
        clearable
        style="width: 140px"
        @update:value="search"
      />
      <n-select
        v-model:value="statusFilter"
        :options="statusOptions"
        placeholder="全部状态"
        clearable
        style="width: 130px"
        @update:value="search"
      />
      <n-button @click="search">查询</n-button>
      <span class="toolbar-total">共 {{ total }} 篇文档</span>
    </div>

    <n-spin :show="loading">
      <!-- scroll-x：列宽合计约 1010px，窄屏时表格内部横向滚动 -->
      <n-data-table
        :columns="columns"
        :data="items"
        :row-key="(row: KnowledgeDocumentItem) => row.doc_id"
        :pagination="false"
        :scroll-x="1010"
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

    <n-modal
      v-model:show="showForm"
      preset="card"
      :title="formTitle"
      style="max-width: 720px"
    >
      <n-form label-placement="top">
        <div class="form-grid">
          <n-form-item label="文档编号">
            <n-input
              v-model:value="form.doc_id"
              :disabled="Boolean(editingId)"
              maxlength="100"
              placeholder="留空自动生成"
            />
          </n-form-item>
          <n-form-item label="分类">
            <n-select v-model:value="form.category" :options="categoryOptions" />
          </n-form-item>
          <n-form-item v-if="!editingId" label="状态">
            <n-select v-model:value="form.status" :options="statusOptions" />
          </n-form-item>
        </div>
        <n-form-item label="标题">
          <n-input v-model:value="form.title" maxlength="200" show-count placeholder="例如：寄养前准备清单" />
        </n-form-item>
        <n-form-item label="来源">
          <n-input v-model:value="form.source" maxlength="200" placeholder="PawCare 护理知识库" />
        </n-form-item>
        <n-form-item label="正文">
          <n-input
            v-model:value="form.content"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 16 }"
            maxlength="20000"
            show-count
            placeholder="按段落或句子书写，系统会按句末标点自动切片"
          />
        </n-form-item>
        <p class="hint">
          保存即按正文重建切片；正文有改动时向量会清空，需要点「重建」重新生成。
        </p>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="showHit"
      preset="card"
      title="命中测试"
      style="max-width: 720px"
    >
      <div class="hit-form">
        <n-input
          v-model:value="hitForm.query"
          placeholder="输入一句宠物主可能问的话，例如：猫换粮软便怎么办"
          @keyup.enter="runHitTest"
        />
        <n-select
          v-model:value="hitForm.category"
          :options="categoryOptions"
          placeholder="全部分类"
          clearable
          style="width: 130px"
        />
        <n-input-number
          v-model:value="hitForm.top_k"
          :min="1"
          :max="10"
          style="width: 92px"
        />
        <n-button type="primary" :loading="hitLoading" @click="runHitTest">测试</n-button>
      </div>

      <n-spin :show="hitLoading">
        <template v-if="hitResult">
          <div class="hit-meta">
            <span :class="hitResult.mode === 'hybrid' ? 'pill sage' : 'pill amber'">
              {{ hitResult.mode === 'hybrid' ? '向量 + 词法' : '仅词法' }}
            </span>
            <span>命中阈值 {{ hitResult.min_score.toFixed(2) }}</span>
            <span>耗时 {{ hitResult.elapsed_ms }} ms</span>
            <span>返回 {{ hitResult.results.length }} 条</span>
          </div>

          <p v-if="!hitResult.results.length" class="muted">
            没有召回任何切片，助手会按「没有检索到资料」处理。
          </p>

          <ul class="hit-list">
            <li v-for="item in hitResult.results" :key="item.chunk_id">
              <div class="hit-head">
                <strong>{{ item.title }}</strong>
                <span class="hit-doc">{{ item.doc_id }}</span>
                <span :class="item.passed ? 'pill sage' : 'pill grey'">
                  {{ item.passed ? '进入上下文' : '低于阈值' }}
                </span>
                <span class="hit-score">{{ item.score.toFixed(3) }}</span>
              </div>
              <div class="score-bar">
                <span :style="{ width: scoreWidth(item.score) }" />
              </div>
              <p class="hit-text">{{ item.content }}</p>
              <div class="hit-channels">
                <span>向量 {{ item.vector_score.toFixed(3) }}</span>
                <span>词法 {{ item.lexical_score.toFixed(3) }}</span>
              </div>
            </li>
          </ul>
        </template>
        <p v-else class="muted">输入问题后点「测试」，可以看到召回的切片和两条打分。</p>
      </n-spin>
    </n-modal>
  </section>
</template>

<style scoped>
.admin-block {
  display: grid;
  /* 表格 scroll-x 会撑出 1010 的 min-content，不限住网格轨道会把整块撑宽 */
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}
.block-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
}
.block-head .muted {
  margin: 0;
  max-width: 620px;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.6;
}
.head-actions {
  display: flex;
  gap: 8px;
}
.toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}
.toolbar-total {
  color: var(--pc-ink-faint);
  font-size: 12px;
}
.pager {
  display: flex;
  justify-content: flex-end;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 16px;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.hint {
  margin: 0;
  color: var(--pc-ink-faint);
  font-size: 12px;
}
.hit-form {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 14px;
}
.hit-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 12px;
  color: var(--pc-ink-soft);
  font-size: 12px;
}
.hit-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 420px;
  overflow: auto;
}
.hit-list li {
  padding: 12px 0;
  border-top: 1px solid var(--pc-line);
}
.hit-list li:first-child {
  border-top: none;
  padding-top: 0;
}
.hit-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.hit-head strong {
  font-size: 13px;
}
.hit-doc {
  color: var(--pc-ink-faint);
  font-size: 11px;
}
.hit-score {
  margin-left: auto;
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  font-weight: 600;
  color: var(--pc-primary);
}
.score-bar {
  height: 4px;
  margin: 8px 0;
  border: 1px solid var(--pc-line);
  border-radius: 2px;
  background: var(--pc-surface-muted);
  overflow: hidden;
}
.score-bar span {
  display: block;
  height: 100%;
  background: var(--pc-primary);
}
.hit-text {
  margin: 0 0 6px;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.6;
}
.hit-channels {
  display: flex;
  gap: 14px;
  color: var(--pc-ink-faint);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.muted {
  color: var(--pc-ink-soft);
  font-size: 12px;
}
@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .head-actions {
    width: 100%;
  }
}
</style>
