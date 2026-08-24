import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useGetMeQuery } from '../services/authApi'
import { Spinner } from './Spinner'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { data, isLoading, isError } = useGetMeQuery()

  if (isLoading) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Checking your session…</p>
      </div>
    )
  }

  if (isError || !data?.user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
