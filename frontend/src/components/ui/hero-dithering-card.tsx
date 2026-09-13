import {
  ArrowRight,
  BookOpen,
  CircleDot,
  Database,
  FileText,
  GitBranch,
  Hash,
  MessagesSquare,
} from "lucide-react"
import { useState, Suspense, lazy } from "react"
import { Link } from "react-router-dom"

const Dithering = lazy(() =>
  import("@paper-design/shaders-react").then((mod) => ({ default: mod.Dithering }))
)

const sources = [
  { name: "Confluence", icon: BookOpen },
  { name: "GitHub", icon: GitBranch },
  { name: "Jira", icon: CircleDot },
  { name: "Slack", icon: Hash },
]

const citations = [
  { label: "Slack #all-sensei", icon: Hash },
  { label: "Jira KAN-1", icon: CircleDot },
  { label: "sensei.ai@d4f31a", icon: GitBranch },
  { label: "billing-design", icon: FileText },
]

interface CTASectionProps {
  ctaHref?: string
  ctaLabel?: string
  secondaryHref?: string
  secondaryLabel?: string
}

export function CTASection({
  ctaHref,
  ctaLabel = "Start asking",
  secondaryHref,
  secondaryLabel,
}: CTASectionProps) {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <section
      className="relative w-full overflow-hidden"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* The shader fills the complete hero background, edge to edge. */}
      <Suspense fallback={<div className="absolute inset-0 bg-muted/20" />}>
        <div
          className="absolute inset-0 z-0 pointer-events-none opacity-40 dark:opacity-30 mix-blend-multiply dark:mix-blend-screen"
          aria-hidden
        >
          <Dithering
            colorBack="#00000000"
            colorFront="#EC4E02"
            shape="warp"
            type="4x4"
            speed={isHovered ? 0.6 : 0.2}
            className="size-full"
            minPixelRatio={1}
          />
        </div>
      </Suspense>

      <div className="relative z-10 flex flex-col items-center px-6 pt-28 pb-12 md:pt-32">
        <div className="max-w-2xl mx-auto text-center flex flex-col items-center">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-primary/10 bg-primary/5 px-4 py-1.5 text-sm font-medium text-primary backdrop-blur-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
            Your team context, indexed
          </div>

          <h2 className="font-serif text-5xl md:text-7xl lg:text-8xl font-medium tracking-[-0.03em] text-foreground mb-8 leading-[1.02]">
            Every decision, <br />
            <span className="text-foreground/80">answered instantly.</span>
          </h2>

          <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mb-12 leading-relaxed">
            Sensei connects Confluence, GitHub, Jira and Slack, and answers
            project questions with citations you can verify — permission-aware,
            grounded, and always up to date.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            {ctaHref ? (
              <Link
                to={ctaHref}
                className="group relative inline-flex h-14 items-center justify-center gap-3 overflow-hidden rounded-full bg-primary px-12 text-base font-medium text-primary-foreground transition-all duration-300 hover:bg-primary/90 hover:scale-105 active:scale-95 hover:ring-4 hover:ring-primary/20"
              >
                <span className="relative z-10">{ctaLabel}</span>
                <ArrowRight className="h-5 w-5 relative z-10 transition-transform duration-300 group-hover:translate-x-1" />
              </Link>
            ) : (
              <button className="group relative inline-flex h-14 items-center justify-center gap-3 overflow-hidden rounded-full bg-primary px-12 text-base font-medium text-primary-foreground transition-all duration-300 hover:bg-primary/90 hover:scale-105 active:scale-95 hover:ring-4 hover:ring-primary/20">
                <span className="relative z-10">{ctaLabel}</span>
                <ArrowRight className="h-5 w-5 relative z-10 transition-transform duration-300 group-hover:translate-x-1" />
              </button>
            )}
            {secondaryHref && secondaryLabel && (
              <Link
                to={secondaryHref}
                className="inline-flex h-14 items-center justify-center rounded-full border border-border bg-background/70 px-10 text-base font-medium text-foreground transition-all duration-300 hover:bg-muted/60"
              >
                {secondaryLabel}
              </Link>
            )}
          </div>
        </div>

        {/* Proof scene — a grounded, cited answer drawn from the connected sources */}
        <div className="w-full max-w-3xl mt-14 md:mt-16">
          <div className="rounded-2xl border border-border bg-background/90 p-4 md:p-6 shadow-sm text-left">
            <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <MessagesSquare className="h-4 w-4 text-foreground/60" />
                Ask Sensei
              </div>
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="inline-flex rounded-full h-2 w-2 bg-primary"></span>
                grounded
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              <div className="self-end max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground">
                When is the funding closing? And what did we decide on the payment SDK?
              </div>

              <div className="self-start max-w-[92%] flex flex-col gap-3">
                <div className="rounded-2xl rounded-bl-md border border-border bg-muted/50 px-4 py-3 text-sm text-foreground leading-relaxed">
                  Funding closes next week. On the SDK, the team signed off on the
                  merge for Friday — the decision thread, the ticket and the commit
                  all line up:
                </div>
                <div className="flex flex-wrap gap-2">
                  {citations.map((c) => (
                    <span key={c.label} className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground">
                      <c.icon className="h-3.5 w-3.5" />
                      {c.label}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  Example answer — real answers cite exactly what you connect.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Source strip + the two facets, one row, no cards */}
      <div className="relative z-10 flex flex-col items-center gap-4 border-t border-border/60 bg-background/40 px-6 py-5 sm:flex-row sm:justify-between">
        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
          <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground/70">
            Connected
          </span>
          {sources.map((s) => (
            <span key={s.name} className="inline-flex items-center gap-1.5 text-sm text-foreground/80">
              <s.icon className="h-4 w-4 text-foreground/50" />
              {s.name}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm text-foreground/80">
          <span className="inline-flex items-center gap-1.5">
            <Database className="h-4 w-4 text-foreground/50" />
            Memory — decisions &amp; context indexed
          </span>
          <span className="inline-flex items-center gap-1.5">
            <MessagesSquare className="h-4 w-4 text-foreground/50" />
            Chat — cited answers
          </span>
        </div>
      </div>
    </section>
  )
}