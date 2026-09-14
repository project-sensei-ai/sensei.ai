import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Activity, Bell, KeyRound, MessageSquare, Database, Sparkles, Users, X, Loader2, Wrench, Video } from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import TeamPanel from '@/components/TeamPanel'
import ActivityFeed from '@/components/ActivityFeed'
import {
  useAckDigestMutation,
  useCheckForChangesMutation,
  useGetActivityQuery,
  useGetDigestsQuery,
  useGetMyBriefQuery,
  useGetMyWorkspaceQuery,
  useGetLedgerQuery,
  useGetTrustQuery,
  useGetReadinessQuery,
  useRerunReadinessMutation,
} from '@/services/onboardingApi'
import { SenseiAvatar } from '@/components/SenseiAvatar'
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
import { Badge } from '@/components/ui/badge'
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
    description: 'GitHub, Confluence, files and links the agent may read',
    to: '/sources',
    icon: Database,
    ownerOnly: false,
  },
  {
    title: 'Tools',
    description: 'What it can do: MCP servers the owner connected, writes gated',
    to: '/tools',
    icon: Wrench,
    ownerOnly: false,
  },
  {
    title: 'Chat',
    description: 'Ask, or ask for work — cited answers, spreadsheets, live Jira',
    to: '/chat',
    icon: MessageSquare,
    ownerOnly: false,
  },
  {
    title: 'Meetings',
    description: 'Bring it into a call — it answers when asked and corrects when sure',
    to: '/meetings',
    icon: Video,
    ownerOnly: false,
  },
]

/**
 * The self-interview. The only score on the dashboard Sensei gave itself —
 * and the two questions it failed are the most useful thing on the page.
 */
function ReadinessCard({ isOwner }: { isOwner: boolean }) {
  const { data } = useGetReadinessQuery(undefined, { pollingInterval: 8000 })
  const [rerun, { isLoading }] = useRerunReadinessMutation()
  const [open, setOpen] = useState(false)
  const r = data?.readiness
  if (!r) return null
  const missing = r.items.filter((i) => !i.answerable)
  const pct = r.total ? Math.round((r.score / r.total) * 100) : 0
  return (
    <Card className={r.status === 'running' ? 'border-dashed' : ''}>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-semibold tabular-nums">{r.status === 'running' && !r.total ? '…' : r.score}</span>
            <span className="text-sm text-muted-foreground">of {r.total || '?'}</span>
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="text-base">
              {r.status === 'running' ? 'Sensei is interviewing itself' : `Ready for ${pct}% of a new joiner's first-week questions`}
            </CardTitle>
            <CardDescription>
              {r.status === 'running'
                ? 'Writing the questions a new joiner would ask, then trying to answer them from the sources alone.'
                : missing.length
                ? `${missing.length} it could not answer from the sources. They are in the ledger — answer each once and it knows forever.`
                : 'It could answer all of them from the sources. Nothing to close.'}
            </CardDescription>
          </div>
          <Badge variant="secondary" className="h-5 text-[10px]">on its own</Badge>
        </div>
      </CardHeader>
      {r.items.length > 0 && (
        <CardContent className="flex flex-col gap-2 pt-0">
          <button className="self-start text-xs text-muted-foreground underline-offset-2 hover:underline" onClick={() => setOpen((o) => !o)}>
            {open ? 'Hide the questions' : 'See the questions it asked itself'}
          </button>
          {open && (
            <ul className="flex flex-col gap-1.5">
              {r.items.map((i) => (
                <li key={i.question} className="flex gap-2 text-sm">
                  <span className={`mt-0.5 shrink-0 ${i.answerable ? 'text-green-600' : 'text-amber-600'}`}>{i.answerable ? '✓' : '✗'}</span>
                  <span className="min-w-0">
                    <span>{i.question}</span>
                    {i.answerable && i.source && <span className="ml-1 text-xs text-muted-foreground">[{i.source}]</span>}
                    {!i.answerable && <span className="ml-1 text-xs text-amber-600">not in the sources</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap items-center gap-3">
            {missing.length > 0 && (
              <Button asChild size="sm" variant="outline"><Link to="/answers">Close them in the ledger</Link></Button>
            )}
            {isOwner && (
              <Button size="sm" variant="ghost" disabled={isLoading || r.status === 'running'} onClick={() => rerun()}>
                {isLoading ? 'Starting…' : 'Interview again'}
              </Button>
            )}
            {r.refresh_error && <span className="text-xs text-muted-foreground">Last re-run did not complete — {r.refresh_error}</span>}
          </div>
        </CardContent>
      )}
    </Card>
  )
}

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
  const { data: digestData } = useGetDigestsQuery()
  const [checkForChanges, { isLoading: checking }] = useCheckForChangesMutation()
  const [ackDigest] = useAckDigestMutation()
  const [checkResult, setCheckResult] = useState<string | null>(null)
  const digests = (digestData?.digests ?? []).filter((d) => !d.acknowledged)
  const { data: ledger } = useGetLedgerQuery()
  const { data: trust } = useGetTrustQuery()
  const user = data?.user
  const workspace = wsData?.workspace
  const isOwner = workspace?.role !== 'member'
  const reach = trust?.coverage

  return (
    <AppShell>
      {user && user.has_password === false && <SetPasswordBanner />}

      {/* The colleague, on duty. What it can reach is stated up front — the
          same numbers the Trust page carries, because they are the promise. */}
      <div className="flex flex-col gap-4 rounded-2xl border bg-gradient-to-br from-primary/[0.06] via-transparent to-transparent p-5 sm:flex-row sm:items-center sm:gap-6">
        <SenseiAvatar size="lg" pulse />
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold tracking-tight">
            Sensei is on duty{workspace ? ` for ${workspace.name}` : ''}
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {user ? `Hi ${user.name.split(' ')[0]}. ` : ''}
            {isOwner
              ? 'It reads what you connected, uses the accounts you granted, and speaks only when it can cite something.'
              : 'Ask it anything about the project, hand it work, or bring it into a meeting.'}
          </p>
          {reach && (
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
              <span><span className="font-semibold text-foreground tabular-nums">{reach.sources}</span> sources · <span className="font-semibold text-foreground tabular-nums">{reach.indexed_chunks}</span> passages</span>
              <span><span className="font-semibold text-foreground tabular-nums">{reach.tools ?? 0}</span> tools{reach.write_enabled ? `, writes allowed on ${reach.write_enabled}` : ', read-only'}</span>
              <span><span className="font-semibold text-foreground tabular-nums">{reach.people_with_access}</span> people can ask</span>
            </div>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <Button asChild size="sm"><Link to="/chat">Ask something</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/meetings">Join a meeting</Link></Button>
        </div>
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

      <ReadinessCard isOwner={isOwner} />

      {/* The number the product is judged on, rather than buried three screens
          deep on the page that produces it. */}
      {ledger?.stats && ledger.stats.answers_given > 0 && (
        <Card>
          <CardContent className="flex flex-wrap gap-x-10 gap-y-4 pt-6">
            <div>
              <p className="text-2xl font-semibold tabular-nums">
                {ledger.stats.without_a_human_pct}%
              </p>
              <p className="text-xs text-muted-foreground">answered without a human</p>
            </div>
            <div>
              <p className="text-2xl font-semibold tabular-nums">{ledger.stats.answers_given}</p>
              <p className="text-xs text-muted-foreground">questions handled</p>
            </div>
            <div>
              <Link to="/answers" className="group">
                <p className="text-2xl font-semibold tabular-nums group-hover:underline">
                  {ledger.stats.open}
                </p>
                <p className="text-xs text-muted-foreground">
                  waiting on a person
                </p>
              </Link>
            </div>
          </CardContent>
        </Card>
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

      {/* A material change is the most time-sensitive thing the agent produces,
          so it sits above everything else it has done. */}
      {digests.map((d) => (
        <Card key={d.id} className="border-amber-500/40 bg-amber-500/[0.04]">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="gap-1 border-amber-500/40 text-xs text-amber-700 dark:text-amber-500">
                    <Bell className="h-3 w-3" /> The project changed
                  </Badge>
                  {d.affects.map((a) => (
                    <Badge key={a} variant="secondary" className="text-xs">{a}</Badge>
                  ))}
                </div>
                <CardTitle className="text-base">{d.headline}</CardTitle>
                <CardDescription>{d.detail}</CardDescription>
              </div>
              <Button
                size="sm" variant="ghost" className="shrink-0"
                onClick={() => ackDigest(d.id)}
              >
                Dismiss
              </Button>
            </div>
          </CardHeader>
        </Card>
      ))}

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
        <CardContent className="flex flex-col gap-3">
          <ActivityFeed />
          {isOwner && (
            <div className="flex flex-wrap items-center gap-3 border-t pt-3">
              <Button
                size="sm" variant="outline" className="gap-1.5"
                disabled={checking}
                onClick={async () => {
                  const r = await checkForChanges().unwrap().catch(() => null)
                  setCheckResult(r?.material ? null : (r?.message ?? 'Could not check just now.'))
                }}
              >
                <Bell className={`h-3.5 w-3.5 ${checking ? 'animate-pulse' : ''}`} />
                {checking ? 'Re-reading the sources…' : 'Check for changes'}
              </Button>
              {/* "Nothing changed" is a real answer and has to be shown, or a
                  silent check looks like one that never ran. */}
              {checkResult && (
                <span className="text-xs text-muted-foreground">{checkResult}</span>
              )}
            </div>
          )}
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
