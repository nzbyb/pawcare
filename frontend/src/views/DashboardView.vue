<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NEmpty, NSpin } from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import { listHealthRecords, listReminders } from '@/api/health'
import { listPets } from '@/api/pets'
import type { Pet, Reminder } from '@/types'
import { daysUntil, dueLabel, formatDate } from '@/utils/format'

interface ReminderRow {
  reminder: Reminder
  pet: Pet
}

const router = useRouter()

const pets = ref<Pet[]>([])
const reminderRows = ref<ReminderRow[]>([])
const healthRecordCount = ref(0)
const loading = ref(true)

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
  },
  {
    key: 'health',
    label: '健康记录',
    value: healthRecordCount.value,
    hint: '疫苗 / 驱虫 / 就诊',
    tone: 'plain',
  },
  {
    key: 'reminders',
    label: '待处理提醒',
    value: reminderRows.value.length,
    hint: '按到期日排序',
    tone: 'warn',
  },
  {
    key: 'overdue',
    label: '已逾期',
    value: overdueCount.value,
    hint: overdueCount.value ? '需要尽快处理' : '没有逾期',
    tone: overdueCount.value ? 'danger' : 'plain',
  },
])

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

onMounted(load)
</script>

<template>
  <div class="page">
    <section class="overview">
      <div class="overview-copy">
        <span class="eyebrow">{{ todayText }} · {{ greeting }}</span>
        <h1>工作台</h1>
        <p>
          当前有 {{ pets.length }} 只宠物、{{ reminderRows.length }} 条提醒待处理。
          需要查档案或安排寄养时，可以直接交给助手。
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
          <span class="metric-label">
            <span class="metric-dot" />
            {{ item.label }}
          </span>
          <strong class="metric-value">{{ item.value }}</strong>
          <span class="metric-hint">{{ item.hint }}</span>
        </article>
      </section>

      <section class="content-grid fade-up delay-1">
        <article class="panel">
          <header class="panel-head">
            <div>
              <h2 class="section-title">即将到期</h2>
              <p class="panel-sub">按到期时间从近到远</p>
            </div>
            <span class="panel-count">{{ reminderRows.length }} 条</span>
          </header>

          <div v-if="reminderRows.length" class="reminder-list">
            <button
              v-for="row in reminderRows.slice(0, 6)"
              :key="row.reminder.id"
              type="button"
              class="reminder-row"
              @click="router.push(`/pets/${row.pet.id}`)"
            >
              <span class="date-badge">
                <strong>{{ formatDate(row.reminder.due_date).slice(8) }}</strong>
                <small>{{ formatDate(row.reminder.due_date).slice(0, 7) }}</small>
              </span>
              <span class="reminder-main">
                <strong>{{ row.reminder.title }}</strong>
                <small>{{ row.pet.name }} · {{ row.reminder.reminder_type }}</small>
              </span>
              <span
                class="pill"
                :class="daysUntil(row.reminder.due_date) < 0 ? 'red' : 'sage'"
              >
                {{ dueLabel(row.reminder.due_date) }}
              </span>
            </button>
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
            <router-link
              v-for="pet in pets.slice(0, 5)"
              :key="pet.id"
              :to="`/pets/${pet.id}`"
              class="pet-mini"
            >
              <span class="mini-avatar">{{ pet.name.slice(0, 1) }}</span>
              <span class="mini-main">
                <strong>{{ pet.name }}</strong>
                <small>{{ pet.breed || (pet.species === 'cat' ? '猫咪' : '狗狗') }}</small>
              </span>
              <AppIcon name="chevronRight" :size="15" class="mini-arrow" />
            </router-link>
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

      <section class="assistant-note fade-up delay-2">
        <div class="assistant-note-head">
          <span class="assistant-icon"><AppIcon name="chat" :size="16" /></span>
          <div>
            <h2>让助手把信息串起来</h2>
            <p>
              “豆豆下个月要寄养五天，帮我看看有没有合适的笼舍。”
              助手会先查档案、查空档，再生成一份需要你确认的预约草稿。
            </p>
          </div>
        </div>
        <n-button type="primary" secondary @click="router.push('/agent')">
          打开智能助手
          <template #icon><AppIcon name="arrowRight" :size="15" /></template>
        </n-button>
      </section>
    </n-spin>
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
  padding: 15px 16px 14px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.metric-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--pc-ink-soft);
  font-size: 12px;
}

.metric-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--pc-line-strong);
}

.tone-warn .metric-dot {
  background: var(--pc-warn);
}

.tone-danger .metric-dot {
  background: var(--pc-danger);
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

.tone-danger .metric-value {
  color: var(--pc-danger);
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
  border: 0;
  border-bottom: 1px solid #efefe9;
  border-radius: 5px;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.14s ease;
}

.reminder-row:last-child,
.pet-mini:last-child {
  border-bottom: 0;
}

.reminder-row:hover,
.pet-mini:hover {
  background: var(--pc-surface-muted);
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
  overflow: hidden;
  font-size: 13.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  border: 1px solid var(--pc-line);
  border-radius: 6px;
  background: var(--pc-surface-muted);
  color: var(--pc-primary);
  font-size: 13px;
  font-weight: 700;
}

.mini-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.mini-main strong {
  font-size: 13.5px;
  font-weight: 600;
}

.mini-main small {
  margin-top: 2px;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.mini-arrow {
  color: var(--pc-ink-faint);
}

.assistant-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 14px;
  padding: 18px 20px;
  border: 1px solid #cfdfd8;
  border-radius: var(--pc-radius);
  background: #f1f6f3;
}

.assistant-note-head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.assistant-icon {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  border-radius: 6px;
  background: var(--pc-primary);
  color: #fff;
}

.assistant-note h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}

.assistant-note p {
  max-width: 720px;
  margin: 4px 0 0;
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

  .assistant-note {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 520px) {
  .metrics {
    grid-template-columns: minmax(0, 1fr);
  }

  .overview-actions {
    width: 100%;
  }

  .overview-actions :deep(.n-button) {
    flex: 1;
  }
}
</style>
