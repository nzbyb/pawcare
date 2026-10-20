export type UserRole = 'pet_owner' | 'boarding_staff' | 'admin'

export interface User {
  id: number
  username: string
  nickname: string
  role: UserRole
  email?: string | null
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

export type KennelSize = 'small' | 'medium' | 'large'

export interface Kennel {
  id: number
  code: string
  size: string
  status: string
  daily_price: number
  note?: string | null
}

export type BoardingOrderStatus =
  | 'pending'
  | 'confirmed'
  | 'checked_in'
  | 'boarding'
  | 'completed'
  | 'cancelled'

export interface BoardingOrder {
  id: number
  pet_id: number
  owner_id: number
  kennel_id: number
  start_date: string
  end_date: string
  status: BoardingOrderStatus
  daily_price: number
  deposit: number
  total_amount: number
  note?: string | null
  confirmed_at?: string | null
  checked_in_at?: string | null
  checked_out_at?: string | null
  draft_id?: number | null
  pet_name?: string | null
  kennel_code?: string | null
  nights?: number | null
}

export interface BoardingDraft {
  id: number
  owner_id: number
  pet_id: number
  kennel_id: number
  start_date: string
  end_date: string
  daily_price: number
  total_amount: number
  status: string
  expires_at: string
  idempotency_key: string
  note?: string | null
  pet_name?: string | null
  kennel_code?: string | null
  nights?: number | null
}

export interface BoardingDraftPayload {
  pet_id: number
  kennel_id: number
  start_date: string
  end_date: string
  note?: string | null
  idempotency_key?: string
}

export interface DailyReport {
  id: number
  order_id: number
  report_date: string
  appetite?: string | null
  stool?: string | null
  spirit?: string | null
  note?: string | null
  photos?: string[] | null
  created_by?: number | null
}

export interface AgentToolEvent {
  name: string
  status: string
  summary: string
  latency_ms?: number | null
}

export interface AgentChatResponse {
  conversation_id: number
  trace_id: string
  content: string
  draft: BoardingDraft | null
  tool_events: AgentToolEvent[]
}

export interface AgentConversation {
  id: number
  title: string
  last_message_at: string
  create_time?: string | null
}

export interface AgentHistoryMessage {
  id: number
  role: string
  content: string
  tool_calls?: unknown
  tool_call_id?: string | null
  token_in?: number | null
  token_out?: number | null
  latency_ms?: number | null
  create_time?: string | null
}
