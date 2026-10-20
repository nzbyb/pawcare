<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  NButton,
  NModal,
  NQrCode,
  NSpin,
  NTag,
  useMessage,
} from 'naive-ui'

import {
  createPayment,
  getPayment,
  mockNotify,
  type Payment,
} from '@/api/payments'
import type { BoardingOrder } from '@/types'

const props = defineProps<{
  show: boolean
  order: BoardingOrder | null
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'paid'): void
}>()

const message = useMessage()

const payment = ref<Payment | null>(null)
const loading = ref(false)
const paying = ref(false)
const errorText = ref('')
const remaining = ref(0)

let pollTimer: number | null = null
let tickTimer: number | null = null
// 组件卸载或弹窗关闭后，迟到的 createPayment 结果不能再启动轮询。
let disposed = false
let loadSeq = 0

function isCurrent(seq: number): boolean {
  return !disposed && seq === loadSeq && props.show
}

const token = computed(() => {
  const content = payment.value?.qr_content
  if (!content) return ''
  try {
    return new URL(content).searchParams.get('token') ?? ''
  } catch {
    return ''
  }
})

const isActive = computed(
  () => payment.value?.status === 'created' || payment.value?.status === 'paying',
)
const isPaid = computed(() => payment.value?.status === 'paid')
const isClosed = computed(() => payment.value?.status === 'closed')

const countdown = computed(() => {
  const total = Math.max(0, remaining.value)
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})

const statusMeta = computed(() => {
  if (!payment.value) return { label: '待生成', type: 'default' as const }
  if (isPaid.value) return { label: '已支付', type: 'success' as const }
  if (isClosed.value) return { label: '已关闭', type: 'default' as const }
  return { label: '等待支付', type: 'warning' as const }
})

function stopTimers(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
  if (tickTimer !== null) {
    window.clearInterval(tickTimer)
    tickTimer = null
  }
}

function tick(): void {
  if (!payment.value) return
  const expires = new Date(payment.value.expires_at).getTime()
  remaining.value = Math.max(0, Math.round((expires - Date.now()) / 1000))
}

async function loadPayment(): Promise<void> {
  if (!props.order) return
  const seq = ++loadSeq
  stopTimers()
  loading.value = true
  errorText.value = ''
  try {
    const created = await createPayment(props.order.id)
    if (!isCurrent(seq)) return
    payment.value = created
    tick()
    if (isActive.value) {
      pollTimer = window.setInterval(poll, 2500)
      tickTimer = window.setInterval(tick, 1000)
    }
  } catch {
    if (isCurrent(seq)) errorText.value = '支付单创建失败，请稍后重试'
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

async function poll(): Promise<void> {
  // 弹窗已关闭或页面已离开时立刻停表，避免定时器在后台一直跑。
  if (disposed || !props.show) {
    stopTimers()
    return
  }
  if (!payment.value) return
  try {
    const latest = await getPayment(payment.value.payment_no, true)
    if (disposed || !props.show) {
      stopTimers()
      return
    }
    payment.value = latest
    if (latest.status === 'paid') {
      handlePaid()
    } else if (latest.status === 'closed') {
      stopTimers()
    }
  } catch (error) {
    // 403/404 说明支付单已不属于当前账号或已不存在，继续轮询只会反复报错。
    const code = (error as { code?: number }).code
    if (code === 403 || code === 404) {
      stopTimers()
      errorText.value = '无权查看该支付单'
    }
  }
}

function handlePaid(): void {
  stopTimers()
  message.success('支付成功，订单已标记为已支付')
  emit('paid')
  window.setTimeout(() => {
    if (!disposed) emit('update:show', false)
  }, 1200)
}

async function handleMockPay(): Promise<void> {
  if (!payment.value || !token.value || paying.value) return
  paying.value = true
  try {
    const result = await mockNotify(payment.value.payment_no, token.value)
    payment.value = { ...payment.value, ...result }
    handlePaid()
  } catch {
    // 拦截器已提示
  } finally {
    paying.value = false
  }
}

async function copyLink(): Promise<void> {
  if (!payment.value) return
  try {
    await navigator.clipboard.writeText(payment.value.qr_content)
    message.success('支付链接已复制')
  } catch {
    message.warning('浏览器不允许复制，请手动选中链接')
  }
}

function close(): void {
  emit('update:show', false)
}

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      payment.value = null
      loadPayment()
    } else {
      // 让仍在途的 createPayment 结果失效，再停表。
      loadSeq += 1
      stopTimers()
    }
  },
)

watch(
  () => props.order?.id,
  () => {
    if (props.show) loadPayment()
  },
)

onBeforeUnmount(() => {
  disposed = true
  loadSeq += 1
  stopTimers()
})
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="收银台"
    class="pay-card"
    :style="{ width: '420px', maxWidth: 'calc(100vw - 32px)' }"
    :mask-closable="!isPaid"
    @update:show="(value: boolean) => emit('update:show', value)"
  >
    <div v-if="loading" class="pay-loading">
      <n-spin size="small" />
      <span>正在生成支付单…</span>
    </div>

    <div v-else-if="errorText" class="pay-error">
      <p>{{ errorText }}</p>
      <n-button size="small" @click="loadPayment">重试</n-button>
    </div>

    <template v-else-if="payment">
      <div class="pay-head">
        <div>
          <span class="pay-label">应付金额</span>
          <div class="pay-amount">
            <small>¥</small>{{ payment.amount.toFixed(2) }}
          </div>
        </div>
        <n-tag size="small" :type="statusMeta.type">{{ statusMeta.label }}</n-tag>
      </div>

      <div class="pay-qr" :class="{ dimmed: !isActive }">
        <n-qr-code
          :value="payment.qr_content"
          :size="168"
          error-correction-level="M"
          :color="isActive ? '#1c1d1a' : '#8a8e84'"
          background-color="#ffffff"
        />
        <p v-if="isActive" class="pay-hint">
          用「模拟扫码」打开支付页，或直接点下方按钮
        </p>
        <p v-else-if="isPaid" class="pay-hint">支付已完成，正在刷新订单…</p>
        <p v-else class="pay-hint">二维码已过期，请重新生成</p>
      </div>

      <dl class="pay-meta">
        <div>
          <dt>支付单号</dt>
          <dd>{{ payment.payment_no }}</dd>
        </div>
        <div>
          <dt>剩余时间</dt>
          <dd>{{ isActive ? countdown : '—' }}</dd>
        </div>
      </dl>

      <div class="pay-actions">
        <n-button
          v-if="isActive"
          type="primary"
          size="large"
          block
          :loading="paying"
          :disabled="!token"
          @click="handleMockPay"
        >
          模拟扫码支付成功
        </n-button>
        <n-button v-else-if="isClosed" type="primary" size="large" block @click="loadPayment">
          重新生成支付单
        </n-button>
      </div>

      <div class="pay-foot">
        <n-button text size="tiny" @click="copyLink">复制支付链接</n-button>
        <n-button text size="tiny" @click="close">关闭</n-button>
      </div>

      <p class="pay-note">
        当前为模拟收银台，不产生真实资金。支付回调会校验二维码凭证，
        并保证重复通知不会重复入账。
      </p>
    </template>
  </n-modal>
</template>

<style scoped>
.pay-loading,
.pay-error {
  display: flex;
  min-height: 180px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--pc-ink-soft);
  font-size: 13px;
}

.pay-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--pc-line);
}

.pay-label {
  color: var(--pc-ink-faint);
  font-size: 11px;
  letter-spacing: 0.04em;
}

.pay-amount {
  margin-top: 2px;
  font-size: 30px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

.pay-amount small {
  margin-right: 3px;
  font-size: 15px;
  font-weight: 500;
  color: var(--pc-ink-soft);
}

.pay-qr {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin: 18px 0 14px;
  padding: 16px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: #fff;
}

.pay-qr.dimmed {
  opacity: 0.55;
}

.pay-hint {
  margin: 0;
  color: var(--pc-ink-faint);
  font-size: 11px;
  text-align: center;
}

.pay-meta {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  margin: 0 0 16px;
  font-size: 12px;
}

.pay-meta div {
  display: contents;
}

.pay-meta dt {
  color: var(--pc-ink-faint);
}

.pay-meta dd {
  margin: 0;
  color: var(--pc-ink-soft);
  font-variant-numeric: tabular-nums;
}

.pay-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pay-foot {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
}

.pay-note {
  margin: 14px 0 0;
  padding-top: 12px;
  border-top: 1px solid var(--pc-line);
  color: var(--pc-ink-faint);
  font-size: 11px;
  line-height: 1.7;
}
</style>
