import { useRef } from 'react'
import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useGetMeQuery } from '../services/authApi'
import { useGetMyWorkspaceQuery } from '../services/onboardingApi'
import { Spinner } from './Spinner'

export default function OnboardingRoute({ children }: { children: ReactNode }) {
  const { data: authData, isLoading: authLoading, isError: authError } = useGetMeQuery()

  const skip = authLoading || authError || !authData?.user
  const { data: wsData, isLoading: wsLoading, isUninitialized: wsUninitialized } =
    useGetMyWorkspaceQuery(undefined, { skip })

  // Capture whether workspace existed BEFORE the user started onboarding.
  // We must not redirect mid-wizard just because step 1 created a workspace.
  const initiallyHadWorkspace = useRef<boolean | null>(null)
  if (initiallyHadWorkspace.current === null && !skip && !wsLoading && !wsUninitialized) {
    initiallyHadWorkspace.current = !!wsData?.workspace
  }

  if (authLoading || (!skip && (wsLoading || wsUninitialized))) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (authError || !authData?.user) {
    return <Navigate to="/login" replace />
  }

  // R3.1 — onboarding an agent is an owner's job. Members have no business here
  // even by typing the URL.
  if (authData.user.role === 'member') {
    return <Navigate to={wsData?.workspace ? '/dashboard' : '/pending'} replace />
  }

  // Only redirect if workspace existed before this onboarding session started
  if (initiallyHadWorkspace.current === true) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}
