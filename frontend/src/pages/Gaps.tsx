import { useState } from 'react'
import {
  AlertTriangle, FileWarning, Loader2, PenLine, RefreshCw, ShieldQuestion, Sparkles, X,
} from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useGetGapsQuery,
  useGetDraftQuery,
  useRequestDraftMutation,
  useRescanGapsMutation,
  useGetMyWorkspaceQuery,
  type Gap,
} from '@/services/onboardingApi'

const SEVERITY: Record<string, { label: string; className: string }> = {
  high: { label: 'High', className: 'border-destructive/40 text-destructive' },
  medium: { label: 'Medium', className: 'border-amber-500/40 text-amber-600 dark:text-amber-500' },
  low: { label: 'Low', className: 'border-border text-muted-foreground' },
}

const KIND: Record<string, string> = {
  missing_document: 'Nothing written',
  unowned_area: 'No owner',
  dangling_reference: 'Reference goes nowhere',
  thin_coverage: 'Barely covered',
}

/** The draft, once the agent has written it. */
function DraftPanel({ gap, onClose }: { gap: Gap; onClose: () => void }) {
  const { data } = useGetDraftQuery(gap.id, { pollingInterval: 5000 })
  const record = data?.draft
  const doc = record?.draft

  return (
    <div className="mt-4 rounded-lg border bg-muted/20">
      <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{doc?.title || `Drafting: ${gap.title}`}</p>
          <p className="text-xs text-muted-foreground">
            Written by the agent from your own sources. Review before publishing.
          </p>
        </div>
        <Button size="icon" variant="ghost" className="h-7 w-7 shrink-0" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {!record || record.status === 'drafting' ? (
        <p className="flex items-center gap-2 px-4 py-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Reading the sources and writing it…
        </p>
      ) : record.status === 'error' ? (
        <p className="px-4 py-4 text-sm text-destructive">{record.error_message}</p>
      ) : doc ? (
        <div className="flex flex-col gap-4 px-4 py-4">
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border bg-background p-3 font-mono text-xs leading-relaxed">
            {doc.body_markdown}
          </pre>

          {doc.sources_used.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-medium">Built from</p>
              <div className="flex flex-wrap gap-1.5">
                {doc.sources_used.map((src) => (
                  <Badge key={src} variant="outline" className="font-mono text-xs">{src}</Badge>
                ))}
              </div>
            </div>
          )}

          {/* The part that makes a machine-written document safe to use. */}
          {doc.assumptions.length > 0 && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/[0.06] p-3">
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-amber-700 dark:text-amber-500">
                <AlertTriangle className="h-3.5 w-3.5" />
                Verify these before you publish
              </p>
              <ul className="flex flex-col gap-1">
                {doc.assumptions.map((a, i) => (
                  <li key={i} className="text-xs text-muted-foreground">— {a}</li>
                ))}
              </ul>
            </div>
          )}

          <Button
            size="sm" variant="outline" className="self-start"
            onClick={() => navigator.clipboard?.writeText(doc.body_markdown)}
          >
            Copy markdown
          </Button>
        </div>
      ) : null}
    </div>
  )
}

function GapCard({ gap, canManage }: { gap: Gap; canManage: boolean }) {
  const [requestDraft, { isLoading }] = useRequestDraftMutation()
  const [open, setOpen] = useState(false)
  const sev = SEVERITY[gap.severity] ?? SEVERITY.low

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className={`text-xs ${sev.className}`}>{sev.label}</Badge>
          <Badge variant="secondary" className="text-xs">{KIND[gap.kind] ?? gap.kind}</Badge>
        </div>
        <CardTitle className="text-base">{gap.title}</CardTitle>
        <CardDescription>{gap.detail}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {gap.evidence.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Noticed from</span>
            {gap.evidence.map((e, i) => (
              <Badge key={i} variant="outline" className="font-mono text-xs">{e}</Badge>
            ))}
          </div>
        )}

        {gap.can_draft ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm" className="gap-1.5" disabled={!canManage || isLoading}
              onClick={() => { requestDraft(gap.id); setOpen(true) }}
            >
              <PenLine className="h-3.5 w-3.5" />
              {open ? 'Rewrite it' : 'Write it for me'}
            </Button>
            <span className="text-xs text-muted-foreground">
              from {gap.draft_from.join(', ') || 'the indexed sources'}
            </span>
          </div>
        ) : (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldQuestion className="h-3.5 w-3.5 shrink-0" />
            Nothing indexed comes close enough to write this from — it needs a person.
          </p>
        )}

        {open && <DraftPanel gap={gap} onClose={() => setOpen(false)} />}
      </CardContent>
    </Card>
  )
}

/**
 * What nobody wrote down.
 *
 * Every other screen reports what the project has. This one reports what it is
 * missing — which, in a real project, is the thing that actually costs people
 * time.
 */
export default function Gaps() {
  const { data, isLoading } = useGetGapsQuery(undefined, { pollingInterval: 8000 })
  const { data: wsData } = useGetMyWorkspaceQuery()
  const [rescan, { isLoading: rescanning }] = useRescanGapsMutation()
  const canManage = wsData?.workspace?.role !== 'member'

  const report = data?.report
  const gaps = report?.gaps ?? []
  const draftable = gaps.filter((g) => g.can_draft).length

  return (
    <AppShell title="Gaps">
      <div className="flex max-w-3xl flex-col gap-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Badge variant="secondary" className="mb-2 gap-1.5">
              <Sparkles className="h-3 w-3" /> Found without being asked
            </Badge>
            <h1 className="text-xl font-semibold">What nobody wrote down</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              The agent audits its own knowledge whenever a source lands, looking
              for what's absent rather than what's there.
            </p>
          </div>
          {canManage && (
            <Button
              variant="ghost" size="sm" className="shrink-0 gap-1.5"
              onClick={() => rescan()} disabled={rescanning || report?.status === 'scanning'}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${rescanning || report?.status === 'scanning' ? 'animate-spin' : ''}`} />
              Re-audit
            </Button>
          )}
        </div>

        {isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </p>
        ) : !report ? (
          <Card>
            <CardHeader>
              <CardTitle>No audit yet</CardTitle>
              <CardDescription>
                One runs automatically when a source finishes indexing, or start
                one now.
              </CardDescription>
            </CardHeader>
          </Card>
        ) : report.status === 'scanning' ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Auditing the project
              </CardTitle>
              <CardDescription>
                Checking for documents that should exist, areas with no owner,
                and references that go nowhere.
              </CardDescription>
            </CardHeader>
          </Card>
        ) : report.status === 'error' ? (
          <Card>
            <CardHeader>
              <CardTitle>The audit didn't finish</CardTitle>
              <CardDescription>{report.error_message}</CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <>
            {report.refresh_error && (
              <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
                The last audit did not complete — {report.refresh_error} This is the last good report.
              </p>
            )}
            {report.summary && (
              <Card className="border-dashed">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileWarning className="h-4 w-4 text-muted-foreground" />
                    {gaps.length} gap{gaps.length === 1 ? '' : 's'}
                    {draftable > 0 && (
                      <span className="font-normal text-muted-foreground">
                        · {draftable} the agent offers to write
                      </span>
                    )}
                  </CardTitle>
                  <CardDescription>{report.summary}</CardDescription>
                </CardHeader>
              </Card>
            )}

            {gaps.map((g) => <GapCard key={g.id} gap={g} canManage={canManage} />)}

            {gaps.length === 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Nothing missing</CardTitle>
                  <CardDescription>
                    The audit found no gaps worth raising in what's connected.
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
