<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NSpin } from 'naive-ui'

import { getHandover } from '@/api/boarding'
import type { HandoverSheet } from '@/types'

const route = useRoute()
const router = useRouter()

const sheet = ref<HandoverSheet | null>(null)
const loading = ref(true)
const error = ref('')

const orderId = Number(route.params.id)

const orderNo = computed(() =>
  sheet.value ? `PC-${String(sheet.value.order.id).padStart(6, '0')}` : '',
)

const generatedAt = computed(() => {
  if (!sheet.value?.generated_at) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(sheet.value.generated_at))
})

const speciesLabels: Record<string, string> = {
  dog: '犬',
  cat: '猫',
  other: '其他',
}

const genderLabels: Record<string, string> = {
  male: '公',
  female: '母',
  unknown: '未知',
}

const recordTypeLabels: Record<string, string> = {
  vaccine: '疫苗',
  deworm: '驱虫',
  medication: '用药',
  visit: '就诊',
  symptom: '症状',
}

const statusLabels: Record<string, string> = {
  pending: '待确认',
  confirmed: '已确认',
  checked_in: '已入住',
  boarding: '寄养中',
  completed: '已完成',
  cancelled: '已取消',
}

const paymentLabels: Record<string, string> = {
  unpaid: '未支付',
  paid: '已支付',
  refunded: '已退款',
}

const belongings = ['牵引绳', '主粮', '零食', '药物', '玩具', '垫子 / 毛毯']

function speciesText(value: string): string {
  return speciesLabels[value] ?? value
}

function genderText(value?: string | null): string {
  return value ? genderLabels[value] ?? value : '未填写'
}

function recordTypeText(value: string): string {
  return recordTypeLabels[value] ?? value
}

function statusText(value: string): string {
  return statusLabels[value] ?? value
}

function paymentText(value: string): string {
  return paymentLabels[value] ?? value
}

function ageText(birthday?: string | null): string {
  if (!birthday) return '未填写'
  const birth = new Date(birthday)
  if (Number.isNaN(birth.getTime())) return '未填写'
  const now = new Date()
  let months =
    (now.getFullYear() - birth.getFullYear()) * 12 +
    now.getMonth() -
    birth.getMonth()
  if (now.getDate() < birth.getDate()) months -= 1
  if (months < 0) return '未填写'
  if (months < 12) return `${months} 个月`
  return `${Math.floor(months / 12)} 岁`
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    sheet.value = await getHandover(orderId)
  } catch (err) {
    error.value =
      err instanceof Error && err.message ? err.message : '交接单加载失败'
  } finally {
    loading.value = false
  }
}

function printSheet(): void {
  window.print()
}

onMounted(load)
</script>

<template>
  <div class="handover-page">
    <header class="handover-bar">
      <button class="bar-back" type="button" @click="router.back()">
        ← 返回
      </button>
      <span class="bar-title">寄养交接单</span>
      <button class="bar-print" type="button" @click="printSheet">
        打印 / 导出 PDF
      </button>
    </header>

    <n-spin :show="loading">
      <div v-if="error" class="error-box">{{ error }}</div>

      <article v-else-if="sheet" class="sheet">
        <header class="sheet-head">
          <div class="sheet-brand">
            <span class="brand-mark">PawCare</span>
            <h1>寄养交接单</h1>
            <p class="brand-sub">Boarding Handover Sheet</p>
          </div>
          <dl class="sheet-meta">
            <div>
              <dt>交接单号</dt>
              <dd>{{ orderNo }}</dd>
            </div>
            <div>
              <dt>生成时间</dt>
              <dd>{{ generatedAt }}</dd>
            </div>
          </dl>
        </header>

        <section class="sheet-grid">
          <div class="cell">
            <h2>宠物信息</h2>
            <dl class="rows">
              <div>
                <dt>名字</dt>
                <dd>{{ sheet.pet.name }}</dd>
              </div>
              <div>
                <dt>种类 / 品种</dt>
                <dd>
                  {{ speciesText(sheet.pet.species) }}
                  <template v-if="sheet.pet.breed"> · {{ sheet.pet.breed }}</template>
                </dd>
              </div>
              <div>
                <dt>性别</dt>
                <dd>{{ genderText(sheet.pet.gender) }}</dd>
              </div>
              <div>
                <dt>绝育</dt>
                <dd>{{ sheet.pet.neutered ? '已绝育' : '未绝育' }}</dd>
              </div>
              <div>
                <dt>年龄</dt>
                <dd>{{ ageText(sheet.pet.birthday) }}</dd>
              </div>
              <div>
                <dt>最近体重</dt>
                <dd>
                  <template v-if="sheet.pet.latest_weight">
                    {{ sheet.pet.latest_weight }} kg
                    <span class="muted">
                      （{{ sheet.pet.latest_weight_date }}）
                    </span>
                  </template>
                  <template v-else>未记录</template>
                </dd>
              </div>
            </dl>
          </div>

          <div class="cell">
            <h2>寄养安排</h2>
            <dl class="rows">
              <div>
                <dt>笼舍</dt>
                <dd>{{ sheet.order.kennel_code ?? '待分配' }}</dd>
              </div>
              <div>
                <dt>入住日期</dt>
                <dd>{{ sheet.order.start_date }}</dd>
              </div>
              <div>
                <dt>退房日期</dt>
                <dd>{{ sheet.order.end_date }}</dd>
              </div>
              <div>
                <dt>寄养天数</dt>
                <dd>{{ sheet.order.nights }} 晚</dd>
              </div>
              <div>
                <dt>订单状态</dt>
                <dd>{{ statusText(sheet.order.status) }}</dd>
              </div>
              <div>
                <dt>费用</dt>
                <dd>
                  ¥{{ sheet.order.total_amount }}
                  <span class="muted">
                    （定金 ¥{{ sheet.order.deposit }} ·
                    {{ paymentText(sheet.order.payment_status) }}）
                  </span>
                </dd>
              </div>
            </dl>
          </div>
        </section>

        <section class="block">
          <h2>健康与注意事项</h2>
          <div v-if="sheet.pet.allergies" class="alert">
            过敏史：{{ sheet.pet.allergies }}
          </div>
          <div class="notes">
            <p v-if="sheet.pet.notes">
              <span class="notes-label">档案备注</span>{{ sheet.pet.notes }}
            </p>
            <p v-if="sheet.order.note">
              <span class="notes-label">寄养备注</span>{{ sheet.order.note }}
            </p>
            <p v-if="!sheet.pet.allergies && !sheet.pet.notes && !sheet.order.note" class="muted">
              暂无特别注意事项。
            </p>
          </div>
        </section>

        <section class="block">
          <h2>健康记录</h2>
          <table v-if="sheet.health_records.length" class="sheet-table">
            <thead>
              <tr>
                <th class="col-type">类型</th>
                <th>项目</th>
                <th class="col-date">日期</th>
                <th class="col-date">下次到期</th>
                <th class="col-note">备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(record, index) in sheet.health_records" :key="index">
                <td>{{ recordTypeText(record.record_type) }}</td>
                <td>{{ record.title }}</td>
                <td>{{ record.record_date }}</td>
                <td>{{ record.next_due_date ?? '—' }}</td>
                <td class="note-cell">{{ record.note ?? '—' }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="empty">暂无健康记录。</p>
        </section>

        <section v-if="sheet.reminders.length" class="block">
          <h2>待处理提醒</h2>
          <ul class="reminder-list">
            <li v-for="(reminder, index) in sheet.reminders" :key="index">
              <span>{{ reminder.title }}</span>
              <span class="reminder-date">
                {{ reminder.due_date }} 到期
              </span>
            </li>
          </ul>
        </section>

        <section class="sheet-grid">
          <div class="cell">
            <h2>主人联系</h2>
            <dl class="rows">
              <div>
                <dt>联系人</dt>
                <dd>{{ sheet.owner.nickname }}</dd>
              </div>
              <div>
                <dt>电话</dt>
                <dd>{{ sheet.owner.phone || '未填写' }}</dd>
              </div>
              <div>
                <dt>邮箱</dt>
                <dd>{{ sheet.owner.email || '未填写' }}</dd>
              </div>
            </dl>
          </div>

          <div class="cell">
            <h2>随行物品</h2>
            <ul class="belongings">
              <li v-for="item in belongings" :key="item">
                <span class="checkbox" />{{ item }}
              </li>
            </ul>
            <p class="hint">交接时请双方逐项核对，未携带的物品请划去。</p>
          </div>
        </section>

        <section class="sign-grid">
          <div class="sign">
            <span class="sign-label">送养人签字</span>
            <span class="sign-line" />
          </div>
          <div class="sign">
            <span class="sign-label">接收人签字</span>
            <span class="sign-line" />
          </div>
          <div class="sign">
            <span class="sign-label">交接日期</span>
            <span class="sign-line" />
          </div>
        </section>

        <footer class="sheet-foot">
          本单由 PawCare 根据宠物档案与寄养订单自动生成 · {{ orderNo }} ·
          签字后双方各留一份
        </footer>
      </article>
    </n-spin>
  </div>
</template>

<style scoped>
.handover-page {
  min-height: 100vh;
  padding: 0 16px 40px;
  background: var(--pc-bg);
}

.handover-bar {
  display: flex;
  max-width: 210mm;
  height: 56px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 auto;
}

.bar-back,
.bar-print {
  padding: 6px 10px;
  border: 1px solid var(--pc-line-strong);
  border-radius: var(--pc-radius-sm);
  background: var(--pc-surface);
  color: var(--pc-ink-soft);
  font-size: 12.5px;
  font-weight: 550;
  cursor: pointer;
}

.bar-back:hover {
  border-color: var(--pc-primary);
  color: var(--pc-primary);
}

.bar-print {
  border-color: var(--pc-primary);
  background: var(--pc-primary);
  color: #fff;
  font-weight: 600;
}

.bar-print:hover {
  background: var(--pc-primary-hover);
}

.bar-title {
  color: var(--pc-ink-faint);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.error-box {
  max-width: 210mm;
  margin: 40px auto;
  padding: 28px;
  border: 1px solid var(--pc-danger);
  border-radius: var(--pc-radius);
  background: var(--pc-danger-soft);
  color: var(--pc-danger);
  font-size: 13px;
  text-align: center;
}

.sheet {
  max-width: 210mm;
  margin: 0 auto;
  padding: 14mm;
  border: 1px solid var(--pc-line);
  background: #fff;
  color: var(--pc-ink);
}

.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--pc-primary);
}

.brand-mark {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--pc-primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.sheet-head h1 {
  margin: 10px 0 2px;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.brand-sub {
  margin: 0;
  color: var(--pc-ink-faint);
  font-size: 10.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.sheet-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 2px 0 0;
  text-align: right;
}

.sheet-meta div {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  font-size: 10.5px;
}

.sheet-meta dt {
  color: var(--pc-ink-faint);
}

.sheet-meta dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.sheet-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-top: 14px;
  border: 1px solid var(--pc-line);
}

.sheet-grid + .sheet-grid {
  margin-top: 12px;
}

.cell {
  padding: 12px 14px 10px;
}

.cell + .cell {
  border-left: 1px solid var(--pc-line);
}

.cell h2,
.block h2 {
  margin: 0 0 9px;
  color: var(--pc-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.rows {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: 0;
}

.rows div {
  display: flex;
  gap: 10px;
  font-size: 11.5px;
  line-height: 1.5;
}

.rows dt {
  width: 64px;
  flex: 0 0 64px;
  color: var(--pc-ink-faint);
}

.rows dd {
  margin: 0;
  font-weight: 550;
}

.muted {
  color: var(--pc-ink-faint);
  font-weight: 400;
}

.block {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--pc-line);
}

.alert {
  margin-bottom: 8px;
  padding: 7px 10px;
  border: 1px solid var(--pc-accent);
  border-radius: 4px;
  background: var(--pc-accent-soft);
  color: var(--pc-accent);
  font-size: 11.5px;
  font-weight: 600;
}

.notes p {
  margin: 0 0 4px;
  font-size: 11.5px;
  line-height: 1.6;
}

.notes p:last-child {
  margin-bottom: 0;
}

.notes-label {
  margin-right: 8px;
  color: var(--pc-ink-faint);
}

.sheet-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}

.sheet-table th {
  padding: 5px 8px;
  border-bottom: 1px solid var(--pc-line-strong);
  color: var(--pc-ink-faint);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-align: left;
}

.sheet-table td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--pc-line);
  line-height: 1.45;
  vertical-align: top;
}

.sheet-table tbody tr:last-child td {
  border-bottom: 0;
}

.col-type {
  width: 56px;
}

.col-date {
  width: 92px;
}

.col-note {
  width: 32%;
}

.note-cell {
  color: var(--pc-ink-soft);
}

.empty {
  margin: 0;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.reminder-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.reminder-list li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--pc-line);
  font-size: 11.5px;
}

.reminder-list li:last-child {
  border-bottom: 0;
}

.reminder-date {
  color: var(--pc-warn);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.belongings {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5px 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.belongings li {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11.5px;
}

.checkbox {
  display: inline-block;
  width: 11px;
  height: 11px;
  border: 1px solid var(--pc-ink-faint);
  border-radius: 2px;
}

.hint {
  margin: 9px 0 0;
  color: var(--pc-ink-faint);
  font-size: 10px;
}

.sign-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 18px;
  margin-top: 22px;
}

.sign {
  display: flex;
  height: 52px;
  flex-direction: column;
  justify-content: flex-end;
  gap: 5px;
}

.sign-line {
  display: block;
  height: 1px;
  background: var(--pc-ink-faint);
}

.sign-label {
  color: var(--pc-ink-faint);
  font-size: 10.5px;
}

.sheet-foot {
  margin-top: 16px;
  padding-top: 10px;
  border-top: 1px solid var(--pc-line);
  color: var(--pc-ink-faint);
  font-size: 9.5px;
  text-align: center;
}

@media (max-width: 720px) {
  .sheet {
    padding: 18px 16px;
  }

  .sheet-grid {
    grid-template-columns: 1fr;
  }

  .cell + .cell {
    border-top: 1px solid var(--pc-line);
    border-left: 0;
  }

  .sheet-head {
    flex-direction: column;
    gap: 10px;
  }

  .sheet-meta {
    text-align: left;
  }

  .sheet-meta div {
    justify-content: flex-start;
  }

  .sign-grid {
    grid-template-columns: 1fr;
  }
}

@media print {
  :global(body) {
    background: #fff;
  }

  .handover-page {
    min-height: 0;
    padding: 0;
    background: #fff;
  }

  .handover-bar {
    display: none;
  }

  .sheet {
    width: auto;
    max-width: none;
    margin: 0;
    padding: 0;
    border: 0;
  }

  .sheet-grid,
  .block,
  .sign-grid {
    break-inside: avoid;
  }

  @page {
    size: A4;
    margin: 13mm;
  }
}
</style>
