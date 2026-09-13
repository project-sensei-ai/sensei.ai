import { useState, type FormEvent } from 'react'
import { Check, HelpCircle, Loader2, MessagesSquare, TrendingUp, X } from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useAnswerQuestionMutation,
  useDismissQuestionMutation,
  useGetLedgerQuery,
  type Unanswered,
} from '@/services/onboardingApi'

function OpenQuestion({ entry, canAnswer }: { entry: Unanswered; canAnswer: boolean }) {
  const [answerQuestion, { isLoading }] = useAnswerQuestionMutation()
  const [dismissQuestion] = useDismissQuestionMutation()
  const [text, setText] = useState('')
  const [composing, setComposing] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    await answerQuestion({ id: entry.id, text }).unwrap().catch(() => {})
    setText('')
    setComposing(false)
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          {entry.times_asked > 1 && (
            <Badge variant="destructive" className="text-xs">
              asked {entry.times_asked} times
            </Badge>
          )}
          {entry.asked_by_name && (
            <span className="text-xs text-muted-foreground">by {entry.asked_by_name}</span>
          )}
        </div>
        <CardTitle className="text-base font-medium leading-snug">{entry.question}</CardTitle>
      </CardHeader>
      <CardContent>
        {!canAnswer ? (
          <p className="text-sm text-muted-foreground">
            Your project owner has been asked to fill this in.
          </p>
        ) : composing ? (
          <form onSubmit={submit} className="flex flex-col gap-2">
            <textarea
              autoFocus
              rows={3}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Answer it once. The agent will answer it for everyone from now on."
              className="w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <div className="flex gap-2">
              <Button type="submit" size="sm" disabled={isLoading || !text.trim()} className="gap-1.5">
                {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                Save and index
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setComposing(false)}>
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex gap-2">
            <Button size="sm" onClick={() => setComposing(true)}>Answer it</Button>
            <Button
              size="sm" variant="ghost" className="gap-1.5 text-muted-foreground"
              onClick={() => dismissQuestion(entry.id)}
            >
              <X className="h-3.5 w-3.5" /> Not worth documenting
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * The answer ledger.
 *
 * Every question the agent could not ground is kept. An owner answers it once,
 * it is indexed, and the agent has it permanently — so the project ends up
 * documented by being used rather than by someone finding an afternoon.
 */
export default function Answers() {
  const { data, isLoading } = useGetLedgerQuery(undefined, { pollingInterval: 20000 })
  const entries = data?.entries ?? []
  const open = entries.filter((e) => e.status === 'open')
  const answered = entries.filter((e) => e.status === 'answered')
  const stats = data?.stats

  return (
    <AppShell title="Answers">
      <div className="flex max-w-3xl flex-col gap-6">
        <div>
          <h1 className="text-xl font-semibold">What the agent couldn't answer</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Questions your team asked that the project had never written down.
            Answer one here and the agent knows it from then on.
          </p>
        </div>

        {stats && (
          <Card className="border-dashed">
            <CardContent className="flex flex-wrap gap-x-10 gap-y-4 pt-6">
              <div>
                <p className="flex items-center gap-1.5 text-2xl font-semibold tabular-nums">
                  <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  {stats.without_a_human_pct}%
                </p>
                <p className="text-xs text-muted-foreground">
                  answered without a human
                </p>
              </div>
              <div>
                <p className="text-2xl font-semibold tabular-nums">{stats.answers_given}</p>
                <p className="text-xs text-muted-foreground">questions handled</p>
              </div>
              <div>
                <p className="text-2xl font-semibold tabular-nums">{stats.answered_by_humans}</p>
                <p className="text-xs text-muted-foreground">
                  gaps closed by the team
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </p>
        ) : (
          <>
            {open.length > 0 && (
              <div className="flex flex-col gap-3">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <HelpCircle className="h-4 w-4 text-muted-foreground" />
                  Waiting on a person ({open.length})
                </p>
                {open.map((e) => (
                  <OpenQuestion key={e.id} entry={e} canAnswer={data?.can_answer ?? false} />
                ))}
              </div>
            )}

            {answered.length > 0 && (
              <div className="flex flex-col gap-3">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <MessagesSquare className="h-4 w-4 text-muted-foreground" />
                  Now part of what the agent knows ({answered.length})
                </p>
                {answered.map((e) => (
                  <Card key={e.id}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium leading-snug">{e.question}</CardTitle>
                      <CardDescription className="text-sm text-foreground/80">{e.answer}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-xs text-muted-foreground">
                        Answered by {e.answered_by}. The agent cites this as “Team answers”.
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {open.length === 0 && answered.length === 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Nothing outstanding</CardTitle>
                  <CardDescription>
                    Everything asked so far, the agent could answer from your sources.
                  </CardDescription>
                </CardHeader>
              </Card>
            )}
          </>
        )}
      </div>
    </AppShell>
  )
}
