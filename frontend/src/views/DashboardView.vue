<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NEmpty, NSpin } from 'naive-ui'

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
    icon: '🐾',
    label: '宠物档案',
    value: pets.value.length,
    hint: '已建档的毛孩子',
    tone: 'coral',
  },
  {
    key: 'health',
    icon: '📋',
    label: '健康记录',
    value: healthRecordCount.value,
    hint: '疫苗、驱虫与就诊',
    tone: 'sage',
  },
  {
    key: 'reminders',
    icon: '⏰',
    label: '待处理提醒',
    value: reminderRows.value.length,
    hint: '按到期日排序',
    tone: 'amber',
  },
  {
    key: 'overdue',
    icon: '🚨',
    label: '已逾期',
    value: overdueCount.value,
    hint: overdueCount.value ? '建议尽快处理' : '目前没有逾期',
    tone: overdueCount.value ? 'red' : 'grey',
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
    <section class="hero fade-up">
      <div class="hero-copy">
        <span class="hero-eyebrow">{{ todayText }} · {{ greeting }}</span>
        <h1>今天也要和毛孩子<br />好好相处。</h1>
        <p>
          健康档案、体重变化和到期提醒都在这里。需要找寄养时，
          先让 PawCare 助手帮你查一查空档。
        </p>
        <div class="hero-actions">
          <n-button type="primary" size="large" @click="router.push('/pets')">
            查看宠物档案
          </n-button>
          <n-button size="large" quaternary @click="router.push('/agent')">
            打开智能助手 →
          </n-button>
        </div>
      </div>
      <div class="hero-visual" aria-hidden="true">
        <span class="hero-paw">🐾</span>
        <span class="float-chip chip-1">疫苗提醒</span>
        <span class="float-chip chip-2">体重趋势</span>
        <span class="float-chip chip-3">寄养空档</span>
      </div>
    </section>

    <n-spin :show="loading">
      <section class="stats fade-up delay-1">
        <article
          v-for="item in stats"
          :key="item.key"
          class="stat-card"
          :class="`tone-${item.tone}`"
        >
          <span class="stat-icon">{{ item.icon }}</span>
          <div>
            <span class="stat-label">{{ item.label }}</span>
            <strong class="stat-value">{{ item.value }}</strong>
            <span class="stat-hint">{{ item.hint }}</span>
          </div>
        </article>
      </section>

      <section class="content-grid fade-up delay-2">
        <n-card class="panel" :bordered="false">
          <template #header>
            <div class="panel-head">
              <div>
                <h2 class="section-title">即将到期</h2>
                <p class="muted panel-sub">按到期时间从近到远</p>
              </div>
              <span class="pill">{{ reminderRows.length }} 条</span>
            </div>
          </template>

          <div v-if="reminderRows.length" class="reminder-list">
            <button
              v-for="row in reminderRows.slice(0, 6)"
              :key="row.reminder.id"
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
            description="暂时没有待处理提醒，继续保持"
            style="padding: 34px 0"
          />
        </n-card>

        <n-card class="panel" :bordered="false">
          <template #header>
            <div class="panel-head">
              <div>
                <h2 class="section-title">我的毛孩子</h2>
                <p class="muted panel-sub">点开查看完整档案</p>
              </div>
              <n-button text type="primary" @click="router.push('/pets')">
                管理
              </n-button>
            </div>
          </template>

          <div v-if="pets.length" class="pet-mini-list">
            <router-link
              v-for="pet in pets.slice(0, 5)"
              :key="pet.id"
              :to="`/pets/${pet.id}`"
              class="pet-mini"
            >
              <span class="mini-avatar">
                {{ pet.species === 'cat' ? '🐱' : pet.species === 'dog' ? '🐶' : '🐾' }}
              </span>
              <span class="mini-main">
                <strong>{{ pet.name }}</strong>
                <small>{{ pet.breed || (pet.species === 'cat' ? '猫咪' : '狗狗') }}</small>
              </span>
              <span class="mini-arrow">→</span>
            </router-link>
          </div>

          <n-empty
            v-else
            description="还没有宠物档案"
            style="padding: 34px 0"
          >
            <template #extra>
              <n-button type="primary" @click="router.push('/pets')">
                去建档
              </n-button>
            </template>
          </n-empty>
        </n-card>
      </section>

      <section class="agent-banner fade-up delay-3">
        <div class="agent-banner-copy">
          <span class="pill">下一阶段</span>
          <h2>让助手替你把信息串起来</h2>
          <p>
            “豆豆下个月要寄养五天，帮我看看有没有合适的笼舍。”
            助手会先查档案、查空档，再生成一份需要你确认的预约草稿。
          </p>
        </div>
        <n-button type="primary" size="large" @click="router.push('/agent')">
          了解智能助手
        </n-button>
      </section>
    </n-spin>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  display: grid;
  overflow: hidden;
  grid-template-columns: minmax(0, 1.35fr) minmax(240px, 0.65fr);
  gap: 24px;
  margin-bottom: 22px;
  padding: 36px 38px;
  border-radius: 26px;
  background:
    radial-gradient(circle at 82% 18%, rgba(255, 255, 255, 0.5), transparent 38%),
    linear-gradient(135deg, #fbe3d4 0%, #f7c8ae 45%, #efac87 100%);
  color: #4a2c1f;
  box-shadow: 0 18px 44px rgba(179, 109, 72, 0.18);
}

.hero-eyebrow {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  opacity: 0.72;
}

.hero h1 {
  margin: 12px 0 0;
  font-size: clamp(30px, 3.6vw, 44px);
  font-weight: 850;
  letter-spacing: -0.035em;
  line-height: 1.16;
}

.hero-copy > p {
  max-width: 520px;
  margin: 16px 0 0;
  font-size: 14px;
  line-height: 1.75;
  opacity: 0.82;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.hero-visual {
  position: relative;
  display: grid;
  place-items: center;
}

.hero-paw {
  font-size: 108px;
  filter: drop-shadow(0 18px 26px rgba(110, 58, 32, 0.18));
  transform: rotate(-8deg);
}

.float-chip {
  position: absolute;
  padding: 7px 12px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 8px 18px rgba(116, 58, 32, 0.1);
  font-size: 11px;
  font-weight: 700;
  backdrop-filter: blur(8px);
}

.chip-1 {
  top: 10%;
  left: 0;
}

.chip-2 {
  right: 0;
  top: 38%;
}

.chip-3 {
  bottom: 14%;
  left: 8%;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 17px 18px;
  border: 1px solid rgba(237, 228, 218, 0.95);
  border-radius: 17px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 22px rgba(116, 88, 63, 0.05);
}

.stat-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 12px;
  background: var(--pc-primary-soft);
  font-size: 18px;
}

.tone-sage .stat-icon {
  background: var(--pc-sage-soft);
}

.tone-amber .stat-icon {
  background: #fdf5e4;
}

.tone-red .stat-icon {
  background: #fdecec;
}

.tone-grey .stat-icon {
  background: #f3f0ec;
}

.stat-label {
  display: block;
  color: var(--pc-ink-soft);
  font-size: 12px;
}

.stat-value {
  display: block;
  margin-top: 1px;
  font-size: 25px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.stat-hint {
  display: block;
  margin-top: 2px;
  color: #9a8f85;
  font-size: 11px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.75fr);
  gap: 18px;
}

.panel {
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--pc-shadow);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-sub {
  margin: 3px 0 0;
  font-size: 12px;
}

.reminder-list {
  display: flex;
  flex-direction: column;
}

.reminder-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 4px;
  border: 0;
  border-bottom: 1px solid #f3ece4;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.16s ease;
}

.reminder-row:last-child {
  border-bottom: 0;
}

.reminder-row:hover {
  border-radius: 12px;
  background: #fdf8f4;
}

.date-badge {
  display: flex;
  width: 46px;
  height: 46px;
  flex: 0 0 46px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 13px;
  background: var(--pc-primary-soft);
  color: #b85f3c;
  line-height: 1.05;
}

.date-badge strong {
  font-size: 17px;
}

.date-badge small {
  margin-top: 2px;
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
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reminder-main small {
  margin-top: 3px;
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.pill.red {
  background: #fdecec;
  color: #b84b4b;
}

.pet-mini-list {
  display: flex;
  flex-direction: column;
}

.pet-mini {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 4px;
  border-bottom: 1px solid #f3ece4;
  transition: background 0.16s ease;
}

.pet-mini:last-child {
  border-bottom: 0;
}

.pet-mini:hover {
  border-radius: 12px;
  background: #fdf8f4;
}

.mini-avatar {
  display: grid;
  width: 40px;
  height: 40px;
  place-items: center;
  border-radius: 13px;
  background: #fdf0e9;
  font-size: 20px;
}

.mini-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.mini-main strong {
  font-size: 14px;
}

.mini-main small {
  margin-top: 2px;
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.mini-arrow {
  color: #c4b6a8;
}

.agent-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-top: 20px;
  padding: 24px 28px;
  border: 1px solid rgba(124, 154, 130, 0.22);
  border-radius: 20px;
  background: linear-gradient(120deg, #f0f5f0, #fbfaf4);
}

.agent-banner-copy h2 {
  margin: 10px 0 0;
  font-size: 20px;
  letter-spacing: -0.02em;
}

.agent-banner-copy p {
  max-width: 640px;
  margin: 8px 0 0;
  color: var(--pc-ink-soft);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 1080px) {
  .stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .hero {
    grid-template-columns: minmax(0, 1fr);
    padding: 28px 24px;
  }

  .hero-visual {
    display: none;
  }

  .content-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .agent-banner {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 520px) {
  .stats {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
