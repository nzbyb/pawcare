<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NButton,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NInput,
  NPagination,
  NSelect,
  NSpin,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'

import { getAgentOverview, getAgentTrace, listAgentToolCalls } from '@/api/admin'
import type {
  AgentOverview,
  AgentToolCallItem,
  AgentToolMetric,
  AgentTrace,
} from '@/types'

const message = useMessage()

const days = ref(7)
const overview = ref<AgentOverview | null>(null)
const loading = ref(false)
const failed = ref(false)

const callStatus = ref<'all' | 'ok' | 'error'>('all')
const callTool = ref<string | null>(null)
const keyword = ref('')
const callPage = ref(1)
const callPageSize = 10
const calls = ref<AgentToolCallItem[]>([])
const callsTotal = ref(0)
const callsLoading = ref(false)

const drawerOpen = ref(false)
const traceLoading = ref(false)
const trace = ref<AgentTrace | null>(null)

const dayOptions = [
  { label: '最近 7 天', value: 7 },
  { label: '最近 30 天', value: 30 },
  { label: '最近 90 天', value: 90 },
]
const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '成功', value: 'ok' },
  { label: '失败', value: 'error' },
]
const roleLabels: Record<string, string> = {
  user: '用户',
  assistant: '助手',
  tool: '工具结果',
  system: '系统',
}

const toolOptions = computed(() => [
  { label: '全部工具', value: '' },
  ...(overview.value?.tools ?? []).map(item => ({
    label: item.tool_name,
    value: item.tool_name,
  })),
])
const maxCalls = computed(() =>
  Math.max(1, ...(overview.value?.daily.map(row => Math.max(row.tool_calls, row.tool_errors)) ?? [])),
)
const successLabel = (rate: number | null) => (rate === null ? '—' : `${rate}%`)

function formatInt(value: number | null | undefined): string {
  return (value ?? 0).toLocaleString('zh-CN')
}

function formatTime(value?: string | null): string {
  if (!value) return '—'
  return value.slice(0, 16).replace('T', ' ')
}

function rateClass(rate: number | null): string {
  if (rate === null) return 'pill grey'
  if (rate >= 95) return 'pill sage'
  if (rate >= 80) return 'pill amber'
  return 'pill red'
}

async function loadOverview(): Promise<void> {
  loading.value = true
  failed.value = false
  try {
    overview.value = await getAgentOverview(days.value)
    if (callTool.value && !overview.value.tools.some(item => item.tool_name === callTool.value)) {
      callTool.value = null
    }
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function loadCalls(): Promise<void> {
  callsLoading.value = true
  try {
    const result = await listAgentToolCalls({
      status: callStatus.value === 'all' ? undefined : callStatus.value,
      tool_name: callTool.value || undefined,
      keyword: keyword.value.trim() || undefined,
      days: days.value,
      page: callPage.value,
      page_size: callPageSize,
    })
    calls.value = result.items
    callsTotal.value = result.total
  } catch {
    calls.value = []
    callsTotal.value = 0
  } finally {
    callsLoading.value = false
  }
}

function searchCalls(): void {
  callPage.value = 1
  void loadCalls()
}

async function reload(): Promise<void> {
  callPage.value = 1
  await Promise.all([loadOverview(), loadCalls()])
}

async function openTrace(traceId: string): Promise<void> {
  drawerOpen.value = true
  traceLoading.value = true
  trace.value = null
  try {
    trace.value = await getAgentTrace(traceId)
  } catch {
    message.error('trace 回放加载失败')
    drawerOpen.value = false
  } finally {
    traceLoading.value = false
  }
}

const toolColumns: DataTableColumns<AgentToolMetric> = [
  { title: '工具', key: 'tool_name', minWidth: 150 },
  { title: '调用', key: 'calls', width: 72, align: 'right' },
  { title: '失败', key: 'errors', width: 72, align: 'right' },
  {
    title: '成功率',
    key: 'success_rate',
    width: 96,
    render: row => h('span', { class: rateClass(row.success_rate) }, successLabel(row.success_rate)),
  },
  { title: '平均延迟', key: 'avg_latency_ms', width: 100, align: 'right', render: row => `${row.avg_latency_ms} ms` },
  { title: '最慢', key: 'max_latency_ms', width: 100, align: 'right', render: row => `${row.max_latency_ms} ms` },
]

const callColumns: DataTableColumns<AgentToolCallItem> = [
  {
    title: '状态',
    key: 'status',
    width: 76,
    render: row =>
      h('span', { class: row.status === 'ok' ? 'pill sage' : 'pill red' }, row.status === 'ok' ? '成功' : '失败'),
  },
  { title: '工具', key: 'tool_name', minWidth: 140 },
  { title: '延迟', key: 'latency_ms', width: 90, align: 'right', render: row => `${row.latency_ms ?? 0} ms` },
  {
    title: '错误码',
    key: 'error_code',
    width: 130,
    render: row => row.error_code ?? '—',
  },
  {
    title: 'trace',
    key: 'trace_id',
    width: 110,
    render: row =>
      h(
        NButton,
        { size: 'tiny', text: true, type: 'primary', onClick: () => void openTrace(row.trace_id) },
        () => row.trace_id.slice(0, 8),
      ),
  },
  { title: '时间', key: 'create_time', width: 150, render: row => formatTime(row.create_time) },
]

onMounted(reload)
</script>

<template>
  <section class="agent-metrics soft-card">
    <header>
      <div>
        <h2 class="section-title">Agent 运行</h2>
        <p class="muted">
          {{ overview?.range.start_date }} → {{ overview?.range.end_date }} ·
          数据来自会话落库的工具调用与模型用量，只读聚合
        </p>
      </div>
      <div class="head-actions">
        <n-select v-model:value="days" :options="dayOptions" style="width: 130px" @update:value="reload" />
        <n-button size="small" :loading="loading || callsLoading" @click="reload">刷新</n-button>
      </div>
    </header>

    <n-spin :show="loading">
      <div v-if="failed" class="failed" role="alert">
        指标加载失败 <n-button size="small" @click="reload">重试</n-button>
      </div>
      <template v-else-if="overview">
        <div class="metrics">
          <div>
            <span>会话 / 轮次</span>
            <strong>{{ formatInt(overview.conversations) }} / {{ formatInt(overview.turns) }}</strong>
            <small>按所选区间内有消息的会话统计</small>
          </div>
          <div>
            <span>工具调用 / 成功率</span>
            <strong>{{ formatInt(overview.tool_calls) }} / {{ successLabel(overview.tool_success_rate) }}</strong>
            <small>失败 {{ formatInt(overview.tool_errors) }} 次</small>
          </div>
          <div>
            <span>工具延迟 P50 / P95</span>
            <strong>{{ overview.tool_latency_p50_ms ?? '—' }} / {{ overview.tool_latency_p95_ms ?? '—' }} ms</strong>
            <small>整轮（含模型）P95 {{ overview.turn_latency_p95_ms ?? '—' }} ms</small>
          </div>
          <div>
            <span>Token 输入 / 输出</span>
            <strong>{{ formatInt(overview.tokens.input) }} / {{ formatInt(overview.tokens.output) }}</strong>
            <small>
              <template v-if="overview.cost.configured">
                估算成本 ¥{{ overview.cost.total.toFixed(4) }}（¥{{ overview.cost.price_input_per_m }}/¥{{ overview.cost.price_output_per_m }} 每百万 token）
              </template>
              <template v-else>未配置单价，不计成本（见 .env 中 LLM_PRICE_*）</template>
            </small>
          </div>
        </div>

        <div class="chart-block">
          <p class="muted">每日工具调用（实心）与失败（斜纹）</p>
          <svg viewBox="0 0 600 120" role="img" aria-label="所选区间每日工具调用与失败次数的柱状图">
            <line x1="0" y1="100" x2="600" y2="100" stroke="var(--pc-line)" />
            <g v-for="(row, index) in overview.daily" :key="row.date">
              <rect
                :x="index * 600 / overview.daily.length + 3"
                :y="100 - row.tool_calls / maxCalls * 85"
                :width="Math.max(2, 600 / overview.daily.length - 8)"
                :height="Math.max(0, row.tool_calls / maxCalls * 85)"
                rx="2"
                fill="var(--pc-primary)"
              >
                <title>{{ row.date }}：调用 {{ row.tool_calls }} 次，失败 {{ row.tool_errors }} 次，{{ row.turns }} 轮</title>
              </rect>
              <rect
                :x="index * 600 / overview.daily.length + 3"
                :y="100 - row.tool_errors / maxCalls * 85"
                :width="Math.max(2, 600 / overview.daily.length - 8)"
                :height="Math.max(0, row.tool_errors / maxCalls * 85)"
                rx="2"
                fill="var(--pc-danger)"
                opacity="0.55"
              >
                <title>{{ row.date }}：失败 {{ row.tool_errors }} 次</title>
              </rect>
            </g>
            <text x="0" y="117">{{ overview.range.start_date }}</text>
            <text x="600" y="117" text-anchor="end">{{ overview.range.end_date }}</text>
          </svg>
        </div>

        <div class="split">
          <div class="panel">
            <h3>按工具聚合</h3>
            <n-data-table
              :columns="toolColumns"
              :data="overview.tools"
              :bordered="false"
              size="small"
              :row-key="(row: AgentToolMetric) => row.tool_name"
            />
            <p v-if="!overview.tools.length" class="muted empty">区间内还没有工具调用。</p>
          </div>
          <div class="panel">
            <h3>最近失败</h3>
            <ul v-if="overview.recent_failures.length" class="failures">
              <li v-for="row in overview.recent_failures" :key="row.id">
                <div>
                  <strong>{{ row.tool_name }}</strong>
                  <span class="pill red">{{ row.error_code || '未知错误' }}</span>
                </div>
                <div class="fail-meta">
                  <span>{{ row.latency_ms ?? 0 }} ms · {{ formatTime(row.create_time) }}</span>
                  <n-button size="tiny" text type="primary" @click="openTrace(row.trace_id)">回放 trace</n-button>
                </div>
              </li>
            </ul>
            <p v-else class="muted empty">区间内没有失败调用。</p>
            <div v-if="overview.error_codes.length" class="error-codes">
              <span v-for="item in overview.error_codes" :key="item.error_code" class="pill amber">
                {{ item.error_code }} × {{ item.count }}
              </span>
            </div>
          </div>
        </div>

        <div class="panel calls">
          <div class="calls-head">
            <h3>工具调用明细</h3>
            <div class="filters">
              <n-select v-model:value="callStatus" :options="statusOptions" style="width: 110px" @update:value="searchCalls" />
              <n-select v-model:value="callTool" :options="toolOptions" style="width: 150px" @update:value="searchCalls" />
              <n-input
                v-model:value="keyword"
                placeholder="按 trace_id 搜索"
                clearable
                style="width: 190px"
                @keyup.enter="searchCalls"
                @clear="searchCalls"
              />
              <n-button size="small" @click="searchCalls">查询</n-button>
            </div>
          </div>
          <n-data-table
            :columns="callColumns"
            :data="calls"
            :loading="callsLoading"
            :bordered="false"
            size="small"
            :row-key="(row: AgentToolCallItem) => row.id"
            :scroll-x="760"
          />
          <div class="pager">
            <n-pagination
              v-model:page="callPage"
              :page-size="callPageSize"
              :item-count="callsTotal"
              @update:page="loadCalls"
            />
          </div>
        </div>
      </template>
    </n-spin>

    <n-drawer v-model:show="drawerOpen" :width="680" placement="right">
      <n-drawer-content closable :title="trace ? `Trace ${trace.trace_id.slice(0, 12)}` : 'Trace 回放'">
        <n-spin :show="traceLoading">
          <div v-if="trace" class="trace">
            <div class="trace-head">
              <div v-if="trace.conversation">
                <strong>{{ trace.conversation.title }}</strong>
                <p class="muted">
                  {{ trace.conversation.nickname || trace.conversation.username }} ·
                  {{ trace.conversation.username }} · 会话 #{{ trace.conversation.id }}
                </p>
              </div>
              <div class="trace-chips">
                <span :class="trace.summary.status === 'ok' ? 'pill sage' : 'pill red'">
                  {{ trace.summary.status === 'ok' ? '成功' : '含失败' }}
                </span>
                <span class="pill grey">工具 {{ trace.summary.tool_calls }}</span>
                <span class="pill grey">失败 {{ trace.summary.errors }}</span>
                <span class="pill grey">{{ trace.summary.latency_ms }} ms</span>
                <span class="pill grey">token {{ trace.summary.token_in }} / {{ trace.summary.token_out }}</span>
              </div>
            </div>

            <ol class="timeline">
              <li v-for="item in trace.messages" :key="item.id" :class="['trace-msg', item.role]">
                <div class="msg-head">
                  <span class="pill grey">{{ roleLabels[item.role] || item.role }}</span>
                  <span class="muted">
                    <template v-if="item.latency_ms !== null">{{ item.latency_ms }} ms · </template>
                    <template v-if="item.token_in || item.token_out">
                      token {{ item.token_in ?? 0 }} / {{ item.token_out ?? 0 }}
                    </template>
                  </span>
                </div>
                <pre class="msg-content">{{ item.content || '（空）' }}</pre>
                <div v-if="item.tool_calls" class="msg-tools">
                  <span class="muted">本轮发起的工具调用：</span>
                  <code>{{ JSON.stringify(item.tool_calls) }}</code>
                </div>
              </li>
            </ol>

            <div v-if="trace.tool_calls.length" class="trace-tools">
              <h3>工具调用</h3>
              <div v-for="row in trace.tool_calls" :key="row.id" class="trace-tool">
                <div class="msg-head">
                  <strong>{{ row.tool_name }}</strong>
                  <span :class="row.status === 'ok' ? 'pill sage' : 'pill red'">
                    {{ row.status === 'ok' ? '成功' : row.error_code || '失败' }}
                  </span>
                  <span class="muted">{{ row.latency_ms ?? 0 }} ms</span>
                </div>
                <p class="muted">参数</p>
                <pre class="msg-content">{{ JSON.stringify(row.arguments ?? {}, null, 2) }}</pre>
                <p class="muted">结果摘要</p>
                <pre class="msg-content">{{ row.result_summary || '（空）' }}</pre>
              </div>
            </div>
          </div>
        </n-spin>
      </n-drawer-content>
    </n-drawer>
  </section>
</template>

<style scoped>
.agent-metrics { padding: 20px; margin: 12px 0 28px; }
header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.head-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
p, small { font-size: 12px; line-height: 1.7; }
.metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 20px 0; }
.metrics div { display: flex; flex-direction: column; gap: 6px; }
.metrics span, small { color: var(--pc-ink-soft); font-size: 12px; }
strong { font-size: 18px; overflow-wrap: anywhere; }
.chart-block { margin-bottom: 20px; }
svg { width: 100%; max-height: 150px; }
text { font-size: 10px; fill: var(--pc-ink-soft); }
.split { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 16px; margin-bottom: 20px; }
.panel { border: 1px solid var(--pc-line); border-radius: var(--pc-radius); padding: 14px; min-width: 0; }
.panel h3 { margin: 0 0 10px; font-size: 13px; }
.failures { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.failures li { border-bottom: 1px solid var(--pc-line); padding-bottom: 8px; display: flex; flex-direction: column; gap: 4px; }
.failures li:last-child { border-bottom: none; padding-bottom: 0; }
.failures li > div { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.fail-meta { justify-content: space-between; }
.fail-meta span { font-size: 12px; color: var(--pc-ink-soft); }
.error-codes { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.calls { margin-top: 4px; }
.calls-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.calls-head h3 { margin: 0; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.pager { display: flex; justify-content: flex-end; margin-top: 12px; }
.empty { padding: 6px 0; }
.failed { display: flex; gap: 12px; align-items: center; padding: 16px 0; }
.trace-head { border-bottom: 1px solid var(--pc-line); padding-bottom: 12px; margin-bottom: 12px; }
.trace-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.timeline { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.trace-msg { border-left: 2px solid var(--pc-line); padding-left: 12px; }
.trace-msg.assistant { border-left-color: var(--pc-primary); }
.trace-msg.tool { border-left-color: var(--pc-warn); }
.msg-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.msg-content {
  margin: 0;
  padding: 10px;
  background: var(--pc-surface-muted);
  border-radius: var(--pc-radius);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 220px;
  overflow: auto;
}
.msg-tools { margin-top: 6px; font-size: 12px; }
.msg-tools code { overflow-wrap: anywhere; }
.trace-tools { margin-top: 20px; }
.trace-tools h3 { font-size: 13px; }
.trace-tool { border-top: 1px solid var(--pc-line); padding: 12px 0; }
@media (max-width: 900px) {
  .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .split { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 500px) {
  header, .calls-head { align-items: flex-start; flex-direction: column; }
}
</style>
