<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty, NSpin } from 'naive-ui'

import { getBoardingTasks } from '@/api/boarding'
import { useAuthStore } from '@/stores/auth'
import type { BoardingTaskKey, BoardingTasks } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const data = ref<BoardingTasks | null>(null)
const loading = ref(false)
const failed = ref(false)
const active = ref<BoardingTaskKey>('arrivals')
const groups: { key: BoardingTaskKey; label: string; hint: string; action: string }[] = [
  { key: 'pending', label: '待接单', hint: '核对需求并确认预约', action: '查看预约' },
  { key: 'arrivals', label: '待入住', hint: '含预约期间尚未入住的订单', action: '办理入住' },
  { key: 'departures', label: '待退房', hint: '含已经超过预约退房日的订单', action: '办理退房' },
  { key: 'missing_reports', label: '未填日报', hint: '今日在住宠物尚无日报', action: '填写日报' },
  { key: 'abnormal_reports', label: '异常日报', hint: '今日食欲、排便或精神状态异常', action: '查看日报' },
]
const current = computed(() => groups.find(item => item.key === active.value)!)
const tasks = computed(() => data.value?.[active.value] ?? [])

async function load(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    data.value = await getBoardingTasks()
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

function open(orderId: number): void {
  router.push({ path: '/boarding', query: {
    order: String(orderId),
    ...(active.value === 'missing_reports' || active.value === 'abnormal_reports' ? { reports: '1' } : {}),
  } })
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">今日寄养任务</h1>
        <p class="page-subtitle">{{ data?.date || '今天' }} · 接单、入住、照护和退房集中处理。</p>
      </div>
      <div class="header-actions">
        <n-button v-if="auth.user?.role === 'admin'" @click="router.push('/admin')">运营管理</n-button>
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
            :class="{ active: active === group.key, danger: group.key === 'abnormal_reports' }"
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
              <strong>{{ task.pet_name }} <span class="pill">{{ task.kennel_code }}</span></strong>
              <p>订单 #{{ task.order_id }} · {{ task.start_date }} → {{ task.end_date }}</p>
              <p v-if="active === 'arrivals' && task.payment_status !== 'paid'" class="payment-note">待完成付款，付款后可办理入住</p>
              <p v-if="active === 'arrivals' && task.start_date < data!.date" class="payment-note">已超过预约入住日，请联系宠物主确认到店时间</p>
              <p v-if="active === 'departures' && task.end_date < data!.date" class="payment-note">已超过预约退房日，请尽快核对离店安排</p>
              <p v-if="task.abnormal_reasons.length" class="abnormal">{{ task.abnormal_reasons.join(' · ') }}</p>
            </div>
            <div class="task-actions">
              <n-button size="small" quaternary @click="router.push(`/pets/${task.pet_id}`)">健康档案</n-button>
              <n-button size="small" type="primary" secondary @click="open(task.order_id)">{{ current.action }}</n-button>
            </div>
          </article>
          <n-empty v-if="!tasks.length && !loading" :description="`暂无${current.label}任务`" class="empty-tasks" />
        </section>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.header-actions, .task-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.task-metrics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 22px; }
.task-metric { display: flex; min-width: 0; flex-direction: column; gap: 12px; padding: 18px; text-align: left; cursor: pointer; color: var(--pc-ink); }
.task-metric.active { border-color: var(--pc-primary); background: var(--pc-primary-soft); }
.task-metric:focus-visible { outline: 2px solid var(--pc-primary); outline-offset: 3px; }
.task-metric strong { font-size: 30px; line-height: 1; }
.task-metric.danger strong, .abnormal { color: var(--pc-danger); }
.task-metric small, .task-info p { color: var(--pc-ink-soft); font-size: 12px; line-height: 1.6; }
.task-panel { overflow: hidden; }
.task-panel-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 20px; border-bottom: 1px solid var(--pc-line); font-size: 12px; }
.task-row { display: flex; justify-content: space-between; align-items: center; gap: 18px; padding: 18px 20px; border-bottom: 1px solid var(--pc-line); }
.task-row:last-child { border-bottom: 0; }
.task-info { min-width: 0; overflow-wrap: anywhere; }
.task-info strong { font-size: 14px; }
.task-info .pill { margin-left: 6px; }
.task-info p { margin: 6px 0 0; }
.task-info .payment-note { color: var(--pc-warn); }
.task-info .abnormal { color: var(--pc-danger); }
.empty-tasks, .error-panel { padding: 40px 20px; text-align: center; }
@media (max-width: 1050px) { .task-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 650px) {
  .task-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .task-row { flex-direction: column; align-items: flex-start; }
  .page-header { flex-direction: column; }
}
</style>
