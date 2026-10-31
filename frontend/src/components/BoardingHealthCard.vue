<script setup lang="ts">
import type { BoardingHealthCheck } from '@/types'

defineProps<{ check: BoardingHealthCheck }>()
</script>

<template>
  <section class="health-check" :class="{ attention: check.status === 'attention' }" aria-label="寄养前健康检查">
    <div class="health-heading">
      <strong>寄养前健康检查</strong>
      <span class="pill" :class="check.warning_count ? 'amber' : 'sage'">
        {{ check.warning_count ? `${check.warning_count} 项待核对` : '资料已核对' }}
      </span>
    </div>
    <p>{{ check.pet_name }} · {{ check.start_date }} → {{ check.end_date }}</p>
    <p class="health-summary">{{ check.summary }}</p>
    <details>
      <summary>查看核对详情（{{ check.items.length }} 项）</summary>
    <ul>
      <li v-for="(item, index) in check.items" :key="`${item.code}-${index}`" :class="item.level">
        <strong>{{ item.title }}</strong>
        <span>{{ item.detail }}</span>
        <small v-if="item.record_date">
          记录日期 {{ item.record_date }}<template v-if="item.next_due_date"> · 下次到期 {{ item.next_due_date }}</template>
        </small>
      </li>
    </ul>
    </details>
    <router-link :to="`/pets/${check.pet_id}`">查看健康档案 →</router-link>
    <small class="health-notice">{{ check.notice }} · 核对日期 {{ check.checked_on }}</small>
  </section>
</template>

<style scoped>
summary { cursor: pointer; font-size: 12px; color: var(--pc-primary); padding: 8px 0; }
.health-check { padding: 16px; border: 1px solid var(--pc-line); border-radius: var(--pc-radius); background: var(--pc-primary-soft); }
.health-check.attention { background: var(--pc-warn-soft); }
.health-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.health-check p { margin: 8px 0; font-size: 12px; color: var(--pc-ink-soft); }
.health-summary { font-weight: 600; }
ul { display: grid; gap: 12px; padding: 0; margin: 14px 0; list-style: none; }
li { display: grid; gap: 4px; padding-left: 10px; border-left: 2px solid var(--pc-line-strong); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
li.warning { border-color: var(--pc-warn); }
li.ok { border-color: var(--pc-ok); }
li span, li small, .health-notice { color: var(--pc-ink-soft); }
.health-check a { font-size: 12px; font-weight: 650; color: var(--pc-primary); }
.health-notice { display: block; margin-top: 12px; font-size: 11px; line-height: 1.6; }
</style>
