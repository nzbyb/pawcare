export type UserRole = 'pet_owner' | 'boarding_staff' | 'admin'

export interface User {
  id: number
  username: string
  nickname: string
  role: UserRole
  phone?: string | null
  status: number
  create_time?: string | null
}

export interface LoginResult {
  token: string
  user: User
}

export type PetSpecies = 'dog' | 'cat' | 'other'
export type PetGender = 'male' | 'female' | 'unknown'

export interface Pet {
  id: number
  owner_id: number
  name: string
  species: PetSpecies
  breed?: string | null
  birthday?: string | null
  gender: PetGender
  neutered: boolean
  allergies?: string | null
  notes?: string | null
  photo_url?: string | null
  status: string
  create_time?: string | null
}

export interface PetPayload {
  name: string
  species: PetSpecies
  breed?: string | null
  birthday?: string | null
  gender: PetGender
  neutered: boolean
  allergies?: string | null
  notes?: string | null
}

export interface WeightRecord {
  id: number
  pet_id: number
  record_date: string
  weight_kg: number
  note?: string | null
}

export type HealthRecordType = 'vaccine' | 'deworm' | 'medication' | 'visit' | 'symptom'

export interface HealthRecord {
  id: number
  pet_id: number
  record_type: HealthRecordType
  title: string
  record_date: string
  next_due_date?: string | null
  note?: string | null
  extra?: Record<string, unknown> | null
  created_by?: number | null
  create_time?: string | null
}

export interface HealthRecordPayload {
  record_type: HealthRecordType
  title: string
  record_date: string
  next_due_date?: string | null
  note?: string | null
}

export interface Reminder {
  id: number
  pet_id: number
  reminder_type: string
  title: string
  due_date: string
  status: string
  source_health_record_id?: number | null
  notified_at?: string | null
}
