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

const form = reactive<PetFormState>({
  name: '',
  species: 'dog',
  breed: '',
  birthday: null,
  gender: 'unknown',
  neutered: false,
  allergies: '',
  notes: '',
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
  },
  { immediate: true },
)

function close(): void {
  emit('update:show', false)
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
