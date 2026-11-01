<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NEmpty, NInput, NSpin } from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import { searchSite } from '@/api/system'
import type { SearchResult } from '@/types'

const route = useRoute()
const router = useRouter()

const keyword = ref(String(route.query.q ?? ''))
const result = ref<SearchResult | null>(null)
const loading = ref(false)
const failed = ref(false)
let requestId = 0

const groupIcons: Record<string, string> = {
  pet: 'paw',
  order: 'calendar',
  announcement: 'bell',
  knowledge: 'book',
}

async function load(text: string): Promise<void> {
  const q = text.trim()
  if (!q) {
    result.value = null
    return
  }
  const current = ++requestId
  loading.value = true
  failed.value = false
  try {
    const data = await searchSite(q)
    if (current === requestId) result.value = data
  } catch {
    if (current === requestId) {
      failed.value = true
      result.value = null
    }
  } finally {
    if (current === requestId) loading.value = false
  }
}

function submit(): void {
  const q = keyword.value.trim()
  if (!q) return
  if (String(route.query.q ?? '') === q) {
    void load(q)
  } else {
    router.replace({ name: 'search', query: { q } })
  }
}

watch(
  () => route.query.q,
  (value) => {
    const text = String(value ?? '')
    keyword.value = text
    void load(text)
  },
)

onMounted(() => {
  if (keyword.value) void load(keyword.value)
})
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">站内搜索</h1>
        <p class="page-subtitle">按名称、品种、笼舍编号或公告内容检索，结果只包含你有权限查看的条目</p>
      </div>
    </header>

    <form class="search-bar" role="search" @submit.prevent="submit">
      <n-input
        v-model:value="keyword"
        size="large"
        clearable
        maxlength="50"
        placeholder="搜索宠物、寄养订单或公告，例如「豆豆」「柯基」"
      >
        <template #prefix>
          <AppIcon name="search" :size="16" />
        </template>
      </n-input>
      <n-button type="primary" size="large" attr-type="submit" :disabled="!keyword.trim()">
        搜索
      </n-button>
    </form>

    <n-spin :show="loading">
      <div v-if="failed" class="state-card soft-card" role="alert">
        搜索失败，请稍后重试
        <n-button size="small" @click="load(keyword)">重试</n-button>
      </div>

      <template v-else-if="result && result.total">
        <p class="muted summary">
          关键词「{{ result.keyword }}」共找到 {{ result.total }} 条结果
        </p>
        <section v-for="group in result.groups" :key="group.type" class="group soft-card">
          <header class="group-head">
            <AppIcon :name="groupIcons[group.type] ?? 'search'" :size="15" />
            <h2 class="section-title">{{ group.label }}</h2>
            <span class="muted">{{ group.items.length }} 条</span>
          </header>
          <router-link
            v-for="item in group.items"
            :key="`${item.type}-${item.id}`"
            :to="item.url"
            class="hit"
          >
            <span class="hit-main">
              <strong>{{ item.title }}</strong>
              <span v-if="item.subtitle" class="muted">{{ item.subtitle }}</span>
            </span>
            <AppIcon name="chevronRight" :size="14" />
          </router-link>
        </section>
      </template>

      <n-empty
        v-else-if="result"
        class="empty"
        :description="`没有找到与「${result.keyword}」相关的记录`"
      />

      <section v-else class="tips soft-card">
        <h2 class="section-title">可以搜什么</h2>
        <ul>
          <li>宠物档案：名字与品种，例如「豆豆」「柯基」</li>
          <li>寄养订单：宠物名或笼舍编号，例如「A-01」</li>
          <li>公告：标题与正文关键词</li>
          <li>护理知识：仅管理员可检索，其他角色可以向智能助手提问</li>
        </ul>
      </section>
    </n-spin>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  gap: 10px;
  margin: 16px 0 20px;
}
.search-bar :deep(.n-input) {
  flex: 1;
}
.summary {
  margin: 0 0 12px;
  font-size: 12px;
}
.group {
  margin-bottom: 12px;
  padding: 6px 18px;
}
.group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0 8px;
  border-bottom: 1px solid var(--pc-line);
}
.group-head .muted {
  margin-left: auto;
  font-size: 11.5px;
}
.hit {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 2px;
  border-bottom: 1px solid var(--pc-line);
  color: var(--pc-ink);
  text-decoration: none;
}
.group .hit:last-child {
  border-bottom: 0;
}
.hit:hover {
  color: var(--pc-primary);
}
.hit-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.hit strong {
  font-size: 13px;
  font-weight: 650;
  overflow-wrap: anywhere;
}
.hit .muted {
  font-size: 12px;
  overflow-wrap: anywhere;
}
.state-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px;
  font-size: 13px;
}
.tips {
  padding: 18px 20px;
}
.tips .section-title {
  margin-bottom: 10px;
}
.tips ul {
  margin: 0;
  padding-left: 18px;
  color: var(--pc-ink-soft);
  font-size: 12.5px;
  line-height: 2;
}
.empty {
  padding: 48px 0;
}
@media (max-width: 640px) {
  .search-bar {
    flex-direction: column;
  }
}
</style>
