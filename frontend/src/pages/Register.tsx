import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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
  const [register, { isLoading }] = useRegisterMutation()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await register({ name, email, password }).unwrap()
      navigate('/dashboard')
    } catch (err) {
      setError(errorMessage(err))
    }
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
                    onSuccess={() => navigate('/dashboard')}
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
            to="/login"
            className="text-foreground underline underline-offset-4"
          >
            Log in
          </Link>
        </p>
      </div>
    </div>
  )
}
