<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NInput, NTag } from 'naive-ui'

import { getConversation, listConversations, streamChat } from '@/api/agent'
import type {
  AgentConversation,
  AgentToolEvent,
  BoardingDraft,
} from '@/types'

interface ChatBubble {
  id: number
  role: 'user' | 'assistant'
  content: string
  toolEvents?: AgentToolEvent[]
  draft?: BoardingDraft | null
  traceId?: string
}

const router = useRouter()

const examples = [
  '豆豆下一次疫苗什么时候到期？',
  '帮我看看下个月有没有适合中型犬的笼舍。',
  '给豆豆预约 11 月 1 日到 11 月 5 日的寄养。',
]

const capabilities = [
  {
    icon: '🔎',
    title: '查档案',
    text: '按宠物名和时间范围查询疫苗、驱虫、就诊记录。',
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
    text: '草稿不会直接下单，需要你在寄养页单独确认。',
  },
]

const roadmap = [
  { label: '权限感知的服务层', done: true },
  { label: '寄养草稿与确认接口', done: true },
  { label: 'Agent 工具层与多轮调用', done: true },
  { label: '会话持久化与 trace', done: true },
  { label: 'SSE 流式输出', done: true },
  { label: 'RAG 知识库与引用', done: false },
  { label: '评测集与消融实验', done: false },
]

const toolLabels: Record<string, string> = {
  list_my_pets: '查询宠物',
  get_pet_health_records: '查询健康记录',
  get_upcoming_reminders: '查询到期提醒',
  check_kennel_availability: '检查寄养空档',
  create_boarding_draft: '生成预约草稿',
  list_boarding_orders: '查询寄养订单',
  get_boarding_daily_reports: '查询每日报告',
}

const messages = ref<ChatBubble[]>([])
const conversations = ref<AgentConversation[]>([])
const conversationId = ref<number | null>(null)
const input = ref('')
const sending = ref(false)
const loadingHistory = ref(false)
const streamingBubbleId = ref<number | null>(null)
const bodyRef = ref<HTMLElement | null>(null)
let nextId = 1

const canSend = computed(() => input.value.trim().length > 0 && !sending.value)
const showWelcome = computed(() => messages.value.length === 0 && !loadingHistory.value)

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderMessage(content: string): string {
  return escapeHtml(content)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- /gm, '• ')
    .replace(/\n/g, '<br>')
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function addMessage(
  role: 'user' | 'assistant',
  content: string,
  extra: Partial<ChatBubble> = {},
): ChatBubble {
  const bubble: ChatBubble = { id: nextId++, role, content, ...extra }
  messages.value.push(bubble)
  return bubble
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const element = bodyRef.value
  if (element) element.scrollTop = element.scrollHeight
}

async function loadConversations(): Promise<void> {
  try {
    conversations.value = await listConversations()
  } catch {
    // 错误提示由 http 拦截器统一展示。
  }
}

async function openConversation(item: AgentConversation): Promise<void> {
  if (sending.value || loadingHistory.value) return
  loadingHistory.value = true
  input.value = ''
  try {
    const data = await getConversation(item.id)
    conversationId.value = item.id
    messages.value = data.messages
      .filter(
        (message) =>
          (message.role === 'user' || message.role === 'assistant') &&
          message.content.trim().length > 0,
      )
      .map((message) => ({
        id: nextId++,
        role: message.role as 'user' | 'assistant',
        content: message.content,
      }))
    await scrollToBottom()
  } catch {
    // 拦截器已提示。
  } finally {
    loadingHistory.value = false
  }
}

function startNewConversation(): void {
  if (sending.value) return
  conversationId.value = null
  messages.value = []
  input.value = ''
}

async function send(text?: string): Promise<void> {
  const content = (text ?? input.value).trim()
  if (!content || sending.value) return

  input.value = ''
  addMessage('user', content)
  sending.value = true
  await scrollToBottom()

  const streamState: { bubbleId: number | null } = { bubbleId: null }
  let completed = false
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), 180_000)

  function ensureBubble(): ChatBubble {
    const existing =
      streamState.bubbleId === null
        ? undefined
        : messages.value.find((item) => item.id === streamState.bubbleId)
    if (existing) return existing
    const created = addMessage('assistant', '')
    streamState.bubbleId = created.id
    streamingBubbleId.value = created.id
    return created
  }

  function upsertTool(event: AgentToolEvent): void {
    const target = ensureBubble()
    const events = [...(target.toolEvents ?? [])]
    const index = events.findIndex(
      (item) => item.name === event.name && item.status === 'running',
    )
    if (index >= 0) events[index] = event
    else events.push(event)
    target.toolEvents = events
    void scrollToBottom()
  }

  const failureText =
    '抱歉，这次请求没有完成。请稍后再试，或者把问题说得更具体一点。'

  try {
    await streamChat(
      {
        ...(conversationId.value
          ? { conversation_id: conversationId.value }
          : {}),
        messages: [{ role: 'user', content }],
      },
      (event, data) => {
        if (event === 'start') {
          const target = ensureBubble()
          target.traceId = String(data.trace_id ?? '')
          const id = Number(data.conversation_id)
          if (Number.isFinite(id)) conversationId.value = id
        } else if (event === 'tool_start') {
          upsertTool({
            name: String(data.name ?? ''),
            status: 'running',
            summary: '正在执行…',
            latency_ms: null,
          })
        } else if (event === 'tool_end') {
          upsertTool({
            name: String(data.name ?? ''),
            status: String(data.status ?? 'ok'),
            summary: String(data.summary ?? ''),
            latency_ms:
              typeof data.latency_ms === 'number' ? data.latency_ms : null,
          })
        } else if (event === 'assistant') {
          ensureBubble().content = String(data.content ?? '')
          void scrollToBottom()
        } else if (event === 'done') {
          const target = ensureBubble()
          target.content = String(data.content ?? '')
          target.toolEvents = (data.tool_events ?? []) as AgentToolEvent[]
          target.draft = (data.draft ?? null) as BoardingDraft | null
          target.traceId = String(data.trace_id ?? '')
          const id = Number(data.conversation_id)
          if (Number.isFinite(id)) conversationId.value = id
          completed = true
          streamingBubbleId.value = null
          void scrollToBottom()
        } else if (event === 'error') {
          ensureBubble().content = String(
            data.message ?? '助手暂时不可用，请稍后再试。',
          )
          streamingBubbleId.value = null
        }
      },
      { signal: controller.signal },
    )
    if (!completed) throw new Error('流式响应未完成')
    await loadConversations()
  } catch {
    const failed =
      streamState.bubbleId === null
        ? undefined
        : messages.value.find((item) => item.id === streamState.bubbleId)
    if (failed && !failed.content) {
      failed.content = failureText
    } else if (!failed) {
      addMessage('assistant', failureText)
    }
  } finally {
    window.clearTimeout(timer)
    streamingBubbleId.value = null
    sending.value = false
    await scrollToBottom()
  }
}

function onInputKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  void send()
}

function goConfirm(): void {
  router.push('/boarding')
}

onMounted(() => {
  void loadConversations()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="title-row">
          <h1 class="page-title">智能助手</h1>
          <n-tag round type="success" size="small">deepseek-flash · 已接入</n-tag>
        </div>
        <p class="page-subtitle">
          用自然语言查询档案、检查寄养空档，并把预约整理成可确认的草稿。
        </p>
      </div>
      <n-button quaternary size="small" :disabled="sending" @click="startNewConversation">
        + 新对话
      </n-button>
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
          <span class="status-dot" :class="{ busy: sending }">
            {{ sending ? '思考中' : '在线' }}
          </span>
        </header>

        <div ref="bodyRef" class="chat-body">
          <template v-if="showWelcome">
            <div class="assistant-bubble">
              <p>
                你好，我是 PawCare 助手。可以帮你查宠物档案、健康记录和疫苗提醒，
                也能查询寄养空档并生成预约草稿。
              </p>
              <p class="bubble-note">
                涉及预约的操作只会生成草稿，必须由你在寄养页确认后才会生效。
              </p>
            </div>

            <div class="examples">
              <span class="muted examples-label">你可以这样问</span>
              <button
                v-for="example in examples"
                :key="example"
                class="example-chip"
                :disabled="sending"
                @click="send(example)"
              >
                {{ example }}
              </button>
            </div>
          </template>

          <div v-if="loadingHistory" class="history-loading">正在读取历史对话…</div>

          <div
            v-for="bubble in messages"
            :key="bubble.id"
            class="bubble-row"
            :class="bubble.role"
          >
            <span v-if="bubble.role === 'assistant'" class="bubble-avatar">🐾</span>
            <div class="bubble" :class="bubble.role">
              <div class="bubble-text" v-html="renderMessage(bubble.content)"></div>
              <div
                v-if="bubble.id === streamingBubbleId && !bubble.content"
                class="stream-status"
              >
                正在思考并调用工具…
              </div>

              <div v-if="bubble.toolEvents?.length" class="tool-events">
                <span
                  v-for="(event, index) in bubble.toolEvents"
                  :key="`${bubble.id}-${index}`"
                  class="tool-chip"
                  :class="{
                    error: event.status === 'error',
                    running: event.status === 'running',
                  }"
                >
                  <span class="tool-mark">
                    {{ event.status === 'ok' ? '✓' : event.status === 'running' ? '…' : '!' }}
                  </span>
                  {{ toolLabels[event.name] ?? event.name }}
                  <em>{{ event.summary }}</em>
                  <em v-if="event.latency_ms != null">{{ event.latency_ms }}ms</em>
                </span>
              </div>

              <div v-if="bubble.draft" class="draft-card">
                <div class="draft-head">
                  <span class="draft-badge">待确认草稿</span>
                  <strong>
                    {{ bubble.draft.pet_name ?? '宠物' }} ·
                    {{ bubble.draft.kennel_code ?? '笼舍' }}
                  </strong>
                </div>
                <div class="draft-grid">
                  <div>
                    <span>入住</span>
                    <strong>{{ bubble.draft.start_date }}</strong>
                  </div>
                  <div>
                    <span>退房</span>
                    <strong>{{ bubble.draft.end_date }}</strong>
                  </div>
                  <div>
                    <span>晚数</span>
                    <strong>{{ bubble.draft.nights ?? '—' }} 晚</strong>
                  </div>
                  <div>
                    <span>预估</span>
                    <strong>¥{{ bubble.draft.total_amount }}</strong>
                  </div>
                </div>
                <div class="draft-foot">
                  <span>15 分钟内有效，确认后才会生成订单</span>
                  <n-button size="small" type="primary" @click="goConfirm">
                    去寄养页确认
                  </n-button>
                </div>
              </div>

              <div v-if="bubble.traceId" class="trace">
                追踪 ID · {{ bubble.traceId.slice(0, 8) }}
              </div>
            </div>
          </div>

          <div v-if="sending && streamingBubbleId === null" class="bubble-row assistant">
            <span class="bubble-avatar">🐾</span>
            <div class="bubble assistant typing" aria-label="助手正在思考">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>

        <footer class="chat-input">
          <n-input
            v-model:value="input"
            type="textarea"
            placeholder="问点什么，Enter 发送，Shift + Enter 换行"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :disabled="sending"
            size="large"
            @keydown="onInputKeydown"
          />
          <n-button
            type="primary"
            size="large"
            round
            :disabled="!canSend"
            :loading="sending"
            @click="send()"
          >
            发送
          </n-button>
        </footer>
      </section>

      <aside class="side">
        <section class="side-card soft-card">
          <div class="side-head">
            <h2 class="section-title">对话记录</h2>
            <span class="muted side-count">{{ conversations.length }}</span>
          </div>
          <div v-if="conversations.length === 0" class="empty-history">
            还没有对话。从右边的问题开始试试。
          </div>
          <div v-else class="conversation-list">
            <button
              v-for="item in conversations"
              :key="item.id"
              class="conversation-item"
              :class="{ active: item.id === conversationId }"
              :disabled="sending || loadingHistory"
              @click="openConversation(item)"
            >
              <strong>{{ item.title }}</strong>
              <small>{{ formatTime(item.last_message_at) }}</small>
            </button>
          </div>
        </section>

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
            下一步：RAG 知识库与引用、评测集扩充与消融实验。
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

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.agent-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr);
  gap: 18px;
  align-items: start;
}

.chat-shell {
  display: flex;
  height: calc(100vh - 190px);
  min-height: 620px;
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
  background: #edf7ec;
  color: #4b7a45;
  font-size: 11px;
  font-weight: 700;
}

.status-dot.busy {
  background: #fdf5e4;
  color: #9a7227;
}

.chat-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
  padding: 22px 20px;
  scroll-behavior: smooth;
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
  cursor: pointer;
  transition: 0.16s ease;
}

.example-chip:hover:not(:disabled) {
  border-color: #e8b79f;
  color: #b85f3c;
  transform: translateY(-1px);
}

.example-chip:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}

.bubble-row.user {
  justify-content: flex-end;
}

.bubble-avatar {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  margin-top: 2px;
  place-items: center;
  border-radius: 10px;
  background: var(--pc-sage-soft);
  font-size: 14px;
}

.bubble {
  max-width: 78%;
  padding: 12px 15px;
  border-radius: 4px 16px 16px;
  background: #fff;
  border: 1px solid #f0e6dc;
  font-size: 14px;
  line-height: 1.72;
}

.bubble.user {
  border-radius: 16px 4px 16px 16px;
  border-color: transparent;
  background: var(--pc-primary);
  color: #fff;
}

.bubble-text {
  overflow-wrap: anywhere;
}

.bubble-text :deep(strong) {
  font-weight: 700;
}

.stream-status {
  color: var(--pc-ink-soft);
  font-size: 12px;
  animation: pulse 1.4s infinite ease-in-out;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.45;
  }

  50% {
    opacity: 1;
  }
}

.history-loading {
  padding: 10px 0;
  color: var(--pc-ink-soft);
  font-size: 12px;
  text-align: center;
}

.tool-events {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  padding-top: 9px;
  border-top: 1px dashed #f0e4d8;
}

.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 9px;
  border-radius: 999px;
  background: #f4f8f2;
  color: #58714f;
  font-size: 11px;
  font-weight: 600;
}

.tool-chip.error {
  background: #fdf1ee;
  color: #a85b48;
}

.tool-chip.running {
  background: #fdf5e4;
  color: #9a7227;
}

.tool-chip.running em {
  color: #b08b4d;
}

.tool-mark {
  font-size: 10px;
}

.tool-chip em {
  color: #8a9b84;
  font-style: normal;
  font-weight: 400;
}

.tool-chip.error em {
  color: #b98a7d;
}

.draft-card {
  margin-top: 12px;
  padding: 13px 14px;
  border: 1px solid #efd9ca;
  border-radius: 13px;
  background: linear-gradient(150deg, #fffaf6, #fdf3ec);
}

.draft-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.draft-head strong {
  font-size: 13px;
}

.draft-badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: #f8e3d7;
  color: #b05f3f;
  font-size: 10px;
  font-weight: 800;
}

.draft-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 11px;
}

.draft-grid div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.draft-grid span {
  color: var(--pc-ink-soft);
  font-size: 10px;
}

.draft-grid strong {
  font-size: 12px;
}

.draft-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed #eccfbd;
}

.draft-foot span {
  color: #9a7c6b;
  font-size: 10px;
}

.trace {
  margin-top: 8px;
  color: #b3a79d;
  font-size: 10px;
  letter-spacing: 0.02em;
}

.bubble.user .trace {
  color: rgba(255, 255, 255, 0.65);
}

.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 15px 17px;
}

.typing span {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #d6b8a6;
  animation: typing 1.2s infinite ease-in-out;
}

.typing span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing {
  0%,
  60%,
  100% {
    opacity: 0.35;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--pc-line);
  background: rgba(255, 255, 255, 0.6);
}

.chat-input :deep(textarea) {
  resize: none;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.side-card {
  padding: 20px;
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.side-count {
  font-size: 11px;
}

.empty-history {
  margin-top: 14px;
  padding: 16px 12px;
  border: 1px dashed #e8ddd2;
  border-radius: 12px;
  color: #9a8f85;
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-top: 12px;
  max-height: 222px;
  overflow-y: auto;
}

.conversation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 11px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--pc-ink-soft);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  transition: 0.16s ease;
}

.conversation-item:hover:not(:disabled) {
  background: #f7f1ea;
  color: var(--pc-ink);
}

.conversation-item.active {
  background: var(--pc-primary-soft);
  color: #b85f3c;
}

.conversation-item:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.conversation-item strong {
  overflow: hidden;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-item small {
  flex: 0 0 auto;
  color: #ac9f94;
  font-size: 10px;
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

  .chat-shell {
    height: 70vh;
  }
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
  }

  .bubble {
    max-width: 88%;
  }

  .draft-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chat-input {
    padding: 12px 14px;
  }
}
</style>
