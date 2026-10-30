<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NEmpty, NSpin } from 'naive-ui'

import AppIcon from '@/components/AppIcon.vue'
import { listPets } from '@/api/pets'
import PetCard from '@/components/PetCard.vue'
import PetFormModal from '@/components/PetFormModal.vue'
import type { Pet } from '@/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canCreate = computed(() => auth.user?.role === 'pet_owner')

const pets = ref<Pet[]>([])
const loading = ref(true)
const showModal = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    pets.value = await listPets()
  } catch {
    pets.value = []
  } finally {
    loading.value = false
  }
}

function onSaved(): void {
  void load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">宠物档案</h1>
        <p class="page-subtitle">
          为每只毛孩子建立独立档案，健康记录和体重变化都会归档在这里。
        </p>
      </div>
      <n-button v-if="canCreate" type="primary" @click="showModal = true">
        <template #icon><AppIcon name="plus" :size="15" /></template>
        新增宠物
      </n-button>
    </div>

    <n-spin :show="loading">
      <div v-if="pets.length" class="grid grid-3">
        <PetCard v-for="pet in pets" :key="pet.id" :pet="pet" />
      </div>

      <div v-else-if="!loading" class="empty-wrap soft-card">
        <n-empty description="还没有宠物档案">
          <template v-if="canCreate" #extra>
            <n-button type="primary" @click="showModal = true">
              建立第一份档案
            </n-button>
          </template>
        </n-empty>
      </div>
    </n-spin>

    <PetFormModal v-if="canCreate" v-model:show="showModal" @saved="onSaved" />
  </div>
</template>

<style scoped>
.empty-wrap {
  display: grid;
  min-height: 320px;
  place-items: center;
  background: var(--pc-surface);
}
</style>
