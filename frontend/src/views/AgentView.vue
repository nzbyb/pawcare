<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NInput } from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import BoardingHealthCard from '@/components/BoardingHealthCard.vue'
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
  retry?: string
  stopped?: boolean
  createdAt?: string | null
  historical?: boolean
}

const router = useRouter()

const examples = [
  '下一次疫苗什么时候到期？',
  '第一次寄养狗狗需要准备哪些东西？',
  '帮我看看下个月有没有适合中型犬的笼舍。',
  '帮我查询下周五入住、周日退房的寄养空档。',
]

const capabilities = [
  {
    icon: 'search',
    title: '查档案',
    text: '按宠物名和时间范围查询疫苗、驱虫、就诊记录。',
  },
  {
    icon: 'book',
    title: '护理知识',
    text: '检索寄养、疫苗、驱虫、换粮等知识，并标注来源。',
  },
  {
    icon: 'calendar',
    title: '查空档',
    text: '输入日期和体型，返回可用笼舍与预估价格。',
  },
  {
    icon: 'clipboard',
    title: '生成草稿',
    text: '把预约信息整理成草稿，展示日期、笼舍和金额。',
  },
  {
    icon: 'shield',
    title: '人工确认',
    text: '草稿不会直接下单，需要你在寄养页单独确认。',
  },
]

const boundaries = [
  '预约需要你在寄养页确认，助手不会自动下单或付款。',
  '只会在你的账号权限范围内查询资料。',
  '护理建议供参考；出现异常症状请及时联系兽医。',
]

const toolLabels: Record<string, string> = {
  list_my_pets: '查询宠物',
  get_pet_health_records: '查询健康记录',
  get_boarding_health_check: '寄养前健康检查',
  get_upcoming_reminders: '查询到期提醒',
  check_kennel_availability: '检查寄养空档',
  create_boarding_draft: '生成预约草稿',
  list_boarding_orders: '查询寄养订单',
  get_boarding_daily_reports: '查询每日报告',
  search_care_knowledge: '检索护理知识',
}

const messages = ref<ChatBubble[]>([])
const conversations = ref<AgentConversation[]>([])
const conversationId = ref<number | null>(null)
const input = ref('')
const sending = ref(false)
const loadingHistory = ref(false)
const streamingBubbleId = ref<number | null>(null)
const bodyRef = ref<HTMLElement | null>(null)
const chatShellRef = ref<HTMLElement | null>(null)
const chatHeight = ref<number | null>(null)
const copiedId = ref<number | null>(null)
const now = ref(Date.now())
let nextId = 1
let activeController: AbortController | null = null
let stopRequested = false
let copyTimer: number | undefined
let clockTimer: number | undefined

const canSend = computed(() => input.value.trim().length > 0 && !sending.value && !loadingHistory.value)
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
  const bubble: ChatBubble = { id: nextId++, role, content, createdAt: new Date().toISOString(), ...extra }
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
        createdAt: message.create_time,
        historical: true,
      }))
    await scrollToBottom()
  } catch {
    // 拦截器已提示。
  } finally {
    loadingHistory.value = false
  }
}

function startNewConversation(): void {
  if (sending.value || loadingHistory.value) return
  conversationId.value = null
  messages.value = []
  input.value = ''
}

async function send(text?: string): Promise<void> {
  const content = (text ?? input.value).trim()
  if (!content || sending.value || loadingHistory.value) return

  input.value = ''
  addMessage('user', content)
  await runTurn(content)
}

async function retryMessage(bubble: ChatBubble): Promise<void> {
  if (sending.value || !bubble.retry) return
  const prompt = bubble.retry
  messages.value = messages.value.filter((item) => item.id !== bubble.id)
  await runTurn(prompt)
}

function stopGenerating(): void {
  if (!sending.value) return
  stopRequested = true
  activeController?.abort()
}

async function runTurn(content: string): Promise<void> {
  sending.value = true
  stopRequested = false
  await scrollToBottom()

  const streamState: { bubbleId: number | null } = { bubbleId: null }
  let completed = false
  const controller = new AbortController()
  activeController = controller
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
        } else if (event === 'delta') {
          const target = ensureBubble()
          target.content += String(data.content ?? '')
          void scrollToBottom()
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
          const target = ensureBubble()
          target.content = String(
            data.message ?? '助手暂时不可用，请稍后再试。',
          )
          target.retry = content
          streamingBubbleId.value = null
        }
      },
      { signal: controller.signal },
    )
    if (!completed) throw new Error('流式响应未完成')
  } catch {
    const failed =
      streamState.bubbleId === null
        ? undefined
        : messages.value.find((item) => item.id === streamState.bubbleId)
    if (stopRequested) {
      if (failed) {
        failed.stopped = true
        failed.retry = content
        if (!failed.content) failed.content = '已停止生成。'
      } else {
        addMessage('assistant', '已停止生成。', {
          stopped: true,
          retry: content,
        })
      }
    } else if (failed && !failed.content) {
      failed.content = failureText
      failed.retry = content
    } else if (!failed) {
      addMessage('assistant', failureText, { retry: content })
    }
  } finally {
    window.clearTimeout(timer)
    if (activeController === controller) activeController = null
    streamingBubbleId.value = null
    sending.value = false
    // 停止或失败时用户消息可能已经落库，刷新一次侧栏。
    void loadConversations()
    await scrollToBottom()
  }
}

async function copyMessage(bubble: ChatBubble): Promise<void> {
  if (!bubble.content) return
  try {
    await navigator.clipboard.writeText(bubble.content)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = bubble.content
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copiedId.value = bubble.id
  window.clearTimeout(copyTimer)
  copyTimer = window.setTimeout(() => {
    copiedId.value = null
  }, 1500)
}

function draftRemaining(draft: BoardingDraft): number {
  return Math.ceil((new Date(draft.expires_at).getTime() - now.value) / 60_000)
}

function draftExpired(draft: BoardingDraft): boolean {
  return new Date(draft.expires_at).getTime() <= now.value
}

function draftHint(draft: BoardingDraft): string {
  const minutes = draftRemaining(draft)
  return minutes > 0 ? `剩余 ${minutes} 分钟` : '草稿已过期'
}

function onInputKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  void send()
}

function goConfirm(): void {
  router.push('/boarding')
}

function fitChat(): void {
  if (!chatShellRef.value) return
  const top = chatShellRef.value.getBoundingClientRect().top + window.scrollY
  chatHeight.value = Math.max(280, window.innerHeight - top - 16)
}

onMounted(() => {
  void nextTick(fitChat)
  window.addEventListener('resize', fitChat)
  void loadConversations()
  clockTimer = window.setInterval(() => {
    now.value = Date.now()
  }, 30_000)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', fitChat)
  window.clearInterval(clockTimer)
  window.clearTimeout(copyTimer)
  activeController?.abort()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="title-row">
          <h1 class="page-title">智能助手</h1>
          <span class="pill sage">宠物护理与寄养</span>
        </div>
        <p class="page-subtitle">
          用自然语言查询档案、检查寄养空档，并把预约整理成可确认的草稿。
        </p>
      </div>
      <n-button quaternary size="small" :disabled="sending" @click="startNewConversation">
        <template #icon><AppIcon name="plus" :size="14" /></template>
        新对话
      </n-button>
    </div>

    <div class="agent-grid">
      <section ref="chatShellRef" class="chat-shell" :style="chatHeight === null ? undefined : { height: `${chatHeight}px` }">
        <header class="chat-head">
          <div class="assistant">
            <span class="assistant-avatar"><AppIcon name="paw" :size="19" /></span>
            <div>
              <strong>PawCare 助手</strong>
              <small>权限感知 · 草稿确认 · 可追溯</small>
            </div>
          </div>
          <span class="agent-status" :class="{ busy: sending }">
            <span class="status-mark" />
            {{ sending ? '思考中' : '在线' }}
          </span>
        </header>

        <div ref="bodyRef" class="chat-body">
          <template v-if="showWelcome">
            <div class="assistant-bubble">
              <p>
                你好，我是 PawCare 助手。可以帮你查宠物档案、健康记录和疫苗提醒，
                检索护理知识，也能查询寄养空档并生成预约草稿。
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
            <span v-if="bubble.role === 'assistant'" class="bubble-avatar">
              <AppIcon name="paw" :size="14" />
            </span>
            <div class="bubble" :class="bubble.role">
              <small v-if="bubble.createdAt" class="message-time">{{ formatTime(bubble.createdAt) }}{{ bubble.historical ? ' · 历史消息，信息以当时为准' : '' }}</small>
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
                <BoardingHealthCard v-if="bubble.draft.health_check" :check="bubble.draft.health_check" />
                <div class="draft-foot">
                  <span>{{ draftHint(bubble.draft) }}，确认后才会生成订单</span>
                  <n-button
                    size="small"
                    type="primary"
                    :disabled="draftExpired(bubble.draft)"
                    @click="goConfirm"
                  >
                    {{ draftExpired(bubble.draft) ? '草稿已过期' : '去寄养页确认' }}
                  </n-button>
                </div>
              </div>

              <div v-if="bubble.traceId" class="trace">
                追踪 ID · {{ bubble.traceId.slice(0, 8) }}
              </div>

              <div
                v-if="
                  bubble.role === 'assistant' &&
                  bubble.content &&
                  bubble.id !== streamingBubbleId
                "
                class="bubble-tools"
              >
                <button
                  type="button"
                  class="bubble-tool"
                  @click="copyMessage(bubble)"
                >
                  {{ copiedId === bubble.id ? '已复制' : '复制' }}
                </button>
                <button v-if="bubble.historical" class="bubble-tool" :disabled="sending" @click="input = '请重新查询最新状态：' + (messages.slice(0, messages.indexOf(bubble)).reverse().find(item => item.role === 'user')?.content ?? '当前宠物的健康提醒')">重新查询最新状态</button>
                <button
                  v-if="bubble.retry"
                  type="button"
                  class="bubble-tool"
                  @click="retryMessage(bubble)"
                >
                  重试
                </button>
                <span
                  v-if="bubble.stopped && bubble.content !== '已停止生成。'"
                  class="bubble-stopped"
                >
                  已停止生成
                </span>
              </div>
            </div>
          </div>

          <div v-if="sending && streamingBubbleId === null" class="bubble-row assistant">
            <span class="bubble-avatar"><AppIcon name="paw" :size="14" /></span>
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
            v-if="sending"
            size="large"
            secondary
            class="stop-button"
            @click="stopGenerating"
          >
            <template #icon><AppIcon name="stop" :size="14" /></template>
            停止
          </n-button>
          <n-button
            v-else
            type="primary"
            size="large"
            :disabled="!canSend"
            @click="send()"
          >
            <template #icon><AppIcon name="send" :size="15" /></template>
            发送
          </n-button>
        </footer>
      </section>

      <aside class="side">
        <details class="side-details">
          <summary>对话记录与使用说明</summary>
        <section class="side-card">
          <div class="side-head">
            <h2 class="section-title">对话记录</h2>
            <span class="side-count">{{ conversations.length }}</span>
          </div>
          <div v-if="conversations.length === 0" class="empty-history">
            还没有对话，可以从示例问题开始。
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

        <section class="side-card">
          <h2 class="section-title">能做什么</h2>
          <div class="capability-list">
            <article v-for="item in capabilities" :key="item.title" class="capability">
              <span class="capability-icon">
                <AppIcon :name="item.icon" :size="15" />
              </span>
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.text }}</p>
              </div>
            </article>
          </div>
        </section>

        <section class="side-card">
          <h2 class="section-title">使用边界</h2>
          <ul class="boundaries">
            <li v-for="item in boundaries" :key="item">
              <AppIcon name="shield" :size="13" />
              <span>{{ item }}</span>
            </li>
          </ul>
        </section>
        </details>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.message-time { display: block; color: var(--pc-ink-soft); margin-bottom: 8px; font-size: 11px; }
.chat-head, .chat-input { flex-shrink: 0; }
.side-details > summary { cursor: pointer; padding: 16px; border: 1px solid var(--pc-line); border-radius: var(--pc-radius); font-size: 13px; color: var(--pc-primary); background: var(--pc-surface); }
.side-details[open] > summary { margin-bottom: 12px; }
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
  gap: 14px;
  align-items: start;
}

.chat-shell {
  display: flex;
  height: calc(100vh - 190px);
  min-height: 280px;
  height: calc(100dvh - 200px);
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--pc-line);
}

.assistant {
  display: flex;
  align-items: center;
  gap: 10px;
}

.assistant-avatar {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid #cfdfd8;
  border-radius: var(--pc-radius-sm);
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
}

.assistant strong {
  display: block;
  font-size: 13.5px;
  font-weight: 650;
}

.assistant small {
  display: block;
  margin-top: 2px;
  color: var(--pc-ink-faint);
  font-size: 11px;
}

.agent-status {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  color: var(--pc-ok);
  font-size: 11.5px;
  font-weight: 600;
  white-space: nowrap;
}

.status-mark {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pc-ok);
}

.agent-status.busy {
  color: var(--pc-warn);
}

.agent-status.busy .status-mark {
  background: var(--pc-warn);
}

.chat-body {
  min-height: 0;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
  padding: 20px 18px;
  background: #fbfbf8;
  scroll-behavior: smooth;
}

.assistant-bubble {
  max-width: 640px;
  padding: 14px 16px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius-sm);
  background: var(--pc-surface);
}

.assistant-bubble p {
  margin: 0;
  font-size: 13px;
  line-height: 1.75;
}

.bubble-note {
  margin-top: 10px !important;
  padding-top: 10px;
  border-top: 1px solid var(--pc-line);
  color: var(--pc-ink-soft);
  font-size: 11.5px !important;
}

.examples {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
}

.examples-label {
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.example-chip {
  padding: 8px 12px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius-sm);
  background: var(--pc-surface);
  color: var(--pc-ink-soft);
  font-size: 12.5px;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.14s ease,
    background 0.14s ease,
    color 0.14s ease;
}

.example-chip:hover:not(:disabled) {
  border-color: var(--pc-primary);
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
}

.example-chip:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.bubble-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.bubble-row.user {
  justify-content: flex-end;
}

.bubble-avatar {
  display: grid;
  width: 26px;
  height: 26px;
  flex: 0 0 26px;
  margin-top: 2px;
  place-items: center;
  border: 1px solid var(--pc-line);
  border-radius: 5px;
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
}

.bubble {
  max-width: 76%;
  padding: 11px 14px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius-sm);
  background: var(--pc-surface);
  font-size: 13px;
  line-height: 1.72;
}

.bubble.user {
  border-color: var(--pc-primary);
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
  color: var(--pc-ink-faint);
  font-size: 11.5px;
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
  color: var(--pc-ink-faint);
  font-size: 11.5px;
  text-align: center;
}

.tool-events {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 9px;
  padding-top: 9px;
  border-top: 1px solid var(--pc-line);
}

.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border: 1px solid var(--pc-line);
  border-radius: 4px;
  background: var(--pc-surface-muted);
  color: var(--pc-ink-soft);
  font-size: 10.5px;
  font-weight: 600;
}

.tool-chip.error {
  border-color: #e4c7c2;
  background: var(--pc-danger-soft);
  color: var(--pc-danger);
}

.tool-chip.running {
  border-color: #e6d7bd;
  background: var(--pc-warn-soft);
  color: var(--pc-warn);
}

.tool-chip.running em {
  color: #a9834f;
}

.tool-mark {
  font-size: 9.5px;
}

.tool-chip em {
  color: var(--pc-ink-faint);
  font-style: normal;
  font-weight: 400;
}

.tool-chip.error em {
  color: #b98a7d;
}

.draft-card {
  margin-top: 11px;
  padding: 12px 14px;
  border: 1px solid #cfdfd8;
  border-radius: var(--pc-radius-sm);
  background: #f4f8f6;
}

.draft-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.draft-head strong {
  font-size: 12.5px;
  font-weight: 650;
}

.draft-badge {
  padding: 1px 7px;
  border: 1px solid #cfdfd8;
  border-radius: 4px;
  background: var(--pc-surface);
  color: var(--pc-primary);
  font-size: 10px;
  font-weight: 700;
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
  color: var(--pc-ink-faint);
  font-size: 10px;
}

.draft-grid strong {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

.draft-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 11px;
  padding-top: 10px;
  border-top: 1px solid #dbe8e2;
}

.draft-foot span {
  color: var(--pc-ink-faint);
  font-size: 10px;
}

.trace {
  margin-top: 7px;
  color: var(--pc-ink-faint);
  font-size: 10px;
  letter-spacing: 0.02em;
}

.bubble.user .trace {
  color: rgba(255, 255, 255, 0.65);
}

.bubble-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.bubble-tool {
  padding: 0;
  border: 0;
  background: none;
  color: var(--pc-ink-faint);
  font: inherit;
  font-size: 11px;
  cursor: pointer;
}

.bubble-tool:hover {
  color: var(--pc-primary);
}

.bubble-tool:focus-visible {
  border-radius: 2px;
  outline: 2px solid var(--pc-primary);
  outline-offset: 2px;
}

.bubble-stopped {
  color: var(--pc-warn);
  font-size: 11px;
}

.stop-button {
  --n-text-color: var(--pc-danger);
}

.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 14px 16px;
}

.typing span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--pc-line-strong);
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
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--pc-line);
  background: var(--pc-surface);
}

.chat-input :deep(textarea) {
  resize: none;
}

.side {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.side-card {
  padding: 16px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.side-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  margin: 0;
  font-size: 13.5px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.side-count {
  color: var(--pc-ink-faint);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.empty-history {
  margin-top: 12px;
  padding: 16px 12px;
  border: 1px dashed var(--pc-line-strong);
  border-radius: var(--pc-radius-sm);
  color: var(--pc-ink-faint);
  font-size: 11.5px;
  line-height: 1.6;
  text-align: center;
}

.conversation-list {
  display: flex;
  max-height: 222px;
  flex-direction: column;
  gap: 3px;
  margin-top: 10px;
  overflow-y: auto;
}

.conversation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 9px;
  border: 0;
  border-left: 2px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: var(--pc-ink-soft);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.14s ease,
    color 0.14s ease;
}

.conversation-item:hover:not(:disabled) {
  background: var(--pc-surface-muted);
  color: var(--pc-ink);
}

.conversation-item.active {
  border-left-color: var(--pc-primary);
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
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
  color: var(--pc-ink-faint);
  font-size: 10px;
}

.capability-list {
  display: flex;
  flex-direction: column;
  gap: 13px;
  margin-top: 14px;
}

.capability {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.capability-icon {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  margin-top: 1px;
  place-items: center;
  border: 1px solid var(--pc-line);
  border-radius: 5px;
  background: var(--pc-surface-muted);
  color: var(--pc-primary);
}

.capability strong {
  font-size: 12.5px;
  font-weight: 650;
}

.capability p {
  margin: 3px 0 0;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
  line-height: 1.6;
}

.boundaries {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.boundaries li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: var(--pc-ink-soft);
  font-size: 11.5px;
  line-height: 1.6;
}

.boundaries svg {
  margin-top: 2px;
  color: var(--pc-primary);
}

@media (max-width: 1050px) {
  .agent-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .chat-shell {
    height: calc(100dvh - 200px);
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
