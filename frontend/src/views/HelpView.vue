<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  NButton,
  NEmpty,
  NInput,
  NSelect,
  NSpin,
  NTabPane,
  NTabs,
  useMessage,
} from 'naive-ui'

import { listMyFeedback, submitFeedback } from '@/api/content'
import type { Feedback } from '@/types'

const message = useMessage()
const tab = ref<'faq' | 'guide' | 'feedback'>('faq')

const faqs = [
  {
    q: '预约草稿为什么 15 分钟后失效？',
    a: '草稿只是占位，不产生订单。超过 15 分钟后笼舍档期可能已被他人确认，所以需要重新生成；确认动作只在页面上由你本人点击完成。',
  },
  {
    q: '为什么智能助手不能直接下单？',
    a: '助手只负责查空档、算价格、生成草稿。确认接口没有注册成工具，模型既不会主动下单，也无法被提示词诱导下单。',
  },
  {
    q: '寄养前健康检查算健康证明吗？',
    a: '不算。它只核对已录入的疫苗、驱虫有效期、过敏信息和近 7 天症状，结果不替代兽医诊断，也不代表已获准入住。',
  },
  {
    q: '取消预约后钱怎么退？',
    a: '未入住的已付订单取消后会生成全额退款申请，由管理员审核执行；退款到账进度可以在寄养订单页查看。',
  },
  {
    q: '每天的报告什么时候能看到？',
    a: '寄养员当天填写后即可在订单详情查看，包含食欲、排便、精神状态和照片。异常日报会在寄养员首页高亮提醒。',
  },
  {
    q: '疫苗和驱虫提醒怎么来的？',
    a: '新增健康记录时可以填写下次到期日，系统会提前 7 天生成待处理提醒，也可以在个人中心关闭某一类通知。',
  },
]

const guideSteps = [
  { title: '建立档案', text: '录入宠物基本信息、体重历史，以及疫苗、驱虫、用药和就诊记录。' },
  { title: '查空档', text: '选择入住和退房日期、笼舍体型，查看剩余笼舍与预估总价；同一宠物不能重复预约重叠档期。' },
  { title: '生成草稿', text: '确认前可以先看寄养前健康核对项，草稿 15 分钟内有效。' },
  { title: '全额支付', text: '草稿确认后生成订单，按总额一次性支付，不收取独立定金。' },
  { title: '入住与照护', text: '寄养员核对资料后办理入住，每日填写照护报告，异常会单独提醒。' },
  { title: '退房', text: '交接确认后办理退房，订单完成；如需取消未入住订单，走退款流程。' },
]

const feeRules = [
  { item: '房费', rule: '按笼舍每日价格 × 入住晚数计算，退房当天不计费。' },
  { item: '支付方式', rule: '全额支付；沙箱环境使用模拟收银台或支付宝沙箱，不产生真实扣款。' },
  { item: '取消与退款', rule: '未入住订单取消后生成全额退款申请，管理员审核后原路退回。' },
  { item: '超期在住', rule: '超过预约退房日仍在住的订单继续占用笼舍，直到实际办理退房。' },
]

const feedbackCategories = [
  { label: '功能异常', value: 'bug' },
  { label: '功能建议', value: 'suggestion' },
  { label: '服务体验', value: 'service' },
  { label: '其他', value: 'other' },
]

const statusLabels: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  resolved: '已解决',
  closed: '已关闭',
}
const statusTone: Record<string, string> = {
  pending: 'amber',
  processing: 'amber',
  resolved: 'sage',
  closed: '',
}

const form = ref({ category: 'suggestion', content: '', contact: '' })
const submitting = ref(false)
const feedbacks = ref<Feedback[]>([])
const feedbackLoading = ref(false)
const canSubmit = computed(() => form.value.content.trim().length >= 5)

async function submit(): Promise<void> {
  if (!canSubmit.value) {
    message.warning('请至少填写 5 个字的反馈内容')
    return
  }
  submitting.value = true
  try {
    await submitFeedback({
      category: form.value.category,
      content: form.value.content.trim(),
      contact: form.value.contact.trim() || null,
    })
    form.value = { category: 'suggestion', content: '', contact: '' }
    message.success('反馈已提交，管理员回复后会收到站内通知')
    await loadFeedback()
    tab.value = 'feedback'
  } finally {
    submitting.value = false
  }
}

async function loadFeedback(): Promise<void> {
  feedbackLoading.value = true
  try {
    feedbacks.value = (await listMyFeedback()).items
  } catch {
    feedbacks.value = []
  } finally {
    feedbackLoading.value = false
  }
}

function dateText(value?: string | null): string {
  return value ? value.slice(0, 16).replace('T', ' ') : ''
}

onMounted(loadFeedback)
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">帮助与反馈</h1>
        <p class="page-subtitle">常见问题、寄养服务指南，以及提交给管理员的问题反馈</p>
      </div>
    </header>

    <n-tabs v-model:value="tab" type="line" animated>
      <n-tab-pane name="faq" tab="常见问题">
        <div class="stack">
          <details v-for="item in faqs" :key="item.q" class="soft-card faq">
            <summary>{{ item.q }}</summary>
            <p>{{ item.a }}</p>
          </details>
        </div>
      </n-tab-pane>

      <n-tab-pane name="guide" tab="服务指南">
        <div class="stack">
          <section class="soft-card guide">
            <h2 class="section-title">寄养流程</h2>
            <ol class="steps">
              <li v-for="(step, index) in guideSteps" :key="step.title">
                <span class="step-no">{{ index + 1 }}</span>
                <div><strong>{{ step.title }}</strong><p>{{ step.text }}</p></div>
              </li>
            </ol>
          </section>

          <section class="soft-card guide">
            <h2 class="section-title">收费标准与规则</h2>
            <div class="table-wrap">
              <table>
                <thead><tr><th>项目</th><th>说明</th></tr></thead>
                <tbody>
                  <tr v-for="rule in feeRules" :key="rule.item">
                    <td>{{ rule.item }}</td><td>{{ rule.rule }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="soft-card guide">
            <h2 class="section-title">联系方式</h2>
            <p class="muted">
              门店电话与地址请以管理员在公告中发布的信息为准；系统问题可以通过「意见反馈」提交，
              处理进度会以站内通知回复。
            </p>
          </section>
        </div>
      </n-tab-pane>

      <n-tab-pane name="feedback" tab="意见反馈">
        <div class="stack">
          <section class="soft-card form-card">
            <h2 class="section-title">提交反馈</h2>
            <p class="muted">描述越具体越容易定位问题；不需要填写真实姓名，联系方式选填。</p>
            <div class="field">
              <label>反馈类型</label>
              <n-select v-model:value="form.category" :options="feedbackCategories" style="width: 180px" />
            </div>
            <div class="field">
              <label>反馈内容</label>
              <n-input
                v-model:value="form.content"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 8 }"
                maxlength="1000"
                show-count
                placeholder="例如：预约页在手机上日期选择器会溢出"
              />
            </div>
            <div class="field">
              <label>联系方式（选填）</label>
              <n-input v-model:value="form.contact" maxlength="100" placeholder="手机号或邮箱，便于回访" />
            </div>
            <n-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
              提交反馈
            </n-button>
          </section>

          <section class="soft-card">
            <div class="list-heading">
              <h2 class="section-title">我的反馈</h2>
              <n-button size="small" quaternary :loading="feedbackLoading" @click="loadFeedback">刷新</n-button>
            </div>
            <n-spin :show="feedbackLoading">
              <div v-if="feedbacks.length" class="feedback-list">
                <article v-for="item in feedbacks" :key="item.id" class="feedback-row">
                  <div class="feedback-head">
                    <span class="pill" :class="statusTone[item.status]">{{ statusLabels[item.status] }}</span>
                    <span class="muted">{{ dateText(item.create_time) }}</span>
                  </div>
                  <p class="feedback-content">{{ item.content }}</p>
                  <p v-if="item.reply" class="feedback-reply">
                    <strong>管理员回复：</strong>{{ item.reply }}
                  </p>
                </article>
              </div>
              <n-empty v-else description="还没有提交过反馈" class="empty" />
            </n-spin>
          </section>
        </div>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<style scoped>
.page-header { margin-bottom: 8px; }
.stack { display: grid; gap: 12px; }
.faq { padding: 16px 18px; }
.faq summary { cursor: pointer; font-size: 13px; font-weight: 700; color: var(--pc-ink); }
.faq summary:focus-visible { outline: 2px solid var(--pc-primary); outline-offset: 3px; }
.faq p { margin: 10px 0 0; font-size: 13px; line-height: 1.8; color: var(--pc-ink-soft); }
.guide { padding: 20px; }
.steps { display: grid; gap: 14px; margin: 16px 0 0; padding: 0; list-style: none; }
.steps li { display: flex; gap: 12px; }
.step-no {
  width: 22px; height: 22px; flex: none; border-radius: 50%;
  display: grid; place-items: center;
  background: var(--pc-primary-soft); color: var(--pc-primary);
  font-size: 12px; font-weight: 700;
}
.steps strong { font-size: 13px; }
.steps p { margin: 4px 0 0; font-size: 12px; line-height: 1.7; color: var(--pc-ink-soft); }
.table-wrap { overflow-x: auto; margin-top: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--pc-line); vertical-align: top; }
th { color: var(--pc-ink-soft); font-weight: 600; white-space: nowrap; }
.form-card { padding: 20px; display: grid; gap: 14px; }
.field { display: grid; gap: 6px; }
.field label { font-size: 12px; font-weight: 700; color: var(--pc-ink); }
.muted { color: var(--pc-ink-soft); font-size: 12px; line-height: 1.7; }
.list-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 20px 0; }
.feedback-list { display: grid; gap: 0; margin-top: 8px; }
.feedback-row { padding: 14px 20px; border-bottom: 1px solid var(--pc-line); }
.feedback-row:last-child { border-bottom: 0; }
.feedback-head { display: flex; align-items: center; gap: 10px; }
.feedback-content { margin: 8px 0 0; font-size: 13px; line-height: 1.7; overflow-wrap: anywhere; }
.feedback-reply {
  margin: 10px 0 0; padding: 10px 12px; border-radius: var(--pc-radius);
  background: var(--pc-primary-soft); font-size: 12px; line-height: 1.7;
}
.empty { padding: 32px 0; }
</style>
