import { request } from './http'

export type PaymentStatus = 'created' | 'paying' | 'paid' | 'closed'
export type PaymentChannel = 'mock' | 'alipay' | 'wechat'

export interface Payment {
  payment_no: string
  order_id: number
  channel: PaymentChannel
  amount: number
  status: PaymentStatus
  qr_content: string
  expires_at: string
  owner_id?: number
  paid_at?: string | null
  transaction_id?: string | null
  create_time?: string
}

export type PublicPayment = Omit<Payment, 'owner_id' | 'paid_at' | 'transaction_id'>

export function createPayment(orderId: number): Promise<Payment> {
  return request.post<Payment>('/payments', { order_id: orderId })
}

export function getPayment(paymentNo: string): Promise<Payment> {
  return request.get<Payment>(`/payments/${encodeURIComponent(paymentNo)}`)
}

export function getMockPayment(
  paymentNo: string,
  token: string,
): Promise<PublicPayment> {
  return request.get<PublicPayment>(
    `/payments/mock/${encodeURIComponent(paymentNo)}`,
    { params: { token } },
  )
}

export function mockNotify(
  paymentNo: string,
  token: string,
): Promise<PublicPayment> {
  return request.post<PublicPayment>('/payments/mock/notify', {
    payment_no: paymentNo,
    token,
  })
}
