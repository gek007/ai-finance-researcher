import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { chatApi } from '@/lib/api'

export function NewChatPage() {
  const navigate = useNavigate()
  const hasStarted = useRef(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (hasStarted.current) {
      return
    }
    hasStarted.current = true

    chatApi
      .createThread()
      .then((thread) => {
        navigate(`/chat/${thread.id}`, { replace: true })
      })
      .catch((error) => {
        setError(error instanceof Error ? error.message : 'Could not create chat')
      })
  }, [navigate])

  return (
    <main className="flex min-h-svh items-center justify-center bg-background px-6 text-foreground">
      <div className="rounded-2xl border bg-card p-6 text-center shadow-sm">
        <p className="text-sm font-medium text-muted-foreground">
          {error ?? 'Starting a new chat...'}
        </p>
      </div>
    </main>
  )
}
