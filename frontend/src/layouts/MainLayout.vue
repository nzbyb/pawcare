<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAvatar, NButton, NDropdown } from 'naive-ui'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const navItems = [
  { key: 'dashboard', label: '工作台', short: '工作台', icon: '🏠', to: '/', match: ['dashboard'] },
  { key: 'pets', label: '宠物档案', short: '宠物', icon: '🐾', to: '/pets', match: ['pets', 'pet-detail'] },
  { key: 'agent', label: '智能助手', short: '助手', icon: '💬', to: '/agent', match: ['agent'] },
]

const roleLabels: Record<string, string> = {
  pet_owner: '宠物主',
  boarding_staff: '寄养员',
  admin: '管理员',
}

const roleLabel = computed(() =>
  auth.user ? roleLabels[auth.user.role] ?? auth.user.role : '',
)

const userOptions = [{ label: '退出登录', key: 'logout' }]

function isActive(item: (typeof navItems)[number]): boolean {
  return item.match.includes(String(route.name))
}

function onUserSelect(key: string | number): void {
  if (key === 'logout') {
    auth.logout()
    router.replace({ name: 'login' })
  }
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <router-link to="/" class="brand">
        <span class="brand-mark">🐾</span>
        <span class="brand-text">
          <strong>PawCare</strong>
          <small>宠物寄养与健康管理</small>
        </span>
      </router-link>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.key"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-card">
        <span class="sidebar-card-badge">AI</span>
        <strong>PawCare 助手</strong>
        <p>寄养预约、健康记录、疫苗提醒，都可以用一句话完成。</p>
        <n-button size="small" block @click="router.push('/agent')">去试试</n-button>
      </div>

      <div class="user-box">
        <n-avatar round :size="38" color="#E8835A">{{ auth.initial }}</n-avatar>
        <div class="user-meta">
          <strong>{{ auth.displayName }}</strong>
          <span>{{ roleLabel }}</span>
        </div>
        <n-dropdown :options="userOptions" trigger="click" @select="onUserSelect">
          <n-button quaternary circle size="small" aria-label="账户菜单">⋯</n-button>
        </n-dropdown>
      </div>
    </aside>

    <main class="main">
      <header class="mobile-bar">
        <router-link to="/" class="mobile-brand">🐾 PawCare</router-link>
        <nav class="mobile-nav">
          <router-link
            v-for="item in navItems"
            :key="item.key"
            :to="item.to"
            :class="{ active: isActive(item) }"
          >
            {{ item.short }}
          </router-link>
        </nav>
        <n-button quaternary size="small" @click="onUserSelect('logout')">退出</n-button>
      </header>

      <router-view v-slot="{ Component }">
        <component :is="Component" :key="route.fullPath" />
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
}

.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  display: flex;
  width: 248px;
  flex-direction: column;
  gap: 22px;
  padding: 24px 18px;
  border-right: 1px solid rgba(237, 228, 218, 0.9);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(18px);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 2px 6px;
}

.brand-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 14px;
  background: linear-gradient(135deg, #f7c9b3, #e8835a);
  box-shadow: 0 8px 18px rgba(232, 131, 90, 0.28);
  font-size: 22px;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.brand-text strong {
  font-size: 19px;
  letter-spacing: -0.01em;
}

.brand-text small {
  margin-top: 3px;
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 13px;
  border-radius: 12px;
  color: var(--pc-ink-soft);
  font-size: 14px;
  font-weight: 600;
  transition: 0.18s ease;
}

.nav-item:hover {
  background: #f7f1ea;
  color: var(--pc-ink);
}

.nav-item.active {
  background: var(--pc-primary-soft);
  color: #b85f3c;
  box-shadow: inset 0 0 0 1px rgba(232, 131, 90, 0.14);
}

.nav-icon {
  font-size: 17px;
}

.sidebar-card {
  position: relative;
  margin-top: auto;
  padding: 16px;
  border: 1px solid rgba(232, 131, 90, 0.18);
  border-radius: 16px;
  background: linear-gradient(160deg, #fff7f2, #fdf0e9);
}

.sidebar-card-badge {
  display: inline-block;
  margin-bottom: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(232, 131, 90, 0.16);
  color: #b85f3c;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.sidebar-card strong {
  display: block;
  font-size: 14px;
}

.sidebar-card p {
  margin: 6px 0 12px;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.6;
}

.user-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 6px 2px;
  border-top: 1px solid var(--pc-line);
}

.user-meta {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  line-height: 1.25;
}

.user-meta strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-meta span {
  color: var(--pc-ink-soft);
  font-size: 11px;
}

.main {
  min-height: 100vh;
  margin-left: 248px;
}

.mobile-bar {
  display: none;
}

@media (max-width: 900px) {
  .sidebar {
    display: none;
  }

  .main {
    margin-left: 0;
  }

  .mobile-bar {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid rgba(237, 228, 218, 0.9);
    background: rgba(251, 247, 242, 0.92);
    backdrop-filter: blur(14px);
  }

  .mobile-brand {
    font-size: 15px;
    font-weight: 800;
    white-space: nowrap;
  }

  .mobile-nav {
    display: flex;
    flex: 1;
    justify-content: flex-end;
    gap: 4px;
  }

  .mobile-nav a {
    padding: 6px 10px;
    border-radius: 9px;
    color: var(--pc-ink-soft);
    font-size: 12px;
    font-weight: 600;
  }

  .mobile-nav a.active {
    background: var(--pc-primary-soft);
    color: #b85f3c;
  }
}
</style>
