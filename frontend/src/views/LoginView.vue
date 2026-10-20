<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NTabPane,
  NTabs,
  useMessage,
} from 'naive-ui'

import AppLogo from '@/components/AppLogo.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()

const activeTab = ref<string>('login')
const loginLoading = ref(false)
const registerLoading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
})

const registerForm = reactive({
  username: '',
  nickname: '',
  password: '',
  confirmPassword: '',
})

const highlights = [
  { title: '健康档案', text: '疫苗、驱虫、就诊记录集中管理，到期自动提醒。' },
  { title: '寄养预约', text: '查看笼舍空档，生成预约草稿，确认后才真正下单。' },
  { title: '智能助手', text: '用一句话查档案、问注意事项、预约寄养。' },
]

function redirectAfterLogin(): void {
  const redirect =
    typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  router.replace(redirect)
}

async function handleLogin(): Promise<void> {
  if (!loginForm.username.trim() || !loginForm.password) {
    message.warning('请输入账号和密码')
    return
  }
  loginLoading.value = true
  try {
    await auth.login(loginForm.username.trim(), loginForm.password)
    message.success(`欢迎回来，${auth.displayName}`)
    redirectAfterLogin()
  } catch {
    // http 拦截器已经提示
  } finally {
    loginLoading.value = false
  }
}

async function handleRegister(): Promise<void> {
  const username = registerForm.username.trim()
  if (username.length < 3) {
    message.warning('账号至少 3 个字符')
    return
  }
  if (registerForm.password.length < 8) {
    message.warning('密码至少 8 位')
    return
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    message.warning('两次输入的密码不一致')
    return
  }

  registerLoading.value = true
  try {
    await auth.register({
      username,
      password: registerForm.password,
      nickname: registerForm.nickname.trim() || undefined,
    })
    message.success('注册成功，欢迎加入 PawCare')
    redirectAfterLogin()
  } catch {
    // http 拦截器已经提示
  } finally {
    registerLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <section class="brand-panel">
      <div class="brand-top">
        <AppLogo variant="inverse" :size="40" />
      </div>

      <div class="brand-copy">
        <span class="eyebrow">毕业设计项目</span>
        <h2>把健康档案、寄养安排和日常提醒，放在同一个地方。</h2>
        <p>
          记录每一次疫苗和体重变化，预约寄养前先看空档，
          再让智能助手帮你把信息整理成一句话就能看懂的答案。
        </p>
      </div>

      <div class="highlights">
        <div v-for="(item, index) in highlights" :key="item.title" class="highlight">
          <span class="highlight-index">0{{ index + 1 }}</span>
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.text }}</p>
          </div>
        </div>
      </div>

      <p class="brand-foot">PawCare · 2026</p>
    </section>

    <section class="form-panel">
      <div class="form-card">
        <div class="form-head">
          <AppLogo class="form-logo" :size="36" :show-text="false" />
          <span class="form-kicker">PawCare</span>
          <h2>{{ activeTab === 'login' ? '登录账户' : '创建账户' }}</h2>
          <p>
            {{
              activeTab === 'login'
                ? '登录后继续管理宠物档案与寄养安排。'
                : '注册后即可建立第一份宠物档案。'
            }}
          </p>
        </div>

        <n-tabs v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="login" tab="登录">
            <n-form class="form" @submit.prevent="handleLogin">
              <n-form-item label="账号">
                <n-input
                  v-model:value="loginForm.username"
                  placeholder="请输入账号"
                  size="large"
                  clearable
                  @keyup.enter="handleLogin"
                />
              </n-form-item>
              <n-form-item label="密码">
                <n-input
                  v-model:value="loginForm.password"
                  type="password"
                  show-password-on="click"
                  placeholder="请输入密码"
                  size="large"
                  @keyup.enter="handleLogin"
                />
              </n-form-item>
              <n-button
                type="primary"
                size="large"
                block
                :loading="loginLoading"
                @click="handleLogin"
              >
                登录
              </n-button>
            </n-form>
          </n-tab-pane>

          <n-tab-pane name="register" tab="注册">
            <n-form class="form" @submit.prevent="handleRegister">
              <n-form-item label="账号">
                <n-input
                  v-model:value="registerForm.username"
                  placeholder="字母、数字或下划线，至少 3 位"
                  size="large"
                  clearable
                />
              </n-form-item>
              <n-form-item label="昵称（可选）">
                <n-input
                  v-model:value="registerForm.nickname"
                  placeholder="怎么称呼你？"
                  size="large"
                  clearable
                />
              </n-form-item>
              <n-form-item label="密码">
                <n-input
                  v-model:value="registerForm.password"
                  type="password"
                  show-password-on="click"
                  placeholder="至少 8 位"
                  size="large"
                />
              </n-form-item>
              <n-form-item label="确认密码">
                <n-input
                  v-model:value="registerForm.confirmPassword"
                  type="password"
                  show-password-on="click"
                  placeholder="再输入一次密码"
                  size="large"
                  @keyup.enter="handleRegister"
                />
              </n-form-item>
              <n-button
                type="primary"
                size="large"
                block
                :loading="registerLoading"
                @click="handleRegister"
              >
                注册并登录
              </n-button>
            </n-form>
          </n-tab-pane>
        </n-tabs>

        <p class="form-tip">
          当前为开发环境。请勿在演示环境填写真实敏感信息。
        </p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(0, 1.02fr) minmax(440px, 0.98fr);
}

.brand-panel {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 44px 52px 36px;
  background: #1f3a32;
  color: #f2f4ef;
}

.brand-top {
  display: flex;
  align-items: center;
}

.brand-copy {
  max-width: 540px;
  padding: 48px 0 30px;
}

.eyebrow {
  display: inline-block;
  margin-bottom: 16px;
  color: rgba(242, 244, 239, 0.5);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.brand-copy h2 {
  margin: 0;
  font-size: clamp(28px, 3vw, 38px);
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.28;
}

.brand-copy > p {
  max-width: 470px;
  margin: 18px 0 0;
  color: rgba(242, 244, 239, 0.66);
  font-size: 13.5px;
  line-height: 1.8;
}

.highlights {
  display: flex;
  max-width: 540px;
  flex-direction: column;
}

.highlight {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 12px;
  padding: 14px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.highlight:last-child {
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}

.highlight-index {
  padding-top: 1px;
  color: rgba(242, 244, 239, 0.4);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.highlight strong {
  font-size: 13px;
  font-weight: 600;
}

.highlight p {
  margin: 3px 0 0;
  color: rgba(242, 244, 239, 0.58);
  font-size: 12px;
  line-height: 1.6;
}

.brand-foot {
  margin: 28px 0 0;
  color: rgba(242, 244, 239, 0.34);
  font-size: 11px;
}

.form-panel {
  display: grid;
  place-items: center;
  padding: 40px 28px;
  background: var(--pc-bg);
}

.form-card {
  width: 100%;
  max-width: 400px;
  padding: 30px 32px 26px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
}

.form-head {
  margin-bottom: 18px;
}

.form-logo {
  display: none;
}

.form-kicker {
  display: block;
  margin-bottom: 6px;
  color: var(--pc-primary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.form-head h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.form-head p {
  margin: 7px 0 0;
  color: var(--pc-ink-soft);
  font-size: 12.5px;
  line-height: 1.6;
}

.form {
  margin-top: 6px;
}

.form-tip {
  margin: 20px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--pc-line);
  color: var(--pc-ink-faint);
  font-size: 11px;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: minmax(0, 1fr);
  }

  .brand-panel {
    display: none;
  }

  .form-panel {
    padding: 28px 16px;
  }

  .form-card {
    padding: 24px 20px;
  }

  .form-logo {
    display: block;
    margin-bottom: 14px;
  }
}
</style>
