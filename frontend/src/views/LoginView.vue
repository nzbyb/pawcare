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
  { icon: '📋', title: '健康档案', text: '疫苗、驱虫、就诊记录集中管理，到期自动提醒。' },
  { icon: '🏡', title: '寄养预约', text: '查看笼舍空档，生成预约草稿，确认后才真正下单。' },
  { icon: '🤖', title: '智能助手', text: '用一句话查档案、问注意事项、预约寄养。' },
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
        <span class="logo">🐾</span>
        <div>
          <h1>PawCare</h1>
          <p>宠物寄养与健康管理</p>
        </div>
      </div>

      <div class="brand-copy">
        <span class="eyebrow">为毛孩子多想一步</span>
        <h2>把健康档案、寄养安排和日常提醒，放在同一个地方。</h2>
        <p>
          记录每一次疫苗和体重变化，预约寄养前先看空档，
          再让智能助手帮你把信息整理成一句话就能看懂的答案。
        </p>
      </div>

      <div class="highlights">
        <div v-for="item in highlights" :key="item.title" class="highlight">
          <span class="highlight-icon">{{ item.icon }}</span>
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.text }}</p>
          </div>
        </div>
      </div>

      <p class="brand-foot">PawCare · 毕业设计项目</p>
    </section>

    <section class="form-panel">
      <div class="form-card">
        <div class="form-head">
          <span class="form-logo">🐾</span>
          <h2>{{ activeTab === 'login' ? '欢迎回来' : '创建 PawCare 账号' }}</h2>
          <p>
            {{
              activeTab === 'login'
                ? '登录后继续照顾你的毛孩子。'
                : '注册后即可建立宠物档案。'
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
  grid-template-columns: minmax(0, 1.05fr) minmax(420px, 0.95fr);
}

.brand-panel {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 48px 56px;
  background:
    radial-gradient(circle at 16% 14%, rgba(255, 255, 255, 0.72), transparent 36%),
    linear-gradient(150deg, #f8d7c4 0%, #f3b997 42%, #e8835a 100%);
  color: #4a2c1f;
}

.brand-top {
  display: flex;
  align-items: center;
  gap: 13px;
}

.logo {
  display: grid;
  width: 52px;
  height: 52px;
  place-items: center;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 12px 30px rgba(97, 52, 29, 0.18);
  font-size: 27px;
}

.brand-top h1 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.02em;
}

.brand-top p {
  margin: 2px 0 0;
  font-size: 13px;
  opacity: 0.78;
}

.brand-copy {
  max-width: 540px;
  padding: 48px 0 32px;
}

.eyebrow {
  display: inline-block;
  margin-bottom: 16px;
  padding: 5px 12px;
  border: 1px solid rgba(74, 44, 31, 0.18);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.brand-copy h2 {
  margin: 0;
  font-size: clamp(30px, 3.4vw, 46px);
  font-weight: 850;
  letter-spacing: -0.035em;
  line-height: 1.18;
}

.brand-copy > p {
  margin: 20px 0 0;
  max-width: 460px;
  font-size: 15px;
  line-height: 1.8;
  opacity: 0.82;
}

.highlights {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 520px;
}

.highlight {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.38);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.28);
  backdrop-filter: blur(8px);
}

.highlight-icon {
  font-size: 20px;
}

.highlight strong {
  font-size: 14px;
}

.highlight p {
  margin: 3px 0 0;
  font-size: 12px;
  line-height: 1.6;
  opacity: 0.8;
}

.brand-foot {
  margin: 34px 0 0;
  font-size: 12px;
  opacity: 0.6;
}

.form-panel {
  display: grid;
  place-items: center;
  padding: 40px 28px;
}

.form-card {
  width: 100%;
  max-width: 420px;
}

.form-head {
  margin-bottom: 22px;
}

.form-logo {
  display: none;
}

.form-head h2 {
  margin: 0;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.form-head p {
  margin: 8px 0 0;
  color: var(--pc-ink-soft);
  font-size: 14px;
}

.form {
  margin-top: 8px;
}

.form-tip {
  margin: 22px 0 0;
  color: #9a8f85;
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: minmax(0, 1fr);
  }

  .brand-panel {
    display: none;
  }

  .form-panel {
    padding: 32px 20px;
  }

  .form-logo {
    display: grid;
    width: 54px;
    height: 54px;
    margin-bottom: 14px;
    place-items: center;
    border-radius: 17px;
    background: linear-gradient(135deg, #f7c9b3, #e8835a);
    font-size: 27px;
  }
}
</style>
