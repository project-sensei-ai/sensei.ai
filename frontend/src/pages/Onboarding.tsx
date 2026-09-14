import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Loader2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { SenseiAvatar } from '@/components/SenseiAvatar'
import { BrandLogo } from '@/components/BrandLogo'
import TeamPanel from '@/components/TeamPanel'
import { useGetMeQuery } from '@/services/authApi'
import {
  useCreateWorkspaceMutation,
  useGetMembersQuery,
  useGetSourcesQuery,
  useGetToolsQuery,
} from '@/services/onboardingApi'
import { AddSourcePanel } from './Sources'
import { ConnectPanel, useOAuthCompletion } from './Tools'

/**
 * Onboarding, as a conversation.
 *
 * A new colleague's first day is a conversation, not a form: what's the
 * project, where do you keep things, which accounts do I get, who's on the
 * team. Sensei asks; the owner answers by connecting things. Each answer
 * becomes a line in the transcript, and the last message is Sensei saying
 * exactly what it can now reach.
 */

type Step = 'name' | 'sources' | 'tools' | 'team' | 'done'

interface Line {
  from: 'sensei' | 'you'
  text: ReactNode
}

function Typing() {
  return (
    <span className="inline-flex items-center gap-1 px-1 py-1">
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
    </span>
  )
}

function Bubble({ line, typing }: { line: Line; typing?: boolean }) {
  const you = line.from === 'you'
  return (
    <div className={`flex items-end gap-3 ${you ? 'flex-row-reverse' : ''}`}>
      {you ? (
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">you</span>
      ) : (
        <SenseiAvatar />
      )}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          you ? 'rounded-br-sm bg-primary text-primary-foreground' : 'rounded-bl-sm bg-muted'
        }`}
      >
        {typing ? <Typing /> : line.text}
      </div>
    </div>
  )
}

/** Sensei "types" for a moment before each message; the pause is the point. */
function useConversation(initial: Line[]) {
  const [lines, setLines] = useState<Line[]>([])
  const [typing, setTyping] = useState(false)
  const queue = useRef<Line[]>([...initial])
  const busy = useRef(false)

  function pump() {
    if (busy.current) return
    const next = queue.current.shift()
    if (!next) return
    busy.current = true
    if (next.from === 'sensei') {
      setTyping(true)
      setTimeout(() => {
        setTyping(false)
        setLines((l) => [...l, next])
        busy.current = false
        pump()
      }, 650)
    } else {
      setLines((l) => [...l, next])
      busy.current = false
      pump()
    }
  }

  useEffect(() => { pump() /* eslint-disable-line react-hooks/exhaustive-deps */ }, [])

  return {
    lines, typing,
    say: (...more: Line[]) => { queue.current.push(...more); pump() },
  }
}

export default function Onboarding() {
  const navigate = useNavigate()
  const { data: authData } = useGetMeQuery()
  const user = authData?.user
  const first = (user?.name || '').split(' ')[0] || 'there'

  const { lines, typing, say } = useConversation([
    { from: 'sensei', text: <>Hi {first}, I'm Sensei. I'm about to join your team as a colleague — I'll read what you point me at, use the accounts you give me, and sit in on meetings when asked.</> },
    { from: 'sensei', text: <>First: what's the project called?</> },
  ])

  const [step, setStep] = useState<Step>('name')
  const [name, setName] = useState('')
  const [createWorkspace, { isLoading: creating }] = useCreateWorkspaceMutation()
  const [wsErr, setWsErr] = useState('')

  const { data: sourcesData } = useGetSourcesQuery(undefined, { skip: step === 'name', pollingInterval: step === 'sources' || step === 'done' ? 3000 : 0 })
  const { data: toolsData, refetch: refetchTools } = useGetToolsQuery(undefined, { skip: step === 'name' })
  const { data: membersData } = useGetMembersQuery(undefined, { skip: step === 'name' })
  const sources = sourcesData?.sources ?? []
  const tools = toolsData?.grants ?? []
  const members = membersData?.members ?? []
  useOAuthCompletion(refetchTools, tools.some((t) => t.status === 'authorizing'))

  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [lines, typing, step, sources.length, tools.length])

  // Narrate what the owner connects, as it happens.
  const seenSources = useRef<Set<string>>(new Set())
  useEffect(() => {
    for (const s of sources) {
      if (!seenSources.current.has(s.id)) {
        seenSources.current.add(s.id)
        if (seenSources.current.size > 0 && step !== 'name') {
          say({ from: 'sensei', text: <>Got <span className="font-medium">{s.label}</span>. I'll start reading it now.</> })
        }
      }
    }
  }, [sources]) // eslint-disable-line react-hooks/exhaustive-deps
  const seenTools = useRef<Set<string>>(new Set())
  useEffect(() => {
    for (const t of tools) {
      if (t.status === 'connected' && !seenTools.current.has(t.id)) {
        seenTools.current.add(t.id)
        say({ from: 'sensei', text: <>{t.name} is connected — {t.read_count} things I can look up and {t.write_count} I could change{t.allow_write ? ", and you have allowed those" : ", which stay off until you say so"}.</> })
      }
    }
  }, [tools]) // eslint-disable-line react-hooks/exhaustive-deps

  async function submitName(e: FormEvent) {
    e.preventDefault()
    setWsErr('')
    try {
      await createWorkspace({ name: name.trim(), description: '' }).unwrap()
      say(
        { from: 'you', text: name.trim() },
        { from: 'sensei', text: <><span className="font-medium">{name.trim()}</span> — got it. Where does the team keep its knowledge? Connect the repo, the wiki space, the ticket project, or drop in files. I read all of it, and I cite what I read.</> },
      )
      setStep('sources')
    } catch (err: any) {
      setWsErr(err?.data?.detail || 'Could not create the project')
    }
  }

  function finishSources() {
    const ready = sources.length
    say(
      { from: 'you', text: ready ? `That's ${ready} source${ready !== 1 ? 's' : ''} for now.` : 'No sources yet — later.' },
      { from: 'sensei', text: <>Now, which accounts do I get? Sign in to a service and I receive a token I can refresh — nothing to paste. Everything is read-only until you switch writes on.</> },
    )
    setStep('tools')
  }

  function finishTools() {
    const n = tools.filter((t) => t.status === 'connected').length
    say(
      { from: 'you', text: n ? `${n} tool connection${n !== 1 ? 's' : ''}.` : 'No tools for now.' },
      { from: 'sensei', text: <>Last thing: who should be able to ask me? Nobody reaches this project unless their email is on this list. When you add someone, I research the project for them and have a brief waiting before they first log in.</> },
    )
    setStep('team')
  }

  function finishTeam() {
    const people = members.length
    const chunks = sources.reduce((n, s) => n + (s.stats?.chunks_count ?? 0), 0)
    const connected = tools.filter((t) => t.status === 'connected')
    const reads = connected.reduce((n, t) => n + t.read_count, 0)
    const writes = connected.filter((t) => t.allow_write).reduce((n, t) => n + t.write_count, 0)
    say(
      { from: 'you', text: `${people} ${people === 1 ? 'person' : 'people'} on the project.` },
      { from: 'sensei', text: (
        <div className="flex flex-col gap-2">
          <p>Here's what I can reach, and it's all on the Trust page too:</p>
          <ul className="list-disc pl-5">
            <li>{sources.length} source{sources.length !== 1 ? 's' : ''}{chunks ? `, ${chunks} passages indexed so far` : ''}</li>
            <li>{connected.length} tool connection{connected.length !== 1 ? 's' : ''}: {reads} things I can look up, {writes} I may change when asked</li>
            <li>{people} {people === 1 ? 'person' : 'people'} who can ask me</li>
          </ul>
          <p>I'll keep reading in the background, audit what nobody wrote down, and write a brief for each teammate. Ask me anything when you're ready.</p>
        </div>
      ) },
    )
    setStep('done')
  }

  return (
    <div className="flex min-h-svh flex-col bg-background">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-2.5">
          <BrandLogo className="h-9 w-auto" />
          <Badge variant="secondary" className="text-[10px]">joining your team</Badge>
        </div>
        {user && <span className="text-xs text-muted-foreground">Setting up as <strong>{user.email}</strong></span>}
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-4 px-4 py-8">
        {lines.map((l, i) => <Bubble key={i} line={l} />)}
        {typing && <Bubble line={{ from: 'sensei', text: '' }} typing />}

        {/* The current question's answer surface, rendered as the owner's turn. */}
        {!typing && step === 'name' && lines.length >= 2 && (
          <form onSubmit={submitName} className="ml-12 flex max-w-[85%] gap-2">
            <Input autoFocus placeholder="e.g. Apollo Delivery" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} disabled={creating} />
            <Button type="submit" disabled={creating || !name.trim()}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            </Button>
            {wsErr && <p className="text-xs text-destructive">{wsErr}</p>}
          </form>
        )}

        {!typing && step === 'sources' && (
          <div className="ml-12 flex flex-col gap-3 rounded-2xl border bg-card p-4 shadow-sm">
            {sources.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {sources.map((s) => (
                  <Badge key={s.id} variant="outline" className="gap-1 text-xs">
                    {s.status === 'ready' ? <CheckCircle2 className="h-3 w-3 text-green-500" /> : <Loader2 className="h-3 w-3 animate-spin" />}
                    {s.label}
                  </Badge>
                ))}
              </div>
            )}
            <AddSourcePanel onClose={() => {}} embedded />
            <Button variant="outline" className="self-end" onClick={finishSources}>
              {sources.length ? "That's enough for now" : 'Skip for now'} <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        )}

        {!typing && step === 'tools' && (
          <div className="ml-12 flex flex-col gap-3 rounded-2xl border bg-card p-4 shadow-sm">
            {tools.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {tools.map((t) => (
                  <Badge key={t.id} variant="outline" className="gap-1 text-xs">
                    {t.status === 'connected' ? <CheckCircle2 className="h-3 w-3 text-green-500" /> : <Loader2 className="h-3 w-3 animate-spin" />}
                    {t.name}{t.status === 'authorizing' ? ' — finish signing in' : ''}
                  </Badge>
                ))}
              </div>
            )}
            <ConnectPanel onClose={() => {}} embedded />
            <Button variant="outline" className="self-end" onClick={finishTools}>
              {tools.length ? 'Continue' : 'Skip for now'} <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        )}

        {!typing && step === 'team' && (
          <div className="ml-12 flex flex-col gap-3 rounded-2xl border bg-card p-4 shadow-sm">
            <TeamPanel compact />
            <Button variant="outline" className="self-end" onClick={finishTeam}>
              Continue <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        )}

        {!typing && step === 'done' && (
          <div className="ml-12 flex gap-2">
            <Button onClick={() => navigate('/dashboard')} className="gap-1.5">
              <Sparkles className="h-4 w-4" /> Open the dashboard
            </Button>
            <Button variant="outline" onClick={() => navigate('/chat')}>Ask something</Button>
          </div>
        )}
        <div ref={bottomRef} />
      </main>
    </div>
  )
}
