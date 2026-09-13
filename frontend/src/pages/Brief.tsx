import { BookOpen, HelpCircle, Loader2, RefreshCw, Sparkles, Users } from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useGetMyBriefQuery,
  useRegenerateBriefMutation,
} from '@/services/onboardingApi'

/**
 * The onboarding brief — the agent's unprompted work, read back.
 *
 * Nobody asked for this page's content. It was written when a project owner
 * added this person, before they ever signed in.
 */
export default function Brief() {
  // Poll only while the agent is still working.
  const { data, isLoading } = useGetMyBriefQuery(undefined, {
    pollingInterval: 6000,
    skipPollingIfUnfocused: true,
  })
  const [regenerate, { isLoading: regenerating }] = useRegenerateBriefMutation()

  const record = data?.brief
  const brief = record?.brief

  if (isLoading) {
    return (
      <AppShell title="Your brief">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      </AppShell>
    )
  }

  if (!record) {
    return (
      <AppShell title="Your brief">
        <Card>
          <CardHeader>
            <CardTitle>No brief yet</CardTitle>
            <CardDescription>
              The agent writes one when a project owner adds you. If you've just
              been added, give it a few minutes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => regenerate()} disabled={regenerating} className="gap-2">
              <Sparkles className="h-4 w-4" /> Write one now
            </Button>
          </CardContent>
        </Card>
      </AppShell>
    )
  }

  if (record.status === 'generating') {
    return (
      <AppShell title="Your brief">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              The agent is reading your project
            </CardTitle>
            <CardDescription>
              Nobody asked it to — it started when you were added. It's taking
              stock of every connected source, then working out what you'll need
              to know. A few minutes.
            </CardDescription>
          </CardHeader>
        </Card>
      </AppShell>
    )
  }

  if (record.status === 'error' || !brief) {
    return (
      <AppShell title="Your brief">
        <Card>
          <CardHeader>
            <CardTitle>Couldn't write your brief</CardTitle>
            <CardDescription>{record.error_message || 'Something went wrong.'}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={() => regenerate()} disabled={regenerating} className="gap-2">
              <RefreshCw className={`h-4 w-4 ${regenerating ? 'animate-spin' : ''}`} /> Try again
            </Button>
          </CardContent>
        </Card>
      </AppShell>
    )
  }

  return (
    <AppShell title="Your brief">
      <div className="flex flex-col gap-6 max-w-3xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Badge variant="secondary" className="mb-2 gap-1.5">
              <Sparkles className="h-3 w-3" /> Written for you, unprompted
            </Badge>
            <h1 className="text-xl font-semibold leading-snug">{brief.headline}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              The agent read every connected source when you were added to this
              project. Everything below names where it came from.
            </p>
          </div>
          <Button
            variant="ghost" size="sm" className="gap-1.5 shrink-0"
            onClick={() => regenerate()} disabled={regenerating}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${regenerating ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>

        {/* Acting on a stale reading list is worse than having none. */}
        {record.stale_reason && (
          <Card className="border-amber-500/40 bg-amber-500/[0.04]">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <RefreshCw className="h-4 w-4 text-amber-600 dark:text-amber-500" />
                The project has changed since this was written
              </CardTitle>
              <CardDescription>{record.stale_reason}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button size="sm" onClick={() => regenerate()} disabled={regenerating}>
                {regenerating ? 'Rewriting…' : 'Rewrite it'}
              </Button>
            </CardContent>
          </Card>
        )}

        {brief.sections.map((s) => (
          <Card key={s.heading}>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{s.heading}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              {s.sources.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {s.sources.map((src) => (
                    <Badge key={src} variant="outline" className="font-mono text-xs">{src}</Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}

        {brief.reading_list.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpen className="h-4 w-4 text-muted-foreground" /> Read these first
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {brief.reading_list.map((r, i) => (
                <div key={`${r.title}-${i}`} className="flex gap-3">
                  <span className="text-xs font-medium text-muted-foreground pt-0.5 tabular-nums">{i + 1}</span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{r.title}</p>
                    <p className="text-xs text-muted-foreground">{r.why}</p>
                    <Badge variant="outline" className="mt-1 font-mono text-xs">{r.source}</Badge>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {brief.people_to_meet.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Users className="h-4 w-4 text-muted-foreground" /> People to talk to
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {brief.people_to_meet.map((p) => (
                <div key={p.name} className="flex items-start gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium uppercase">
                    {p.name.slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{p.name}</p>
                    <p className="text-xs text-muted-foreground">{p.why}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* The honest part. An agent that only reports what it found is selling
            something; one that reports what is missing is useful. */}
        {brief.open_questions.length > 0 && (
          <Card className="border-dashed">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <HelpCircle className="h-4 w-4 text-muted-foreground" />
                What nobody wrote down
              </CardTitle>
              <CardDescription>
                Things you'll need that aren't in any connected source. Worth
                asking a human — or worth someone documenting.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-col gap-2">
                {brief.open_questions.map((q, i) => (
                  <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                    <span className="text-muted-foreground/50">—</span>
                    <span>{q}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  )
}
