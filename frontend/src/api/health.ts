import { request } from './http'
import type { HealthRecord, HealthRecordPayload, Reminder } from '@/types'

export function listHealthRecords(petId: number): Promise<HealthRecord[]> {
  return request.get<HealthRecord[]>(`/pets/${petId}/health-records`)
}

export function createHealthRecord(
  petId: number,
  payload: HealthRecordPayload,
): Promise<HealthRecord> {
  return request.post<HealthRecord>(`/pets/${petId}/health-records`, payload)
}

export function updateHealthRecord(
  recordId: number,
  payload: Partial<HealthRecordPayload>,
): Promise<HealthRecord> {
  return request.put<HealthRecord>(`/health-records/${recordId}`, payload)
}

export function deleteHealthRecord(recordId: number): Promise<void> {
  return request.delete<void>(`/health-records/${recordId}`)
}

export function listReminders(petId: number): Promise<Reminder[]> {
  return request.get<Reminder[]>(`/pets/${petId}/reminders`)
}

export type ReminderUpdatePayload =
  | { status: 'done' }
  | { snooze_days: number }

export function updateReminder(
  petId: number,
  reminderId: number,
  payload: ReminderUpdatePayload,
): Promise<Reminder> {
  return request.patch<Reminder>(
    `/pets/${petId}/reminders/${reminderId}`,
    payload,
  )
}
