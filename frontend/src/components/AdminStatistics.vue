<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NSelect, NSpin, useMessage } from 'naive-ui'
import { request } from '@/api/http'

interface Statistics {
  start_date: string
  end_date: string
  orders: number
  received: number
  refunded: number
  net: number
  occupancy_rate: number
  actual_occupied: number
  kennel_total: number
  daily: { date: string; orders: number; received: number; refunded: number; net: number }[]
}

const message = useMessage()
const days = ref(7)
const data = ref<Statistics | null>(null)
const loading = ref(false)
const failed = ref(false)
const exporting = ref(false)
let requestId = 0
const maxOrders = computed(() => Math.max(1, ...data.value?.daily.map(row => row.orders) ?? []))
const money = (amount: number) => `¥${amount.toFixed(2)}`
async function load(): Promise<void> {
  const current = ++requestId
  loading.value = true
  failed.value = false
  try {
    const result = await request.get<Statistics>('/admin/statistics', { params: { days: days.value } })
    if (current === requestId) data.value = result
  } catch { if (current === requestId) failed.value = true }
  finally { if (current === requestId) loading.value = false }
}

async function exportReport(): Promise<void> {
  exporting.value = true
  try {
    const blob = await request.get<Blob>('/admin/statistics/export', {
      params: { days: days.value },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `pawcare-statistics-${data.value?.end_date ?? ''}-${days.value}d.xlsx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    message.success('报表已导出')
  } catch {
    message.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}
onMounted(load)
</script>

<template>
  <section class="statistics soft-card">
    <header>
      <div><h2 class="section-title">运营趋势</h2><p class="muted">{{ data?.start_date }} → {{ data?.end_date }} · 按支付和退款实际完成日统计</p></div>
      <div class="head-actions">
        <n-select v-model:value="days" :options="[{ label: '最近7天', value: 7 }, { label: '最近30天', value: 30 }]" style="width: 130px" @update:value="load" />
        <n-button size="small" :loading="exporting" @click="exportReport">导出 Excel</n-button>
      </div>
    </header>
    <n-spin :show="loading">
      <div v-if="failed" role="alert">统计加载失败 <n-button size="small" @click="load">重试</n-button></div>
      <template v-else-if="data">
        <div class="metrics">
          <div><span>新建订单</span><strong>{{ data.orders }}</strong></div>
          <div><span>实收 / 退款</span><strong>{{ money(data.received) }} / {{ money(data.refunded) }}</strong></div>
          <div><span>净收款</span><strong>{{ money(data.net) }}</strong></div>
          <div><span>今日实际入住率</span><strong>{{ data.occupancy_rate }}%</strong><small>{{ data.actual_occupied }} / {{ data.kennel_total }} 间，含逾期在住</small></div>
        </div>
        <p class="muted">每日新建订单（包含后续取消的订单）</p>
        <svg viewBox="0 0 600 120" role="img" aria-label="所选日期范围的每日新建订单趋势；详细数据可展开查看">
          <line x1="0" y1="100" x2="600" y2="100" stroke="var(--pc-line)" />
          <rect v-for="(row, index) in data.daily" :key="row.date"
            :x="index * 600 / data.daily.length + 3" :y="100 - row.orders / maxOrders * 85"
            :width="Math.max(2, 600 / data.daily.length - 6)" :height="Math.max(0, row.orders / maxOrders * 85)" rx="2" fill="var(--pc-primary)">
            <title>{{ row.date }}：{{ row.orders }} 单</title>
          </rect>
          <text x="0" y="117">{{ data.start_date }}</text><text x="600" y="117" text-anchor="end">{{ data.end_date }}</text>
        </svg>
        <details><summary>查看每日订单及收支明细</summary>
          <div class="table-wrap"><table><thead><tr><th>日期</th><th>新订单</th><th>实收</th><th>退款</th><th>净收款</th></tr></thead>
            <tbody><tr v-for="row in data.daily" :key="row.date"><td>{{ row.date }}</td><td>{{ row.orders }}</td><td>{{ money(row.received) }}</td><td>{{ money(row.refunded) }}</td><td>{{ money(row.net) }}</td></tr></tbody>
          </table></div>
        </details>
      </template>
    </n-spin>
  </section>
</template>

<style scoped>
.statistics { padding: 20px; margin: 12px 0 28px; }
header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.head-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
p, summary { font-size: 12px; line-height: 1.7; }
summary { cursor: pointer; color: var(--pc-primary); }
.metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 20px 0; }
.metrics div { display: flex; flex-direction: column; gap: 8px; }
.metrics span, small { color: var(--pc-ink-soft); font-size: 12px; }
strong { font-size: 18px; overflow-wrap: anywhere; }
svg { width: 100%; max-height: 150px; }
text { font-size: 10px; fill: var(--pc-ink-soft); }
.table-wrap { overflow: auto; max-height: 300px; }
table { width: 100%; font-size: 12px; border-collapse: collapse; }
th, td { padding: 10px; text-align: left; white-space: nowrap; border-bottom: 1px solid var(--pc-line); }
@media (max-width: 900px) { .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 500px) { header { align-items: flex-start; flex-direction: column; } }
</style>
