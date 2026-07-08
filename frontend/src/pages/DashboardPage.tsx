import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth-context'
import { ApiError, api } from '@/lib/http'

type CurrentUserResponse = {
  id: string
  email: string | null
}

export function DashboardPage() {
  const { user, signOut } = useAuth()
  const [currentUser, setCurrentUser] = useState<CurrentUserResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isChecking, setIsChecking] = useState(false)

  async function checkBackendSession() {
    setError(null)
    setIsChecking(true)
    try {
      setCurrentUser(await api.get<CurrentUserResponse>('/me'))
    } catch (error) {
      setError(formatError(error))
      setCurrentUser(null)
    } finally {
      setIsChecking(false)
    }
  }

  async function handleSignOut() {
    setError(null)
    try {
      await signOut()
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Could not sign out')
    }
  }

  return (
    <main className="min-h-svh bg-background px-6 py-10 text-left text-foreground">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8">
        <header className="flex flex-col justify-between gap-4 rounded-2xl border bg-card p-6 shadow-sm sm:flex-row sm:items-center">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Document Copilot</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">Analyst workspace</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Signed in as {user?.email ?? 'an authenticated user'}.
            </p>
          </div>
          <div className="flex gap-2">
            <Button asChild>
              <Link to="/chat">Open chat</Link>
            </Button>
            <Button variant="outline" type="button" onClick={handleSignOut}>
              Sign out
            </Button>
          </div>
        </header>

        <section className="rounded-2xl border bg-card p-6 shadow-sm">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
            <div>
              <h2 className="text-xl font-semibold">Backend auth probe</h2>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                This calls <code>/me</code> through the shared API client. The client reads the
                Supabase session and attaches the bearer token automatically.
              </p>
            </div>
            <Button type="button" onClick={checkBackendSession} disabled={isChecking}>
              {isChecking ? 'Checking...' : 'Check /me'}
            </Button>
          </div>

          {currentUser ? (
            <dl className="mt-6 grid gap-4 rounded-xl bg-muted p-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="font-medium">User ID</dt>
                <dd className="mt-1 break-all text-muted-foreground">{currentUser.id}</dd>
              </div>
              <div>
                <dt className="font-medium">Email</dt>
                <dd className="mt-1 break-all text-muted-foreground">
                  {currentUser.email ?? 'No email returned'}
                </dd>
              </div>
            </dl>
          ) : null}

          {error ? (
            <p className="mt-6 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </p>
          ) : null}
        </section>
      </div>
    </main>
  )
}

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.isNetworkError) {
      return 'Could not reach the backend. Check that FastAPI is running and CORS is configured.'
    }
    if (error.status === 401) {
      return 'The backend rejected this session. Sign in again and retry.'
    }
    return error.message
  }
  return error instanceof Error ? error.message : 'Request failed'
}
