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
    primaryColor: '#2F5D50',
    primaryColorHover: '#3A6E5F',
    primaryColorPressed: '#264B41',
    primaryColorSuppl: '#2F5D50',
    infoColor: '#2F5D50',
    successColor: '#2F6B4F',
    warningColor: '#8A5A23',
    errorColor: '#A8423B',
    borderRadius: '8px',
    borderRadiusSmall: '6px',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    fontSize: '14px',
  },
  Button: {
    borderRadiusMedium: '6px',
    borderRadiusLarge: '6px',
    fontWeight: '600',
  },
  Card: {
    borderRadius: '8px',
  },
  Input: {
    borderRadius: '6px',
  },
  Tag: {
    borderRadius: '4px',
  },
  Tabs: {
    tabFontWeightActive: '600',
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
