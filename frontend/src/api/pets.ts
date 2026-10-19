import { request } from './http'
import type { Pet, PetPayload, WeightRecord } from '@/types'

export function listPets(): Promise<Pet[]> {
  return request.get<Pet[]>('/pets')
}

export function getPet(petId: number): Promise<Pet> {
  return request.get<Pet>(`/pets/${petId}`)
}

export function createPet(payload: PetPayload): Promise<Pet> {
  return request.post<Pet>('/pets', payload)
}

export function updatePet(
  petId: number,
  payload: Partial<PetPayload>,
): Promise<Pet> {
  return request.put<Pet>(`/pets/${petId}`, payload)
}

export function deletePet(petId: number): Promise<void> {
  return request.delete<void>(`/pets/${petId}`)
}

export function listWeights(petId: number): Promise<WeightRecord[]> {
  return request.get<WeightRecord[]>(`/pets/${petId}/weights`)
}

export function addWeight(
  petId: number,
  payload: { record_date: string; weight_kg: number; note?: string | null },
): Promise<WeightRecord> {
  return request.post<WeightRecord>(`/pets/${petId}/weights`, payload)
}
