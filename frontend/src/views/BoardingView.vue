<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  NButton,
  NDatePicker,
  NEmpty,
  NInput,
  NModal,
  NSelect,
  NSpin,
  NTag,
  useMessage,
} from 'naive-ui'

import {
  cancelDraft as cancelDraftApi,
  cancelOrder as cancelOrderApi,
  checkAvailability,
  checkInOrder,
  checkOutOrder,
  confirmDraft as confirmDraftApi,
  confirmOrder,
  createDraft as createDraftApi,
  createReport,
  listDrafts,
  listOrders,
  listReports,
} from '@/api/boarding'
import { listPets } from '@/api/pets'
import { useAuthStore } from '@/stores/auth'
import type {
  BoardingDraft,
  BoardingOrder,
  DailyReport,
  Kennel,
  KennelSize,
  Pet,
} from '@/types'

type TagType = 'default' | 'success' | 'warning' | 'error' | 'info'
type OrderAction = 'confirm' | 'check-in' | 'check-out' | 'cancel'

const auth = useAuthStore()
const message = useMessage()

const isOwner = computed(() => auth.user?.role === 'pet_owner')
const isStaff = computed(
  () => auth.user?.role === 'boarding_staff' || auth.user?.role === 'admin',
)

const loading = ref(true)
const searching = ref(false)
const submitting = ref(false)
const actioningId = ref<number | null>(null)

const pets = ref<Pet[]>([])
const kennels = ref<Kennel[]>([])
const orders = ref<BoardingOrder[]>([])
const drafts = ref<BoardingDraft[]>([])

const dateRange = ref<[string, string] | null>(null)
const size = ref<string>('all')
const petId = ref<number | null>(null)
const kennelId = ref<number | null>(null)
const note = ref('')
const draft = ref<BoardingDraft | null>(null)
const countdown = ref(0)
const statusFilter = ref('all')

let timer: number | undefined

const sizeOptions = [
  { label: '全部体型', value: 'all' },
  { label: '小型', value: 'small' },
  { label: '中型', value: 'medium' },
  { label: '大型', value: 'large' },
]

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '待接单', value: 'pending' },
  { label: '已确认', value: 'confirmed' },
  { label: '寄养中', value: 'checked_in' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' },
]

const appetiteOptions = [
  { label: '食欲好', value: 'good' },
  { label: '一般', value: 'normal' },
  { label: '较差', value: 'poor' },
]

const stoolOptions = [
  { label: '正常', value: 'normal' },
  { label: '偏软', value: 'soft' },
  { label: '腹泻', value: 'diarrhea' },
]

const spiritOptions = [
  { label: '精神好', value: 'good' },
  { label: '一般', value: 'normal' },
  { label: '低落', value: 'low' },
]

const petOptions = computed(() =>
  pets.value.map((pet) => ({
    label: `${pet.name}${pet.breed ? ` · ${pet.breed}` : ''}`,
    value: pet.id,
  })),
)

const filteredOrders = computed(() =>
  statusFilter.value === 'all'
    ? orders.value
    : orders.value.filter((order) => order.status === statusFilter.value),
)

const stats = computed(() => ({
  pending: orders.value.filter((item) => item.status === 'pending').length,
  confirmed: orders.value.filter((item) => item.status === 'confirmed').length,
  boarding: orders.value.filter(
    (item) => item.status === 'checked_in' || item.status === 'boarding',
  ).length,
}))

const statusMap: Record<string, { label: string; type: TagType }> = {
  pending: { label: '待接单', type: 'warning' },
  confirmed: { label: '已确认', type: 'info' },
  checked_in: { label: '寄养中', type: 'success' },
  boarding: { label: '寄养中', type: 'success' },
  completed: { label: '已完成', type: 'default' },
  cancelled: { label: '已取消', type: 'error' },
}

function statusMeta(status: string): { label: string; type: TagType } {
  return statusMap[status] ?? { label: status, type: 'default' }
}

const sizeLabels: Record<string, string> = {
  small: '小型',
  medium: '中型',
  large: '大型',
}
const appetiteLabels: Record<string, string> = {
  good: '好',
  normal: '一般',
  poor: '较差',
}
const stoolLabels: Record<string, string> = {
  normal: '正常',
  soft: '偏软',
  diarrhea: '腹泻',
}
const spiritLabels: Record<string, string> = {
  good: '好',
  normal: '一般',
  low: '低落',
}

function sizeLabel(value: string): string {
  return sizeLabels[value] ?? value
}

function appetiteLabel(value?: string | null): string {
  return appetiteLabels[value ?? ''] ?? '未记录'
}

function stoolLabel(value?: string | null): string {
  return stoolLabels[value ?? ''] ?? '未记录'
}

function spiritLabel(value?: string | null): string {
  return spiritLabels[value ?? ''] ?? '未记录'
}

function isoDate(offset: number): string {
  const result = new Date()
  result.setDate(result.getDate() + offset)
  const month = String(result.getMonth() + 1).padStart(2, '0')
  const day = String(result.getDate()).padStart(2, '0')
  return `${result.getFullYear()}-${month}-${day}`
}

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function stopCountdown(): void {
  if (timer !== undefined) {
    window.clearInterval(timer)
    timer = undefined
  }
}

function updateCountdown(): void {
  if (!draft.value) {
    countdown.value = 0
    return
  }
  const remain = Math.floor(
    (new Date(draft.value.expires_at).getTime() - Date.now()) / 1000,
  )
  countdown.value = Math.max(0, remain)
  if (countdown.value === 0) {
    stopCountdown()
    draft.value = null
    message.warning('草稿已过期，请重新生成')
    void load()
  }
}

function startCountdown(): void {
  stopCountdown()
  updateCountdown()
  timer = window.setInterval(updateCountdown, 1000)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const tasks: Promise<unknown>[] = [
      listOrders().then((items) => {
        orders.value = items
      }),
    ]
    if (isOwner.value) {
      tasks.push(
        listPets().then((items) => {
          pets.value = items
          if (petId.value === null) {
            petId.value = items[0]?.id ?? null
          }
        }),
      )
      tasks.push(
        listDrafts().then((items) => {
          drafts.value = items.filter((item) => item.status === 'pending')
          if (!draft.value && drafts.value.length) {
            draft.value = drafts.value[0]
            startCountdown()
          }
        }),
      )
    }
    await Promise.all(tasks)
  } catch {
    // http 拦截器已经提示
  } finally {
    loading.value = false
  }
}

async function search(): Promise<void> {
  if (!dateRange.value) {
    message.warning('请选择寄养日期')
    return
  }
  searching.value = true
  try {
    const [start, end] = dateRange.value
    kennels.value = await checkAvailability({
      start_date: start,
      end_date: end,
      size: size.value === 'all' ? undefined : (size.value as KennelSize),
    })
    kennelId.value = kennels.value[0]?.id ?? null
  } catch {
    kennels.value = []
  } finally {
    searching.value = false
  }
}

async function createDraft(): Promise<void> {
  if (!dateRange.value || petId.value === null || kennelId.value === null) {
    message.warning('请选择宠物、日期和笼舍')
    return
  }
  submitting.value = true
  try {
    const [start, end] = dateRange.value
    draft.value = await createDraftApi({
      pet_id: petId.value,
      kennel_id: kennelId.value,
      start_date: start,
      end_date: end,
      note: note.value.trim() || null,
    })
    note.value = ''
    startCountdown()
    message.success('草稿已生成，请在 15 分钟内确认')
    await search()
  } catch {
    // http 拦截器已经提示
  } finally {
    submitting.value = false
  }
}

async function confirmCurrentDraft(): Promise<void> {
  if (!draft.value) return
  submitting.value = true
  try {
    await confirmDraftApi(draft.value.id, draft.value.idempotency_key)
    message.success('预约已确认，等待寄养员接单')
    draft.value = null
    stopCountdown()
    await Promise.all([load(), search()])
  } catch {
    // http 拦截器已经提示
  } finally {
    submitting.value = false
  }
}

async function dropCurrentDraft(): Promise<void> {
  if (!draft.value) return
  try {
    await cancelDraftApi(draft.value.id)
    message.success('草稿已取消')
    draft.value = null
    stopCountdown()
    await load()
  } catch {
    // http 拦截器已经提示
  }
}

async function runOrderAction(
  order: BoardingOrder,
  action: OrderAction,
): Promise<void> {
  actioningId.value = order.id
  try {
    if (action === 'confirm') {
      await confirmOrder(order.id)
      message.success('已接单')
    } else if (action === 'check-in') {
      await checkInOrder(order.id)
      message.success('已办理入住')
    } else if (action === 'check-out') {
      await checkOutOrder(order.id)
      message.success('已办理退房')
    } else {
      await cancelOrderApi(order.id)
      message.success('订单已取消')
    }
    await load()
  } catch {
    // http 拦截器已经提示
  } finally {
    actioningId.value = null
  }
}

const showReports = ref(false)
const reportOrder = ref<BoardingOrder | null>(null)
const reportList = ref<DailyReport[]>([])
const reportsLoading = ref(false)
const reportDate = ref<string | null>(null)
const reportAppetite = ref('good')
const reportStool = ref('normal')
const reportSpirit = ref('good')
const reportNote = ref('')

async function openReports(order: BoardingOrder): Promise<void> {
  reportOrder.value = order
  showReports.value = true
  const today = isoDate(0)
  if (today < order.start_date) {
    reportDate.value = order.start_date
  } else if (today > order.end_date) {
    reportDate.value = order.end_date
  } else {
    reportDate.value = today
  }
  reportsLoading.value = true
  try {
    reportList.value = await listReports(order.id)
  } catch {
    reportList.value = []
  } finally {
    reportsLoading.value = false
  }
}

async function submitReport(): Promise<void> {
  if (!reportOrder.value || !reportDate.value) {
    message.warning('请选择日报日期')
    return
  }
  try {
    await createReport(reportOrder.value.id, {
      report_date: reportDate.value,
      appetite: reportAppetite.value,
      stool: reportStool.value,
      spirit: reportSpirit.value,
      note: reportNote.value.trim() || null,
    })
    message.success('日报已保存')
    reportNote.value = ''
    reportList.value = await listReports(reportOrder.value.id)
  } catch {
    // http 拦截器已经提示
  }
}

onMounted(async () => {
  dateRange.value = [isoDate(7), isoDate(10)]
  await load()
  await search()
})

onBeforeUnmount(stopCountdown)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="title-row">
          <h1 class="page-title">寄养预约</h1>
          <n-tag round type="warning" size="small">
            {{ isStaff ? '寄养员工作台' : '先草稿，后确认' }}
          </n-tag>
        </div>
        <p class="page-subtitle">
          查询笼舍空档、生成预约草稿，再由你亲自确认。订单状态和每日报告都在这里。
        </p>
      </div>

      <div v-if="isStaff" class="stat-strip">
        <div class="stat-chip">
          <strong>{{ stats.pending }}</strong>
          <span>待接单</span>
        </div>
        <div class="stat-chip">
          <strong>{{ stats.confirmed }}</strong>
          <span>待入住</span>
        </div>
        <div class="stat-chip sage">
          <strong>{{ stats.boarding }}</strong>
          <span>寄养中</span>
        </div>
      </div>
    </div>

    <div v-if="isOwner" class="booking-grid">
      <section class="soft-card panel">
        <h2 class="section-title">选择时间与笼舍</h2>
        <p class="panel-sub">先查空档，再挑一间合适的房间。</p>

        <div class="field-grid">
          <label class="field">
            <span>寄养日期</span>
            <n-date-picker
              v-model:formatted-value="dateRange"
              type="daterange"
              value-format="yyyy-MM-dd"
              clearable
              style="width: 100%"
            />
          </label>
          <label class="field">
            <span>体型筛选</span>
            <n-select v-model:value="size" :options="sizeOptions" />
          </label>
          <label class="field">
            <span>寄养宠物</span>
            <n-select
              v-model:value="petId"
              :options="petOptions"
              placeholder="选择宠物"
            />
          </label>
        </div>

        <div class="search-row">
          <n-button :loading="searching" @click="search">查询空档</n-button>
          <span class="muted hint">按晚计价，退房当天不计费</span>
        </div>

        <div v-if="kennels.length" class="kennel-list">
          <button
            v-for="kennel in kennels"
            :key="kennel.id"
            type="button"
            class="kennel-card"
            :class="{ selected: kennelId === kennel.id }"
            @click="kennelId = kennel.id"
          >
            <div class="kennel-top">
              <strong>{{ kennel.code }}</strong>
              <n-tag size="small" round>{{ sizeLabel(kennel.size) }}</n-tag>
            </div>
            <p>{{ kennel.note || '标准笼舍' }}</p>
            <div class="kennel-price">
              ¥{{ kennel.daily_price }}<small>/晚</small>
            </div>
          </button>
        </div>
        <div v-else-if="!searching" class="kennel-empty">
          <n-empty description="这个时间段没有可用笼舍" size="small" />
        </div>

        <label class="field note-field">
          <span>特殊需求（选填）</span>
          <n-input
            v-model:value="note"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="例如：需要每天喂药、怕生、自带粮食"
            maxlength="300"
          />
        </label>

        <n-button
          type="primary"
          size="large"
          block
          :loading="submitting"
          :disabled="!kennelId || petId === null"
          @click="createDraft"
        >
          生成预约草稿
        </n-button>
      </section>

      <aside class="soft-card panel draft-panel">
        <template v-if="draft">
          <div class="draft-head">
            <span class="pill">待确认草稿</span>
            <span class="countdown">{{ formatDuration(countdown) }}</span>
          </div>

          <div class="draft-pet">
            <strong>{{ draft.pet_name }}</strong>
            <span class="muted">{{ draft.kennel_code }}</span>
          </div>

          <div class="draft-rows">
            <div><span>入住</span><strong>{{ draft.start_date }}</strong></div>
            <div><span>退房</span><strong>{{ draft.end_date }}</strong></div>
            <div><span>晚数</span><strong>{{ draft.nights }} 晚</strong></div>
            <div><span>房费</span><strong>¥{{ draft.total_amount }}</strong></div>
          </div>

          <n-button
            type="primary"
            size="large"
            block
            :loading="submitting"
            @click="confirmCurrentDraft"
          >
            确认预约
          </n-button>
          <n-button quaternary block @click="dropCurrentDraft">放弃草稿</n-button>
          <p class="draft-tip">
            确认后才会锁定档期并生成订单。助手只能生成草稿，不能替你确认。
          </p>
        </template>

        <template v-else>
          <div class="draft-empty">
            <span class="draft-icon">📝</span>
            <h3>为什么先出草稿？</h3>
            <p>
              日期、笼舍和金额会先整理成一份 15 分钟有效的草稿；只有你在这里点击确认，
              系统才会重新校验档期并创建订单。
            </p>
            <ul>
              <li>草稿不会占用笼舍</li>
              <li>金额在草稿阶段就锁定</li>
              <li>确认接口不在 Agent 工具列表里</li>
            </ul>
          </div>
        </template>
      </aside>
    </div>

    <section class="soft-card panel orders-panel">
      <div class="orders-head">
        <div>
          <h2 class="section-title">{{ isStaff ? '寄养订单' : '我的预约' }}</h2>
          <p class="panel-sub">
            {{ isStaff ? '接单、办理入住和退房，并记录每日状态。' : '确认后的订单会出现在这里。' }}
          </p>
        </div>
        <n-select
          v-model:value="statusFilter"
          :options="statusOptions"
          size="small"
          style="width: 130px"
        />
      </div>

      <n-spin :show="loading">
        <div v-if="filteredOrders.length" class="order-list">
          <article v-for="order in filteredOrders" :key="order.id" class="order-card">
            <div class="order-main">
              <div class="order-title">
                <strong>{{ order.pet_name || `宠物 #${order.pet_id}` }}</strong>
                <n-tag size="small" round :type="statusMeta(order.status).type">
                  {{ statusMeta(order.status).label }}
                </n-tag>
              </div>
              <p class="order-meta">
                {{ order.start_date }} → {{ order.end_date }}
                <span class="dot-sep">·</span>
                {{ order.nights }} 晚
                <span class="dot-sep">·</span>
                {{ order.kennel_code }}
              </p>
              <p v-if="order.note" class="order-note">{{ order.note }}</p>
            </div>

            <div class="order-side">
              <div class="order-amount">
                ¥{{ order.total_amount }}
                <small>定金 ¥{{ order.deposit }}</small>
              </div>
              <div class="order-actions">
                <n-button size="small" quaternary @click="openReports(order)">
                  日报
                </n-button>

                <template v-if="isStaff">
                  <n-button
                    v-if="order.status === 'pending'"
                    size="small"
                    type="primary"
                    :loading="actioningId === order.id"
                    @click="runOrderAction(order, 'confirm')"
                  >
                    接单
                  </n-button>
                  <n-button
                    v-if="order.status === 'confirmed'"
                    size="small"
                    type="primary"
                    :loading="actioningId === order.id"
                    @click="runOrderAction(order, 'check-in')"
                  >
                    办理入住
                  </n-button>
                  <n-button
                    v-if="order.status === 'checked_in' || order.status === 'boarding'"
                    size="small"
                    type="primary"
                    :loading="actioningId === order.id"
                    @click="runOrderAction(order, 'check-out')"
                  >
                    办理退房
                  </n-button>
                </template>

                <n-button
                  v-else-if="order.status === 'pending' || order.status === 'confirmed'"
                  size="small"
                  quaternary
                  :loading="actioningId === order.id"
                  @click="runOrderAction(order, 'cancel')"
                >
                  取消
                </n-button>
              </div>
            </div>
          </article>
        </div>

        <n-empty v-else description="还没有寄养订单" />
      </n-spin>
    </section>

    <n-modal
      v-model:show="showReports"
      preset="card"
      :title="`${reportOrder?.pet_name ?? ''} 的寄养日报`"
      style="width: 660px; max-width: 94vw"
    >
      <n-spin :show="reportsLoading">
        <div v-if="reportList.length" class="report-list">
          <article v-for="report in reportList" :key="report.id" class="report-item">
            <div class="report-date">{{ report.report_date }}</div>
            <div class="report-body">
              <div class="report-tags">
                <span class="pill grey">食欲 {{ appetiteLabel(report.appetite) }}</span>
                <span class="pill grey">便便 {{ stoolLabel(report.stool) }}</span>
                <span class="pill grey">精神 {{ spiritLabel(report.spirit) }}</span>
              </div>
              <p>{{ report.note || '寄养员没有留下文字备注。' }}</p>
            </div>
          </article>
        </div>
        <n-empty v-else description="还没有日报" />
      </n-spin>

      <div
        v-if="
          isStaff &&
          reportOrder &&
          ['checked_in', 'boarding', 'completed'].includes(reportOrder.status)
        "
        class="report-form"
      >
        <h3>填写日报</h3>
        <div class="report-form-grid">
          <n-date-picker
            v-model:formatted-value="reportDate"
            type="date"
            value-format="yyyy-MM-dd"
            style="width: 100%"
          />
          <n-select v-model:value="reportAppetite" :options="appetiteOptions" />
          <n-select v-model:value="reportStool" :options="stoolOptions" />
          <n-select v-model:value="reportSpirit" :options="spiritOptions" />
        </div>
        <n-input
          v-model:value="reportNote"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="今天的状态、进食、排便和互动情况"
        />
        <n-button type="primary" @click="submitReport">保存日报</n-button>
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-strip {
  display: flex;
  gap: 10px;
}

.stat-chip {
  display: flex;
  min-width: 84px;
  flex-direction: column;
  padding: 10px 14px;
  border: 1px solid #f0e0d4;
  border-radius: 14px;
  background: #fff8f3;
}

.stat-chip strong {
  font-size: 20px;
  line-height: 1.1;
}

.stat-chip span {
  margin-top: 3px;
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.stat-chip.sage {
  border-color: #dce8de;
  background: var(--pc-sage-soft);
}

.booking-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.75fr);
  gap: 18px;
  align-items: start;
  margin-bottom: 18px;
}

.panel {
  padding: 22px;
}

.panel-sub {
  margin: 5px 0 18px;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.6;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--pc-ink-soft);
  font-size: 12px;
  font-weight: 600;
}

.search-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 14px 0 16px;
}

.hint {
  font-size: 11px;
}

.kennel-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.kennel-card {
  padding: 13px 14px;
  border: 1px solid #eee3d8;
  border-radius: 14px;
  background: #fff;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: 0.18s ease;
}

.kennel-card:hover {
  border-color: #e6b79f;
  box-shadow: 0 8px 18px rgba(116, 88, 63, 0.08);
}

.kennel-card.selected {
  border-color: var(--pc-primary);
  background: #fff8f4;
  box-shadow: 0 0 0 2px rgba(232, 131, 90, 0.12);
}

.kennel-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.kennel-top strong {
  font-size: 14px;
}

.kennel-card p {
  margin: 7px 0;
  color: var(--pc-ink-soft);
  font-size: 11px;
  line-height: 1.5;
}

.kennel-price {
  color: #b85f3c;
  font-size: 17px;
  font-weight: 800;
}

.kennel-price small {
  margin-left: 2px;
  color: var(--pc-ink-soft);
  font-size: 11px;
  font-weight: 500;
}

.kennel-empty {
  display: grid;
  min-height: 120px;
  place-items: center;
  margin-bottom: 14px;
  border: 1px dashed #eee3d8;
  border-radius: 14px;
}

.note-field {
  margin-bottom: 14px;
}

.draft-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.draft-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.countdown {
  color: #b85f3c;
  font-size: 16px;
  font-variant-numeric: tabular-nums;
  font-weight: 800;
}

.draft-pet {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 14px;
  border-radius: 14px;
  background: #fdf7f2;
}

.draft-pet strong {
  font-size: 18px;
}

.draft-pet span {
  font-size: 12px;
}

.draft-rows {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.draft-rows div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #f0e5da;
  font-size: 13px;
}

.draft-rows span {
  color: var(--pc-ink-soft);
}

.draft-tip {
  margin: 0;
  color: #9a8f85;
  font-size: 11px;
  line-height: 1.6;
}

.draft-empty {
  padding: 8px 2px;
}

.draft-icon {
  display: grid;
  width: 46px;
  height: 46px;
  place-items: center;
  border-radius: 14px;
  background: var(--pc-primary-soft);
  font-size: 22px;
}

.draft-empty h3 {
  margin: 14px 0 8px;
  font-size: 16px;
}

.draft-empty p {
  margin: 0;
  color: var(--pc-ink-soft);
  font-size: 13px;
  line-height: 1.7;
}

.draft-empty ul {
  margin: 14px 0 0;
  padding-left: 18px;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.9;
}

.orders-panel {
  margin-bottom: 24px;
}

.orders-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.orders-head .panel-sub {
  margin-bottom: 0;
}

.order-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.order-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 15px 16px;
  border: 1px solid #f0e7de;
  border-radius: 15px;
  background: #fffdfa;
}

.order-title {
  display: flex;
  align-items: center;
  gap: 9px;
}

.order-title strong {
  font-size: 15px;
}

.order-meta {
  margin: 6px 0 0;
  color: var(--pc-ink-soft);
  font-size: 12px;
}

.dot-sep {
  margin: 0 4px;
  color: #cbbfb4;
}

.order-note {
  margin: 7px 0 0;
  color: #9a8f85;
  font-size: 11px;
  line-height: 1.6;
}

.order-side {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: flex-end;
  gap: 9px;
}

.order-amount {
  color: #b85f3c;
  font-size: 18px;
  font-weight: 800;
}

.order-amount small {
  display: block;
  margin-top: 2px;
  color: var(--pc-ink-soft);
  font-size: 10px;
  font-weight: 500;
  text-align: right;
}

.order-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.report-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-item {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #f0e7de;
  border-radius: 13px;
  background: #fffdfa;
}

.report-date {
  flex: 0 0 84px;
  color: var(--pc-ink-soft);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.report-body {
  min-width: 0;
  flex: 1;
}

.report-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.report-body p {
  margin: 8px 0 0;
  color: var(--pc-ink);
  font-size: 13px;
  line-height: 1.65;
}

.report-form {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #f0e7de;
}

.report-form h3 {
  margin: 0 0 12px;
  font-size: 14px;
}

.report-form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.report-form .n-input {
  margin-bottom: 10px;
}

@media (max-width: 1050px) {
  .booking-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 720px) {
  .field-grid,
  .kennel-list,
  .report-form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .stat-strip {
    flex-wrap: wrap;
  }

  .order-card {
    flex-direction: column;
  }

  .order-side {
    width: 100%;
    align-items: flex-start;
  }

  .order-amount small {
    text-align: left;
  }

  .order-actions {
    justify-content: flex-start;
  }
}
</style>
