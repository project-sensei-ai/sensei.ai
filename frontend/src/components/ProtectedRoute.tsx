import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useGetMeQuery } from '../services/authApi'
import { useGetMyWorkspaceQuery } from '../services/onboardingApi'
import { Spinner } from './Spinner'

interface Props {
  children: ReactNode
  skipWorkspaceCheck?: boolean
}

export default function ProtectedRoute({ children, skipWorkspaceCheck = false }: Props) {
  const { data: authData, isLoading: authLoading, isError: authError } = useGetMeQuery()

  const skipWs = skipWorkspaceCheck || authLoading || authError || !authData?.user

  const {
    isLoading: wsLoading,
    isUninitialized: wsUninitialized,
    isError: wsIsError,
    error: wsError,
  } = useGetMyWorkspaceQuery(undefined, { skip: skipWs })

  // Show spinner while auth loads, or while workspace query is pending / loading
  if (authLoading || (!skipWs && (wsLoading || wsUninitialized))) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Checking your session…</p>
      </div>
    )
  }

  if (authError || !authData?.user) {
    return <Navigate to="/login" replace />
  }

  if (!skipWorkspaceCheck) {
    const status = wsError && 'status' in wsError ? (wsError as { status: number }).status : null
    if (wsIsError && (status === 404 || status !== null)) {
      return <Navigate to="/onboarding" replace />
    }
  }

  return <>{children}</>
}
