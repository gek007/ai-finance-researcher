import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth-context'
import { supabase } from '@/lib/supabase'

type AuthMode = 'sign-in' | 'sign-up'

export function AuthPage() {
  const { user, isLoading } = useAuth()
  const [mode, setMode] = useState<AuthMode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isLoading && user) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage(null)
    setError(null)
    setIsSubmitting(true)

    const credentials = {
      email: email.trim(),
      password,
    }

    const { error } =
      mode === 'sign-in'
        ? await supabase.auth.signInWithPassword(credentials)
        : await supabase.auth.signUp(credentials)

    if (error) {
      setError(error.message)
    } else if (mode === 'sign-up') {
      setMessage('Account created. Check your email if confirmation is enabled.')
    }

    setIsSubmitting(false)
  }

  const isSignIn = mode === 'sign-in'

  return (
    <main className="flex min-h-svh items-center justify-center bg-background px-6 py-12 text-left text-foreground">
      <section className="w-full max-w-md rounded-2xl border bg-card p-8 shadow-sm">
        <div className="mb-8 space-y-2">
          <p className="text-sm font-medium text-muted-foreground">Document Copilot</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            {isSignIn ? 'Sign in' : 'Create your account'}
          </h1>
          <p className="text-sm text-muted-foreground">
            Use your Supabase email account to access the analyst workspace.
          </p>
        </div>

        <form className="space-y-5" onSubmit={handleSubmit}>
          <label className="block space-y-2">
            <span className="text-sm font-medium">Email</span>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none ring-ring transition focus-visible:ring-2"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-medium">Password</span>
            <input
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none ring-ring transition focus-visible:ring-2"
              type="password"
              autoComplete={isSignIn ? 'current-password' : 'new-password'}
              minLength={6}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>

          {error ? <p className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p> : null}
          {message ? <p className="rounded-lg bg-muted p-3 text-sm text-muted-foreground">{message}</p> : null}

          <Button className="w-full" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Please wait...' : isSignIn ? 'Sign in' : 'Sign up'}
          </Button>
        </form>

        <button
          className="mt-6 text-sm text-muted-foreground underline-offset-4 hover:underline"
          type="button"
          onClick={() => {
            setMode(isSignIn ? 'sign-up' : 'sign-in')
            setError(null)
            setMessage(null)
          }}
        >
          {isSignIn ? 'Need an account? Sign up' : 'Already have an account? Sign in'}
        </button>
      </section>
    </main>
  )
}
