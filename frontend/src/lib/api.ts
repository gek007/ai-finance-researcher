import { api } from '@/lib/http'

export type ChatThread = {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  message_json: unknown
  created_at: string
}

export type ThreadDetail = {
  thread: ChatThread
  messages: ChatMessage[]
}

export const chatApi = {
  listThreads: () => api.get<ChatThread[]>('/chat/threads'),
  createThread: () => api.post<ChatThread>('/chat/threads', {}),
  getThread: (threadId: string) => api.get<ThreadDetail>(`/chat/threads/${threadId}`),
}
