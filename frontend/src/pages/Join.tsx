import { useEffect, useRef, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Spinner } from '@/components/Spinner'
import { useGetMeQuery } from '@/services/authApi'
import { useJoinWorkspaceMutation } from '@/services/onboardingApi'

/**
 * Invite-link landing page. Reached from the URL in StepInvite.
 * Unauthenticated visitors are sent to log in with ?next= pointing back here,
 * so the token survives the round trip.
 */
export default function Join() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const navigate = useNavigate()

  const { data: authData, isLoading: authLoading } = useGetMeQuery()
  const signedIn = !!authData?.user

  const [joinWorkspace, { isLoading: joining, isSuccess, data, error }] = useJoinWorkspaceMutation()

  // Fire exactly once, even under StrictMode's double-invoke.
  const attempted = useRef(false)
  useEffect(() => {
    if (!token || !signedIn || attempted.current) return
    attempted.current = true
    joinWorkspace({ token })
  }, [token, signedIn, joinWorkspace])

  const detail =
    error && 'data' in error ? (error.data as { detail?: string })?.detail : undefined

  function Shell({ title, description, children }: {
    title: string
    description: string
    children?: ReactNode
  }) {
    return (
      <div className="bg-background text-foreground flex min-h-svh flex-col items-center justify-center p-8">
        <div className="flex w-full max-w-sm flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{description}</CardDescription>
            </CardHeader>
            {children}
          </Card>
        </div>
      </div>
    )
  }

  if (!token) {
    return (
      <Shell
        title="Invite link incomplete"
        description="This link is missing its invite token. Ask your project owner for a fresh one."
      >
        <CardFooter>
          <Button variant="outline" className="w-full" asChild>
            <Link to="/">Back to home</Link>
          </Button>
        </CardFooter>
      </Shell>
    )
  }

  if (authLoading) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Checking your session…</p>
      </div>
    )
  }

  if (!signedIn) {
    const next = encodeURIComponent(`/join?token=${token}`)
    return (
      <Shell
        title="You've been invited to Sensei"
        description="Log in or create an account to join this project workspace."
      >
        <CardFooter className="flex flex-col gap-2">
          <Button className="w-full" asChild>
            <Link to={`/register?next=${next}`}>Create an account</Link>
          </Button>
          <Button variant="outline" className="w-full" asChild>
            <Link to={`/login?next=${next}`}>I already have an account</Link>
          </Button>
        </CardFooter>
      </Shell>
    )
  }

  if (joining) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Joining the workspace…</p>
      </div>
    )
  }

  if (isSuccess) {
    const name = data?.workspace?.name ?? 'the workspace'
    return (
      <Shell
        title={data?.already_member ? `You're already in ${name}` : `You're in — welcome to ${name} 🎉`}
        description="Sensei already knows this project. Ask it anything — every answer comes with its sources."
      >
        <CardContent className="text-sm text-muted-foreground">
          <p className="mb-2">Try starting with:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>What does this project do?</li>
            <li>Who has access to the repo, and who actually wrote the code?</li>
            <li>What's been changing recently?</li>
          </ul>
        </CardContent>
        <CardFooter>
          <Button className="w-full" onClick={() => navigate('/chat')}>
            Start asking →
          </Button>
        </CardFooter>
      </Shell>
    )
  }

  return (
    <Shell
      title="Couldn't join this workspace"
      description={detail ?? 'The invite link may have expired. Ask your project owner for a new one.'}
    >
      <CardFooter className="flex flex-col gap-2">
        <Button variant="outline" className="w-full" asChild>
          <Link to="/dashboard">Go to my dashboard</Link>
        </Button>
      </CardFooter>
    </Shell>
  )
}
