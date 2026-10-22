<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NDatePicker,
  NEmpty,
  NInput,
  NPagination,
  NSelect,
  NSpin,
  NTabPane,
  NTabs,
  useDialog,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import {
  getAdminOverview,
  getKennelOccupancy,
  listAuditLogs,
  listKnowledge,
  listUsers,
  updateUserStatus,
} from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import type {
  AdminOverview,
  AdminUser,
  AuditLogItem,
  KennelOccupancy,
  KennelOccupancyItem,
  KnowledgeChunkItem,
  UserRole,
} from '@/types'

type TabName = 'overview' | 'users' | 'kennels' | 'audit' | 'knowledge'

const dialog = useDialog()
const message = useMessage()
const auth = useAuthStore()

const activeTab = ref<TabName>('overview')

const roleLabels: Record<string, string> = {
  pet_owner: '宠物主',
  boarding_staff: '寄养员',
  admin: '管理员',
}

const rolePill: Record<string, string> = {
  pet_owner: 'pill',
  boarding_staff: 'pill sage',
  admin: 'pill amber',
}

const roleOptions = [
  { label: '全部角色', value: 'all' },
  { label: '宠物主', value: 'pet_owner' },
  { label: '寄养员', value: 'boarding_staff' },
  { label: '管理员', value: 'admin' },
]

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '正常', value: 1 },
  { label: '已停用', value: 0 },
]

const sizeLabels: Record<string, string> = {
  small: '小型',
  medium: '中型',
  large: '大型',
}

const orderStatusLabels: Record<string, string> = {
  pending: '待确认',
  confirmed: '已确认',
  checked_in: '寄养中',
  boarding: '寄养中',
  checked_out: '已退房',
  completed: '已完成',
  cancelled: '已取消',
}

const actionLabels: Record<string, string> = {
  'kennel.create': '新增笼舍',
  'kennel.update': '修改笼舍',
  'boarding_draft.create': '生成预约草稿',
  'boarding_draft.confirm': '确认预约',
  'boarding_draft.cancel': '取消草稿',
  'boarding_order.confirm': '确认订单',
  'boarding_order.check_in': '办理入住',
  'boarding_order.check_out': '办理退房',
  'boarding_order.cancel': '取消订单',
  'boarding_report.create': '填写日报',
  'payment.create': '发起支付',
  'payment.paid': '支付完成',
  'user.enable': '启用账号',
  'user.disable': '停用账号',
}

const actionFilterOptions = [
  { label: '全部操作', value: 'all' },
  { label: '预约与草稿', value: 'boarding_draft.' },
  { label: '寄养订单', value: 'boarding_order.' },
  { label: '寄养日报', value: 'boarding_report.' },
  { label: '支付', value: 'payment.' },
  { label: '账号', value: 'user.' },
  { label: '笼舍', value: 'kennel.' },
]

function formatDate(value?: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(value))
}

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function formatMoney(value: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0,
  }).format(value)
}

/* ---------------------------- 用户管理 ---------------------------- */

const users = ref<AdminUser[]>([])
const userTotal = ref(0)
const userPage = ref(1)
const userPageSize = 10
const usersLoading = ref(false)
const keyword = ref('')
const roleFilter = ref<string | UserRole>('all')
const statusFilter = ref<string | number>('all')

async function loadUsers(): Promise<void> {
  usersLoading.value = true
  try {
    const page = await listUsers({
      keyword: keyword.value.trim() || undefined,
      role:
        roleFilter.value === 'all' ? undefined : (roleFilter.value as UserRole),
      status: statusFilter.value === 'all' ? undefined : Number(statusFilter.value),
      page: userPage.value,
      page_size: userPageSize,
    })
    users.value = page.items
    userTotal.value = page.total
  } catch {
    users.value = []
    userTotal.value = 0
  } finally {
    usersLoading.value = false
  }
}

function searchUsers(): void {
  userPage.value = 1
  void loadUsers()
}

function changeUserPage(page: number): void {
  userPage.value = page
  void loadUsers()
}

function toggleUser(row: AdminUser): void {
  const disable = row.status === 1
  dialog.warning({
    title: disable ? '停用账号' : '启用账号',
    content: disable
      ? `停用后 ${row.nickname} 会立即下线，且无法再次登录。`
      : `启用后 ${row.nickname} 可以重新登录。`,
    positiveText: disable ? '停用' : '启用',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await updateUserStatus(row.id, disable ? 0 : 1)
        message.success(disable ? '账号已停用' : '账号已启用')
        await loadUsers()
      } catch {
        // http 拦截器已经提示
      }
    },
  })
}

const userColumns: DataTableColumns<AdminUser> = [
  {
    title: '账号',
    key: 'username',
    minWidth: 160,
    render: (row) =>
      h('div', { style: 'display:flex;flex-direction:column;gap:2px' }, [
        h('strong', { style: 'font-size:13px' }, row.nickname),
        h('span', { class: 'muted', style: 'font-size:12px' }, `@${row.username}`),
      ]),
  },
  {
    title: '角色',
    key: 'role',
    width: 96,
    render: (row) =>
      h('span', { class: rolePill[row.role] ?? 'pill grey' }, roleLabels[row.role] ?? row.role),
  },
  {
    title: '联系方式',
    key: 'contact',
    minWidth: 180,
    render: (row) => row.phone || row.email || '—',
  },
  {
    title: '宠物 / 订单',
    key: 'counts',
    width: 110,
    render: (row) => `${row.pet_count} / ${row.order_count}`,
  },
  {
    title: '状态',
    key: 'status',
    width: 88,
    render: (row) =>
      h(
        'span',
        { class: row.status === 1 ? 'pill sage' : 'pill red' },
        row.status === 1 ? '正常' : '已停用',
      ),
  },
  {
    title: '注册时间',
    key: 'create_time',
    width: 120,
    render: (row) => formatDate(row.create_time),
  },
  {
    title: '操作',
    key: 'action',
    width: 90,
    render: (row) => {
      if (row.id === auth.user?.id) {
        return h('span', { class: 'muted', style: 'font-size:12px' }, '当前账号')
      }
      return h(
        NButton,
        {
          size: 'small',
          quaternary: true,
          type: row.status === 1 ? 'error' : 'primary',
          onClick: () => toggleUser(row),
        },
        { default: () => (row.status === 1 ? '停用' : '启用') },
      )
    },
  },
]

/* ---------------------------- 笼舍占用 ---------------------------- */

function todayString(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const date = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${date}`
}

const occupancyDay = ref(todayString())
const occupancy = ref<KennelOccupancy | null>(null)
const occupancyLoading = ref(false)

const occupancySummary = computed(
  () =>
    occupancy.value?.summary ?? {
      total: 0,
      occupied: 0,
      available: 0,
      blocked: 0,
    },
)

const occupancyCards = computed(() => occupancy.value?.items ?? [])

const displayStatusLabels: Record<string, string> = {
  occupied: '已占用',
  available: '空闲',
  cleaning: '清洁中',
  maintenance: '维护中',
}

const displayStatusPills: Record<string, string> = {
  occupied: 'pill amber',
  available: 'pill sage',
  cleaning: 'pill grey',
  maintenance: 'pill red',
}

function displayStatus(item: KennelOccupancyItem): string {
  return displayStatusLabels[item.display_status] ?? item.display_status
}

function displayStatusClass(item: KennelOccupancyItem): string {
  return displayStatusPills[item.display_status] ?? 'pill grey'
}

async function loadOccupancy(): Promise<void> {
  occupancyLoading.value = true
  try {
    occupancy.value = await getKennelOccupancy(occupancyDay.value || undefined)
  } catch {
    occupancy.value = null
  } finally {
    occupancyLoading.value = false
  }
}

/* ---------------------------- 审计日志 ---------------------------- */

const logs = ref<AuditLogItem[]>([])
const logTotal = ref(0)
const logPage = ref(1)
const logPageSize = 20
const logsLoading = ref(false)
const actionFilter = ref('all')

async function loadLogs(): Promise<void> {
  logsLoading.value = true
  try {
    const page = await listAuditLogs({
      action: actionFilter.value === 'all' ? undefined : actionFilter.value,
      page: logPage.value,
      page_size: logPageSize,
    })
    logs.value = page.items
    logTotal.value = page.total
  } catch {
    logs.value = []
    logTotal.value = 0
  } finally {
    logsLoading.value = false
  }
}

function searchLogs(): void {
  logPage.value = 1
  void loadLogs()
}

function changeLogPage(page: number): void {
  logPage.value = page
  void loadLogs()
}

function logDetail(row: AuditLogItem): string {
  const data = row.after_data ?? row.before_data
  if (!data) return '—'
  const parts = Object.entries(data)
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${value}`)
  return parts.join(' · ') || '—'
}

const logColumns: DataTableColumns<AuditLogItem> = [
  {
    title: '时间',
    key: 'create_time',
    width: 140,
    render: (row) => formatDateTime(row.create_time),
  },
  {
    title: '操作人',
    key: 'actor',
    width: 130,
    render: (row) =>
      h('div', { style: 'display:flex;flex-direction:column;gap:2px' }, [
        h('strong', { style: 'font-size:12.5px' }, row.actor_name),
        row.actor_username
          ? h('span', { class: 'muted', style: 'font-size:11.5px' }, `@${row.actor_username}`)
          : null,
      ]),
  },
  {
    title: '操作',
    key: 'action',
    width: 120,
    render: (row) => actionLabels[row.action] ?? row.action,
  },
  {
    title: '对象',
    key: 'target',
    width: 160,
    render: (row) =>
      row.target_id
        ? `${row.target_type} #${row.target_id}`
        : row.target_type,
  },
  {
    title: '变更摘要',
    key: 'detail',
    minWidth: 220,
    render: (row) =>
      h('span', { class: 'muted', style: 'font-size:12px' }, logDetail(row)),
  },
  {
    title: 'IP',
    key: 'ip',
    width: 120,
    render: (row) => row.ip || '—',
  },
]

/* ---------------------------- 运营概览 ---------------------------- */

const overview = ref<AdminOverview | null>(null)
const overviewLoading = ref(false)

async function loadOverview(): Promise<void> {
  overviewLoading.value = true
  try {
    overview.value = await getAdminOverview()
  } catch {
    // http 拦截器已经提示
  } finally {
    overviewLoading.value = false
  }
}

/* ---------------------------- 知识库 ---------------------------- */

const knowledgeItems = ref<KnowledgeChunkItem[]>([])
const knowledgeTotal = ref(0)
const knowledgePage = ref(1)
const knowledgePageSize = 10
const knowledgeKeyword = ref('')
const knowledgeLoading = ref(false)

const knowledgeColumns: DataTableColumns<KnowledgeChunkItem> = [
  {
    title: '标题',
    key: 'title',
    width: 190,
    render: (row) =>
      h(
        'div',
        { style: 'display:flex;min-width:0;flex-direction:column;line-height:1.35' },
        [
          h(
            'strong',
            {
              style:
                'overflow:hidden;font-size:12.5px;font-weight:600;text-overflow:ellipsis;white-space:nowrap',
            },
            row.title,
          ),
          h(
            'span',
            { style: 'color:var(--pc-ink-faint);font-size:10.5px' },
            row.doc_id,
          ),
        ],
      ),
  },
  {
    title: '分类',
    key: 'category',
    width: 92,
    render: (row) => row.category || '—',
  },
  {
    title: '来源',
    key: 'source',
    width: 130,
    render: (row) => row.source || '—',
  },
  {
    title: '切片',
    key: 'chunk_index',
    width: 64,
    render: (row) => `#${row.chunk_index + 1}`,
  },
  {
    title: '内容摘要',
    key: 'content',
    minWidth: 320,
    render: (row) =>
      h(
        'span',
        {
          title: row.content,
          style:
            'display:block;max-width:420px;overflow:hidden;color:var(--pc-ink-soft);font-size:12px;text-overflow:ellipsis;white-space:nowrap',
        },
        row.content,
      ),
  },
  {
    title: '向量',
    key: 'has_embedding',
    width: 72,
    render: (row) =>
      h(
        'span',
        { class: row.has_embedding ? 'pill sage' : 'pill grey' },
        row.has_embedding ? '已生成' : '待生成',
      ),
  },
]

async function loadKnowledge(): Promise<void> {
  knowledgeLoading.value = true
  try {
    const page = await listKnowledge({
      keyword: knowledgeKeyword.value.trim() || undefined,
      page: knowledgePage.value,
      page_size: knowledgePageSize,
    })
    knowledgeItems.value = page.items
    knowledgeTotal.value = page.total
  } catch {
    knowledgeItems.value = []
    knowledgeTotal.value = 0
  } finally {
    knowledgeLoading.value = false
  }
}

function searchKnowledge(): void {
  knowledgePage.value = 1
  void loadKnowledge()
}

function changeKnowledgePage(page: number): void {
  knowledgePage.value = page
  void loadKnowledge()
}

/* ---------------------------- 切换 ---------------------------- */

function onTabChange(name: string | number): void {
  if (name === 'overview') {
    void loadOverview()
  } else if (name === 'kennels') {
    void loadOccupancy()
  } else if (name === 'audit') {
    void loadLogs()
  } else if (name === 'knowledge') {
    void loadKnowledge()
  }
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">管理控制台</h1>
        <p class="page-subtitle">
          查看账号与笼舍状态，核对最近发生的关键业务操作。
        </p>
      </div>
    </div>

    <n-tabs
      v-model:value="activeTab"
      type="line"
      animated
      @update:value="onTabChange"
    >
      <n-tab-pane name="overview" tab="运营概览">
        <n-spin :show="overviewLoading">
          <template v-if="overview">
            <section class="overview-section">
              <header class="overview-head">
                <h2>账号与宠物</h2>
                <span>统计截至 {{ overview.date }}</span>
              </header>
              <div class="stat-row">
                <div class="stat">
                  <span>账号总数</span>
                  <strong>{{ overview.users.total }}</strong>
                </div>
                <div class="stat">
                  <span>正常账号</span>
                  <strong class="ok">{{ overview.users.active }}</strong>
                </div>
                <div class="stat">
                  <span>宠物主</span>
                  <strong>{{ overview.users.owners }}</strong>
                </div>
                <div class="stat">
                  <span>宠物档案</span>
                  <strong>{{ overview.pets.active }}</strong>
                </div>
              </div>
            </section>

            <section class="overview-section">
              <header class="overview-head">
                <h2>寄养与收入</h2>
                <span>寄养员 {{ overview.users.staff }} 人 · 管理员 {{ overview.users.admins }} 人</span>
              </header>
              <div class="stat-row">
                <div class="stat">
                  <span>订单总数</span>
                  <strong>{{ overview.orders.total }}</strong>
                </div>
                <div class="stat">
                  <span>进行中</span>
                  <strong class="warn">{{ overview.orders.active }}</strong>
                </div>
                <div class="stat">
                  <span>今日入住 / 退房</span>
                  <strong>
                    {{ overview.orders.today_check_in }} / {{ overview.orders.today_check_out }}
                  </strong>
                </div>
                <div class="stat">
                  <span>累计实收</span>
                  <strong>{{ formatMoney(overview.revenue.paid_total) }}</strong>
                </div>
              </div>
            </section>

            <section class="overview-section">
              <header class="overview-head">
                <h2>提醒与知识库</h2>
                <span>健康提醒 7 天内到期会推送到通知中心</span>
              </header>
              <div class="stat-row">
                <div class="stat">
                  <span>待处理提醒</span>
                  <strong class="warn">{{ overview.reminders.pending }}</strong>
                </div>
                <div class="stat">
                  <span>7 天内到期</span>
                  <strong>{{ overview.reminders.due_soon }}</strong>
                </div>
                <div class="stat">
                  <span>知识文档</span>
                  <strong>{{ overview.knowledge.documents }}</strong>
                </div>
                <div class="stat">
                  <span>知识切片</span>
                  <strong>{{ overview.knowledge.chunks }}</strong>
                </div>
              </div>
            </section>
          </template>
          <div v-else-if="!overviewLoading" class="empty-wrap soft-card">
            <n-empty description="暂时没有可展示的统计数据" />
          </div>
        </n-spin>
      </n-tab-pane>

      <n-tab-pane name="users" tab="用户管理">
        <div class="toolbar">
          <n-input
            v-model:value="keyword"
            placeholder="搜索账号 / 昵称 / 邮箱 / 手机号"
            clearable
            style="width: 280px"
            @keyup.enter="searchUsers"
            @clear="searchUsers"
          >
            <template #prefix><AppIcon name="search" :size="14" /></template>
          </n-input>
          <n-select
            v-model:value="roleFilter"
            :options="roleOptions"
            style="width: 128px"
            @update:value="searchUsers"
          />
          <n-select
            v-model:value="statusFilter"
            :options="statusOptions"
            style="width: 118px"
            @update:value="searchUsers"
          />
          <n-button quaternary @click="searchUsers">查询</n-button>
          <span class="toolbar-total">共 {{ userTotal }} 个账号</span>
        </div>

        <div class="table-card">
          <n-spin :show="usersLoading">
            <n-data-table
              :columns="userColumns"
              :data="users"
              :row-key="(row: AdminUser) => row.id"
              :bordered="false"
              :scroll-x="820"
              size="small"
            />
            <div v-if="!usersLoading && !users.length" class="empty-wrap">
              <n-empty description="没有匹配的账号" />
            </div>
          </n-spin>
        </div>

        <div class="pager">
          <n-pagination
            :page="userPage"
            :page-size="userPageSize"
            :item-count="userTotal"
            @update:page="changeUserPage"
          />
        </div>
      </n-tab-pane>

      <n-tab-pane name="kennels" tab="笼舍占用">
        <div class="toolbar">
          <span class="toolbar-label">查看日期</span>
          <n-date-picker
            v-model:formatted-value="occupancyDay"
            value-format="yyyy-MM-dd"
            type="date"
            :is-date-disabled="(ts: number) => ts < Date.now() - 86400000 * 30"
            style="width: 150px"
            @update:formatted-value="loadOccupancy"
          />
          <n-button quaternary @click="loadOccupancy">刷新</n-button>
        </div>

        <div class="stat-row">
          <div class="stat">
            <span>笼舍总数</span>
            <strong>{{ occupancySummary.total }}</strong>
          </div>
          <div class="stat">
            <span>已占用</span>
            <strong class="warn">{{ occupancySummary.occupied }}</strong>
          </div>
          <div class="stat">
            <span>空闲</span>
            <strong class="ok">{{ occupancySummary.available }}</strong>
          </div>
          <div class="stat">
            <span>清洁 / 维护</span>
            <strong>{{ occupancySummary.blocked }}</strong>
          </div>
        </div>

        <n-spin :show="occupancyLoading">
          <div v-if="occupancyCards.length" class="kennel-grid">
            <article
              v-for="item in occupancyCards"
              :key="item.id"
              class="kennel-card"
              :class="{ 'is-occupied': item.display_status === 'occupied' }"
            >
              <header class="kennel-head">
                <strong>{{ item.code }}</strong>
                <span :class="displayStatusClass(item)">{{ displayStatus(item) }}</span>
              </header>
              <p class="kennel-meta">
                {{ sizeLabels[item.size] ?? item.size }} · ¥{{ item.daily_price }} / 晚
              </p>

              <div v-if="item.occupancy" class="kennel-guest">
                <div class="guest-line">
                  <span class="guest-name">{{ item.occupancy.pet_name }}</span>
                  <span class="pill grey">
                    {{ orderStatusLabels[item.occupancy.order_status] ?? item.occupancy.order_status }}
                  </span>
                </div>
                <p class="guest-owner">
                  {{ item.occupancy.owner_name }}
                  <template v-if="item.occupancy.owner_phone">
                    · {{ item.occupancy.owner_phone }}
                  </template>
                </p>
                <p class="guest-stay">
                  {{ item.occupancy.start_date }} → {{ item.occupancy.end_date }}
                </p>
              </div>
              <p v-else class="kennel-empty">
                {{ item.display_status === 'maintenance' ? '维护中，暂停接单' : '当天没有入住安排' }}
              </p>
            </article>
          </div>
          <div v-else-if="!occupancyLoading" class="empty-wrap soft-card">
            <n-empty description="还没有笼舍数据" />
          </div>
        </n-spin>
      </n-tab-pane>

      <n-tab-pane name="audit" tab="审计日志">
        <div class="toolbar">
          <n-select
            v-model:value="actionFilter"
            :options="actionFilterOptions"
            style="width: 150px"
            @update:value="searchLogs"
          />
          <n-button quaternary @click="searchLogs">刷新</n-button>
          <span class="toolbar-total">只读 · 共 {{ logTotal }} 条</span>
        </div>

        <div class="table-card">
          <n-spin :show="logsLoading">
            <n-data-table
              :columns="logColumns"
              :data="logs"
              :row-key="(row: AuditLogItem) => row.id"
              :bordered="false"
              :scroll-x="900"
              size="small"
            />
            <div v-if="!logsLoading && !logs.length" class="empty-wrap">
              <n-empty description="这个分类还没有操作记录" />
            </div>
          </n-spin>
        </div>

        <div class="pager">
          <n-pagination
            :page="logPage"
            :page-size="logPageSize"
            :item-count="logTotal"
            @update:page="changeLogPage"
          />
        </div>
      </n-tab-pane>

      <n-tab-pane name="knowledge" tab="知识库">
        <div class="toolbar">
          <n-input
            v-model:value="knowledgeKeyword"
            placeholder="搜索标题 / 内容 / 文档 ID"
            clearable
            style="width: 280px"
            @keyup.enter="searchKnowledge"
            @clear="searchKnowledge"
          >
            <template #prefix><AppIcon name="search" :size="14" /></template>
          </n-input>
          <n-button quaternary @click="searchKnowledge">查询</n-button>
          <span class="toolbar-total">只读 · 共 {{ knowledgeTotal }} 个切片</span>
        </div>

        <div class="table-card">
          <n-spin :show="knowledgeLoading">
            <n-data-table
              :columns="knowledgeColumns"
              :data="knowledgeItems"
              :row-key="(row: KnowledgeChunkItem) => row.id"
              :bordered="false"
              :scroll-x="900"
              size="small"
            />
            <div v-if="!knowledgeLoading && !knowledgeItems.length" class="empty-wrap">
              <n-empty description="没有匹配的知识条目" />
            </div>
          </n-spin>
        </div>

        <div class="pager">
          <n-pagination
            :page="knowledgePage"
            :page-size="knowledgePageSize"
            :item-count="knowledgeTotal"
            @update:page="changeKnowledgePage"
          />
        </div>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.toolbar-label {
  color: var(--pc-ink-soft);
  font-size: 12.5px;
}

.toolbar-total {
  margin-left: auto;
  color: var(--pc-ink-faint);
  font-size: 12px;
}

.table-card {
  overflow: hidden;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.empty-wrap {
  display: grid;
  min-height: 220px;
  place-items: center;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 14px 0 4px;
}

.overview-section {
  margin-bottom: 18px;
}

.overview-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 9px;
}

.overview-head h2 {
  margin: 0;
  font-size: 13.5px;
  font-weight: 650;
}

.overview-head span {
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.stat {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.stat span {
  color: var(--pc-ink-soft);
  font-size: 12px;
}

.stat strong {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.stat strong.warn {
  color: var(--pc-accent);
}

.stat strong.ok {
  color: var(--pc-ok);
}

.kennel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 12px;
}

.kennel-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.kennel-card.is-occupied {
  border-color: var(--pc-line-strong);
  background: var(--pc-primary-soft);
}

.kennel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kennel-head strong {
  font-size: 14px;
  letter-spacing: 0.02em;
}

.kennel-meta {
  margin: 0;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.kennel-guest {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 2px;
  padding-top: 9px;
  border-top: 1px solid var(--pc-line);
}

.guest-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.guest-name {
  font-size: 13.5px;
  font-weight: 650;
}

.guest-owner,
.guest-stay {
  margin: 0;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.5;
}

.guest-stay {
  color: var(--pc-ink-faint);
  font-variant-numeric: tabular-nums;
}

.kennel-empty {
  margin: 2px 0 0;
  padding-top: 9px;
  border-top: 1px solid var(--pc-line);
  color: var(--pc-ink-faint);
  font-size: 12px;
}

@media (max-width: 760px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .toolbar-total {
    margin-left: 0;
  }
}
</style>
