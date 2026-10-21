<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NSpin,
  NSwitch,
  useMessage,
} from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import {
  changePassword,
  updateNotificationPrefs,
  updateProfile,
} from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/types'

const auth = useAuthStore()
const message = useMessage()

const loading = ref(true)
const savingProfile = ref(false)
const savingPrefs = ref(false)
const savingPassword = ref(false)

const profile = reactive({ nickname: '', email: '', phone: '' })
const prefs = reactive({
  notify_health: true,
  notify_order: true,
  notify_system: true,
})
const password = reactive({
  old_password: '',
  new_password: '',
  confirm: '',
})

const roleLabels: Record<string, string> = {
  pet_owner: '宠物主',
  boarding_staff: '寄养员',
  admin: '管理员',
}

const roleLabel = computed(() =>
  auth.user ? roleLabels[auth.user.role] ?? auth.user.role : '',
)

const emailVerified = computed(() => Boolean(auth.user?.email_verified_at))
const phoneVerified = computed(() => Boolean(auth.user?.phone_verified_at))

const joinedAt = computed(() => {
  const value = auth.user?.create_time
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(value))
})

function fill(user: User | null): void {
  profile.nickname = user?.nickname ?? ''
  profile.email = user?.email ?? ''
  profile.phone = user?.phone ?? ''
  prefs.notify_health = user?.notify_health ?? true
  prefs.notify_order = user?.notify_order ?? true
  prefs.notify_system = user?.notify_system ?? true
}

async function load(): Promise<void> {
  loading.value = true
  try {
    await auth.refreshMe()
  } finally {
    fill(auth.user)
    loading.value = false
  }
}

async function saveProfile(): Promise<void> {
  const nickname = profile.nickname.trim()
  if (!nickname) {
    message.warning('昵称不能为空')
    return
  }
  const email = profile.email.trim() || null
  const phone = profile.phone.trim() || null
  if (!email && !phone) {
    message.warning('邮箱或手机号至少填写一个')
    return
  }

  savingProfile.value = true
  try {
    const user = await updateProfile({ nickname, email, phone })
    auth.applyUser(user)
    fill(user)
    message.success('资料已更新')
  } catch {
    // http 拦截器已经提示
  } finally {
    savingProfile.value = false
  }
}

async function savePrefs(): Promise<void> {
  savingPrefs.value = true
  try {
    const user = await updateNotificationPrefs({
      notify_health: prefs.notify_health,
      notify_order: prefs.notify_order,
      notify_system: prefs.notify_system,
    })
    auth.applyUser(user)
    message.success('通知偏好已保存')
  } catch {
    // http 拦截器已经提示
  } finally {
    savingPrefs.value = false
  }
}

async function savePassword(): Promise<void> {
  if (!password.old_password) {
    message.warning('请填写原密码')
    return
  }
  if (password.new_password.length < 8) {
    message.warning('新密码至少 8 位')
    return
  }
  if (password.new_password !== password.confirm) {
    message.warning('两次输入的新密码不一致')
    return
  }
  if (password.new_password === password.old_password) {
    message.warning('新密码不能与原密码相同')
    return
  }

  savingPassword.value = true
  try {
    const { token } = await changePassword({
      old_password: password.old_password,
      new_password: password.new_password,
    })
    // 修改密码会让旧令牌全部失效，这里换成服务端新签发的令牌。
    auth.applyToken(token)
    password.old_password = ''
    password.new_password = ''
    password.confirm = ''
    message.success('密码已修改，其他设备的登录已失效')
  } catch {
    // http 拦截器已经提示
  } finally {
    savingPassword.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">个人中心</h1>
        <p class="page-subtitle">
          维护联系方式和登录密码，并决定接收哪些站内通知。
        </p>
      </div>
    </div>

    <n-spin :show="loading">
      <div class="profile-grid">
        <div class="stack">
          <section class="card">
            <header class="card-head">
              <div class="head-icon"><AppIcon name="user" :size="16" /></div>
              <div>
                <h2 class="section-title">基本资料</h2>
                <p class="card-desc">
                  昵称会显示在工作台和交接单上，联系方式用于找回密码。
                </p>
              </div>
            </header>

            <n-form label-placement="top" class="card-body">
              <div class="form-grid">
                <n-form-item label="昵称" required>
                  <n-input
                    v-model:value="profile.nickname"
                    placeholder="例如：豆豆爸爸"
                    maxlength="50"
                  />
                </n-form-item>
                <n-form-item label="登录账号">
                  <n-input :value="auth.user?.username ?? ''" disabled />
                </n-form-item>
                <n-form-item>
                  <template #label>
                    邮箱
                    <span
                      v-if="profile.email.trim()"
                      class="verify-badge"
                      :class="{ on: emailVerified }"
                    >{{ emailVerified ? '已验证' : '未验证' }}</span>
                  </template>
                  <n-input
                    v-model:value="profile.email"
                    placeholder="name@example.com"
                    maxlength="120"
                  />
                </n-form-item>
                <n-form-item>
                  <template #label>
                    手机号
                    <span
                      v-if="profile.phone.trim()"
                      class="verify-badge"
                      :class="{ on: phoneVerified }"
                    >{{ phoneVerified ? '已验证' : '未验证' }}</span>
                  </template>
                  <n-input
                    v-model:value="profile.phone"
                    placeholder="11 位手机号"
                    maxlength="30"
                  />
                </n-form-item>
              </div>
              <p class="form-hint">
                邮箱或手机号至少填写一个；更换后需要重新验证，找回密码时才可用。
              </p>
            </n-form>

            <footer class="card-foot">
              <n-button
                type="primary"
                :loading="savingProfile"
                @click="saveProfile"
              >
                保存资料
              </n-button>
            </footer>
          </section>

          <section class="card">
            <header class="card-head">
              <div class="head-icon"><AppIcon name="shield" :size="16" /></div>
              <div>
                <h2 class="section-title">账号安全</h2>
                <p class="card-desc">
                  修改后当前设备会自动换用新凭证，其他设备需要重新登录。
                </p>
              </div>
            </header>

            <n-form label-placement="top" class="card-body">
              <div class="form-grid">
                <n-form-item label="原密码" required>
                  <n-input
                    v-model:value="password.old_password"
                    type="password"
                    show-password-on="click"
                    placeholder="当前登录密码"
                  />
                </n-form-item>
                <div />
                <n-form-item label="新密码" required>
                  <n-input
                    v-model:value="password.new_password"
                    type="password"
                    show-password-on="click"
                    placeholder="至少 8 位"
                  />
                </n-form-item>
                <n-form-item label="确认新密码" required>
                  <n-input
                    v-model:value="password.confirm"
                    type="password"
                    show-password-on="click"
                    placeholder="再输入一次"
                  />
                </n-form-item>
              </div>
            </n-form>

            <footer class="card-foot">
              <n-button
                type="primary"
                secondary
                :loading="savingPassword"
                @click="savePassword"
              >
                修改密码
              </n-button>
            </footer>
          </section>
        </div>

        <aside class="stack">
          <section class="card">
            <header class="card-head">
              <div class="head-icon"><AppIcon name="bell" :size="16" /></div>
              <div>
                <h2 class="section-title">通知偏好</h2>
                <p class="card-desc">关闭后不再产生该类新通知，历史记录仍保留。</p>
              </div>
            </header>

            <div class="card-body prefs">
              <label class="pref-row">
                <span>
                  <strong>健康提醒</strong>
                  <small>疫苗、驱虫等临近到期时提醒</small>
                </span>
                <n-switch v-model:value="prefs.notify_health" />
              </label>
              <label class="pref-row">
                <span>
                  <strong>订单动态</strong>
                  <small>预约确认、入住、退房与支付结果</small>
                </span>
                <n-switch v-model:value="prefs.notify_order" />
              </label>
              <label class="pref-row">
                <span>
                  <strong>系统通知</strong>
                  <small>账号安全与平台公告</small>
                </span>
                <n-switch v-model:value="prefs.notify_system" />
              </label>
            </div>

            <footer class="card-foot">
              <n-button
                type="primary"
                secondary
                :loading="savingPrefs"
                @click="savePrefs"
              >
                保存偏好
              </n-button>
            </footer>
          </section>

          <section class="card">
            <header class="card-head">
              <div class="head-icon"><AppIcon name="clipboard" :size="16" /></div>
              <div>
                <h2 class="section-title">账号信息</h2>
                <p class="card-desc">由平台维护，如需变更请联系管理员。</p>
              </div>
            </header>
            <dl class="card-body info-list">
              <div>
                <dt>登录账号</dt>
                <dd>{{ auth.user?.username ?? '—' }}</dd>
              </div>
              <div>
                <dt>账号角色</dt>
                <dd>{{ roleLabel || '—' }}</dd>
              </div>
              <div>
                <dt>注册时间</dt>
                <dd>{{ joinedAt }}</dd>
              </div>
              <div>
                <dt>账号状态</dt>
                <dd>
                  <span class="pill" :class="auth.user?.status === 1 ? 'sage' : 'red'">
                    <span class="status-dot" />
                    {{ auth.user?.status === 1 ? '正常' : '已停用' }}
                  </span>
                </dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 1fr);
  gap: 14px;
  align-items: start;
}

.stack {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 14px;
}

.card {
  overflow: hidden;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.card-head {
  display: flex;
  gap: 11px;
  padding: 16px 18px 14px;
  border-bottom: 1px solid var(--pc-line);
}

.head-icon {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  place-items: center;
  border-radius: 6px;
  background: var(--pc-primary-soft);
  color: var(--pc-primary);
}

.card-desc {
  margin: 4px 0 0;
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.55;
}

.card-body {
  padding: 18px;
}

.card-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 18px;
  border-top: 1px solid var(--pc-line);
  background: var(--pc-surface-muted);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.form-hint {
  margin: -4px 0 0;
  color: var(--pc-ink-faint);
  font-size: 12px;
  line-height: 1.6;
}

.verify-badge {
  margin-left: 6px;
  padding: 0 5px;
  border-radius: 3px;
  background: var(--pc-surface-muted);
  color: var(--pc-ink-faint);
  font-size: 10px;
  font-weight: 600;
  line-height: 1.7;
}

.verify-badge.on {
  background: var(--pc-ok-soft);
  color: var(--pc-ok);
}

.prefs {
  display: flex;
  flex-direction: column;
  padding-top: 6px;
  padding-bottom: 6px;
}

.pref-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 0;
  border-bottom: 1px solid var(--pc-line);
  cursor: pointer;
}

.pref-row:last-child {
  border-bottom: 0;
}

.pref-row span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.pref-row strong {
  font-size: 13px;
  font-weight: 600;
}

.pref-row small {
  color: var(--pc-ink-faint);
  font-size: 11.5px;
  line-height: 1.5;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
}

.info-list > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.info-list dt {
  color: var(--pc-ink-soft);
  font-size: 12.5px;
}

.info-list dd {
  margin: 0;
  font-size: 12.5px;
  font-weight: 600;
  text-align: right;
}

@media (max-width: 1080px) {
  .profile-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 620px) {
  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .form-grid > div:empty {
    display: none;
  }
}
</style>
