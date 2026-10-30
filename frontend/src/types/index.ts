export type UserRole = 'pet_owner' | 'boarding_staff' | 'admin'

export interface User {
  id: number
  username: string
  nickname: string
  role: UserRole
  email?: string | null
  phone?: string | null
  email_verified_at?: string | null
  phone_verified_at?: string | null
  status: number
  notify_health: boolean
  notify_order: boolean
  notify_system: boolean
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
  photo_url?: string | null
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
  payment_status: 'unpaid' | 'paid' | 'refunded'
  paid_amount: number
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
  health_check?: BoardingHealthCheck | null
}

export interface BoardingHealthCheck {
  pet_id: number
  pet_name: string
  start_date: string
  end_date: string
  checked_on: string
  status: 'attention' | 'ready'
  warning_count: number
  summary: string
  notice: string
  items: {
    code: string
    title: string
    level: 'warning' | 'info' | 'ok'
    detail: string
    source_record_id: number | null
    record_date: string | null
    next_due_date: string | null
  }[]
}

export type BoardingTaskKey = 'pending' | 'arrivals' | 'departures' | 'missing_reports' | 'abnormal_reports'

export interface BoardingTaskItem {
  order_id: number
  pet_id: number
  pet_name: string
  kennel_code: string
  start_date: string
  end_date: string
  status: BoardingOrderStatus
  payment_status: 'unpaid' | 'paid' | 'refunded'
  report_id: number | null
  report_date: string | null
  abnormal_reasons: string[]
}

export type BoardingTasks = { date: string; counts: Record<BoardingTaskKey, number> }
  & Record<BoardingTaskKey, BoardingTaskItem[]>

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

export type NotificationCategory = 'health' | 'order' | 'system'

export interface NotificationItem {
  id: number
  category: NotificationCategory
  title: string
  content: string
  link?: string | null
  is_read: boolean
  create_time?: string | null
}

export interface NotificationPage {
  items: NotificationItem[]
  unread: number
}

export interface HandoverHealthRecord {
  record_type: string
  title: string
  record_date: string
  next_due_date?: string | null
  note?: string | null
}

export interface HandoverReminder {
  title: string
  due_date: string
  status: string
}

export interface HandoverSheet {
  order: BoardingOrder
  pet: {
    name: string
    species: string
    breed?: string | null
    gender?: string | null
    neutered: boolean
    birthday?: string | null
    allergies?: string | null
    notes?: string | null
    latest_weight?: number | null
    latest_weight_date?: string | null
  }
  owner: {
    nickname: string
    phone?: string | null
    email?: string | null
  }
  health_records: HandoverHealthRecord[]
  reminders: HandoverReminder[]
  generated_at: string
}

export interface AdminUser {
  id: number
  username: string
  nickname: string
  role: UserRole
  email?: string | null
  phone?: string | null
  status: number
  pet_count: number
  order_count: number
  create_time?: string | null
}

export interface AdminUserPage {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

export interface KennelOccupancyInfo {
  order_id: number
  order_status: string
  payment_status: string
  pet_name: string
  pet_species?: string | null
  owner_name: string
  owner_phone?: string | null
  start_date: string
  end_date: string
}

export interface KennelOccupancyItem {
  id: number
  code: string
  size: string
  status: string
  display_status: string
  daily_price: number
  note?: string | null
  occupancy?: KennelOccupancyInfo | null
}

export interface KennelOccupancy {
  date: string
  summary: {
    total: number
    occupied: number
    available: number
    blocked: number
  }
  items: KennelOccupancyItem[]
}

export interface AuditLogItem {
  id: number
  actor_id?: number | null
  actor_name: string
  actor_username?: string | null
  action: string
  target_type: string
  target_id?: number | null
  before_data?: Record<string, unknown> | null
  after_data?: Record<string, unknown> | null
  trace_id?: string | null
  ip?: string | null
  create_time?: string | null
}

export interface AuditLogPage {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
}

export interface AdminOverview {
  date: string
  users: {
    total: number
    active: number
    owners: number
    staff: number
    admins: number
  }
  pets: { active: number }
  orders: {
    total: number
    active: number
    completed: number
    today_check_in: number
    today_check_out: number
  }
  revenue: { paid_total: number }
  reminders: { pending: number; due_soon: number }
  knowledge: { documents: number; chunks: number }
}

export interface KnowledgeChunkItem {
  id: number
  doc_id: string
  chunk_index: number
  title: string
  category?: string | null
  source?: string | null
  content: string
  has_embedding: boolean
}

export interface KnowledgePage {
  items: KnowledgeChunkItem[]
  total: number
  page: number
  page_size: number
}

