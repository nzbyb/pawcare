<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import {
  NButton,
  NDatePicker,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSwitch,
  useMessage,
} from 'naive-ui'

import { createPet, updatePet } from '@/api/pets'
import { uploadImage, validateImage } from '@/api/uploads'
import type { Pet, PetGender, PetPayload, PetSpecies } from '@/types'

interface PetFormState {
  name: string
  species: string
  breed: string
  birthday: string | null
  gender: string
  neutered: boolean
  allergies: string
  notes: string
  photoUrl: string | null
}

const props = defineProps<{
  show: boolean
  pet?: Pet | null
}>()

const emit = defineEmits<{
  (event: 'update:show', value: boolean): void
  (event: 'saved', pet: Pet): void
}>()

const message = useMessage()
const saving = ref(false)
const uploading = ref(false)
const photoInput = ref<HTMLInputElement | null>(null)

const form = reactive<PetFormState>({
  name: '',
  species: 'dog',
  breed: '',
  birthday: null,
  gender: 'unknown',
  neutered: false,
  allergies: '',
  notes: '',
  photoUrl: null,
})

const speciesOptions = [
  { label: '狗狗', value: 'dog' },
  { label: '猫咪', value: 'cat' },
  { label: '其他', value: 'other' },
]

const genderOptions = [
  { label: '男孩子', value: 'male' },
  { label: '女孩子', value: 'female' },
  { label: '未知', value: 'unknown' },
]

watch(
  () => [props.show, props.pet] as const,
  ([show, pet]) => {
    if (!show) return
    form.name = pet?.name ?? ''
    form.species = pet?.species ?? 'dog'
    form.breed = pet?.breed ?? ''
    form.birthday = pet?.birthday ?? null
    form.gender = pet?.gender ?? 'unknown'
    form.neutered = pet?.neutered ?? false
    form.allergies = pet?.allergies ?? ''
    form.notes = pet?.notes ?? ''
    form.photoUrl = pet?.photo_url ?? null
  },
  { immediate: true },
)

function close(): void {
  emit('update:show', false)
}

function pickPhoto(): void {
  photoInput.value?.click()
}

async function onPhotoChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  const error = validateImage(file)
  if (error) {
    message.warning(error)
    return
  }

  uploading.value = true
  try {
    const result = await uploadImage(file, 'pet')
    form.photoUrl = result.url
    message.success('照片已上传')
  } catch {
    // http 拦截器已经提示
  } finally {
    uploading.value = false
  }
}

async function submit(): Promise<void> {
  if (!form.name.trim()) {
    message.warning('请填写宠物名字')
    return
  }

  const payload: PetPayload = {
    name: form.name.trim(),
    species: form.species as PetSpecies,
    breed: form.breed.trim() || null,
    birthday: form.birthday || null,
    gender: form.gender as PetGender,
    neutered: form.neutered,
    allergies: form.allergies.trim() || null,
    notes: form.notes.trim() || null,
    photo_url: form.photoUrl,
  }

  saving.value = true
  try {
    const pet = props.pet
      ? await updatePet(props.pet.id, payload)
      : await createPet(payload)
    message.success(props.pet ? '宠物档案已更新' : '宠物档案已建立')
    emit('saved', pet)
    close()
  } catch {
    // http 拦截器已经提示
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="pet ? '编辑宠物档案' : '新增宠物档案'"
    style="width: 580px; max-width: 92vw"
    :mask-closable="false"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top">
      <div class="photo-row">
        <div class="photo-preview" :class="{ empty: !form.photoUrl }">
          <img v-if="form.photoUrl" :src="form.photoUrl" :alt="form.name || '宠物照片'" />
          <span v-else>{{ form.name.trim().slice(0, 1) || '宠' }}</span>
        </div>
        <div class="photo-actions">
          <div class="photo-buttons">
            <n-button size="small" :loading="uploading" @click="pickPhoto">
              {{ form.photoUrl ? '更换照片' : '上传照片' }}
            </n-button>
            <n-button
              v-if="form.photoUrl"
              size="small"
              quaternary
              @click="form.photoUrl = null"
            >
              移除
            </n-button>
          </div>
          <p>JPG / PNG / WEBP，最大 10MB。也可以先保存档案，之后再补照片。</p>
        </div>
        <input
          ref="photoInput"
          type="file"
          accept="image/*"
          hidden
          @change="onPhotoChange"
        />
      </div>

      <div class="form-grid">
        <n-form-item label="名字" required>
          <n-input v-model:value="form.name" placeholder="例如：豆豆" maxlength="50" />
        </n-form-item>
        <n-form-item label="种类" required>
          <n-select v-model:value="form.species" :options="speciesOptions" />
        </n-form-item>
        <n-form-item label="品种">
          <n-input v-model:value="form.breed" placeholder="例如：柯基" maxlength="50" />
        </n-form-item>
        <n-form-item label="性别">
          <n-select v-model:value="form.gender" :options="genderOptions" />
        </n-form-item>
        <n-form-item label="生日">
          <n-date-picker
            v-model:formatted-value="form.birthday"
            value-format="yyyy-MM-dd"
            type="date"
            clearable
            placeholder="选择生日"
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="是否绝育">
          <n-switch v-model:value="form.neutered">
            <template #checked>已绝育</template>
            <template #unchecked>未绝育</template>
          </n-switch>
        </n-form-item>
      </div>

      <n-form-item label="过敏信息">
        <n-input
          v-model:value="form.allergies"
          placeholder="例如：鸡肉、花粉；没有可留空"
        />
      </n-form-item>
      <n-form-item label="备注">
        <n-input
          v-model:value="form.notes"
          type="textarea"
          :autosize="{ minRows: 3, maxRows: 5 }"
          placeholder="性格、习惯、需要特别留意的地方"
          maxlength="500"
          show-count
        />
      </n-form-item>
    </n-form>

    <template #footer>
      <div class="footer">
        <n-button quaternary @click="close">取消</n-button>
        <n-button type="primary" :loading="saving" @click="submit">
          {{ pet ? '保存修改' : '建立档案' }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<style scoped>
.photo-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--pc-line);
}

.photo-preview {
  display: grid;
  width: 64px;
  height: 64px;
  flex: 0 0 64px;
  place-items: center;
  overflow: hidden;
  border: 1px solid var(--pc-line);
  border-radius: 7px;
  background: var(--pc-surface-muted);
  color: var(--pc-primary);
  font-size: 22px;
  font-weight: 700;
}

.photo-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-actions {
  min-width: 0;
}

.photo-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.photo-actions p {
  margin: 7px 0 0;
  color: var(--pc-ink-faint);
  font-size: 11px;
  line-height: 1.6;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 560px) {
  .form-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
