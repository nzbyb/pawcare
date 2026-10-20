<script setup lang="ts">
import type { Pet } from '@/types'
import { genderLabel, petAge, speciesLabel } from '@/utils/format'

defineProps<{ pet: Pet }>()
</script>

<template>
  <router-link :to="`/pets/${pet.id}`" class="pet-card">
    <div class="avatar">
      <strong>{{ pet.name.slice(0, 1) }}</strong>
      <small>{{ pet.species === 'cat' ? 'CAT' : pet.species === 'dog' ? 'DOG' : 'PET' }}</small>
    </div>

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
  padding: 16px;
  border: 1px solid var(--pc-line);
  border-radius: var(--pc-radius);
  background: var(--pc-surface);
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.pet-card:hover {
  border-color: var(--pc-line-strong);
  background: #fcfcfa;
}

.avatar {
  display: flex;
  width: 52px;
  height: 52px;
  flex: 0 0 52px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--pc-line);
  border-radius: 7px;
  background: var(--pc-surface-muted);
  color: var(--pc-primary);
  line-height: 1.1;
}

.avatar strong {
  font-size: 18px;
  font-weight: 700;
}

.avatar small {
  margin-top: 3px;
  color: var(--pc-ink-faint);
  font-size: 8px;
  font-weight: 650;
  letter-spacing: 0.08em;
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
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta {
  margin: 4px 0 8px;
  color: var(--pc-ink-faint);
  font-size: 11.5px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.arrow {
  color: var(--pc-line-strong);
  font-size: 16px;
  transition:
    transform 0.15s ease,
    color 0.15s ease;
}

.pet-card:hover .arrow {
  transform: translateX(2px);
  color: var(--pc-primary);
}
</style>
