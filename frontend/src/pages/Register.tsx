import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Briefcase, Mail, Users } from 'lucide-react'
import {
  errorMessage,
  useRegisterMutation,
} from '../services/authApi'
import GoogleButton from '../components/GoogleButton'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
} from '@/components/ui/card'
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'

export default function Register() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // Invite links send people here with ?next=/join?token=… so the token survives login.
  const next = searchParams.get('next') || '/dashboard'
  // R2 — you say which you are before anything else. Members do not self-register;
  // a project owner puts their address on the allowlist and they arrive by link.
  const [role, setRole] = useState<'owner' | 'member' | null>(null)
  const [register, { isLoading }] = useRegisterMutation()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await register({ name, email, password, role: 'owner' }).unwrap()
      navigate(next)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (role === null) {
    return (
      <div className="bg-background text-foreground flex min-h-svh flex-col items-center justify-center p-8">
        <div className="flex w-full max-w-md flex-col gap-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold tracking-tight">Get started</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Which of these is you?
            </p>
          </div>

          <button
            type="button"
            onClick={() => setRole('owner')}
            className="rounded-xl border bg-card p-5 text-left transition hover:border-foreground/30"
          >
            <Briefcase className="mb-2 h-5 w-5" />
            <p className="font-medium">I'm setting up a project</p>
            <p className="text-muted-foreground mt-1 text-sm">
              Connect your sources, onboard the agent, and choose who on your team
              can ask it questions.
            </p>
          </button>

          <button
            type="button"
            onClick={() => setRole('member')}
            className="rounded-xl border bg-card p-5 text-left transition hover:border-foreground/30"
          >
            <Users className="mb-2 h-5 w-5" />
            <p className="font-medium">I'm joining a project</p>
            <p className="text-muted-foreground mt-1 text-sm">
              Your project owner adds you, and you'll get a link to set your
              password.
            </p>
          </button>

          <p className="text-muted-foreground text-center text-sm">
            Already have an account?{' '}
            <Link to="/login" className="text-foreground underline underline-offset-4">
              Log in
            </Link>
          </p>
        </div>
      </div>
    )
  }

  if (role === 'member') {
    return (
      <div className="bg-background text-foreground flex min-h-svh flex-col items-center justify-center p-8">
        <div className="flex w-full max-w-sm flex-col gap-6">
          <div className="rounded-xl border bg-card p-6 text-center">
            <Mail className="mx-auto mb-3 h-6 w-6 text-muted-foreground" />
            <h1 className="text-lg font-semibold">Ask your project owner to add you</h1>
            <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
              Team members don't sign up on their own. Your project owner adds
              your email to the project, and you'll get a link to set your
              password and join.
            </p>
            <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
              That's deliberate: the owner's list is the only way in, so the agent
              never answers to someone who wasn't approved.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Button variant="outline" onClick={() => setRole(null)}>
              ← Back
            </Button>
            <p className="text-muted-foreground text-center text-sm">
              Already set your password?{' '}
              <Link to="/login" className="text-foreground underline underline-offset-4">
                Log in
              </Link>
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col items-center justify-center p-8">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight">
            Create your account
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Start using Sensei in under a minute
          </p>
        </div>

        <form onSubmit={onSubmit}>
          <Card>
            <CardContent>
              {error && (
                <p
                  role="alert"
                  className="mb-4 rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive"
                >
                  {error}
                </p>
              )}
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="name">Name</FieldLabel>
                  <Input
                    id="name"
                    type="text"
                    required
                    autoComplete="name"
                    placeholder="Ada Lovelace"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="email">Email</FieldLabel>
                  <Input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <Input
                    id="password"
                    type="password"
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder="At least 8 characters"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <FieldDescription>Minimum 8 characters.</FieldDescription>
                </Field>
                <FieldGroup>
                  <Button type="submit" disabled={isLoading} className="w-full">
                    {isLoading ? 'Creating account…' : 'Create account'}
                  </Button>
                  <GoogleButton
                    onSuccess={() => navigate(next)}
                    onError={setError}
                  />
                </FieldGroup>
              </FieldGroup>
            </CardContent>
          </Card>
        </form>

        <p className="text-muted-foreground text-center text-sm">
          Already have an account?{' '}
          <Link
            to={next !== '/dashboard' ? `/login?next=${encodeURIComponent(next)}` : '/login'}
            className="text-foreground underline underline-offset-4"
          >
            Log in
          </Link>
        </p>
      </div>
    </div>
  )
}
