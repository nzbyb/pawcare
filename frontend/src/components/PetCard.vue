<script setup lang="ts">
import type { Pet } from '@/types'
import {
  genderLabel,
  petAge,
  speciesEmoji,
  speciesLabel,
} from '@/utils/format'

defineProps<{ pet: Pet }>()
</script>

<template>
  <router-link :to="`/pets/${pet.id}`" class="pet-card">
    <div class="avatar">{{ speciesEmoji(pet.species) }}</div>

    <div class="info">
      <div class="title-row">
        <h3>{{ pet.name }}</h3>
        <span v-if="pet.neutered" class="pill sage">已绝育</span>
      </div>
      <p class="meta">
        {{ speciesLabel(pet.species) }}
        <span v-if="pet.breed"> · {{ pet.breed }}</span>
        · {{ petAge(pet.birthday) }}
      </p>
      <div class="tags">
        <span class="pill grey">{{ genderLabel(pet.gender) }}</span>
        <span v-if="pet.allergies" class="pill">过敏：{{ pet.allergies }}</span>
      </div>
    </div>

    <span class="arrow" aria-hidden="true">→</span>
  </router-link>
</template>

<style scoped>
.pet-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border: 1px solid rgba(237, 228, 218, 0.95);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 10px 26px rgba(116, 88, 63, 0.06);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.pet-card:hover {
  transform: translateY(-3px);
  border-color: rgba(232, 131, 90, 0.36);
  box-shadow: var(--pc-shadow-hover);
}

.avatar {
  display: grid;
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  place-items: center;
  border-radius: 18px;
  background: linear-gradient(145deg, #fdf0e9, #f8ddce);
  font-size: 28px;
}

.info {
  min-width: 0;
  flex: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-row h3 {
  margin: 0;
  overflow: hidden;
  font-size: 17px;
  font-weight: 750;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta {
  margin: 4px 0 8px;
  color: var(--pc-ink-soft);
  font-size: 12px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.arrow {
  color: #c4b6a8;
  font-size: 18px;
  transition:
    transform 0.18s ease,
    color 0.18s ease;
}

.pet-card:hover .arrow {
  transform: translateX(3px);
  color: var(--pc-primary);
}
</style>
