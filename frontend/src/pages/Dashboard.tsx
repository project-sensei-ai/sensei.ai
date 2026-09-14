import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity,
  Bell,
  CircleDot,
  Database,
  FolderGit2,
  Globe,
  KeyRound,
  Loader2,
  MessageSquare,
  RefreshCw,
  Sparkles,
  Upload,
  Users,
  Video,
  X,
} from 'lucide-react'
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
  useGetSourcesQuery,
  useGetTrustQuery,
  useGetReadinessQuery,
  useRerunReadinessMutation,
  type SourceStatus,
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

const typeIcon = {
  github: FolderGit2,
  url: Globe,
  file: Upload,
  confluence: Globe,
  jira: CircleDot,
  slack: MessageSquare,
  meeting: Video,
} as const

const statusMeta: Record<SourceStatus, { label: string; className: string; dot: string }> = {
  ready: {
    label: 'Ready',
    className: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-500',
    dot: 'bg-emerald-500',
  },
  indexing: {
    label: 'Indexing',
    className: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-500',
    dot: 'bg-amber-500 animate-pulse',
  },
  error: {
    label: 'Error',
    className: 'border-destructive/40 bg-destructive/10 text-destructive',
    dot: 'bg-destructive',
  },
  pending: {
    label: 'Queued',
    className: 'border-border bg-muted text-muted-foreground',
    dot: 'bg-muted-foreground',
  },
}

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

function SourceSnapshot({ isOwner }: { isOwner: boolean }) {
  const { data } = useGetSourcesQuery()

  const sources = data?.sources ?? []

  if (sources.length === 0) {
    return (
      <Card className="border-dashed">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4 text-muted-foreground" />
            Knowledge base
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted-foreground">
            Nothing is connected yet. Add GitHub, Jira, Confluence, Slack or
            files so the agent has something to read.
          </p>
          <Button asChild size="sm" className="gap-1.5">
            <Link to="/sources">
              <FolderGit2 className="h-4 w-4" />
              Connect sources
            </Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4 text-muted-foreground" />
            Knowledge base
          </CardTitle>
          <Button asChild variant="ghost" size="sm">
            <Link to="/sources">Manage</Link>
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2.5">
        {sources.map((s) => {
          const Icon = typeIcon[s.type] ?? FolderGit2
          const meta = statusMeta[s.status]
          return (
            <div key={s.id} className="flex items-center gap-3">
              <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{s.label}</p>
                {s.status === 'ready' && s.stats?.chunks_count != null && (
                  <p className="text-xs text-muted-foreground">
                    {s.stats.chunks_count} chunk{s.stats.chunks_count === 1 ? '' : 's'}
                  </p>
                )}
                {s.status === 'error' && (
                  <p className="truncate text-xs text-destructive">
                    {s.error_message ?? 'Failed to index'}
                  </p>
                )}
              </div>
              <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs ${meta.className}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
                {meta.label}
              </span>
            </div>
          )
        })}
        {isOwner && (
          <p className="text-xs text-muted-foreground">
            “Check for changes” re-reads them and re-indexes whatever moved.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const { data } = useGetMeQuery()
  const { data: wsData } = useGetMyWorkspaceQuery()
  const { data: briefData } = useGetMyBriefQuery(undefined, { pollingInterval: 10000 })
  const briefRecord = briefData?.brief
  const { data: activity } = useGetActivityQuery()
  const { data: digestData } = useGetDigestsQuery()
  const { data: ledger } = useGetLedgerQuery()
  const { data: sourcesData } = useGetSourcesQuery()
  const { data: trust } = useGetTrustQuery()
  const [checkForChanges, { isLoading: checking }] = useCheckForChangesMutation()
  const [ackDigest] = useAckDigestMutation()
  const [checkResult, setCheckResult] = useState<string | null>(null)
  const digests = (digestData?.digests ?? []).filter((d) => !d.acknowledged)
  const user = data?.user
  const workspace = wsData?.workspace
  const isOwner = workspace?.role !== 'member'
  const reach = trust?.coverage
  const chunksIndexed = (sourcesData?.sources ?? []).reduce(
    (sum, s) => sum + (s.status === 'ready' ? s.stats?.chunks_count ?? 0 : 0),
    0,
  )

  return (
    <AppShell>
      {user && user.has_password === false && <SetPasswordBanner />}

      {/* The colleague, on duty: who it works for, what it can reach, and the
          actions people come here for. */}
      <div className="flex flex-col gap-4 rounded-2xl border bg-gradient-to-br from-primary/[0.06] via-transparent to-transparent p-5 sm:flex-row sm:items-center sm:gap-6">
        <SenseiAvatar size="lg" pulse />
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold tracking-tight">
            Sensei is on duty{workspace ? ` for ${workspace.name}` : ''}
          </h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {user ? `Welcome back, ${user.name.split(' ')[0]}. ` : ''}
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
          {checkResult && (
            <p className="mt-2 text-xs text-muted-foreground">{checkResult}</p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button asChild size="sm"><Link to="/chat">Ask something</Link></Button>
          <Button asChild size="sm" variant="outline"><Link to="/meetings">Join a meeting</Link></Button>
          {isOwner && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              disabled={checking}
              onClick={async () => {
                const r = await checkForChanges().unwrap().catch(() => null)
                setCheckResult(r?.material ? null : (r?.message ?? 'Could not check just now.'))
              }}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${checking ? 'animate-spin' : ''}`} />
              {checking ? 'Re-reading the sources…' : 'Check for changes'}
            </Button>
          )}
        </div>
      </div>

      {/* A material change is the most time-sensitive thing the agent produces. */}
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

      {/* The agent's unprompted work, surfaced first */}
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

      {/* The number the product is judged on, front and centre. */}
      {ledger?.stats && ledger.stats.answers_given > 0 && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-x-10 gap-y-4 pt-6">
            <div>
              <p className="text-2xl font-semibold tabular-nums">
                {ledger.stats.answers_given}
              </p>
              <p className="text-xs text-muted-foreground">questions handled</p>
            </div>
            <div>
              <p className="text-2xl font-semibold tabular-nums">
                {ledger.stats.without_a_human_pct}%
              </p>
              <p className="text-xs text-muted-foreground">answered without a human</p>
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
            <div>
              <Link to="/sources" className="group">
                <p className="text-2xl font-semibold tabular-nums group-hover:underline">
                  {chunksIndexed}
                </p>
                <p className="text-xs text-muted-foreground">
                  chunks indexed
                </p>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {/* The agent's continuous work, next to the source health it depends on */}
        <Card className="lg:col-span-2">
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
            {!isOwner && (
              <p className="text-xs text-muted-foreground">
                Only workspace owners can force a re-check.
              </p>
            )}
          </CardContent>
        </Card>

        <SourceSnapshot isOwner={isOwner} />
      </div>

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