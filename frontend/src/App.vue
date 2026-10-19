<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NMessageProvider,
  NNotificationProvider,
  dateZhCN,
  zhCN,
  type GlobalThemeOverrides,
} from 'naive-ui'

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#E8835A',
    primaryColorHover: '#F09A75',
    primaryColorPressed: '#D06F47',
    primaryColorSuppl: '#E8835A',
    infoColor: '#7C9A82',
    successColor: '#5FA87A',
    warningColor: '#E0A84A',
    errorColor: '#D95D5D',
    borderRadius: '12px',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
  },
  Button: {
    borderRadiusMedium: '10px',
    fontWeight: '600',
  },
  Card: {
    borderRadius: '18px',
  },
  Input: {
    borderRadius: '10px',
  },
  Tag: {
    borderRadius: '999px',
  },
}
</script>

<template>
  <n-config-provider
    :theme-overrides="themeOverrides"
    :locale="zhCN"
    :date-locale="dateZhCN"
  >
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <router-view />
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
