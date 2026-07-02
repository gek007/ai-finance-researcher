import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/lib/auth'
import { useAuth } from '@/lib/auth-context'
import { AuthPage } from '@/pages/AuthPage'
import { DashboardPage } from '@/pages/DashboardPage'

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading, error } = useAuth()

  if (isLoading) {
    return (
      <main className="flex min-h-svh items-center justify-center bg-background text-foreground">
        Loading session...
      </main>
    )
  }

  if (error) {
    return (
      <main className="flex min-h-svh items-center justify-center bg-background px-6 text-center text-destructive">
        {error}
      </main>
    )
  }

  if (!user) {
    return <Navigate to="/auth" replace />
  }

  return children
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
