<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NSpin, useMessage } from 'naive-ui'

import { getAdminSettings, updateAdminSettings } from '@/api/system'
import type { SystemSettingItem } from '@/types'

const message = useMessage()

const items = ref<SystemSettingItem[]>([])
const form = reactive<Record<string, string>>({})
const loading = ref(false)
const saving = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = await getAdminSettings()
    for (const item of items.value) form[item.key] = item.value
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  try {
    await updateAdminSettings(
      items.value.map((item) => ({ key: item.key, value: form[item.key] ?? '' })),
    )
    message.success('设置已保存，前台页面会立即生效')
    await load()
  } finally {
    saving.value = false
  }
}

function reset(): void {
  for (const item of items.value) form[item.key] = item.value
}

function updatedAt(key: string): string {
  const value = items.value.find((item) => item.key === key)?.update_time
  return value ? `最近修改：${value.slice(0, 16).replace('T', ' ')}` : '尚未修改，当前为默认值'
}

onMounted(load)
</script>

<template>
  <section class="admin-block">
    <header class="block-head">
      <div>
        <h2 class="section-title">系统设置</h2>
        <p class="muted">
          门店信息显示在「帮助与反馈 → 服务指南」，保存后立即生效；每次修改都会写入审计日志。
        </p>
      </div>
      <div class="actions">
        <n-button @click="reset">还原</n-button>
        <n-button type="primary" :loading="saving" @click="save">保存设置</n-button>
      </div>
    </header>

    <n-spin :show="loading">
      <n-form label-placement="top" class="settings-form">
        <n-form-item label="门店名称">
          <n-input v-model:value="form.store_name" maxlength="60" placeholder="例如：PawCare 宠物寄养中心" />
          <span class="hint">{{ updatedAt('store_name') }}</span>
        </n-form-item>
        <n-form-item label="客服电话">
          <n-input v-model:value="form.service_phone" maxlength="40" placeholder="例如：400-000-0000" />
          <span class="hint">{{ updatedAt('service_phone') }}</span>
        </n-form-item>
        <n-form-item label="门店地址">
          <n-input v-model:value="form.store_address" maxlength="120" placeholder="留空时前台显示「暂未设置」" />
          <span class="hint">{{ updatedAt('store_address') }}</span>
        </n-form-item>
        <n-form-item label="营业时间">
          <n-input v-model:value="form.business_hours" maxlength="60" placeholder="例如：每天 08:00 - 21:00" />
          <span class="hint">{{ updatedAt('business_hours') }}</span>
        </n-form-item>
        <n-form-item label="预约须知">
          <n-input
            v-model:value="form.booking_notice"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 6 }"
            maxlength="500"
            show-count
            placeholder="显示在服务指南的预约须知里"
          />
          <span class="hint">{{ updatedAt('booking_notice') }}</span>
        </n-form-item>
      </n-form>
    </n-spin>
  </section>
</template>

<style scoped>
.admin-block { display: grid; gap: 16px; }
.block-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.actions { display: flex; gap: 10px; }
.muted { color: var(--pc-ink-soft); font-size: 12px; line-height: 1.7; }
.settings-form { max-width: 560px; }
.hint { display: block; margin-top: 4px; color: var(--pc-ink-faint); font-size: 11px; }
</style>
