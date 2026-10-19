import { request } from './http'
import { getToken } from '@/utils/storage'
import type {
  AgentChatResponse,
  AgentConversation,
  AgentHistoryMessage,
} from '@/types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export type AgentStreamHandler = (
  event: string,
  data: Record<string, unknown>,
) => void

export function chat(payload: {
  conversation_id?: number
  messages: Array<{ role: 'user'; content: string }>
}): Promise<AgentChatResponse> {
  return request.post<AgentChatResponse>('/agent/chat', payload, {
    timeout: 70_000,
  })
}

function dispatchSseBlock(block: string, onEvent: AgentStreamHandler): void {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  if (dataLines.length === 0) return
  try {
    onEvent(event, JSON.parse(dataLines.join('\n')) as Record<string, unknown>)
  } catch {
    // 单条脏事件不应中断整个流。
  }
}

export async function streamChat(
  payload: {
    conversation_id?: number
    messages: Array<{ role: 'user'; content: string }>
  },
  onEvent: AgentStreamHandler,
  options: { signal?: AbortSignal } = {},
): Promise<void> {
  const token = getToken()
  const response = await fetch(`${API_BASE}/agent/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  })

  if (!response.ok || !response.body) {
    let message = '请求失败'
    try {
      const body = (await response.json()) as { message?: string; detail?: string }
      message = body.message || body.detail || message
    } catch {
      // 非 JSON 错误响应，保留默认文案。
    }
    throw new Error(message)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = buffer.replace(/\r\n/g, '\n')

    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      dispatchSseBlock(block, onEvent)
      boundary = buffer.indexOf('\n\n')
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) dispatchSseBlock(buffer, onEvent)
}

export function listConversations(): Promise<AgentConversation[]> {
  return request.get<AgentConversation[]>('/agent/conversations')
}

export function getConversation(
  conversationId: number,
): Promise<{ conversation_id: number; messages: AgentHistoryMessage[] }> {
  return request.get<{ conversation_id: number; messages: AgentHistoryMessage[] }>(
    `/agent/conversations/${conversationId}`,
  )
}
