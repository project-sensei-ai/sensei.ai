import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Activity, KeyRound, MessageSquare, Database, Sparkles, Users, X, Loader2 } from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import TeamPanel from '@/components/TeamPanel'
import ActivityFeed from '@/components/ActivityFeed'
import { useGetActivityQuery, useGetMyBriefQuery, useGetMyWorkspaceQuery } from '@/services/onboardingApi'
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
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'

const NUDGE_KEY = 'sensei-hide-password-nudge'

const overviewCards = [
  {
    title: 'Sources',
    description: 'GitHub, Confluence, Jira, files and links the agent may read',
    to: '/sources',
    icon: Database,
    ownerOnly: false,
  },
  {
    title: 'Chat',
    description: 'Ask anything about the project — every answer cites its source',
    to: '/chat',
    icon: MessageSquare,
    ownerOnly: false,
  },
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
  const { data: wsData } = useGetMyWorkspaceQuery()
  const { data: briefData } = useGetMyBriefQuery(undefined, { pollingInterval: 10000 })
  const briefRecord = briefData?.brief
  const { data: activity } = useGetActivityQuery()
  const user = data?.user
  const workspace = wsData?.workspace
  const isOwner = workspace?.role !== 'member'

  return (
    <AppShell>
      {user && user.has_password === false && <SetPasswordBanner />}

      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Welcome back{user ? `, ${user.name.split(' ')[0]}` : ''}
        </h1>
        <p className="text-muted-foreground">
          {workspace
            ? isOwner
              ? `You own ${workspace.name}. The agent reads only what you connect.`
              : `You're on ${workspace.name}. Ask the agent anything about it.`
            : "Here's your project context at a glance."}
        </p>
      </div>

      {/* The agent's unprompted work, surfaced first — it happened before this
          person ever signed in. */}
      {briefRecord && (
        <Link to="/brief" className="group">
          <Card className="border-primary/30 bg-primary/[0.03] transition-colors group-hover:border-primary/50">
            <CardHeader>
              <div className="flex items-center gap-2">
                {briefRecord.status === 'generating'
                  ? <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  : <Sparkles className="h-4 w-4 text-primary" />}
                <CardTitle className="text-base">
                  {briefRecord.status === 'generating'
                    ? 'The agent is reading your project'
                    : briefRecord.status === 'error'
                    ? "Your brief couldn't be written"
                    : 'Your onboarding brief is ready'}
                </CardTitle>
              </div>
              <CardDescription>
                {briefRecord.status === 'generating'
                  ? "Nobody asked it to — it started when you were added. A few minutes."
                  : briefRecord.status === 'error'
                  ? briefRecord.error_message
                  : briefRecord.brief?.headline}
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {overviewCards.map((card) => (
          <Link key={card.title} to={card.to} className="group">
            <Card className="h-full transition-colors group-hover:border-foreground/20">
              <CardHeader>
                <card.icon className="mb-1 h-5 w-5 text-muted-foreground" />
                <CardTitle>{card.title}</CardTitle>
                <CardDescription>{card.description}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>

      {/* Autonomy, made visible. Everything above happened because someone
          clicked; some of what follows happened because nobody did. */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4 text-muted-foreground" />
            What the agent has been doing
          </CardTitle>
          <CardDescription>
            {activity?.unprompted_count
              ? `${activity.unprompted_count} of these it started on its own.`
              : 'Work it does in the background, without being asked.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ActivityFeed />
        </CardContent>
      </Card>

      {/* R3.4 — the second place an owner manages the allowlist. Same component
          as the onboarding wizard, so the rule cannot drift between them. */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4 text-muted-foreground" />
            Team
          </CardTitle>
          <CardDescription>
            {isOwner
              ? 'Everyone who can ask the agent about this project. Nobody else can reach it.'
              : 'Everyone on this project.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TeamPanel />
        </CardContent>
      </Card>
    </AppShell>
  )
}
