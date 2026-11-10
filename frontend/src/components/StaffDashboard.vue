<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NCheckbox,
  NEmpty,
  NInput,
  NModal,
  NPagination,
  NSelect,
  NSpin,
  useMessage,
} from 'naive-ui'

import {
  claimAbnormalCase,
  getAbnormalCase,
  getBoardingTasks,
  listAbnormalCases,
  reopenAbnormalCase,
  resolveAbnormalCase,
} from '@/api/boarding'
import { useAuthStore } from '@/stores/auth'
import type {
  AbnormalCaseItem,
  AbnormalCasePage,
  AbnormalCaseStatus,
  BoardingTaskKey,
  BoardingTasks,
} from '@/types'
import { formatDate } from '@/utils/format'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()
const data = ref<BoardingTasks | null>(null)
const loading = ref(false)
const failed = ref(false)
const active = ref<BoardingTaskKey>('arrivals')
const groups: { key: BoardingTaskKey; label: string; hint: string; action: string }[] = [
  { key: 'pending', label: '待接单', hint: '核对需求并确认预约', action: '查看预约' },
  { key: 'arrivals', label: '待入住', hint: '含预约期间尚未入住的订单', action: '办理入住' },
  { key: 'departures', label: '待退房', hint: '含已经超过预约退房日的订单', action: '办理退房' },
  { key: 'missing_reports', label: '未填日报', hint: '今日在住宠物尚无日报', action: '填写日报' },
  { key: 'abnormal_reports', label: '异常日报', hint: '今日食欲、排便或精神状态异常', action: '处置异常' },
]
const current = computed(() => groups.find(item => item.key === active.value)!)
const tasks = computed(() => data.value?.[active.value] ?? [])

const casePage = ref<AbnormalCasePage | null>(null)
const caseItems = computed(() => casePage.value?.items ?? [])
const caseLoading = ref(false)
const caseStatus = ref<'all' | AbnormalCaseStatus>('all')
const casePageNum = ref(1)
const casePageSize = 8
const caseCounts = computed(() => casePage.value?.counts ?? { open: 0, processing: 0, resolved: 0, critical_open: 0 })
const caseFilterOptions = [
  { label: '全部状态', value: 'all' },
  { label: '待处置', value: 'open' },
  { label: '处理中', value: 'processing' },
  { label: '已处理', value: 'resolved' },
]
const isAdmin = computed(() => auth.user?.role === 'admin')

const resolveVisible = ref(false)
const resolveTarget = ref<AbnormalCaseItem | null>(null)
const submitting = ref(false)
const resolveForm = reactive({
  action_taken: '',
  vet_contacted: false,
  notify_owner: true,
})

const appetiteLabels: Record<string, string> = { good: '食欲好', normal: '食欲正常', poor: '食欲较差' }
const stoolLabels: Record<string, string> = { normal: '排便正常', soft: '便便偏软', diarrhea: '腹泻' }
const spiritLabels: Record<string, string> = { good: '精神好', normal: '精神一般', low: '精神低落' }
const statusLabels: Record<AbnormalCaseStatus, string> = {
  open: '待处置',
  processing: '处理中',
  resolved: '已处理',
}

function label(map: Record<string, string>, value?: string | null): string {
  return value ? map[value] ?? value : '—'
}

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    const firstLoad = data.value === null
    data.value = await getBoardingTasks()
    if (firstLoad || !data.value.counts[active.value]) {
      const priority: BoardingTaskKey[] = ['abnormal_reports', 'departures', 'missing_reports', 'arrivals', 'pending']
      active.value = priority.find(key => data.value!.counts[key] > 0) ?? 'arrivals'
    }
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
  await loadCases()
}

async function loadCases(): Promise<void> {
  caseLoading.value = true
  try {
    casePage.value = await listAbnormalCases({
      ...(caseStatus.value === 'all' ? {} : { status: caseStatus.value }),
      page: casePageNum.value,
      page_size: casePageSize,
    })
  } catch {
    message.error('处置单加载失败，请稍后重试')
  } finally {
    caseLoading.value = false
  }
}

function filterCases(value: string): void {
  caseStatus.value = value as 'all' | AbnormalCaseStatus
  casePageNum.value = 1
  loadCases()
}

function changePage(page: number): void {
  casePageNum.value = page
  loadCases()
}

function open(orderId: number): void {
  router.push({ path: '/boarding', query: {
    order: String(orderId),
    ...(active.value === 'missing_reports' || active.value === 'abnormal_reports' ? { reports: '1' } : {}),
  } })
}

async function openResolveById(caseId: number): Promise<void> {
  try {
    const item = await getAbnormalCase(caseId)
    openResolve(item)
  } catch {
    message.error('处置单不存在或已关闭')
  }
}

function openResolve(item: AbnormalCaseItem): void {
  resolveTarget.value = item
  resolveForm.action_taken = ''
  resolveForm.vet_contacted = item.vet_contacted
  resolveForm.notify_owner = true
  resolveVisible.value = true
}

async function claim(item: AbnormalCaseItem): Promise<void> {
  try {
    await claimAbnormalCase(item.id)
    message.success('已认领，请当天完成处置')
    await Promise.all([load(), loadCases()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '认领失败')
  }
}

async function submitResolve(): Promise<void> {
  const target = resolveTarget.value
  if (!target) return
  const action = resolveForm.action_taken.trim()
  if (action.length < 2) {
    message.warning('请填写至少两个字的处置措施')
    return
  }
  submitting.value = true
  try {
    await resolveAbnormalCase(target.id, {
      action_taken: action,
      vet_contacted: resolveForm.vet_contacted,
      notify_owner: resolveForm.notify_owner,
    })
    message.success(resolveForm.notify_owner ? '处置完成，已通知宠物主' : '处置完成')
    resolveVisible.value = false
    await Promise.all([load(), loadCases()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '处置失败')
  } finally {
    submitting.value = false
  }
}

async function reopen(item: AbnormalCaseItem): Promise<void> {
  try {
    await reopenAbnormalCase(item.id)
    message.success('处置单已重新打开')
    await Promise.all([load(), loadCases()])
  } catch (error) {
    message.error(error instanceof Error ? error.message : '操作失败')
  }
}

function canResolve(item: AbnormalCaseItem): boolean {
  if (item.status === 'resolved') return false
  return isAdmin.value || !item.handler_id || item.handler_id === auth.user?.id
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">今日寄养任务</h1>
        <p class="page-subtitle">{{ data?.date || '今天' }} · 含未来待接单、今日照护及逾期未退房任务。</p>
      </div>
      <div class="header-actions">
        <n-button v-if="isAdmin" @click="router.push('/admin')">运营管理</n-button>
        <n-button :loading="loading" @click="load">刷新任务</n-button>
      </div>
    </header>

    <n-spin :show="loading">
      <div v-if="failed" class="error-panel soft-card" role="alert">
        <p>任务加载失败，请重试。</p>
        <n-button @click="load">重新加载</n-button>
      </div>
      <template v-else>
        <div class="task-metrics" role="group" aria-label="选择任务类型">
          <button v-for="group in groups" :key="group.key" type="button" class="soft-card task-metric"
            :class="{ active: active === group.key, danger: group.key === 'abnormal_reports' && (data?.counts[group.key] ?? 0) > 0 }"
            :aria-pressed="active === group.key" @click="active = group.key">
            <span>{{ group.label }}</span>
            <strong>{{ data?.counts[group.key] ?? '—' }}</strong>
            <small>{{ group.hint }}</small>
          </button>
        </div>
        <section class="soft-card task-panel">
          <div class="task-panel-heading">
            <h2 class="section-title">{{ current.label }}</h2>
            <span class="muted">{{ current.hint }}</span>
          </div>
          <article v-for="task in tasks" :key="task.order_id" class="task-row">
            <div class="task-info">
              <strong>{{ task.pet_name }} <span class="pill">{{ task.kennel_code }}</span>
                <span v-if="task.severity" class="severity" :class="task.severity">
                  {{ task.severity === 'critical' ? '紧急' : '关注' }}
                </span>
                <span v-if="task.case_status" class="case-status" :class="task.case_status">
                  {{ statusLabels[task.case_status] }}
                </span>
              </strong>
              <p>订单 #{{ task.order_id }} · {{ task.start_date }} → {{ task.end_date }}</p>
              <p v-if="active === 'arrivals' && task.payment_status !== 'paid'" class="payment-note">待完成付款，付款后可办理入住</p>
              <p v-if="active === 'arrivals' && task.start_date < data!.date" class="payment-note">已超过预约入住日，请联系宠物主确认到店时间</p>
              <p v-if="active === 'departures' && task.end_date < data!.date" class="payment-note">已超过预约退房日，请尽快核对离店安排</p>
              <p v-if="task.abnormal_reasons.length" class="abnormal">{{ task.abnormal_reasons.join(' · ') }}<span v-if="task.handler_name"> · {{ task.handler_name }} 处理中</span></p>
            </div>
            <div class="task-actions">
              <n-button size="small" quaternary @click="router.push(`/pets/${task.pet_id}`)">健康档案</n-button>
              <n-button v-if="active === 'abnormal_reports' && task.case_id" size="small" type="primary" secondary
                @click="openResolveById(task.case_id)">
                {{ task.case_status === 'resolved' ? '查看处置' : '处置异常' }}
              </n-button>
              <n-button v-else size="small" type="primary" secondary @click="open(task.order_id)">{{ current.action }}</n-button>
            </div>
          </article>
          <n-empty v-if="!tasks.length && !loading" :description="`暂无${current.label}任务`" class="empty-tasks" />
        </section>
      </template>
    </n-spin>

    <section class="soft-card case-panel">
      <header class="case-heading">
        <div>
          <h2 class="section-title">异常处置</h2>
          <p class="muted">
            日报出现异常时自动建单，处置完成后可一键告知宠物主。
            <template v-if="casePage?.stats?.avg_resolve_minutes">
              · 近 30 天平均处置 {{ casePage.stats.avg_resolve_minutes }} 分钟
            </template>
          </p>
        </div>
        <n-select :value="caseStatus" :options="caseFilterOptions" style="width: 130px" size="small"
          @update:value="filterCases" />
      </header>

      <div class="case-summary">
        <span>待处置 <strong>{{ caseCounts.open }}</strong></span>
        <span>处理中 <strong>{{ caseCounts.processing }}</strong></span>
        <span>紧急未结 <strong :class="{ danger: caseCounts.critical_open > 0 }">{{ caseCounts.critical_open }}</strong></span>
        <span>已处理 <strong>{{ caseCounts.resolved }}</strong></span>
      </div>

      <n-spin :show="caseLoading">
        <article v-for="item in caseItems" :key="item.id" class="case-row" :class="{ critical: item.severity === 'critical' && item.status !== 'resolved' }">
          <div class="case-info">
            <strong>
              {{ item.pet_name || '宠物' }} <span class="pill">{{ item.kennel_code || '—' }}</span>
              <span class="severity" :class="item.severity">{{ item.severity_label }}</span>
              <span class="case-status" :class="item.status">{{ statusLabels[item.status] }}</span>
            </strong>
            <p>{{ formatDate(item.report_date) }} 日报 · {{ item.reason_labels.join('、') }} · 主人 {{ item.owner_name || '—' }}</p>
            <p class="report-line">
              食欲：{{ label(appetiteLabels, item.report.appetite) }} · 排便：{{ label(stoolLabels, item.report.stool) }} · 精神：{{ label(spiritLabels, item.report.spirit) }}
              <template v-if="item.report.note"> · 备注：{{ item.report.note }}</template>
            </p>
            <p v-if="item.status === 'resolved'" class="resolved-line">
              {{ formatDateTime(item.resolved_at) }} · {{ item.resolver_name || item.handler_name || '—' }} 处置：{{ item.action_taken }}
              <span v-if="item.vet_contacted" class="tag">已联系兽医</span>
              <span v-if="item.owner_notified" class="tag">已告知主人</span>
            </p>
            <p v-else-if="item.handler_name" class="muted">由 {{ item.handler_name }} 认领 · {{ formatDateTime(item.claimed_at) }}</p>
          </div>
          <div class="case-actions">
            <n-button size="small" quaternary @click="router.push(`/pets/${item.pet_id}`)">健康档案</n-button>
            <n-button v-if="item.status === 'open'" size="small" secondary @click="claim(item)">认领</n-button>
            <n-button v-if="canResolve(item)" size="small" type="primary" secondary @click="openResolve(item)">处置完成</n-button>
            <n-button v-if="isAdmin && item.status === 'resolved'" size="small" quaternary @click="reopen(item)">重新打开</n-button>
            <n-button size="small" quaternary @click="router.push({ path: '/boarding', query: { order: String(item.order_id), reports: '1' } })">查看订单</n-button>
          </div>
        </article>
        <n-empty v-if="!caseItems.length && !caseLoading" description="暂无处置单" class="empty-tasks" />
      </n-spin>

      <div v-if="(casePage?.total ?? 0) > casePageSize" class="case-pagination">
        <n-pagination :page="casePageNum" :page-size="casePageSize" :item-count="casePage?.total ?? 0" @update:page="changePage" />
      </div>
    </section>

    <n-modal :show="resolveVisible" preset="card" style="width: min(560px, 94vw)" title="处置异常日报"
      @update:show="resolveVisible = $event">
      <template v-if="resolveTarget">
        <p class="modal-summary">
          {{ resolveTarget.pet_name || '宠物' }} · {{ formatDate(resolveTarget.report_date) }} 日报 ·
          {{ resolveTarget.reason_labels.join('、') }}
        </p>
        <n-input v-model:value="resolveForm.action_taken" type="textarea" :rows="4" :maxlength="500" show-count
          placeholder="记录处置措施，例如：已加喂易消化湿粮，联系主人确认后观察排便" />
        <div class="modal-options">
          <n-checkbox v-model:checked="resolveForm.vet_contacted">已联系兽医</n-checkbox>
          <n-checkbox v-model:checked="resolveForm.notify_owner">把处置结果通知宠物主</n-checkbox>
        </div>
        <p v-if="resolveTarget.status === 'resolved'" class="muted">
          该处置单已完成：{{ resolveTarget.action_taken }}
        </p>
      </template>
      <div class="modal-actions">
        <n-button @click="resolveVisible = false">取消</n-button>
        <n-button type="primary" :loading="submitting" :disabled="resolveTarget?.status === 'resolved'"
          @click="submitResolve">
          完成处置
        </n-button>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.header-actions, .task-actions, .case-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.task-metrics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 22px; }
.task-metric { display: flex; min-width: 0; flex-direction: column; gap: 12px; padding: 18px; text-align: left; cursor: pointer; color: var(--pc-ink); }
.task-metric.active { border-color: var(--pc-primary); background: var(--pc-primary-soft); }
.task-metric:focus-visible { outline: 2px solid var(--pc-primary); outline-offset: 3px; }
.task-metric strong { font-size: 30px; line-height: 1; }
.task-metric.danger strong, .abnormal, .danger { color: var(--pc-danger); }
.task-metric small, .task-info p, .case-info p { color: var(--pc-ink-soft); font-size: 12px; line-height: 1.6; }
.task-panel, .case-panel { overflow: hidden; }
.task-panel-heading, .case-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 20px; border-bottom: 1px solid var(--pc-line); font-size: 12px; }
.case-heading { justify-content: space-between; }
.task-row, .case-row { display: flex; justify-content: space-between; align-items: center; gap: 18px; padding: 18px 20px; border-bottom: 1px solid var(--pc-line); }
.task-row:last-child, .case-row:last-child { border-bottom: 0; }
.case-panel { margin-top: 22px; }
.case-row.critical { border-left: 2px solid var(--pc-danger); }
.case-info { min-width: 0; overflow-wrap: anywhere; }
.case-info strong { font-size: 14px; }
.case-info .pill { margin-left: 6px; }
.case-info p { margin: 6px 0 0; }
.report-line { color: var(--pc-ink-soft); }
.resolved-line { color: var(--pc-ink); }
.task-info { min-width: 0; overflow-wrap: anywhere; }
.task-info strong { font-size: 14px; }
.task-info .pill { margin-left: 6px; }
.task-info p { margin: 6px 0 0; }
.task-info .payment-note { color: var(--pc-warn); }
.task-info .abnormal { color: var(--pc-danger); }
.severity, .case-status { display: inline-block; margin-left: 6px; padding: 1px 8px; border: 1px solid var(--pc-line); border-radius: 999px; font-size: 11px; font-weight: 500; }
.severity.warning { color: var(--pc-warn); border-color: var(--pc-warn); }
.severity.critical { color: var(--pc-danger); border-color: var(--pc-danger); }
.case-status.open { color: var(--pc-danger); border-color: var(--pc-danger); }
.case-status.processing { color: var(--pc-primary); border-color: var(--pc-primary); }
.case-status.resolved { color: var(--pc-ink-soft); }
.case-summary { display: flex; flex-wrap: wrap; gap: 20px; padding: 14px 20px; border-bottom: 1px solid var(--pc-line); font-size: 12px; color: var(--pc-ink-soft); }
.case-summary strong { font-size: 15px; color: var(--pc-ink); }
.case-summary .danger { color: var(--pc-danger); }
.case-pagination { display: flex; justify-content: flex-end; padding: 14px 20px; }
.tag { margin-left: 6px; padding: 1px 6px; border: 1px solid var(--pc-line); border-radius: 4px; font-size: 11px; }
.modal-summary { margin: 0 0 12px; color: var(--pc-ink-soft); font-size: 13px; }
.modal-options { display: flex; flex-wrap: wrap; gap: 18px; margin-top: 14px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.empty-tasks, .error-panel { padding: 40px 20px; text-align: center; }
@media (max-width: 1050px) { .task-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 650px) {
  .task-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .task-row, .case-row { flex-direction: column; align-items: flex-start; }
  .page-header { flex-direction: column; }
}
</style>
