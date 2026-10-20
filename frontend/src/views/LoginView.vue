<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton,
  NCheckbox,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NRadioButton,
  NRadioGroup,
  NTabPane,
  NTabs,
  useMessage,
} from 'naive-ui'

import AppLogo from '@/components/AppLogo.vue'
import {
  resetPassword,
  sendVerificationCode,
  type VerificationChannel,
} from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/
const PHONE_RE = /^1[3-9]\d{9}$/

const activeTab = ref<string>('login')
const loginLoading = ref(false)
const registerLoading = ref(false)
const registerSending = ref(false)
const resetSending = ref(false)
const registerCooldown = ref(0)
const resetCooldown = ref(0)
const agreed = ref(false)

const agreementVisible = ref(false)
const agreementTab = ref<'terms' | 'privacy'>('terms')
const resetVisible = ref(false)
const resetForm = reactive({
  channel: 'email' as VerificationChannel,
  contact: '',
  code: '',
  password: '',
  confirmPassword: '',
})

const loginForm = reactive({
  username: '',
  password: '',
})

const registerForm = reactive({
  username: '',
  nickname: '',
  channel: 'email' as VerificationChannel,
  contact: '',
  code: '',
  password: '',
  confirmPassword: '',
})

const highlights = [
  { title: '健康档案', text: '疫苗、驱虫、就诊记录集中管理，到期自动提醒。' },
  { title: '寄养预约', text: '查看笼舍空档，生成预约草稿，确认后才真正下单。' },
  { title: '智能助手', text: '用一句话查档案、问注意事项、预约寄养。' },
]

const contactLabel = computed(() =>
  registerForm.channel === 'email' ? '邮箱' : '手机号',
)

const passwordScore = computed(() => {
  const value = registerForm.password
  if (!value) return 0
  let score = value.length >= 8 ? 1 : 0
  if (value.length >= 8 && /[A-Za-z]/.test(value) && /\d/.test(value)) score += 1
  if (value.length >= 8 && (/[^A-Za-z0-9]/.test(value) || value.length >= 12)) {
    score += 1
  }
  return score
})

const passwordLabel = computed(
  () => ['太短', '弱', '中', '强'][passwordScore.value] ?? '太短',
)

const timers: number[] = []

function startCooldown(target: Ref<number>, seconds: number): void {
  target.value = seconds
  const timer = window.setInterval(() => {
    target.value -= 1
    if (target.value <= 0) {
      target.value = 0
      window.clearInterval(timer)
    }
  }, 1000)
  timers.push(timer)
}

onBeforeUnmount(() => {
  timers.forEach((timer) => window.clearInterval(timer))
})

function handleChannelChange(
  value: string | number | boolean | null,
  form: { channel: VerificationChannel; contact: string; code: string },
): void {
  form.channel = String(value) === 'phone' ? 'phone' : 'email'
  form.contact = ''
  form.code = ''
}

function contactError(channel: VerificationChannel, value: string): string | null {
  if (!value) return `请输入${channel === 'email' ? '邮箱' : '手机号'}`
  if (channel === 'email' && !EMAIL_RE.test(value)) return '邮箱格式不正确'
  if (channel === 'phone' && !PHONE_RE.test(value)) return '请输入 11 位大陆手机号'
  return null
}

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

async function handleSendCode(scene: 'register' | 'reset'): Promise<void> {
  const sending = scene === 'register' ? registerSending : resetSending
  const cooldown = scene === 'register' ? registerCooldown : resetCooldown
  const form = scene === 'register' ? registerForm : resetForm
  if (sending.value || cooldown.value > 0) return

  const target = form.contact.trim()
  const error = contactError(form.channel, target)
  if (error) {
    message.warning(error)
    return
  }

  sending.value = true
  try {
    const result = await sendVerificationCode({
      channel: form.channel,
      target,
      scene,
    })
    startCooldown(cooldown, result.cooldown)
    if (result.debug_code) {
      form.code = result.debug_code
      message.info(`本地调试验证码：${result.debug_code}`)
    } else {
      message.success('验证码已发送，请查收')
    }
  } catch {
    // http 拦截器已经提示
  } finally {
    sending.value = false
  }
}

async function handleRegister(): Promise<void> {
  const username = registerForm.username.trim()
  if (username.length < 3) {
    message.warning('账号至少 3 个字符')
    return
  }
  const contact = registerForm.contact.trim()
  const error = contactError(registerForm.channel, contact)
  if (error) {
    message.warning(error)
    return
  }
  if (!/^\d{6}$/.test(registerForm.code)) {
    message.warning('请输入 6 位验证码')
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
  if (!agreed.value) {
    message.warning('请先阅读并同意用户协议和隐私政策')
    return
  }

  registerLoading.value = true
  try {
    await auth.register({
      username,
      password: registerForm.password,
      nickname: registerForm.nickname.trim() || undefined,
      code: registerForm.code,
      ...(registerForm.channel === 'email'
        ? { email: contact }
        : { phone: contact }),
    })
    message.success('注册成功，欢迎加入 PawCare')
    redirectAfterLogin()
  } catch {
    // http 拦截器已经提示
  } finally {
    registerLoading.value = false
  }
}

function openReset(): void {
  resetForm.code = ''
  resetForm.password = ''
  resetForm.confirmPassword = ''
  resetCooldown.value = 0
  resetVisible.value = true
}

async function handleReset(): Promise<void> {
  const target = resetForm.contact.trim()
  const error = contactError(resetForm.channel, target)
  if (error) {
    message.warning(error)
    return
  }
  if (!/^\d{6}$/.test(resetForm.code)) {
    message.warning('请输入 6 位验证码')
    return
  }
  if (resetForm.password.length < 8) {
    message.warning('新密码至少 8 位')
    return
  }
  if (resetForm.password !== resetForm.confirmPassword) {
    message.warning('两次输入的新密码不一致')
    return
  }

  resetSending.value = true
  try {
    const result = await resetPassword({
      channel: resetForm.channel,
      target,
      code: resetForm.code,
      new_password: resetForm.password,
    })
    resetVisible.value = false
    activeTab.value = 'login'
    loginForm.username = result.username
    loginForm.password = ''
    message.success('密码已重置，请用新密码登录')
  } catch {
    // http 拦截器已经提示
  } finally {
    resetSending.value = false
  }
}

function openAgreement(tab: 'terms' | 'privacy'): void {
  agreementTab.value = tab
  agreementVisible.value = true
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
                : '邮箱或手机号验证后即可建立第一份宠物档案。'
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
              <div class="form-actions">
                <n-button text type="primary" size="small" @click="openReset">
                  忘记密码？
                </n-button>
              </div>
              <n-button
                type="primary"
                size="large"
                block
                :loading="loginLoading"
                @click="handleLogin"
              >
                登录
              </n-button>
              <p class="field-hint">
                连续 5 次密码错误将锁定账号 15 分钟；登录失败不会提示账号是否存在。
              </p>
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

              <n-form-item label="验证方式">
                <n-radio-group
                  :value="registerForm.channel"
                  size="small"
                  @update:value="handleChannelChange($event, registerForm)"
                >
                  <n-radio-button value="email">邮箱</n-radio-button>
                  <n-radio-button value="phone">手机号</n-radio-button>
                </n-radio-group>
              </n-form-item>
              <n-form-item :label="contactLabel">
                <n-input
                  v-model:value="registerForm.contact"
                  :placeholder="
                    registerForm.channel === 'email'
                      ? '用于接收验证码，例如 name@example.com'
                      : '11 位大陆手机号'
                  "
                  size="large"
                  clearable
                />
              </n-form-item>
              <n-form-item label="验证码">
                <div class="code-row">
                  <n-input
                    v-model:value="registerForm.code"
                    placeholder="6 位数字"
                    size="large"
                    maxlength="6"
                  />
                  <n-button
                    size="large"
                    :disabled="registerCooldown > 0"
                    :loading="registerSending"
                    @click="handleSendCode('register')"
                  >
                    {{
                      registerCooldown > 0
                        ? `${registerCooldown}s 后重发`
                        : '获取验证码'
                    }}
                  </n-button>
                </div>
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
              <div v-if="registerForm.password" class="strength">
                <span
                  v-for="level in 3"
                  :key="level"
                  class="strength-bar"
                  :class="{ active: passwordScore >= level }"
                />
                <span class="strength-label">密码强度：{{ passwordLabel }}</span>
              </div>
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

              <div class="agreement">
                <n-checkbox v-model:checked="agreed">
                  <span class="agreement-text">
                    我已阅读并同意
                    <n-button text type="primary" size="tiny" @click.stop="openAgreement('terms')">
                      用户协议
                    </n-button>
                    和
                    <n-button text type="primary" size="tiny" @click.stop="openAgreement('privacy')">
                      隐私政策
                    </n-button>
                  </span>
                </n-checkbox>
              </div>

              <n-button
                type="primary"
                size="large"
                block
                :loading="registerLoading"
                @click="handleRegister"
              >
                注册并登录
              </n-button>
              <p class="field-hint">
                验证码 5 分钟内有效且只能使用一次；PawCare 不会向你索要验证码。
              </p>
            </n-form>
          </n-tab-pane>
        </n-tabs>

        <p class="form-tip">
          演示环境的账号与数据均为合成数据，请勿填写真实敏感信息。
        </p>
      </div>
    </section>

    <n-modal
      v-model:show="resetVisible"
      preset="card"
      title="重置密码"
      class="dialog-card"
      :style="{ width: '420px', maxWidth: 'calc(100vw - 32px)' }"
    >
      <n-form class="form" @submit.prevent="handleReset">
        <n-form-item label="验证方式">
          <n-radio-group
            :value="resetForm.channel"
            size="small"
            @update:value="handleChannelChange($event, resetForm)"
          >
            <n-radio-button value="email">邮箱</n-radio-button>
            <n-radio-button value="phone">手机号</n-radio-button>
          </n-radio-group>
        </n-form-item>
        <n-form-item :label="resetForm.channel === 'email' ? '注册邮箱' : '注册手机号'">
          <n-input
            v-model:value="resetForm.contact"
            :placeholder="
              resetForm.channel === 'email'
                ? '填写注册时验证的邮箱'
                : '填写注册时验证的手机号'
            "
            size="large"
            clearable
          />
        </n-form-item>
        <n-form-item label="验证码">
          <div class="code-row">
            <n-input
              v-model:value="resetForm.code"
              placeholder="6 位数字"
              size="large"
              maxlength="6"
            />
            <n-button
              size="large"
              :disabled="resetCooldown > 0"
              :loading="resetSending"
              @click="handleSendCode('reset')"
            >
              {{ resetCooldown > 0 ? `${resetCooldown}s 后重发` : '获取验证码' }}
            </n-button>
          </div>
        </n-form-item>
        <n-form-item label="新密码">
          <n-input
            v-model:value="resetForm.password"
            type="password"
            show-password-on="click"
            placeholder="至少 8 位"
            size="large"
          />
        </n-form-item>
        <n-form-item label="确认新密码">
          <n-input
            v-model:value="resetForm.confirmPassword"
            type="password"
            show-password-on="click"
            placeholder="再输入一次新密码"
            size="large"
            @keyup.enter="handleReset"
          />
        </n-form-item>
        <n-button
          type="primary"
          size="large"
          block
          :loading="resetSending"
          @click="handleReset"
        >
          重置密码
        </n-button>
        <p class="field-hint">
          重置后旧密码和此前签发的登录令牌会立即失效。
        </p>
      </n-form>
    </n-modal>

    <n-modal
      v-model:show="agreementVisible"
      preset="card"
      title="用户协议与隐私政策"
      class="dialog-card"
      :style="{ width: '620px', maxWidth: 'calc(100vw - 32px)' }"
    >
      <n-tabs v-model:value="agreementTab" type="line" animated>
        <n-tab-pane name="terms" tab="用户协议">
          <div class="legal-text">
            <p>1. PawCare 是河南科技职业大学本科毕业设计作品，用于演示宠物寄养与健康管理功能，不提供真实商业寄养服务。</p>
            <p>2. 演示环境的账号、宠物与订单均为合成数据。请勿录入真实身份证号、银行卡号、支付信息等敏感内容。</p>
            <p>3. 请妥善保管账号和密码。连续 5 次密码错误会临时锁定账号 15 分钟。</p>
            <p>4. 验证码只用于注册和重置密码，5 分钟内有效且只能使用一次，请勿转发给他人。</p>
            <p>5. 系统会随版本迭代调整功能，影响使用的重大变更会在页面提示。</p>
          </div>
        </n-tab-pane>
        <n-tab-pane name="privacy" tab="隐私政策">
          <div class="legal-text">
            <p>1. 收集范围：账号、昵称、邮箱或手机号、宠物档案与健康记录、寄养订单、智能助手对话内容。</p>
            <p>2. 使用目的：账号登录与身份验证、疫苗与用药提醒、寄养安排、故障排查和效果评测。</p>
            <p>3. 存储方式：数据保存在本项目自建的 MySQL 数据库中；验证码只保存 HMAC 摘要，不保存明文。</p>
            <p>4. 第三方共享：生成智能助手回答时会调用大模型接口；除此之外不向第三方出售或共享你的数据。</p>
            <p>5. 数据删除：可联系管理员删除账号及关联数据；演示环境会定期重置。</p>
            <p>6. 未成年人应在监护人陪同下使用本系统。</p>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-modal>
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

.form-actions {
  display: flex;
  justify-content: flex-end;
  margin: -6px 0 14px;
}

.code-row {
  display: flex;
  width: 100%;
  gap: 8px;
}

.code-row :deep(.n-input) {
  flex: 1;
  min-width: 0;
}

.code-row :deep(.n-button) {
  flex: none;
  min-width: 108px;
}

.strength {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: -6px 0 14px;
}

.strength-bar {
  width: 34px;
  height: 3px;
  border-radius: 2px;
  background: var(--pc-line);
}

.strength-bar.active {
  background: var(--pc-primary);
}

.strength-label {
  margin-left: 4px;
  color: var(--pc-ink-faint);
  font-size: 11px;
}

.agreement {
  margin: 2px 0 16px;
}

.agreement-text {
  color: var(--pc-ink-soft);
  font-size: 12px;
  line-height: 1.7;
}

.field-hint {
  margin: 12px 0 0;
  color: var(--pc-ink-faint);
  font-size: 11px;
  line-height: 1.65;
}

.form-tip {
  margin: 20px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--pc-line);
  color: var(--pc-ink-faint);
  font-size: 11px;
  line-height: 1.6;
}

.dialog-card {
  border-radius: var(--pc-radius);
}

.legal-text {
  max-height: 52vh;
  overflow-y: auto;
  padding-right: 4px;
}

.legal-text p {
  margin: 0 0 10px;
  color: var(--pc-ink-soft);
  font-size: 12.5px;
  line-height: 1.85;
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
