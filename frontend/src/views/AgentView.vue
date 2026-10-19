<script setup lang="ts">
import { NButton, NInput, NTag } from 'naive-ui'

const examples = [
  '豆豆下一次疫苗什么时候到期？',
  '帮我看看国庆期间有没有适合大型犬的笼舍。',
  '给豆豆预约 10 月 1 日到 10 月 5 日的寄养。',
]

const capabilities = [
  {
    icon: '🔎',
    title: '查档案',
    text: '按宠物名和时间范围查询疫苗、驱虫、就诊与体重记录。',
  },
  {
    icon: '📅',
    title: '查空档',
    text: '输入日期和体型，返回可用笼舍与预估价格。',
  },
  {
    icon: '📝',
    title: '生成草稿',
    text: '把预约信息整理成草稿，展示日期、笼舍和金额。',
  },
  {
    icon: '✅',
    title: '人工确认',
    text: '草稿不会直接下单，需要你在界面上单独确认。',
  },
]

const roadmap = [
  { label: '工具层与权限校验', done: true },
  { label: 'LangGraph Agent 循环', done: false },
  { label: 'SSE 流式输出与工具轨迹', done: false },
  { label: 'RAG 知识库与引用', done: false },
  { label: '评测集与消融实验', done: false },
]
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="title-row">
          <h1 class="page-title">智能助手</h1>
          <n-tag round type="warning" size="small">接口开发中</n-tag>
        </div>
        <p class="page-subtitle">
          用自然语言查询档案、检查寄养空档，并把预约整理成可确认的草稿。
        </p>
      </div>
    </div>

    <div class="agent-grid">
      <section class="chat-shell soft-card">
        <header class="chat-head">
          <div class="assistant">
            <span class="assistant-avatar">🐾</span>
            <div>
              <strong>PawCare 助手</strong>
              <small>权限感知 · 草稿确认 · 可追溯</small>
            </div>
          </div>
          <span class="status-dot">开发中</span>
        </header>

        <div class="chat-body">
          <div class="assistant-bubble">
            <p>
              你好，我是 PawCare 助手。等接口接入后，你可以直接问我宠物的健康记录、
              疫苗到期时间，或者让我帮你查寄养空档。
            </p>
            <p class="bubble-note">
              涉及下单的操作只会生成草稿，必须由你确认后才会生效。
            </p>
          </div>

          <div class="examples">
            <span class="muted examples-label">你可以这样问</span>
            <button
              v-for="example in examples"
              :key="example"
              class="example-chip"
              disabled
            >
              {{ example }}
            </button>
          </div>
        </div>

        <footer class="chat-input">
          <n-input
            placeholder="助手接口接入后即可对话"
            disabled
            round
            size="large"
          />
          <n-button type="primary" size="large" disabled round>发送</n-button>
        </footer>
      </section>

      <aside class="side">
        <section class="side-card soft-card">
          <h2 class="section-title">能做什么</h2>
          <div class="capability-list">
            <article v-for="item in capabilities" :key="item.title" class="capability">
              <span class="capability-icon">{{ item.icon }}</span>
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.text }}</p>
              </div>
            </article>
          </div>
        </section>

        <section class="side-card soft-card">
          <h2 class="section-title">开发进度</h2>
          <ul class="roadmap">
            <li v-for="item in roadmap" :key="item.label" :class="{ done: item.done }">
              <span class="dot">{{ item.done ? '✓' : '' }}</span>
              {{ item.label }}
            </li>
          </ul>
          <p class="roadmap-note">
            当前阶段先把档案与健康管理的核心链路做稳，再接 Agent。
          </p>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.agent-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr);
  gap: 18px;
  align-items: start;
}

.chat-shell {
  display: flex;
  min-height: 600px;
  flex-direction: column;
  overflow: hidden;
}

.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--pc-line);
}

.assistant {
  display: flex;
  align-items: center;
  gap: 11px;
}

.assistant-avatar {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 14px;
  background: linear-gradient(140deg, #f7c9b3, #e8835a);
  font-size: 21px;
}

.assistant strong {
  display: block;
  font-size: 14px;
}

.assistant small {
  display: block;
  margin-top: 2px;
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.status-dot {
  padding: 5px 11px;
  border-radius: 999px;
  background: #fdf5e4;
  color: #9a7227;
  font-size: 11px;
  font-weight: 700;
}

.chat-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 22px;
  padding: 22px 20px;
}

.assistant-bubble {
  max-width: 640px;
  padding: 16px 18px;
  border-radius: 4px 18px 18px;
  background: #fdf7f2;
  border: 1px solid #f4e5da;
}

.assistant-bubble p {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
}

.bubble-note {
  margin-top: 10px !important;
  padding-top: 10px;
  border-top: 1px dashed #ecd9cb;
  color: var(--pc-ink-soft);
  font-size: 12px !important;
}

.examples {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.examples-label {
  font-size: 12px;
}

.example-chip {
  padding: 9px 13px;
  border: 1px solid #eee3d8;
  border-radius: 11px;
  background: #fff;
  color: #8a7c71;
  font-size: 13px;
  text-align: left;
  cursor: not-allowed;
  opacity: 0.85;
}

.chat-input {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--pc-line);
  background: rgba(255, 255, 255, 0.6);
}

.side {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.side-card {
  padding: 20px;
}

.capability-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 16px;
}

.capability {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.capability-icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border-radius: 11px;
  background: var(--pc-sage-soft);
  font-size: 16px;
}

.capability strong {
  font-size: 13px;
}

.capability p {
  margin: 3px 0 0;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.6;
}

.roadmap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
}

.roadmap li {
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--pc-ink-soft);
  font-size: 12px;
}

.roadmap li.done {
  color: var(--pc-ink);
  font-weight: 600;
}

.dot {
  display: grid;
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  place-items: center;
  border: 1px solid #e2d7cc;
  border-radius: 999px;
  color: #fff;
  font-size: 10px;
}

.roadmap li.done .dot {
  border-color: var(--pc-sage);
  background: var(--pc-sage);
}

.roadmap-note {
  margin: 14px 0 0;
  padding-top: 12px;
  border-top: 1px solid #f1e8df;
  color: #9a8f85;
  font-size: 11px;
  line-height: 1.6;
}

@media (max-width: 1050px) {
  .agent-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
