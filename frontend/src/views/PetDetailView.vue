<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NDatePicker,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NSelect,
  NSpin,
  NTabPane,
  NTabs,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

import {
  createHealthRecord,
  deleteHealthRecord,
  listHealthRecords,
  listReminders,
  updateReminder,
} from '@/api/health'
import { addWeight, getPet, listWeights } from '@/api/pets'
import PetFormModal from '@/components/PetFormModal.vue'
import type {
  HealthRecord,
  HealthRecordType,
  Pet,
  Reminder,
  WeightRecord,
} from '@/types'
import {
  daysUntil,
  dueLabel,
  formatDate,
  genderLabel,
  petAge,
  recordTypeLabel,
  speciesLabel,
  today,
} from '@/utils/format'

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const route = useRoute()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const petId = Number(route.params.id)

const pet = ref<Pet | null>(null)
const weights = ref<WeightRecord[]>([])
const records = ref<HealthRecord[]>([])
const reminders = ref<Reminder[]>([])
const loading = ref(true)
const activeTab = ref<string | number>('weight')
const showEdit = ref(false)
const showHealthModal = ref(false)
const showWeightModal = ref(false)
const savingHealth = ref(false)
const reminderBusy = ref<{ id: number; action: 'done' | 'snooze' } | null>(null)
const savingWeight = ref(false)
const chartRef = ref<HTMLDivElement | null>(null)

let chart: ReturnType<typeof echarts.init> | null = null

interface HealthFormState {
  record_type: string
  title: string
  record_date: string | null
  next_due_date: string | null
  note: string
}

interface WeightFormState {
  record_date: string | null
  weight_kg: number | null
  note: string
}

const healthForm = reactive<HealthFormState>({
  record_type: 'vaccine',
  title: '',
  record_date: today(),
  next_due_date: null,
  note: '',
})

const weightForm = reactive<WeightFormState>({
  record_date: today(),
  weight_kg: null,
  note: '',
})

const recordTypeOptions = [
  { label: '疫苗', value: 'vaccine' },
  { label: '驱虫', value: 'deworm' },
  { label: '用药', value: 'medication' },
  { label: '就诊', value: 'visit' },
  { label: '症状', value: 'symptom' },
]

const latestWeight = computed(() =>
  weights.value.length ? weights.value[weights.value.length - 1] : null,
)

const nextReminder = computed(() =>
  reminders.value.length ? reminders.value[0] : null,
)

function recordTagType(recordType: string): 'success' | 'info' | 'warning' | 'error' | 'default' {
  const map: Record<
    string,
    'success' | 'info' | 'warning' | 'error' | 'default'
  > = {
    vaccine: 'success',
    deworm: 'info',
    medication: 'warning',
    visit: 'default',
    symptom: 'error',
  }
  return map[recordType] ?? 'default'
}

async function load(): Promise<void> {
  if (!Number.isFinite(petId) || petId <= 0) {
    message.error('无效的宠物编号')
    router.replace('/pets')
    return
  }

  loading.value = true
  try {
    const [petData, weightData, recordData, reminderData] = await Promise.all([
      getPet(petId),
      listWeights(petId),
      listHealthRecords(petId),
      listReminders(petId),
    ])
    pet.value = petData
    weights.value = weightData
    records.value = recordData
    reminders.value = reminderData
  } catch {
    router.replace('/pets')
  } finally {
    loading.value = false
  }
}

async function handleReminder(
  reminder: Reminder,
  action: 'done' | 'snooze',
): Promise<void> {
  if (!pet.value || reminderBusy.value) return
  reminderBusy.value = { id: reminder.id, action }
  try {
    const updated = await updateReminder(
      pet.value.id,
      reminder.id,
      action === 'done' ? { status: 'done' } : { snooze_days: 7 },
    )
    if (action === 'done') {
      reminders.value = reminders.value.filter((item) => item.id !== reminder.id)
      message.success('已标记完成')
    } else {
      reminders.value = reminders.value
        .map((item) => (item.id === reminder.id ? updated : item))
        .sort((a, b) => a.due_date.localeCompare(b.due_date))
      message.success('已延后 7 天')
    }
  } catch {
    // 错误提示由 http 拦截器统一展示。
  } finally {
    reminderBusy.value = null
  }
}

function ensureChart(): ReturnType<typeof echarts.init> | null {
  if (!chartRef.value) return null
  if (chart && chart.getDom() !== chartRef.value) {
    chart.dispose()
    chart = null
  }
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }
  return chart
}

function renderChart(): void {
  const instance = ensureChart()
  if (!instance) return

  instance.setOption(
    {
      grid: { left: 50, right: 20, top: 30, bottom: 34 },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: weights.value.map((item) => item.record_date),
        axisLine: { lineStyle: { color: '#e2e2db' } },
        axisTick: { show: false },
        axisLabel: { color: '#8a8e84', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { color: '#efefe9' } },
        axisLabel: { color: '#8a8e84', fontSize: 11, formatter: '{value} kg' },
      },
      series: [
        {
          name: '体重',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
          data: weights.value.map((item) => item.weight_kg),
          lineStyle: { width: 2, color: '#2F5D50' },
          itemStyle: {
            color: '#2F5D50',
            borderColor: '#ffffff',
            borderWidth: 2,
          },
          areaStyle: { color: 'rgba(47, 93, 80, 0.08)' },
        },
      ],
    },
    true,
  )
}

function onTabChange(key: string | number): void {
  activeTab.value = key
  if (key === 'weight') {
    nextTick(renderChart)
  }
}

function openHealthModal(): void {
  healthForm.record_type = 'vaccine'
  healthForm.title = ''
  healthForm.record_date = today()
  healthForm.next_due_date = null
  healthForm.note = ''
  showHealthModal.value = true
}

function openWeightModal(): void {
  weightForm.record_date = today()
  weightForm.weight_kg = latestWeight.value?.weight_kg ?? null
  weightForm.note = ''
  showWeightModal.value = true
}

async function saveHealthRecord(): Promise<void> {
  if (!healthForm.title.trim()) {
    message.warning('请填写记录标题')
    return
  }
  const recordDate = healthForm.record_date
  if (!recordDate) {
    message.warning('请选择记录日期')
    return
  }

  savingHealth.value = true
  try {
    await createHealthRecord(petId, {
      record_type: healthForm.record_type as HealthRecordType,
      title: healthForm.title.trim(),
      record_date: recordDate,
      next_due_date: healthForm.next_due_date || null,
      note: healthForm.note.trim() || null,
    })
    message.success('健康记录已保存')
    showHealthModal.value = false
    await load()
  } catch {
    // http 拦截器已经提示
  } finally {
    savingHealth.value = false
  }
}

async function saveWeight(): Promise<void> {
  const recordDate = weightForm.record_date
  const weight = weightForm.weight_kg
  if (!recordDate) {
    message.warning('请选择记录日期')
    return
  }
  if (weight === null || weight <= 0) {
    message.warning('请填写有效体重')
    return
  }

  savingWeight.value = true
  try {
    await addWeight(petId, {
      record_date: recordDate,
      weight_kg: weight,
      note: weightForm.note.trim() || null,
    })
    message.success('体重已记录')
    showWeightModal.value = false
    await load()
  } catch {
    // http 拦截器已经提示
  } finally {
    savingWeight.value = false
  }
}

function confirmDeleteRecord(record: HealthRecord): void {
  dialog.warning({
    title: '删除健康记录',
    content: `确定删除「${record.title}」吗？相关待处理提醒也会一并关闭。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteHealthRecord(record.id)
        message.success('健康记录已删除')
        await load()
      } catch {
        // http 拦截器已经提示
      }
    },
  })
}

function onPetSaved(updated: Pet): void {
  pet.value = updated
}

function onResize(): void {
  chart?.resize()
}

watch(weights, () => {
  if (activeTab.value === 'weight') {
    nextTick(renderChart)
  }
})

onMounted(() => {
  window.addEventListener('resize', onResize)
  void load()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="page">
    <n-spin :show="loading">
      <template v-if="pet">
        <div class="back-row">
          <router-link to="/pets" class="back-link">← 返回宠物列表</router-link>
        </div>

        <section class="pet-hero soft-card fade-up">
          <div class="hero-main">
            <div class="avatar">
              <strong>{{ pet.name.slice(0, 1) }}</strong>
              <small>{{ pet.species === 'cat' ? 'CAT' : pet.species === 'dog' ? 'DOG' : 'PET' }}</small>
            </div>
            <div class="hero-info">
              <div class="name-row">
                <h1>{{ pet.name }}</h1>
                <span v-if="pet.neutered" class="pill sage">已绝育</span>
              </div>
              <p class="meta-line">
                {{ speciesLabel(pet.species) }}
                <span v-if="pet.breed"> · {{ pet.breed }}</span>
                · {{ genderLabel(pet.gender) }}
                · {{ petAge(pet.birthday) }}
              </p>
              <div class="hero-tags">
                <span class="pill grey">生日 {{ formatDate(pet.birthday) }}</span>
                <span v-if="pet.allergies" class="pill">
                  过敏：{{ pet.allergies }}
                </span>
              </div>
            </div>
          </div>

          <div class="hero-side">
            <div class="mini-stat">
              <span>最近体重</span>
              <strong>
                {{ latestWeight ? `${latestWeight.weight_kg} kg` : '—' }}
              </strong>
            </div>
            <div class="mini-stat">
              <span>下次提醒</span>
              <strong>
                {{ nextReminder ? dueLabel(nextReminder.due_date) : '暂无' }}
              </strong>
            </div>
            <n-button size="small" @click="showEdit = true">编辑档案</n-button>
          </div>
        </section>

        <section v-if="pet.notes" class="note-card soft-card fade-up delay-1">
          <strong>备注</strong>
          <p>{{ pet.notes }}</p>
        </section>

        <section class="tab-shell soft-card fade-up delay-2">
          <n-tabs
            :value="activeTab"
            type="line"
            animated
            @update:value="onTabChange"
          >
            <n-tab-pane name="weight" tab="体重趋势">
              <div class="tab-toolbar">
                <span class="muted">记录体重变化，观察长期趋势</span>
                <n-button size="small" type="primary" @click="openWeightModal">
                  + 记录体重
                </n-button>
              </div>

              <div v-if="weights.length" ref="chartRef" class="chart"></div>
              <n-empty
                v-else
                description="还没有体重记录"
                style="padding: 48px 0"
              />
            </n-tab-pane>

            <n-tab-pane name="health" tab="健康档案">
              <div class="tab-toolbar">
                <span class="muted">疫苗、驱虫、用药和就诊记录</span>
                <n-button size="small" type="primary" @click="openHealthModal">
                  + 新增记录
                </n-button>
              </div>

              <div v-if="records.length" class="record-list">
                <article
                  v-for="record in records"
                  :key="record.id"
                  class="record-item"
                >
                  <div class="record-head">
                    <div class="record-title">
                      <n-tag
                        size="small"
                        :type="recordTagType(record.record_type)"
                      >
                        {{ recordTypeLabel(record.record_type) }}
                      </n-tag>
                      <strong>{{ record.title }}</strong>
                    </div>
                    <n-button
                      text
                      type="error"
                      size="small"
                      @click="confirmDeleteRecord(record)"
                    >
                      删除
                    </n-button>
                  </div>
                  <div class="record-meta">
                    <span>记录日期 {{ formatDate(record.record_date) }}</span>
                    <span v-if="record.next_due_date">
                      下次 {{ formatDate(record.next_due_date) }}
                    </span>
                  </div>
                  <p v-if="record.note" class="record-note">{{ record.note }}</p>
                </article>
              </div>
              <n-empty
                v-else
                description="还没有健康记录"
                style="padding: 48px 0"
              />
            </n-tab-pane>

            <n-tab-pane name="reminders" tab="提醒">
              <div class="tab-toolbar">
                <span class="muted">由健康记录的“下次日期”自动生成</span>
              </div>

              <div v-if="reminders.length" class="reminder-list">
                <article
                  v-for="reminder in reminders"
                  :key="reminder.id"
                  class="reminder-item"
                >
                  <span class="date-badge">
                    <strong>{{ formatDate(reminder.due_date).slice(8) }}</strong>
                    <small>{{ formatDate(reminder.due_date).slice(0, 7) }}</small>
                  </span>
                  <div class="reminder-main">
                    <strong>{{ reminder.title }}</strong>
                    <small>{{ recordTypeLabel(reminder.reminder_type) }}</small>
                  </div>
                  <span
                    class="pill"
                    :class="daysUntil(reminder.due_date) < 0 ? 'red' : 'sage'"
                  >
                    {{ dueLabel(reminder.due_date) }}
                  </span>
                  <span class="reminder-actions">
                    <n-button
                      size="tiny"
                      secondary
                      :loading="
                        reminderBusy?.id === reminder.id &&
                        reminderBusy.action === 'done'
                      "
                      :disabled="reminderBusy?.id === reminder.id"
                      @click="handleReminder(reminder, 'done')"
                    >
                      完成
                    </n-button>
                    <n-button
                      size="tiny"
                      quaternary
                      :loading="
                        reminderBusy?.id === reminder.id &&
                        reminderBusy.action === 'snooze'
                      "
                      :disabled="reminderBusy?.id === reminder.id"
                      @click="handleReminder(reminder, 'snooze')"
                    >
                      延后 7 天
                    </n-button>
                  </span>
                </article>
              </div>
              <n-empty
                v-else
                description="目前没有待处理提醒"
                style="padding: 48px 0"
              />
            </n-tab-pane>
          </n-tabs>
        </section>

        <PetFormModal v-model:show="showEdit" :pet="pet" @saved="onPetSaved" />

        <n-modal
          v-model:show="showHealthModal"
          preset="card"
          title="新增健康记录"
          style="width: 540px; max-width: 92vw"
          :mask-closable="false"
        >
          <n-form label-placement="top">
            <div class="form-grid">
              <n-form-item label="记录类型" required>
                <n-select
                  v-model:value="healthForm.record_type"
                  :options="recordTypeOptions"
                />
              </n-form-item>
              <n-form-item label="标题" required>
                <n-input
                  v-model:value="healthForm.title"
                  placeholder="例如：狂犬疫苗"
                  maxlength="100"
                />
              </n-form-item>
              <n-form-item label="记录日期" required>
                <n-date-picker
                  v-model:formatted-value="healthForm.record_date"
                  value-format="yyyy-MM-dd"
                  type="date"
                  style="width: 100%"
                />
              </n-form-item>
              <n-form-item label="下次到期日">
                <n-date-picker
                  v-model:formatted-value="healthForm.next_due_date"
                  value-format="yyyy-MM-dd"
                  type="date"
                  clearable
                  placeholder="可留空"
                  style="width: 100%"
                />
              </n-form-item>
            </div>
            <n-form-item label="备注">
              <n-input
                v-model:value="healthForm.note"
                type="textarea"
                :autosize="{ minRows: 3, maxRows: 5 }"
                placeholder="医院、剂量、注意事项"
                maxlength="500"
                show-count
              />
            </n-form-item>
          </n-form>

          <template #footer>
            <div class="modal-footer">
              <n-button quaternary @click="showHealthModal = false">
                取消
              </n-button>
              <n-button
                type="primary"
                :loading="savingHealth"
                @click="saveHealthRecord"
              >
                保存记录
              </n-button>
            </div>
          </template>
        </n-modal>

        <n-modal
          v-model:show="showWeightModal"
          preset="card"
          title="记录体重"
          style="width: 460px; max-width: 92vw"
          :mask-closable="false"
        >
          <n-form label-placement="top">
            <n-form-item label="记录日期" required>
              <n-date-picker
                v-model:formatted-value="weightForm.record_date"
                value-format="yyyy-MM-dd"
                type="date"
                style="width: 100%"
              />
            </n-form-item>
            <n-form-item label="体重（kg）" required>
              <n-input-number
                v-model:value="weightForm.weight_kg"
                :min="0.1"
                :max="200"
                :step="0.1"
                placeholder="例如 12.5"
                style="width: 100%"
              />
            </n-form-item>
            <n-form-item label="备注">
              <n-input
                v-model:value="weightForm.note"
                placeholder="例如：饭后称重"
                maxlength="200"
              />
            </n-form-item>
          </n-form>

          <template #footer>
            <div class="modal-footer">
              <n-button quaternary @click="showWeightModal = false">
                取消
              </n-button>
              <n-button
                type="primary"
                :loading="savingWeight"
                @click="saveWeight"
              >
                保存体重
              </n-button>
            </div>
          </template>
        </n-modal>
      </template>
    </n-spin>
  </div>
</template>

<style scoped>
.back-row {
  margin-bottom: 14px;
}

.back-link {
  color: var(--pc-ink-faint);
  font-size: 12.5px;
}

.back-link:hover {
  color: var(--pc-primary);
}

.pet-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 24px;
}

.hero-main {
  display: flex;
  align-items: center;
  gap: 18px;
}

.avatar {
  display: flex;
  width: 68px;
  height: 68px;
  flex: 0 0 68px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--pc-line);
  border-radius: 7px;
  background: var(--pc-surface-muted);
  color: var(--pc-primary);
  line-height: 1.1;
}

.avatar strong {
  font-size: 24px;
  font-weight: 700;
}

.avatar small {
  margin-top: 3px;
  color: var(--pc-ink-faint);
  font-size: 8px;
  font-weight: 650;
  letter-spacing: 0.08em;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.name-row h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.meta-line {
  margin: 5px 0 9px;
  color: var(--pc-ink-soft);
  font-size: 12.5px;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hero-side {
  display: flex;
  align-items: center;
  gap: 18px;
}

.mini-stat {
  display: flex;
  flex-direction: column;
  padding-left: 18px;
  border-left: 1px solid var(--pc-line);
}

.mini-stat span {
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.mini-stat strong {
  margin-top: 3px;
  font-size: 15px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.note-card {
  margin-top: 12px;
  padding: 14px 18px;
}

.note-card strong {
  color: var(--pc-ink-faint);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.note-card p {
  margin: 5px 0 0;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.tab-shell {
  margin-top: 12px;
  padding: 16px 20px 22px;
}

.tab-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0 14px;
  font-size: 12px;
}

.chart {
  width: 100%;
  height: 320px;
}

.record-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.record-item {
  padding: 13px 15px;
  border: 1px solid var(--pc-line);
  border-radius: 6px;
  background: var(--pc-surface);
}

.record-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.record-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.record-title strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 7px;
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.record-note {
  margin: 7px 0 0;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
}

.reminder-list {
  display: flex;
  flex-direction: column;
}

.reminder-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 2px;
  border-bottom: 1px solid #efefe9;
}

.reminder-item:last-child {
  border-bottom: 0;
}

.date-badge {
  display: flex;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--pc-line);
  border-radius: 6px;
  background: var(--pc-surface-muted);
  color: var(--pc-ink);
  line-height: 1.1;
}

.date-badge strong {
  font-size: 16px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.date-badge small {
  margin-top: 2px;
  font-size: 9px;
}

.reminder-main {
  display: flex;
  flex: 1;
  flex-direction: column;
}

.reminder-main strong {
  font-size: 13.5px;
  font-weight: 600;
}

.reminder-main small {
  margin-top: 2px;
  color: var(--pc-ink-faint);
  font-size: 11px;
}

.reminder-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 4px;
}

.pill.red {
  background: var(--pc-danger-soft);
  color: var(--pc-danger);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 900px) {
  .pet-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .hero-side {
    width: 100%;
    padding-top: 14px;
    border-top: 1px solid var(--pc-line);
  }

  .mini-stat:first-child {
    padding-left: 0;
    border-left: 0;
  }

  .mini-stat {
    flex: 1;
  }
}

@media (max-width: 560px) {
  .hero-main {
    align-items: flex-start;
  }

  .reminder-item > .pill {
    display: none;
  }

  .reminder-actions {
    gap: 0;
  }

  .avatar {
    width: 56px;
    height: 56px;
    flex-basis: 56px;
  }

  .avatar strong {
    font-size: 20px;
  }

  .name-row h1 {
    font-size: 20px;
  }

  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .chart {
    height: 260px;
  }
}
</style>
