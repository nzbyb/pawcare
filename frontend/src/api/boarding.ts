import { request } from './http'
import type { RefundOrder } from '@/types'

export function requestRefund(orderId: number): Promise<RefundOrder> {
  return request.post(`/payments/refunds/orders/${orderId}`)
}

export function processRefund(refundId: number): Promise<RefundOrder> {
  return request.post(`/payments/refunds/${refundId}/process`)
}
import type {
  BoardingHealthCheck,
  BoardingTasks,
  BoardingDraft,
  BoardingDraftPayload,
  BoardingOrder,
  DailyReport,
  HandoverSheet,
  Kennel,
  KennelSize,
} from '@/types'

export function getBoardingHealthCheck(params: {
  pet_id: number
  start_date: string
  end_date: string
}): Promise<BoardingHealthCheck> {
  return request.get<BoardingHealthCheck>('/boarding/health-check', { params })
}

export function getBoardingTasks(): Promise<BoardingTasks> {
  return request.get<BoardingTasks>('/boarding/tasks/today')
}

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

export function getHandover(orderId: number): Promise<HandoverSheet> {
  return request.get<HandoverSheet>(`/boarding/orders/${orderId}/handover`)
}

export function createReport(
  orderId: number,
  payload: {
    report_date: string
    appetite?: string
    stool?: string
    spirit?: string
    note?: string | null
    photos?: string[] | null
  },
): Promise<DailyReport> {
  return request.post<DailyReport>(`/boarding/orders/${orderId}/reports`, payload)
}
