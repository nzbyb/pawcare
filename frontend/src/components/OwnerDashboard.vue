<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty, NSpin, useMessage } from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import PetFormModal from '@/components/PetFormModal.vue'
import {
  listHealthRecords,
  listReminders,
  updateReminder,
} from '@/api/health'
import { listPets } from '@/api/pets'
import type { Pet, Reminder } from '@/types'
import { daysUntil, dueLabel, formatDate, recordTypeLabel, speciesLabel } from '@/utils/format'

/** 到期前 7 天视为「即将到期」，与提醒列表的橙色标记保持一致。 */
const SOON_DAYS = 7

interface ReminderRow {
  reminder: Reminder
  pet: Pet
}

const router = useRouter()
const message = useMessage()

const pets = ref<Pet[]>([])
const reminderRows = ref<ReminderRow[]>([])
const healthRecordCount = ref(0)
const loading = ref(true)
const reminderBusy = ref<{ id: number; action: 'done' | 'snooze' } | null>(null)

const showPetModal = ref(false)
const editingPet = ref<Pet | null>(null)

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const todayText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date()),
)

const overdueCount = computed(
  () => reminderRows.value.filter((row) => daysUntil(row.reminder.due_date) < 0).length,
)

const stats = computed(() => [
  {
    key: 'pets',
    label: '宠物档案',
    value: pets.value.length,
    hint: '已建档',
    tone: 'plain',
    icon: 'paw',
  },
  {
    key: 'health',
    label: '健康记录',
    value: healthRecordCount.value,
    hint: '疫苗 / 驱虫 / 就诊',
    tone: 'ok',
    icon: 'clipboard',
  },
  {
    key: 'reminders',
    label: '待处理提醒',
    value: reminderRows.value.length,
    hint: '按到期日排序',
    tone: 'warn',
    icon: 'bell',
  },
  {
    key: 'overdue',
    label: '已逾期',
    value: overdueCount.value,
    hint: overdueCount.value ? '需要尽快处理' : '没有逾期',
    tone: overdueCount.value ? 'danger' : 'plain',
    icon: 'clock',
  },
])

function reminderDays(row: ReminderRow): number {
  return daysUntil(row.reminder.due_date)
}

/** normal = 7 天以上，soon = 7 天内到期，overdue = 已过期。 */
function reminderState(row: ReminderRow): 'normal' | 'soon' | 'overdue' {
  const days = reminderDays(row)
  if (days < 0) return 'overdue'
  if (days <= SOON_DAYS) return 'soon'
  return 'normal'
}

function reminderStateLabel(row: ReminderRow): string {
  const state = reminderState(row)
  if (state === 'overdue') return '已过期'
  if (state === 'soon') return '即将到期'
  return ''
}

function openPetEdit(pet: Pet): void {
  editingPet.value = pet
  showPetModal.value = true
}

function onPetSaved(pet: Pet): void {
  pets.value = pets.value.map((item) => (item.id === pet.id ? pet : item))
  reminderRows.value = reminderRows.value.map((row) =>
    row.pet.id === pet.id ? { ...row, pet } : row,
  )
}

async function load(): Promise<void> {
  loading.value = true
  try {
    pets.value = await listPets()

    const perPet = await Promise.all(
      pets.value.map(async (pet) => {
        try {
          const [reminders, healthRecords] = await Promise.all([
            listReminders(pet.id),
            listHealthRecords(pet.id),
          ])
          return {
            pet,
            reminders,
            healthCount: healthRecords.length,
          }
        } catch {
          return { pet, reminders: [], healthCount: 0 }
        }
      }),
    )

    reminderRows.value = perPet
      .flatMap((item) =>
        item.reminders.map((reminder) => ({ reminder, pet: item.pet })),
      )
      .sort((a, b) => a.reminder.due_date.localeCompare(b.reminder.due_date))

    healthRecordCount.value = perPet.reduce(
      (total, item) => total + item.healthCount,
      0,
    )
  } catch {
    pets.value = []
    reminderRows.value = []
    healthRecordCount.value = 0
  } finally {
    loading.value = false
  }
}

async function handleReminder(
  row: ReminderRow,
  action: 'done' | 'snooze',
): Promise<void> {
  if (reminderBusy.value) return
  reminderBusy.value = { id: row.reminder.id, action }
  try {
    const updated = await updateReminder(
      row.pet.id,
      row.reminder.id,
      action === 'done' ? { status: 'done' } : { snooze_days: 7 },
    )
    if (action === 'done') {
      reminderRows.value = reminderRows.value.filter(
        (item) => item.reminder.id !== row.reminder.id,
      )
      message.success('已标记完成')
    } else {
      reminderRows.value = reminderRows.value
        .map((item) =>
          item.reminder.id === row.reminder.id
            ? { ...item, reminder: updated }
            : item,
        )
        .sort((a, b) => a.reminder.due_date.localeCompare(b.reminder.due_date))
      message.success('已延后 7 天')
    }
  } catch {
    // 错误提示由 http 拦截器统一展示。
  } finally {
    reminderBusy.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <section class="overview">
      <div class="overview-copy">
        <span class="eyebrow">{{ todayText }} · {{ greeting }}</span>
        <h1>工作台</h1>
        <p>
          当前有 {{ pets.length }} 只宠物、{{ reminderRows.length }} 条提醒待处理，
          在这里查看档案与提醒，或前往寄养页查看预约状态。
        </p>
      </div>
      <div class="overview-actions">
        <n-button type="primary" @click="router.push('/pets')">
          <template #icon><AppIcon name="paw" :size="15" /></template>
          宠物档案
        </n-button>
        <n-button secondary @click="router.push('/boarding')">
          <template #icon><AppIcon name="calendar" :size="15" /></template>
          寄养预约
        </n-button>
      </div>
    </section>

    <n-spin :show="loading">
      <section class="metrics fade-up">
        <article
          v-for="item in stats"
          :key="item.key"
          class="metric"
          :class="`tone-${item.tone}`"
        >
          <div class="metric-head">
            <span class="metric-label">{{ item.label }}</span>
            <span class="metric-icon">
              <AppIcon :name="item.icon" :size="16" />
            </span>
          </div>
          <strong class="metric-value">{{ item.value }}</strong>
          <span class="metric-hint">{{ item.hint }}</span>
        </article>
      </section>

      <section class="content-grid fade-up delay-1">
        <article class="panel">
          <header class="panel-head">
            <div>
              <h2 class="section-title">待处理提醒</h2>
              <p class="panel-sub">按到期时间排序，橙色标记为七天内到期</p>
            </div>
            <span class="panel-count">{{ reminderRows.length }} 条</span>
          </header>

          <div v-if="reminderRows.length" class="reminder-list">
            <div
              v-for="row in reminderRows.slice(0, 6)"
              :key="row.reminder.id"
              class="reminder-row"
              :class="`row-${reminderState(row)}`"
              role="button"
              tabindex="0"
              @click="router.push(`/pets/${row.pet.id}`)"
              @keydown.enter.prevent="router.push(`/pets/${row.pet.id}`)"
              @keydown.space.prevent="router.push(`/pets/${row.pet.id}`)"
            >
              <span class="date-badge">
                <strong>{{ formatDate(row.reminder.due_date).slice(8) }}</strong>
                <small>{{ formatDate(row.reminder.due_date).slice(0, 7) }}</small>
              </span>
              <span class="reminder-main">
                <span class="reminder-title">
                  <strong>{{ row.reminder.title }}</strong>
                  <span
                    v-if="reminderStateLabel(row)"
                    class="status-tag"
                    :class="reminderState(row) === 'overdue' ? 'red' : 'amber'"
                  >
                    {{ reminderStateLabel(row) }}
                  </span>
                </span>
                <small>{{ row.pet.name }} · {{ recordTypeLabel(row.reminder.reminder_type) }}</small>
              </span>
              <span class="reminder-side">
                <span
                  class="pill"
                  :class="
                    reminderState(row) === 'overdue'
                      ? 'red'
                      : reminderState(row) === 'soon'
                        ? 'amber'
                        : 'sage'
                  "
                >
                  {{ dueLabel(row.reminder.due_date) }}
                </span>
                <span class="reminder-actions">
                  <n-button
                    size="tiny"
                    quaternary
                    class="reminder-action"
                    :loading="
                      reminderBusy?.id === row.reminder.id &&
                      reminderBusy.action === 'done'
                    "
                    :disabled="reminderBusy?.id === row.reminder.id"
                    @click.stop="handleReminder(row, 'done')"
                  >
                    完成
                  </n-button>
                  <n-button
                    size="tiny"
                    quaternary
                    class="reminder-action"
                    :loading="
                      reminderBusy?.id === row.reminder.id &&
                      reminderBusy.action === 'snooze'
                    "
                    :disabled="reminderBusy?.id === row.reminder.id"
                    @click.stop="handleReminder(row, 'snooze')"
                  >
                    延后
                  </n-button>
                </span>
              </span>
            </div>
          </div>

          <n-empty
            v-else
            description="暂时没有待处理提醒"
            style="padding: 36px 0"
          />
        </article>

        <article class="panel">
          <header class="panel-head">
            <div>
              <h2 class="section-title">我的宠物</h2>
              <p class="panel-sub">点开查看完整档案</p>
            </div>
            <n-button text type="primary" @click="router.push('/pets')">
              管理
            </n-button>
          </header>

          <div v-if="pets.length" class="pet-mini-list">
            <div v-for="pet in pets.slice(0, 5)" :key="pet.id" class="pet-mini">
              <router-link :to="`/pets/${pet.id}`" class="pet-mini-link">
                <span class="mini-avatar">
                  <img v-if="pet.photo_url" :src="pet.photo_url" :alt="pet.name" loading="lazy" />
                  <template v-else>{{ pet.name.slice(0, 1) }}</template>
                </span>
                <span class="mini-main">
                  <span class="mini-title">
                    <strong>{{ pet.name }}</strong>
                    <span class="species-chip">{{ speciesLabel(pet.species) }}</span>
                  </span>
                  <small>{{ pet.breed || '品种未填写' }}</small>
                </span>
              </router-link>
              <span class="mini-actions">
                <n-button size="tiny" quaternary @click="openPetEdit(pet)">
                  编辑
                </n-button>
                <n-button
                  size="tiny"
                  quaternary
                  @click="router.push(`/pets/${pet.id}`)"
                >
                  查看档案
                </n-button>
              </span>
            </div>
          </div>

          <n-empty
            v-else
            description="还没有宠物档案"
            style="padding: 36px 0"
          >
            <template #extra>
              <n-button type="primary" @click="router.push('/pets')">
                去建档
              </n-button>
            </template>
          </n-empty>
        </article>
      </section>

      <section class="record-note fade-up delay-2">
        <div class="record-note-head">
          <span class="record-icon"><AppIcon name="clipboard" :size="16" /></span>
          <p>
            自动跟踪宠物疫苗、洗护、体检周期，到期自动提醒，
            方便统一管理宠物健康档案与预约记录。
          </p>
        </div>
        <n-button secondary @click="router.push('/pets')">
          查看宠物档案
          <template #icon><AppIcon name="arrowRight" :size="15" /></template>
        </n-button>
      </section>
    </n-spin>

    <PetFormModal
      v-model:show="showPetModal"
      :pet="editingPet"
      @saved="onPetSaved"
    />
  </div>
</template>

<style scoped>
.overview {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--pc-line);
}

.overview-copy {
  max-width: 640px;
}

.eyebrow {
  display: block;
  margin-bottom: 8px;
  color: var(--pc-ink-faint);
  font-size: 12px;
}

.overview h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.overview p {
  margin: 8px 0 0;
  color: var(--pc-ink-soft);
  font-size: 13px;
  line-height: 1.7;
}

.overview-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.metric {
  padding: 14px 16px 14px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
  transition:
    transform 0.16s ease,
    box-shadow 0.16s ease,
    border-color 0.16s ease;
}

.metric:hover {
  transform: translateY(-2px);
  border-color: var(--pc-line-strong);
  box-shadow: 0 6px 18px rgba(28, 29, 26, 0.07);
}

.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.metric-label {
  color: var(--pc-ink-soft);
  font-size: 12px;
}

.metric-icon {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  place-items: center;
  border-radius: var(--pc-radius-sm);
  background: var(--pc-surface-muted);
  color: var(--pc-ink-soft);
}

.tone-plain .metric-icon {
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
}

.tone-ok .metric-label,
.tone-ok .metric-value {
  color: var(--pc-ok);
}

.tone-ok .metric-icon {
  background: var(--pc-ok-soft);
  color: var(--pc-ok);
}

.tone-warn .metric-label,
.tone-warn .metric-value {
  color: var(--pc-warn);
}

.tone-warn .metric-icon {
  background: var(--pc-warn-soft);
  color: var(--pc-warn);
}

.tone-danger .metric-label,
.tone-danger .metric-value {
  color: var(--pc-danger);
}

.tone-danger .metric-icon {
  background: var(--pc-danger-soft);
  color: var(--pc-danger);
}

.metric-value {
  display: block;
  margin: 6px 0 2px;
  font-size: 27px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}

.metric-hint {
  color: var(--pc-ink-faint);
  font-size: 11px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 0.7fr);
  gap: 14px;
}

.panel {
  overflow: hidden;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--pc-line);
}

.panel-sub {
  margin: 3px 0 0;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.panel-count {
  color: var(--pc-ink-faint);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.reminder-list,
.pet-mini-list {
  display: flex;
  flex-direction: column;
  padding: 4px 8px;
}

.reminder-row,
.pet-mini {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 11px 10px;
  border-bottom: 1px solid #efefe9;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.14s ease;
}

.reminder-row {
  outline: none;
}

.reminder-row:last-child,
.pet-mini:last-child {
  border-bottom: 0;
}

.reminder-row:hover,
.pet-mini:hover {
  background: var(--pc-surface-muted);
}

.reminder-row:focus-visible {
  box-shadow: inset 0 0 0 1px var(--pc-primary);
}

.row-soon .reminder-main strong,
.row-soon .date-badge strong {
  color: var(--pc-warn);
}

.row-overdue .reminder-main strong,
.row-overdue .date-badge strong {
  color: var(--pc-danger);
}

.row-soon .date-badge {
  border-color: #e8d8bf;
  background: var(--pc-warn-soft);
}

.row-overdue .date-badge {
  border-color: #e8cbc7;
  background: var(--pc-danger-soft);
}

.reminder-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
}

.status-tag {
  flex: 0 0 auto;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10.5px;
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
}

.status-tag.amber {
  background: var(--pc-warn-soft);
  color: var(--pc-warn);
}

.status-tag.red {
  background: var(--pc-danger-soft);
  color: var(--pc-danger);
}

.reminder-side {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
}

.reminder-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.reminder-action {
  --n-height: 24px;
  --n-padding: 0 4px;
  --n-font-size: 11.5px;
  color: var(--pc-ink-soft);
}

.reminder-action:hover {
  color: var(--pc-primary);
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
  line-height: 1.1;
}

.date-badge strong {
  font-size: 16px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.date-badge small {
  margin-top: 2px;
  color: var(--pc-ink-faint);
  font-size: 9px;
}

.reminder-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.reminder-main strong {
  min-width: 0;
  overflow: hidden;
  font-size: 13.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.14s ease;
}

.reminder-main small {
  margin-top: 2px;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.mini-avatar {
  display: grid;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--pc-line);
  border-radius: 6px;
  background: var(--pc-surface-muted);
  color: var(--pc-primary);
  font-size: 13px;
  font-weight: 700;
}

.mini-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.pet-mini-link {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 12px;
  color: inherit;
}

.mini-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.mini-title {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
}

.mini-main strong {
  overflow: hidden;
  font-size: 13.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.species-chip {
  flex: 0 0 auto;
  padding: 0 5px;
  border: 1px solid var(--pc-line);
  border-radius: 3px;
  color: var(--pc-ink-faint);
  font-size: 10px;
  line-height: 1.6;
}

.mini-main small {
  margin-top: 2px;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.mini-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 2px;
}

.mini-actions :deep(.n-button) {
  --n-height: 24px;
  --n-padding: 0 6px;
  --n-font-size: 11.5px;
  color: var(--pc-ink-soft);
}

.mini-actions :deep(.n-button:hover) {
  color: var(--pc-primary);
}

.record-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 14px;
  padding: 16px 20px;
  border: 1px solid #cfdfd8;
  border-radius: var(--pc-radius);
  background: #f1f6f3;
}

.record-note-head {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 12px;
}

.record-icon {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  border-radius: 6px;
  background: var(--pc-primary);
  color: #fff;
}

.record-note p {
  max-width: 760px;
  margin: 0;
  color: var(--pc-ink-soft);
  font-size: 12.5px;
  line-height: 1.65;
}

@media (max-width: 1080px) {
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .overview {
    align-items: flex-start;
    flex-direction: column;
  }

  .content-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .record-note {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
}

@media (max-width: 520px) {
  .metrics {
    grid-template-columns: minmax(0, 1fr);
  }

  .reminder-side > .pill {
    display: none;
  }

  .overview-actions {
    width: 100%;
  }

  .overview-actions :deep(.n-button) {
    flex: 1;
  }
}
</style>
