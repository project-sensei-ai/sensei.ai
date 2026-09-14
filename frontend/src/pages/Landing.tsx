import { Link } from 'react-router-dom'
import {
  ArrowRight, BookOpen, Check, CircleDot, ClipboardList, FileSpreadsheet, GitBranch, Hash,
  ListChecks, Lock, MessageSquareText, Mic, Search, ShieldCheck, Sparkles, UserPlus, Users,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { BrandLogo } from '@/components/BrandLogo'
import { CTASection } from '@/components/ui/hero-dithering-card'
import { useGetMeQuery } from '../services/authApi'
import { Spinner } from '@/components/Spinner'

// Every question below is real: it is answerable on the sample project, and
// the place the answer hides is where it actually lives there.
const PAINS = [
  { q: 'Where is the rollback procedure?', where: 'A Confluence runbook nobody links to. New joiners find it in week three.', icon: BookOpen },
  { q: 'Who owns notify-service?', where: 'The team directory says nobody has since July. Priya covers incidents in the meantime.', icon: Users },
  { q: 'Why don’t we deploy on Fridays?', where: 'ADR-005, decided in a meeting. The decision log has it; the person who asks does not.', icon: ClipboardList },
  { q: 'Is the barcode crash still open?', where: 'In Jira, changed an hour ago. A stale index would answer wrong; Sensei reads it live.', icon: CircleDot },
]

const STEPS = [
  {
    n: '1', title: 'Hand it what you would hand a new hire', icon: UserPlus,
    body: 'The wiki space, the repo, the ticket project, the Slack channel, files and URLs. Sign in to the tools the team uses and Sensei receives its own token. Every tool it gets is classified read or write, and writes stay off until you switch them on.',
  },
  {
    n: '2', title: 'It gets to work before anyone asks', icon: Sparkles,
    body: 'It interviews itself with the questions a new joiner would ask and grades the answers honestly. It writes each teammate a cited brief before they first log in, audits what nobody wrote down, and re-reads sources for change.',
  },
  {
    n: '3', title: 'It is in the room', icon: MessageSquareText,
    body: 'Ask it in the web chat. Mention it in Slack. Let it sit in a meeting. Same colleague, same sources, same rule about when to speak and when to stay quiet.',
  },
]

const FEATURES = [
  { title: 'Cited, plain answers', body: 'Sentences, not walls of markdown. The key fact in bold, the sources underneath, and the steps it took kept on the message as “Thought for 4s”.', icon: Search },
  { title: 'Who did what', body: '“What has Daniel worked on?” is read from commits, pull requests and tickets by person, not from prose about him.', icon: GitBranch },
  { title: 'Live where it matters', body: 'Ticket status and open pull requests are read from Jira and GitHub at the moment you ask, never from an index that was right yesterday.', icon: CircleDot },
  { title: 'Does the work', body: 'Ask for a spreadsheet or a handover document and it gathers the facts first, then hands you the file.', icon: FileSpreadsheet },
  { title: 'Refuses what it was not allowed', body: 'A write the owner has not allowed is cancelled inside the agent loop, and Sensei says exactly that instead of pretending.', icon: Lock },
  { title: 'Remembers what it could not answer', body: 'Unanswered questions go to a ledger. One human reply becomes permanent, cited knowledge for everyone.', icon: ListChecks },
]

const TRUST = [
  'Every credential is encrypted at rest and shown with its ceiling, what it could reach, beside its floor, what Sensei reads.',
  'Two members of one project can be answered from different sources. The filter runs inside the vector query, not after it.',
  'It never speaks unprompted without a source to cite, and every reply and every silence is recorded with its reason.',
  'Writes are off by default, per connection. Allowing them is one switch an owner flips, and it is listed on the Trust page.',
]

const ACCOUNTS = [
  { email: 'maya@apollo.demo', password: 'Apollo-Demo-2026!', role: 'Owner', project: 'Apollo Delivery, a dispatch platform with a repo, a Confluence space, Jira, Slack and files' },
  { email: 'priya@apollo.demo', password: 'Apollo-Demo-2026!', role: 'Member', project: 'Same project, a teammate’s view, with a brief written before her first login' },
  { email: 'judge@sensei.demo', password: 'Demo-miwVU8NczE6N', role: 'Owner', project: 'Sensei Demo Project, this codebase describing itself, GitHub tools read-only' },
]

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">{children}</div>
}

export default function Landing() {
  const { data: authData, isLoading: authLoading } = useGetMeQuery()
  const signedIn = !authLoading && !!authData?.user

  return (
    <div className="bg-background text-foreground relative min-h-svh">
      <CTASection
        ctaHref={signedIn ? '/dashboard' : '/register'}
        ctaLabel={signedIn ? 'Open dashboard' : 'Onboard Sensei'}
        secondaryHref={signedIn ? undefined : '#try'}
        secondaryLabel={signedIn ? undefined : 'Try the sample project'}
      />

      <header className="absolute inset-x-0 top-0 z-20 mx-auto flex w-full max-w-7xl items-center justify-between px-4 pt-6 md:px-6">
        <Link to="/" aria-label="Sensei home" className="flex items-center">
          <BrandLogo className="h-10 w-auto" />
        </Link>
        <nav className="flex items-center gap-2">
          <a href="#how" className="hidden text-sm text-muted-foreground hover:text-foreground md:inline-block px-3">How it works</a>
          <a href="#try" className="hidden text-sm text-muted-foreground hover:text-foreground md:inline-block px-3">Try it</a>
          {authLoading ? (
            <Spinner />
          ) : signedIn ? (
            <Button asChild variant="outline" size="sm">
              <Link to="/dashboard">Open dashboard</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link to="/login">Log in</Link>
              </Button>
              <Button asChild size="sm">
                <Link to="/register">Get started</Link>
              </Button>
            </>
          )}
        </nav>
      </header>

      {/* ── The problem ──────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-6xl px-6 py-20 md:py-28">
        <div className="grid gap-10 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] md:gap-16">
          <div>
            <Eyebrow>The problem</Eyebrow>
            <h2 className="font-serif text-3xl md:text-4xl font-medium tracking-[-0.02em] leading-[1.1]">
              Every team has one person everyone interrupts.
            </h2>
            <p className="mt-5 text-muted-foreground text-lg leading-relaxed">
              The runbook is in Confluence, the decision is in a Slack thread, the reason is in a
              meeting nobody wrote down, and who owns the notify service is in someone&rsquo;s head.
              New joiners lose weeks finding that person. That person loses hours being found.
            </p>
            <p className="mt-4 text-muted-foreground text-lg leading-relaxed">
              A chatbot does not fix this, because the knowledge is not in a chat.
            </p>
          </div>
          <ul className="grid gap-4 sm:grid-cols-2">
            {PAINS.map((p) => (
              <li key={p.q} className="rounded-2xl border border-border bg-card p-5">
                <p.icon className="h-5 w-5 text-foreground/60" aria-hidden />
                <p className="mt-3 font-medium leading-snug">&ldquo;{p.q}&rdquo;</p>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{p.where}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────── */}
      <section id="how" className="border-t border-border bg-muted/30 scroll-mt-16">
        <div className="mx-auto w-full max-w-6xl px-6 py-20 md:py-28">
          <Eyebrow>How it works</Eyebrow>
          <h2 className="font-serif text-3xl md:text-4xl font-medium tracking-[-0.02em] leading-[1.1] max-w-2xl">
            You onboard it like a hire. It works like one.
          </h2>
          <ol className="mt-12 grid gap-6 md:grid-cols-3">
            {STEPS.map((s) => (
              <li key={s.n} className="relative rounded-2xl border border-border bg-background p-6">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-semibold">{s.n}</span>
                  <s.icon className="h-5 w-5 text-foreground/60" aria-hidden />
                </div>
                <h3 className="mt-4 text-lg font-semibold leading-snug">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{s.body}</p>
              </li>
            ))}
          </ol>
          <p className="mt-8 text-sm text-muted-foreground">
            On the sample project, Sensei answers <strong className="text-foreground">7 of the 8</strong> questions a
            new joiner would ask in week one, from the sources alone. The eighth is already in the ledger, waiting for one human sentence.
          </p>
        </div>
      </section>

      {/* ── What it does ─────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-6xl px-6 py-20 md:py-28">
        <Eyebrow>When asked</Eyebrow>
        <h2 className="font-serif text-3xl md:text-4xl font-medium tracking-[-0.02em] leading-[1.1] max-w-2xl">
          Ask it the way you would ask a colleague.
        </h2>
        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <li key={f.title} className="rounded-2xl border border-border bg-card p-6">
              <f.icon className="h-5 w-5 text-foreground/60" aria-hidden />
              <h3 className="mt-4 font-semibold leading-snug">{f.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">{f.body}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* ── In the room ──────────────────────────────────────────────── */}
      <section className="border-t border-border bg-muted/30">
        <div className="mx-auto w-full max-w-6xl px-6 py-20 md:py-28">
          <Eyebrow>In the room</Eyebrow>
          <h2 className="font-serif text-3xl md:text-4xl font-medium tracking-[-0.02em] leading-[1.1] max-w-2xl">
            It knows when to speak, and when not to.
          </h2>
          <div className="mt-12 grid gap-6 md:grid-cols-2">
            <div className="rounded-2xl border border-border bg-background p-6">
              <div className="flex items-center gap-2 font-semibold"><Hash className="h-5 w-5 text-foreground/60" aria-hidden /> In Slack</div>
              <ul className="mt-4 space-y-3 text-sm text-muted-foreground leading-relaxed">
                <li><strong className="text-foreground">Mention it or message it</strong> and it always answers, in the thread, with the sources named.</li>
                <li><strong className="text-foreground">Ask the room</strong> something the project&rsquo;s sources answer and it steps in. No citation, no post.</li>
                <li><strong className="text-foreground">Small talk</strong> is left alone, and the reason is recorded.</li>
                <li>Every message in a channel it was added to is indexed as it arrives, so a decision at 10:02 is askable at 10:03.</li>
              </ul>
            </div>
            <div className="rounded-2xl border border-border bg-background p-6">
              <div className="flex items-center gap-2 font-semibold"><Mic className="h-5 w-5 text-foreground/60" aria-hidden /> In meetings</div>
              <ul className="mt-4 space-y-3 text-sm text-muted-foreground leading-relaxed">
                <li><strong className="text-foreground">Addressed by name</strong>, it answers, from the sources, out loud if you like.</li>
                <li><strong className="text-foreground">A wrong claim</strong> is corrected only when the documentation contradicts it, with a citation and confidence of 0.8 or more. Anything less, it stays quiet and records why.</li>
                <li><strong className="text-foreground">When the call ends</strong> it writes the notes, decisions and action items, and indexes them, so next week&rsquo;s &ldquo;what did we decide&rdquo; has a source.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ── Trust ────────────────────────────────────────────────────── */}
      <section className="mx-auto w-full max-w-6xl px-6 py-20 md:py-28">
        <div className="grid gap-10 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] md:gap-16">
          <div>
            <Eyebrow>Trust</Eyebrow>
            <h2 className="font-serif text-3xl md:text-4xl font-medium tracking-[-0.02em] leading-[1.1]">
              Access is a page you can read, not a promise.
            </h2>
            <p className="mt-5 text-muted-foreground text-lg leading-relaxed">
              An owner hands a colleague real credentials. The Trust page shows what each one could reach,
              what Sensei actually reads, which tools may write, and what it will never do.
            </p>
          </div>
          <ul className="space-y-4">
            {TRUST.map((t) => (
              <li key={t} className="flex gap-3 text-sm md:text-base text-muted-foreground leading-relaxed">
                <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-foreground/60" aria-hidden />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── Built on Strands ─────────────────────────────────────────── */}
      <section className="border-t border-border bg-muted/30">
        <div className="mx-auto w-full max-w-6xl px-6 py-16">
          <Eyebrow>Under the hood</Eyebrow>
          <div className="grid gap-8 md:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] md:items-start">
            <p className="text-muted-foreground leading-relaxed">
              One Strands <code>Agent</code> loop, equipped per question: custom <code>@tool</code>s for the index,
              live Jira and the files it makes, plus every tool the owner granted through <code>MCPClient</code>.
              A <code>BeforeToolCallEvent</code> hook enforces the write gate. A three-agent <code>Graph</code> researches
              each onboarding brief. Typed <code>structured_output</code> produces briefs, gap reports, claim verdicts and
              meeting notes. <code>stream_async</code> narrates the steps to the UI. Claude Haiku 4.5 answers, with
              Groq&rsquo;s free tier as the fallback chain. One container, HTTPS, on AWS.
            </p>
            <ul className="grid grid-cols-2 gap-2 text-sm">
              {['Strands Agents SDK', 'Model Context Protocol', 'Claude Haiku 4.5', 'FastAPI + React', 'MongoDB + ChromaDB', 'AWS EC2 + Caddy'].map((t) => (
                <li key={t} className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2">
                  <Check className="h-4 w-4 text-foreground/60" aria-hidden />{t}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Try it ───────────────────────────────────────────────────── */}
      <section id="try" className="mx-auto w-full max-w-6xl px-6 py-20 md:py-28 scroll-mt-16">
        <Eyebrow>Try it now</Eyebrow>
        <h2 className="font-serif text-3xl md:text-4xl font-medium tracking-[-0.02em] leading-[1.1] max-w-2xl">
          A real project is already onboarded. Log in and ask.
        </h2>
        <p className="mt-4 text-muted-foreground text-lg leading-relaxed max-w-2xl">
          No account, key or credit card of your own is needed. Start with &ldquo;Who is on call the week of 15 September?&rdquo;
          or &ldquo;Put the open Jira tickets in a spreadsheet.&rdquo;
        </p>
        <div className="mt-8 overflow-x-auto rounded-2xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr><th className="px-4 py-3 font-medium">Account</th><th className="px-4 py-3 font-medium">Password</th><th className="px-4 py-3 font-medium">Role</th><th className="px-4 py-3 font-medium">What you will see</th></tr>
            </thead>
            <tbody>
              {ACCOUNTS.map((a) => (
                <tr key={a.email} className="border-t border-border">
                  <td className="px-4 py-3 font-mono text-xs md:text-sm whitespace-nowrap">{a.email}</td>
                  <td className="px-4 py-3 font-mono text-xs md:text-sm whitespace-nowrap">{a.password}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{a.role}</td>
                  <td className="px-4 py-3 text-muted-foreground">{a.project}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-8 flex flex-wrap gap-3">
          {!signedIn && (
            <Button asChild size="lg" className="rounded-full px-8">
              <Link to="/login">Log in to the sample project <ArrowRight className="ml-2 h-4 w-4" /></Link>
            </Button>
          )}
          <Button asChild variant="outline" size="lg" className="rounded-full px-8">
            <Link to={signedIn ? '/dashboard' : '/register'}>{signedIn ? 'Open dashboard' : 'Onboard your own project'}</Link>
          </Button>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-3 px-6 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <span>Sensei, built for the Agents for Humans hackathon, Professional Agents track.</span>
          <a href="https://github.com/project-sensei-ai/sensei.ai" className="hover:text-foreground" target="_blank" rel="noreferrer">
            Source on GitHub, MIT licensed
          </a>
        </div>
      </footer>
    </div>
  )
}
