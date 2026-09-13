import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Spinner } from '@/components/Spinner'
import {
  errorMessage,
  useAcceptInviteMutation,
  useInspectInviteQuery,
} from '@/services/authApi'
import { useJoinWorkspaceMutation } from '@/services/onboardingApi'

function Shell({ title, description, children }: {
  title: string
  description: ReactNode
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

/**
 * Invite landing page. The token is bound to one address, works once, and
 * expires — so this page can show who it was issued to before anyone signs in,
 * and nothing about the project itself.
 */
export default function Join() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const navigate = useNavigate()

  const { data: invite, isLoading, error: inviteError } = useInspectInviteQuery(token, { skip: !token })
  const [acceptInvite, { isLoading: accepting }] = useAcceptInviteMutation()
  const [joinWorkspace, { isLoading: joining }] = useJoinWorkspaceMutation()

  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  // Someone who already has an account just needs the membership activated.
  useEffect(() => {
    if (!invite || invite.needs_password || done) return
    joinWorkspace({ token })
      .unwrap()
      .then((r) => setDone(r.workspace.name))
      .catch((err) => setError(errorMessage(err)))
  }, [invite, token, joinWorkspace, done])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await acceptInvite({ token, name: name.trim() || undefined, password }).unwrap()
      navigate('/dashboard')
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (!token) {
    return (
      <Shell title="Invite link incomplete" description="This link is missing its token. Ask your project owner for a new one.">
        <CardFooter>
          <Button variant="outline" className="w-full" asChild><Link to="/">Back to home</Link></Button>
        </CardFooter>
      </Shell>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Checking your invite…</p>
      </div>
    )
  }

  if (inviteError) {
    return (
      <Shell title="This invite can't be used" description={errorMessage(inviteError)}>
        <CardFooter className="flex-col gap-2">
          <Button variant="outline" className="w-full" asChild><Link to="/login">Go to login</Link></Button>
        </CardFooter>
      </Shell>
    )
  }

  if (done) {
    return (
      <Shell title={`You're in — welcome to ${done}`} description="The agent already knows this project. Ask it anything; every answer comes with its sources.">
        <CardFooter>
          <Button className="w-full" onClick={() => navigate('/chat')}>Start asking →</Button>
        </CardFooter>
      </Shell>
    )
  }

  if (joining) {
    return (
      <div className="min-h-svh bg-background flex flex-col items-center justify-center gap-3">
        <Spinner />
        <p className="text-sm text-muted-foreground">Joining…</p>
      </div>
    )
  }

  return (
    <Shell
      title={`Join ${invite?.workspace_name}`}
      description={
        <>
          {invite?.invited_by ? `${invite.invited_by} added ` : 'You were added as '}
          <span className="text-foreground font-medium">{invite?.email}</span>
          {invite?.invited_by ? ' to this project.' : '.'} Choose a password to finish.
        </>
      }
    >
      <form onSubmit={onSubmit}>
        <CardContent>
          {error && (
            <p role="alert" className="mb-4 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </p>
          )}
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="name">Your name</FieldLabel>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Priya Raman" autoComplete="name" />
            </Field>
            <Field>
              <FieldLabel htmlFor="password">Choose a password</FieldLabel>
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
              />
            </Field>
          </FieldGroup>
          <p className="mt-4 flex items-start gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            You pick your own password — we never email one. This link works once
            and only for {invite?.email}.
          </p>
        </CardContent>
        <CardFooter>
          <Button type="submit" className="w-full" disabled={accepting}>
            {accepting ? 'Setting up…' : 'Set password and join'}
          </Button>
        </CardFooter>
      </form>
    </Shell>
  )
}
