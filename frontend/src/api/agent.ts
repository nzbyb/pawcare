import { request } from './http'
import type {
  AgentChatResponse,
  AgentConversation,
  AgentHistoryMessage,
} from '@/types'

export function chat(payload: {
  conversation_id?: number
  messages: Array<{ role: 'user'; content: string }>
}): Promise<AgentChatResponse> {
  return request.post<AgentChatResponse>('/agent/chat', payload, {
    timeout: 70_000,
  })
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
