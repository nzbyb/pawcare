import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import { createDiscreteApi } from 'naive-ui'

import { clearToken, getToken } from '@/utils/storage'

interface ErrorBody {
  code?: number
  message?: string
  detail?: string
}

/** 请求配置扩展：silent 用于后台轮询，失败时不弹全局提示。 */
export interface RequestOptions extends AxiosRequestConfig {
  silent?: boolean
}

const { message } = createDiscreteApi(['message'])

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 20_000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body.code === 'number') {
      if (body.code !== 200) {
        if (body.code === 401) handleUnauthorized()
        const text = body.message || '请求失败'
        if (!(response.config as RequestOptions).silent) {
          message.error(text)
        }
        // 带上业务码，调用方需要区分 403 / 404 这类“再试也没用”的错误。
        const failure = new Error(text) as Error & { code?: number }
        failure.code = body.code
        return Promise.reject(failure)
      }
      return body.data
    }
    return body
  },
  (error: AxiosError<ErrorBody>) => {
    const status = error.response?.status
    const body = error.response?.data
    const text = body?.message || body?.detail || error.message || '网络异常'

    if (status === 401) {
      handleUnauthorized()
    }
    if (!(error.config as RequestOptions | undefined)?.silent) {
      message.error(status === 429 ? '操作太频繁，请稍后再试' : text)
    }
    return Promise.reject(error)
  },
)

function handleUnauthorized(): void {
  clearToken()
  if (!window.location.pathname.startsWith('/login')) {
    const redirect = encodeURIComponent(
      window.location.pathname + window.location.search,
    )
    window.location.href = `/login?redirect=${redirect}`
  }
}

export const request = {
  get<T>(url: string, config?: RequestOptions): Promise<T> {
    return http.get(url, config) as unknown as Promise<T>
  },
  post<T>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    return http.post(url, data, config) as unknown as Promise<T>
  },
  put<T>(url: string, data?: unknown, config?: RequestOptions): Promise<T> {
    return http.put(url, data, config) as unknown as Promise<T>
  },
  delete<T>(url: string, config?: RequestOptions): Promise<T> {
    return http.delete(url, config) as unknown as Promise<T>
  },
}

export default http
