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
  pay_url?: string | null
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

export function getPayment(
  paymentNo: string,
  silent = false,
): Promise<Payment> {
  return request.get<Payment>(`/payments/${encodeURIComponent(paymentNo)}`, {
    // 收银台轮询属于后台请求，失败交给页面处理，不弹全局错误提示。
    silent,
  })
}

export function refreshPayment(paymentNo: string): Promise<Payment> {
  return request.post<Payment>(
    `/payments/${encodeURIComponent(paymentNo)}/refresh`,
  )
}

export function getPublicPayment(
  paymentNo: string,
  token: string,
): Promise<PublicPayment> {
  return request.get<PublicPayment>(
    `/payments/public/${encodeURIComponent(paymentNo)}`,
    { params: { token } },
  )
}

export function refreshPublicPayment(
  paymentNo: string,
  token: string,
): Promise<PublicPayment> {
  return request.post<PublicPayment>(
    `/payments/public/${encodeURIComponent(paymentNo)}/refresh`,
    undefined,
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
