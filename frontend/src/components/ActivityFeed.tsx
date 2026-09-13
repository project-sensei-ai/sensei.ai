import { FileWarning, PenLine, Database, Sparkles, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { useGetActivityQuery, type ActivityEvent } from '@/services/onboardingApi'

const ICON = {
  brief: Sparkles,
  audit: FileWarning,
  draft: PenLine,
  source: Database,
} as const

function when(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  const mins = Math.round((Date.now() - then) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

function Row({ event }: { event: ActivityEvent }) {
  const Icon = ICON[event.kind] ?? Database
  return (
    <div className="flex gap-3 py-2.5">
      <div
        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
          event.unprompted ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
        }`}
      >
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium leading-snug">{event.title}</p>
          {/* The whole point of this feed: which of these did nobody ask for. */}
          {event.unprompted && (
            <Badge variant="secondary" className="h-5 text-[10px]">on its own</Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{event.detail}</p>
      </div>
      <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{when(event.at)}</span>
    </div>
  )
}

/**
 * A timeline of the agent's work.
 *
 * Most of what this product does happens when nobody is watching. Without
 * somewhere to see it, autonomy is indistinguishable from nothing happening.
 */
export default function ActivityFeed({ limit = 8 }: { limit?: number }) {
  const { data, isLoading } = useGetActivityQuery(undefined, { pollingInterval: 15000 })
  const events = (data?.events ?? []).slice(0, limit)

  if (isLoading) {
    return (
      <p className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading…
      </p>
    )
  }
  if (!events.length) {
    return (
      <p className="py-3 text-sm text-muted-foreground">
        Nothing yet. Connect a source or add a teammate and the agent will get to work.
      </p>
    )
  }

  return (
    <div className="flex flex-col divide-y">
      {events.map((e, i) => <Row key={`${e.at}-${i}`} event={e} />)}
    </div>
  )
}
