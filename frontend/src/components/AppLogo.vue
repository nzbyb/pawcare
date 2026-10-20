<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: number
    variant?: 'default' | 'inverse'
    showText?: boolean
    compact?: boolean
  }>(),
  {
    size: 34,
    variant: 'default',
    showText: true,
    compact: false,
  },
)
</script>

<template>
  <span class="app-logo" :class="variant">
    <svg
      class="mark"
      :width="size"
      :height="size"
      viewBox="0 0 48 48"
      role="img"
      aria-label="PawCare"
    >
      <rect class="badge" width="48" height="48" rx="11" />
      <g class="paw">
        <rect x="12" y="19.6" width="5.8" height="7.4" rx="2.9" transform="rotate(-27 14.9 23.3)" />
        <rect x="18.2" y="14.6" width="5.8" height="7.8" rx="2.9" transform="rotate(-9 21.1 18.5)" />
        <rect x="24" y="14.6" width="5.8" height="7.8" rx="2.9" transform="rotate(9 26.9 18.5)" />
        <rect x="30.2" y="19.6" width="5.8" height="7.4" rx="2.9" transform="rotate(27 33.1 23.3)" />
        <rect x="14.4" y="27" width="19.2" height="11.6" rx="5.8" />
      </g>
    </svg>

    <span v-if="showText" class="wordmark">
      <span class="name"><strong>Paw</strong><em>Care</em></span>
      <small v-if="!compact">宠物寄养与健康管理</small>
    </span>
  </span>
</template>

<style scoped>
.app-logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--pc-ink);
  line-height: 1.2;
}

.mark {
  display: block;
  flex: 0 0 auto;
}

.badge {
  fill: var(--pc-primary);
}

.paw {
  fill: #fff;
}

.wordmark {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.name em {
  color: var(--pc-primary);
  font-style: normal;
  font-weight: 550;
}

.wordmark small {
  margin-top: 3px;
  color: var(--pc-ink-faint);
  font-size: 10.5px;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.inverse {
  color: #f4f6f1;
}

.inverse .badge {
  fill: #fff;
}

.inverse .paw {
  fill: var(--pc-primary);
}

.inverse .name em {
  color: #cfe0d7;
}

.inverse .wordmark small {
  color: rgba(244, 246, 241, 0.66);
}
</style>
