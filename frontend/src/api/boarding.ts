import { request } from './http'
import type {
  BoardingDraft,
  BoardingDraftPayload,
  BoardingOrder,
  DailyReport,
  Kennel,
  KennelSize,
} from '@/types'

export function listKennels(): Promise<Kennel[]> {
  return request.get<Kennel[]>('/kennels')
}

export function checkAvailability(params: {
  start_date: string
  end_date: string
  size?: KennelSize
}): Promise<Kennel[]> {
  return request.get<Kennel[]>('/kennels/availability', { params })
}

export function createDraft(payload: BoardingDraftPayload): Promise<BoardingDraft> {
  return request.post<BoardingDraft>('/boarding/drafts', payload)
}

export function listDrafts(): Promise<BoardingDraft[]> {
  return request.get<BoardingDraft[]>('/boarding/drafts')
}

export function confirmDraft(
  draftId: number,
  idempotencyKey: string,
): Promise<BoardingOrder> {
  return request.post<BoardingOrder>(`/boarding/drafts/${draftId}/confirm`, {
    idempotency_key: idempotencyKey,
  })
}

export function cancelDraft(draftId: number): Promise<void> {
  return request.delete<void>(`/boarding/drafts/${draftId}`)
}

export function listOrders(status?: string): Promise<BoardingOrder[]> {
  return request.get<BoardingOrder[]>('/boarding/orders', {
    params: status ? { status } : undefined,
  })
}

export function confirmOrder(orderId: number): Promise<BoardingOrder> {
  return request.post<BoardingOrder>(`/boarding/orders/${orderId}/confirm`)
}

export function checkInOrder(orderId: number): Promise<BoardingOrder> {
  return request.post<BoardingOrder>(`/boarding/orders/${orderId}/check-in`)
}

export function checkOutOrder(orderId: number): Promise<BoardingOrder> {
  return request.post<BoardingOrder>(`/boarding/orders/${orderId}/check-out`)
}

export function cancelOrder(orderId: number): Promise<BoardingOrder> {
  return request.post<BoardingOrder>(`/boarding/orders/${orderId}/cancel`)
}

export function listReports(orderId: number): Promise<DailyReport[]> {
  return request.get<DailyReport[]>(`/boarding/orders/${orderId}/reports`)
}

export function createReport(
  orderId: number,
  payload: {
    report_date: string
    appetite?: string
    stool?: string
    spirit?: string
    note?: string | null
  },
): Promise<DailyReport> {
  return request.post<DailyReport>(`/boarding/orders/${orderId}/reports`, payload)
}
