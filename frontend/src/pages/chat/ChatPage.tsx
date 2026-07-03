import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport, type UIMessage } from 'ai'
import { ArrowLeft, SendHorizontal } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { chatApi, type ChatMessage, type ChatThread } from '@/lib/api'
import { buildApiUrl } from '@/lib/http'
import { supabase } from '@/lib/supabase'

const CHAT_STREAM_URL = buildApiUrl('/chat/stream')

export function ChatPage() {
  const { threadId } = useParams<{ threadId: string }>()
  const [thread, setThread] = useState<ChatThread | null>(null)
  const [input, setInput] = useState('')
  const [isLoadingThread, setIsLoadingThread] = useState(() => Boolean(threadId))
  const [loadError, setLoadError] = useState<string | null>(null)
  const visibleLoadError = threadId ? loadError : 'Missing chat thread id'

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: CHAT_STREAM_URL,
        fetch: authenticatedFetch,
        prepareSendMessagesRequest: ({ messages }) => ({
          body: {
            threadId: threadId ?? '',
            messages,
          },
        }),
      }),
    [threadId],
  )

  const { messages, setMessages, sendMessage, status, error, stop } = useChat({
    id: threadId ?? 'missing-thread',
    transport,
  })

  useEffect(() => {
    if (!threadId) {
      return
    }

    let isMounted = true

    chatApi
      .getThread(threadId)
      .then((detail) => {
        if (!isMounted) {
          return
        }
        setThread(detail.thread)
        setMessages(detail.messages.map(toUiMessage))
      })
      .catch((error) => {
        if (!isMounted) {
          return
        }
        setLoadError(error instanceof Error ? error.message : 'Could not load chat')
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingThread(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [setMessages, threadId])

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = input.trim()
    if (!text || !threadId || status !== 'ready') {
      return
    }

    setInput('')
    void sendMessage({ text })
  }

  const isStreaming = status === 'submitted' || status === 'streaming'

  return (
    <main className="flex min-h-svh bg-background text-left text-foreground">
      <div className="mx-auto flex min-h-svh w-full max-w-5xl flex-col px-6 py-6">
        <header className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Button asChild variant="ghost" size="sm" className="-ml-2 mb-2">
              <Link to="/">
                <ArrowLeft />
                Workspace
              </Link>
            </Button>
            <p className="text-sm font-medium text-muted-foreground">Document Copilot</p>
            <h1 className="my-2 text-3xl font-semibold tracking-tight">
              {thread?.title ?? 'Chat'}
            </h1>
            <p className="text-sm text-muted-foreground">
              Ask a question now and the backend will stream the Phase 4 stub reply.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/chat">New chat</Link>
          </Button>
        </header>

        <section className="flex flex-1 flex-col gap-4 overflow-hidden py-6">
          {isLoadingThread ? (
            <CenteredState>Loading chat history...</CenteredState>
          ) : visibleLoadError ? (
            <CenteredState>{visibleLoadError}</CenteredState>
          ) : messages.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="flex flex-1 flex-col gap-4 overflow-y-auto pr-1">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {isStreaming ? (
                <p className="text-sm text-muted-foreground">Assistant is streaming...</p>
              ) : null}
            </div>
          )}

          {error ? (
            <p className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              {error.message}
            </p>
          ) : null}
        </section>

        <form onSubmit={handleSubmit} className="flex gap-3 border-t pt-5">
          <label className="sr-only" htmlFor="chat-message">
            Message
          </label>
          <textarea
            id="chat-message"
            value={input}
            onChange={(event) => setInput(event.currentTarget.value)}
            disabled={isLoadingThread || status !== 'ready'}
            placeholder="Ask about a filing..."
            rows={2}
            className="min-h-14 flex-1 resize-none rounded-xl border bg-background px-4 py-3 text-sm shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60"
          />
          {isStreaming ? (
            <Button type="button" variant="outline" onClick={stop}>
              Stop
            </Button>
          ) : (
            <Button type="submit" disabled={!input.trim() || isLoadingThread || status !== 'ready'}>
              <SendHorizontal />
              Send
            </Button>
          )}
        </form>
      </div>
    </main>
  )
}

function EmptyState() {
  return (
    <CenteredState>
      <span className="block text-base font-medium text-foreground">Start this thread</span>
      <span className="mt-2 block max-w-md text-sm text-muted-foreground">
        Send a first message to prove the authenticated browser to FastAPI to Supabase loop.
      </span>
    </CenteredState>
  )
}

function CenteredState({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 items-center justify-center rounded-2xl border bg-card p-8 text-center shadow-sm">
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  )
}

function MessageBubble({ message }: { message: UIMessage }) {
  const isUser = message.role === 'user'
  const text = textFromUiMessage(message)

  return (
    <article className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
          isUser ? 'bg-primary text-primary-foreground' : 'border bg-card text-card-foreground'
        }`}
      >
        <p className="mb-1 text-xs font-medium opacity-70">{isUser ? 'You' : 'Assistant'}</p>
        <div className="whitespace-pre-wrap leading-relaxed">{text || '(empty message)'}</div>
      </div>
    </article>
  )
}

function toUiMessage(message: ChatMessage): UIMessage {
  if (isUiMessage(message.message_json)) {
    return message.message_json
  }

  return {
    id: message.id,
    role: message.role,
    parts: [{ type: 'text', text: message.content }],
  }
}

function isUiMessage(value: unknown): value is UIMessage {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const candidate = value as { id?: unknown; role?: unknown; parts?: unknown }
  return (
    typeof candidate.id === 'string' &&
    typeof candidate.role === 'string' &&
    Array.isArray(candidate.parts)
  )
}

function textFromUiMessage(message: UIMessage): string {
  return message.parts
    .map((part) => (part.type === 'text' ? part.text : ''))
    .join('')
}

async function authenticatedFetch(input: RequestInfo | URL, init?: RequestInit) {
  const headers = new Headers(init?.headers)
  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  return fetch(input, { ...init, headers })
}
