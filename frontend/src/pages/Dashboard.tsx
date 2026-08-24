import { useState, type FormEvent } from 'react'
import { KeyRound, X } from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import {
  errorMessage,
  useGetMeQuery,
  useSetPasswordMutation,
} from '@/services/authApi'
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'

const NUDGE_KEY = 'sensei-hide-password-nudge'

const overviewCards = [
  { title: 'Sources', description: 'Confluence, GitHub, Jira, Teams' },
  { title: 'Memory', description: 'Project context & decisions' },
  { title: 'Chat', description: 'Cited, grounded answers' },
]

function SetPasswordBanner() {
  const [setPassword, { isLoading }] = useSetPasswordMutation()
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(NUDGE_KEY) === '1',
  )

  if (dismissed) return null

  const dismiss = () => {
    localStorage.setItem(NUDGE_KEY, '1')
    setDismissed(true)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await setPassword({ password: newPassword }).unwrap()
      localStorage.removeItem(NUDGE_KEY)
      setNewPassword('')
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <Alert className="relative pr-10">
      <KeyRound />
      <div className="flex flex-1 flex-col gap-2">
        <AlertTitle>Add a password</AlertTitle>
        <AlertDescription>
          You signed up with Google. Set a password to also log in with your
          email.
        </AlertDescription>
        <form onSubmit={onSubmit} className="flex gap-2 pt-1">
          <Input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="At least 8 characters"
            className="max-w-xs bg-background"
          />
          <Button type="submit" size="sm" disabled={isLoading}>
            {isLoading ? 'Saving…' : 'Save'}
          </Button>
        </form>
        {error && (
          <p
            role="alert"
            className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {error}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss"
        className="text-muted-foreground hover:text-foreground absolute top-3 right-3 transition"
      >
        <X className="size-4" />
      </button>
    </Alert>
  )
}

export default function Dashboard() {
  const { data } = useGetMeQuery()
  const user = data?.user

  return (
    <AppShell>
      {user && !user.has_password && <SetPasswordBanner />}

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome back{user ? `, ${user.name.split(' ')[0]}` : ''}
        </h1>
        <p className="text-muted-foreground">
          Here's your project context at a glance.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {overviewCards.map((card) => (
          <Card key={card.title}>
            <CardHeader>
              <CardTitle>{card.title}</CardTitle>
              <CardDescription>{card.description}</CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </AppShell>
  )
}
