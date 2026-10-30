<script setup lang="ts">
import OwnerDashboard from '@/components/OwnerDashboard.vue'
import StaffDashboard from '@/components/StaffDashboard.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <OwnerDashboard v-if="auth.user?.role === 'pet_owner'" />
  <StaffDashboard v-else />
</template>
