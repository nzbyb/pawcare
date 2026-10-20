<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NButton, NSpin, NTag, useMessage } from 'naive-ui'

import AppLogo from '@/components/AppLogo.vue'
import {
  getMockPayment,
  mockNotify,
  type PublicPayment,
} from '@/api/payments'

const route = useRoute()
const message = useMessage()

const payment = ref<PublicPayment | null>(null)
const loading = ref(true)
const paying = ref(false)
const errorText = ref('')
const remaining = ref(0)

let tickTimer: number | null = null

const paymentNo = computed(() => String(route.params.paymentNo ?? ''))
const token = computed(() => {
  const value = route.query.token
  return typeof value === 'string' ? value : ''
})

const isActive = computed(
  () => payment.value?.status === 'created' || payment.value?.status === 'paying',
)
const isPaid = computed(() => payment.value?.status === 'paid')
const isClosed = computed(() => payment.value?.status === 'closed')

const countdown = computed(() => {
  const total = Math.max(0, remaining.value)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})

function tick(): void {
  if (!payment.value) return
  const expires = new Date(payment.value.expires_at).getTime()
  remaining.value = Math.max(0, Math.round((expires - Date.now()) / 1000))
  if (remaining.value === 0 && isActive.value) {
    payment.value = { ...payment.value, status: 'closed' }
    stopTick()
  }
}

function startTick(): void {
  stopTick()
  tick()
  tickTimer = window.setInterval(tick, 1000)
}

function stopTick(): void {
  if (tickTimer !== null) {
    window.clearInterval(tickTimer)
    tickTimer = null
  }
}

async function load(): Promise<void> {
  if (!paymentNo.value || !token.value) {
    errorText.value = '支付链接不完整，请回到订单页重新获取二维码'
    loading.value = false
    return
  }
  loading.value = true
  errorText.value = ''
  try {
    payment.value = await getMockPayment(paymentNo.value, token.value)
    if (isActive.value) startTick()
  } catch {
    errorText.value = '支付单不存在或凭证已失效'
  } finally {
    loading.value = false
  }
}

async function confirmPay(): Promise<void> {
  if (!payment.value || paying.value) return
  paying.value = true
  try {
    payment.value = await mockNotify(payment.value.payment_no, token.value)
    stopTick()
    message.success('支付成功')
  } catch {
    // 拦截器已提示
    load()
  } finally {
    paying.value = false
  }
}

onMounted(load)
onBeforeUnmount(stopTick)
</script>

<template>
  <div class="pay-page">
    <div class="pay-shell">
      <header class="pay-brand">
        <AppLogo :size="30" :compact="true" />
      </header>

      <main class="pay-card">
        <div v-if="loading" class="pay-state">
          <n-spin size="small" />
          <p>正在读取支付单…</p>
        </div>

        <div v-else-if="errorText" class="pay-state">
          <span class="pay-mark error">!</span>
          <h1>无法打开支付页</h1>
          <p>{{ errorText }}</p>
        </div>

        <template v-else-if="payment">
          <div class="pay-head">
            <span class="pay-kicker">模拟收银台</span>
            <h1>
              <small>¥</small>{{ payment.amount.toFixed(2) }}
            </h1>
            <p class="pay-sub">寄养订单 #{{ payment.order_id }}</p>
          </div>

          <div class="pay-status">
            <n-tag :type="isPaid ? 'success' : isClosed ? 'default' : 'warning'" size="small">
              {{ isPaid ? '支付成功' : isClosed ? '二维码已过期' : '等待支付' }}
            </n-tag>
            <span v-if="isActive" class="pay-countdown">剩余 {{ countdown }}</span>
          </div>

          <div v-if="isActive" class="pay-body">
            <n-button
              type="primary"
              size="large"
              block
              :loading="paying"
              @click="confirmPay"
            >
              模拟支付 ¥{{ payment.amount.toFixed(2) }}
            </n-button>
            <p class="pay-hint">
              这是毕业设计项目的模拟收银台，不会产生真实扣款。
            </p>
          </div>

          <div v-else-if="isPaid" class="pay-body">
            <p class="pay-done">订单已支付，可返回订单页查看。</p>
          </div>

          <div v-else class="pay-body">
            <p class="pay-done">支付单已关闭，请回到订单页重新获取二维码。</p>
          </div>

          <dl class="pay-meta">
            <div>
              <dt>支付单号</dt>
              <dd>{{ payment.payment_no }}</dd>
            </div>
            <div>
              <dt>渠道</dt>
              <dd>模拟支付</dd>
            </div>
          </dl>
        </template>
      </main>

      <footer class="pay-foot">
        支付回调会校验二维码凭证；重复通知不会重复入账。
      </footer>
    </div>
  </div>
</template>

<style scoped>
.pay-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 32px 16px;
  background: var(--pc-bg);
}

.pay-shell {
  width: 100%;
  max-width: 400px;
}

.pay-brand {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.pay-card {
  padding: 26px 26px 22px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.pay-state {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
}

.pay-state h1 {
  margin: 0;
  font-size: 17px;
}

.pay-state p {
  margin: 0;
  color: var(--pc-ink-soft);
  font-size: 12.5px;
  line-height: 1.7;
}

.pay-mark {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border: 1px solid var(--pc-danger);
  border-radius: 50%;
  color: var(--pc-danger);
  font-weight: 700;
}

.pay-head {
  padding-bottom: 16px;
  border-bottom: 1px solid var(--pc-line);
}

.pay-kicker {
  color: var(--pc-primary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.pay-head h1 {
  margin: 6px 0 2px;
  font-size: 34px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
}

.pay-head h1 small {
  margin-right: 4px;
  font-size: 17px;
  font-weight: 500;
  color: var(--pc-ink-soft);
}

.pay-sub {
  margin: 0;
  color: var(--pc-ink-faint);
  font-size: 12px;
}

.pay-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0;
}

.pay-countdown {
  color: var(--pc-ink-faint);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.pay-body {
  padding: 4px 0 16px;
}

.pay-hint {
  margin: 10px 0 0;
  color: var(--pc-ink-faint);
  font-size: 11px;
  line-height: 1.7;
  text-align: center;
}

.pay-done {
  margin: 0;
  color: var(--pc-ink-soft);
  font-size: 13px;
  line-height: 1.7;
  text-align: center;
}

.pay-meta {
  display: grid;
  gap: 6px;
  margin: 0;
  padding-top: 14px;
  border-top: 1px solid var(--pc-line);
  font-size: 12px;
}

.pay-meta div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.pay-meta dt {
  color: var(--pc-ink-faint);
}

.pay-meta dd {
  margin: 0;
  color: var(--pc-ink-soft);
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}

.pay-foot {
  margin-top: 14px;
  color: var(--pc-ink-faint);
  font-size: 11px;
  line-height: 1.7;
  text-align: center;
}
</style>
