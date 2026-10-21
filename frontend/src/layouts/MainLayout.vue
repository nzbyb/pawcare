<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NDropdown } from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import AppLogo from '@/components/AppLogo.vue'
import NotificationBell from '@/components/NotificationBell.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const navItems = [
  { key: 'dashboard', label: '工作台', short: '工作台', icon: 'home', to: '/', match: ['dashboard'] },
  { key: 'pets', label: '宠物档案', short: '宠物', icon: 'paw', to: '/pets', match: ['pets', 'pet-detail'] },
  { key: 'boarding', label: '寄养预约', short: '寄养', icon: 'calendar', to: '/boarding', match: ['boarding'] },
  { key: 'agent', label: '智能助手', short: '助手', icon: 'chat', to: '/agent', match: ['agent'] },
]

const accountItem = {
  key: 'profile',
  label: '个人中心',
  short: '我的',
  icon: 'user',
  to: '/profile',
  match: ['profile'],
}

const roleLabels: Record<string, string> = {
  pet_owner: '宠物主',
  boarding_staff: '寄养员',
  admin: '管理员',
}

const roleLabel = computed(() =>
  auth.user ? roleLabels[auth.user.role] ?? auth.user.role : '',
)

const currentTitle = computed(() => String(route.meta.title ?? '工作台'))

const todayText = computed(() =>
  new Intl.DateTimeFormat('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).format(new Date()),
)

const userOptions = [
  { label: '个人中心', key: 'profile' },
  { label: '退出登录', key: 'logout' },
]

function isActive(item: (typeof navItems)[number]): boolean {
  return item.match.includes(String(route.name))
}

function onUserSelect(key: string | number): void {
  if (key === 'profile') {
    router.push(accountItem.to)
    return
  }
  if (key === 'logout') {
    auth.logout()
    router.replace({ name: 'login' })
  }
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <router-link to="/" class="brand" aria-label="PawCare 首页">
        <AppLogo :size="34" />
      </router-link>

      <div class="nav-label">工作区</div>
      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.key"
          :to="item.to"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          <AppIcon :name="item.icon" :size="16" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="nav-label nav-label-account">账户</div>
      <nav class="nav">
        <router-link
          :to="accountItem.to"
          class="nav-item"
          :class="{ active: isActive(accountItem) }"
        >
          <AppIcon :name="accountItem.icon" :size="16" />
          <span>{{ accountItem.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-foot">
        <div class="sidebar-note">
          <span class="sidebar-note-label">当前环境</span>
          <span class="sidebar-note-value"><span class="status-dot" /> 开发演示</span>
        </div>

        <div class="user-box">
          <span class="user-avatar">{{ auth.initial }}</span>
          <div class="user-meta">
            <strong>{{ auth.displayName }}</strong>
            <span>{{ roleLabel }}</span>
          </div>
          <n-dropdown :options="userOptions" trigger="click" @select="onUserSelect">
            <n-button quaternary circle size="small" aria-label="账户菜单">
              <AppIcon name="chevronDown" :size="15" />
            </n-button>
          </n-dropdown>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="crumb">
          <span class="crumb-root">PawCare</span>
          <AppIcon name="chevronRight" :size="13" />
          <span class="crumb-current">{{ currentTitle }}</span>
        </div>
        <div class="topbar-actions">
          <span class="topbar-date">{{ todayText }}</span>
          <NotificationBell />
          <button class="assistant-button" type="button" @click="router.push('/agent')">
            <AppIcon name="chat" :size="15" />
            打开助手
          </button>
        </div>
      </header>

      <header class="mobile-bar">
        <router-link to="/" class="mobile-brand" aria-label="PawCare 首页">
          <AppLogo :size="26" :show-text="false" />
        </router-link>
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
        <NotificationBell />
        <n-dropdown :options="userOptions" trigger="click" @select="onUserSelect">
          <n-button quaternary circle size="small" aria-label="账户菜单">
            <AppIcon name="user" :size="15" />
          </n-button>
        </n-dropdown>
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
  width: 232px;
  flex-direction: column;
  padding: 20px 14px 16px;
  border-right: 1px solid var(--pc-line);
  background: var(--pc-surface);
}

.brand {
  display: flex;
  align-items: center;
  padding: 2px 6px 0;
}

.nav-label {
  margin: 26px 8px 8px;
  color: var(--pc-ink-faint);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.nav-label-account {
  margin-top: 20px;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 38px;
  padding: 0 10px;
  border-radius: var(--pc-radius-sm);
  color: var(--pc-ink-soft);
  font-size: 13.5px;
  font-weight: 550;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.nav-item:hover {
  background: var(--pc-surface-muted);
  color: var(--pc-ink);
}

.nav-item.active {
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
  font-weight: 650;
}

.nav-item.active::before {
  position: absolute;
  top: 9px;
  bottom: 9px;
  left: -14px;
  width: 2px;
  background: var(--pc-primary);
  content: '';
}

.sidebar-foot {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: auto;
}

.sidebar-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 8px;
  border-top: 1px solid var(--pc-line);
  font-size: 11px;
}

.sidebar-note-label {
  color: var(--pc-ink-faint);
}

.sidebar-note-value {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--pc-ink-soft);
}

.sidebar-note-value .status-dot {
  color: var(--pc-ok);
}

.user-box {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 2px 6px;
}

.user-avatar {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  border-radius: 6px;
  background: var(--pc-surface-muted);
  color: var(--pc-primary);
  font-size: 13px;
  font-weight: 700;
}

.user-meta {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  line-height: 1.3;
}

.user-meta strong {
  overflow: hidden;
  font-size: 12.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-meta span {
  color: var(--pc-ink-faint);
  font-size: 11px;
}

.main {
  min-height: 100vh;
  margin-left: 232px;
}

.topbar {
  display: flex;
  height: 54px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 32px;
  border-bottom: 1px solid var(--pc-line);
  background: var(--pc-surface);
}

.crumb {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--pc-ink-faint);
  font-size: 12.5px;
}

.crumb-root {
  color: var(--pc-ink-soft);
}

.crumb-current {
  color: var(--pc-ink);
  font-weight: 600;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.topbar-date {
  color: var(--pc-ink-faint);
  font-size: 12px;
}

.assistant-button {
  display: inline-flex;
  height: 30px;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  border: 1px solid var(--pc-line-strong);
  border-radius: var(--pc-radius-sm);
  background: var(--pc-surface);
  color: var(--pc-ink);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.assistant-button:hover {
  border-color: var(--pc-primary);
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
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

  .topbar {
    display: none;
  }

  .mobile-bar {
    position: sticky;
    top: 0;
    z-index: 30;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--pc-line);
    background: var(--pc-surface);
  }

  .mobile-brand {
    display: inline-flex;
    align-items: center;
  }

  .mobile-nav {
    display: flex;
    flex: 1;
    justify-content: flex-end;
    gap: 2px;
  }

  .mobile-nav a {
    padding: 5px 8px;
    border-radius: 5px;
    color: var(--pc-ink-soft);
    font-size: 12px;
    font-weight: 550;
  }

  .mobile-nav a.active {
    background: var(--pc-primary-soft);
    color: var(--pc-primary);
  }
}
</style>
