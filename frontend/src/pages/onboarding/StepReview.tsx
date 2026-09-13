import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useGetSourcesQuery, type SourceStatus } from '@/services/onboardingApi'
import { CheckCircle, Clock, Loader2, AlertCircle } from 'lucide-react'

interface Props {
  onDone: () => void
}

const STATUS_CONFIG: Record<SourceStatus, { label: string; icon: React.ReactNode; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
  pending: { label: 'Pending', icon: <Clock className="h-3 w-3" />, variant: 'secondary' },
  indexing: { label: 'Indexing…', icon: <Loader2 className="h-3 w-3 animate-spin" />, variant: 'default' },
  ready: { label: 'Ready', icon: <CheckCircle className="h-3 w-3" />, variant: 'outline' },
  error: { label: 'Error', icon: <AlertCircle className="h-3 w-3" />, variant: 'destructive' },
}

const TYPE_LABELS: Record<string, string> = {
  github: 'GitHub',
  file: 'File',
  url: 'URL',
  confluence: 'Confluence',
  jira: 'Jira',
  slack: 'Slack',
}

export default function StepReview({ onDone }: Props) {
  const allDone = (sources: any[]) => sources.every((s) => s.status === 'ready' || s.status === 'error')

  const { data, isLoading } = useGetSourcesQuery(undefined, {
    pollingInterval: 3000,
  })

  const sources = data?.sources ?? []
  const done = allDone(sources)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review ingestion</CardTitle>
        <CardDescription>
          Sensei is indexing your sources. Wait for all to finish, then continue.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isLoading ? (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading sources…
          </div>
        ) : sources.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sources added yet.</p>
        ) : (
          sources.map((source) => {
            const cfg = STATUS_CONFIG[source.status as SourceStatus]
            return (
              <div key={source.id} className="flex items-center justify-between rounded-lg border px-4 py-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium">{source.label}</span>
                  <span className="text-xs text-muted-foreground">{TYPE_LABELS[source.type] ?? source.type}</span>
                  {source.error_message && (
                    <span className="text-xs text-destructive">{source.error_message}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {source.status === 'ready' && source.stats && (
                    <span className="text-xs text-muted-foreground">
                      {source.stats.chunks_count ?? 0} chunks · {source.stats.pages_crawled ?? 0} pages
                    </span>
                  )}
                  <Badge variant={cfg.variant} className="gap-1 text-xs">
                    {cfg.icon} {cfg.label}
                  </Badge>
                </div>
              </div>
            )
          })
        )}
      </CardContent>
      <CardFooter>
        <Button className="w-full" disabled={!done || sources.length === 0} onClick={onDone}>
          {done ? 'Continue to invite →' : 'Waiting for ingestion…'}
        </Button>
      </CardFooter>
    </Card>
  )
}
