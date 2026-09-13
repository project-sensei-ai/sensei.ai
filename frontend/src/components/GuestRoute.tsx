import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useGetMeQuery } from '../services/authApi'
import { Spinner } from './Spinner'

export default function GuestRoute({ children }: { children: ReactNode }) {
  const { data: authData, isLoading: authLoading, isError: authError } = useGetMeQuery()

  if (authLoading) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Checking your session…</p>
      </div>
    )
  }

  // Already signed in — /dashboard (via ProtectedRoute) picks the right landing:
  // dashboard, onboarding (owner, no workspace), or pending (member, no workspace).
  if (!authError && authData?.user) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}