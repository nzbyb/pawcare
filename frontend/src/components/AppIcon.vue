<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ name: string; size?: number | string; strokeWidth?: number }>(),
  { size: 16, strokeWidth: 1.8 },
)

const paths: Record<string, string[]> = {
  home: ['M3 10.5 12 3l9 7.5', 'M5 9.5V21h14V9.5', 'M9 21v-6h6v6'],
  paw: [
    'M8.5 14c0-2 1.6-3.5 3.5-3.5s3.5 1.5 3.5 3.5c0 1.8-1.4 2.8-2.6 3.2-.5.2-.6.3-.9.3s-.4-.1-.9-.3C9.9 16.8 8.5 15.8 8.5 14Z',
    'M6.2 11.6a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4Z',
    'M17.8 11.6a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4Z',
    'M9.5 7.5a1.6 1.6 0 1 1 0-3.2 1.6 1.6 0 0 1 0 3.2Z',
    'M14.5 7.5a1.6 1.6 0 1 1 0-3.2 1.6 1.6 0 0 1 0 3.2Z',
  ],
  calendar: ['M4 6.5h16v14H4z', 'M8 3.5v5', 'M16 3.5v5', 'M4 10.5h16'],
  chat: ['M4 5.5h16v11H9l-5 4v-15Z'],
  plus: ['M12 5v14', 'M5 12h14'],
  arrowRight: ['M5 12h14', 'm13 6 6 6-6 6'],
  chevronRight: ['m9 6 6 6-6 6'],
  chevronDown: ['m6 9 6 6 6-6'],
  search: ['M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z', 'm16 16 4 4'],
  logout: ['M10 4H5v16h5', 'M14 8l4 4-4 4', 'M18 12H9'],
  user: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z', 'M4 21c0-4 3.6-6 8-6s8 2 8 6'],
  clipboard: ['M8 4h8v3H8z', 'M6 6h12v15H6z', 'M9 11h6', 'M9 15h6'],
  shield: ['M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z'],
  check: ['m5 12 4 4 10-10'],
  clock: ['M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16Z', 'M12 8v4l3 2'],
  bell: ['M6 16h12l-1.5-2.5V9a4.5 4.5 0 0 0-9 0v4.5L6 16Z', 'M10 19a2 2 0 0 0 4 0'],
  book: [
    'M5 4.5h6.5A2.5 2.5 0 0 1 14 7v13a2 2 0 0 0-2-2H5V4.5Z',
    'M19 4.5h-3.5A2.5 2.5 0 0 0 13 7v13a2 2 0 0 1 2-2h4V4.5Z',
  ],
  send: ['M4 12 20 4l-6 16-2.5-6.5L4 12Z', 'm11.5 13.5 4-4'],
  stop: ['M7 7h10v10H7z'],
  lock: ['M6 10h12v10H6z', 'M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10'],
}

const shapes = computed(() => paths[props.name] ?? paths.paw)
</script>

<template>
  <svg
    class="app-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    :stroke-width="strokeWidth"
    stroke="currentColor"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path v-for="(d, index) in shapes" :key="index" :d="d" />
  </svg>
</template>

<style scoped>
.app-icon {
  display: block;
  flex: 0 0 auto;
}
</style>
