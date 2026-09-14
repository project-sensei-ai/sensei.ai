import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Check, ChevronDown, ChevronRight, ChevronUp, Download, FileSpreadsheet, FileText, Loader2, MessageSquarePlus, Send, Trash2, User } from 'lucide-react'
import { AnswerText } from '@/components/AnswerText'
import { AppShell } from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/Spinner'
import { SenseiAvatar } from '@/components/SenseiAvatar'
import {
  useListChatSessionsQuery,
  useCreateChatSessionMutation,
  useGetChatSessionQuery,
  useArchiveChatSessionMutation,
  type Artifact,
  type ChatCitation,
  type ChatMessage,
  type ChatStep,
} from '@/services/onboardingApi'

// ── Helpers ────────────────────────────────────────────────────────────────────

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function CitationList({ citations }: { citations: ChatCitation[] }) {
  const [open, setOpen] = useState(false)
  if (citations.length === 0) return null
  return (
    <div className="mt-3 border-t pt-3">
      <button
        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        {citations.length} source{citations.length !== 1 ? 's' : ''} cited
      </button>
      {open && (
        <ul className="mt-2 flex flex-col gap-2">
          {citations.map((c) => (
            <li key={c.index} className="rounded-md bg-muted/60 px-3 py-2 text-xs">
              <span className="font-medium">{c.source_label}</span>
              <span className="ml-2 text-muted-foreground">({Math.round(c.score * 100)}% match)</span>
              <p className="mt-1 text-muted-foreground leading-relaxed">{c.excerpt}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function seconds(ms: number): string {
  const s = ms / 1000
  return s < 10 ? `${Math.max(0.1, Math.round(s * 10) / 10)}s` : `${Math.round(s)}s`
}

/** What the agent did while it was answering, folded away once the answer is in. */
function ThoughtDisclosure({ steps, durationMs }: { steps: ChatStep[]; durationMs?: number | null }) {
  const [open, setOpen] = useState(false)
  if (steps.length === 0) return null
  const total = durationMs ?? steps[steps.length - 1]?.ms ?? null
  const summary = [
    total != null && total > 0 ? `Thought for ${seconds(total)}` : 'Thought',
    `${steps.length} step${steps.length !== 1 ? 's' : ''}`,
  ].join(' · ')
  return (
    <div className="mb-2">
      <button
        className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {summary}
      </button>
      {open && (
        <ol className="mt-1.5 flex flex-col gap-1 border-l pl-3">
          {steps.map((s, i) => (
            <li key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
              <Check className="h-3 w-3 shrink-0 text-primary/70" />
              <span className="flex-1">{s.label}</span>
              <span className="tabular-nums text-muted-foreground/60">{seconds(s.ms)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

/** The steps as they happen: earlier ones ticked, the current one moving. */
function LiveSteps({ steps, writing }: { steps: string[]; writing: boolean }) {
  if (steps.length === 0) return null
  return (
    <ol className="ml-11 flex flex-col gap-1" aria-live="polite">
      {steps.map((label, i) => {
        const current = i === steps.length - 1
        return (
          <li
            key={i}
            className={`flex items-center gap-2 text-xs ${current ? 'text-foreground' : 'text-muted-foreground'}`}
          >
            {current
              ? <Loader2 className={`h-3 w-3 shrink-0 text-primary ${writing ? '' : 'animate-spin'}`} />
              : <Check className="h-3 w-3 shrink-0 text-primary/70" />}
            <span className={current && !writing ? 'animate-pulse' : ''}>{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

function MessageBubble({ msg, live = false }: { msg: ChatMessage & { error?: boolean }; live?: boolean }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div
        className={`shrink-0 flex h-8 w-8 items-center justify-center rounded-full text-sm ${
          isUser ? 'bg-primary text-primary-foreground' : ''
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <SenseiAvatar size="sm" />}
      </div>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : (msg as any).error
            ? 'bg-destructive/10 text-destructive border border-destructive/20 rounded-tl-sm'
            : 'bg-muted rounded-tl-sm'
        }`}
      >
        {!isUser && !live && msg.steps && msg.steps.length > 0 && (
          <ThoughtDisclosure steps={msg.steps} durationMs={msg.duration_ms} />
        )}
        {isUser || (msg as any).error
          ? <p className="whitespace-pre-wrap">{msg.content}</p>
          : <AnswerText text={msg.content} live={live} />}
        {!isUser && msg.artifacts && msg.artifacts.length > 0 && (
          <ArtifactList artifacts={msg.artifacts} />
        )}
        {!isUser && msg.citations && msg.citations.length > 0 && (
          <CitationList citations={msg.citations} />
        )}
      </div>
    </div>
  )
}

function ArtifactList({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) return null
  return (
    <div className="mt-3 flex flex-col gap-2">
      {artifacts.map((a) => (
        <a
          key={a.id}
          href={a.url}
          className="flex items-center gap-3 rounded-lg border bg-background/60 px-3 py-2 text-xs transition-colors hover:bg-background"
        >
          {a.kind === 'spreadsheet'
            ? <FileSpreadsheet className="h-5 w-5 shrink-0 text-green-600" />
            : <FileText className="h-5 w-5 shrink-0 text-blue-600" />}
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium">{a.filename}</span>
            <span className="block text-muted-foreground">{a.summary} · {Math.max(1, Math.round(a.size / 1024))} KB</span>
          </span>
          <Download className="h-4 w-4 shrink-0 text-muted-foreground" />
        </a>
      ))}
    </div>
  )
}

// What a colleague gets asked on day one. Each is a real capability, and the
// chip is the fastest way for a reviewer to find out.
const STARTERS = [
  "Who's on call next week, and who's the release captain?",
  'What has Daniel worked on recently?',
  'Put the open issues and PRs in a spreadsheet',
  'What did we decide about Friday deploys?',
  'Is there a runbook for rollbacks?',
]

function Starters({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {STARTERS.map((q) => (
        <button
          key={q}
          onClick={() => onPick(q)}
          className="rounded-full border bg-background px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
        >
          {q}
        </button>
      ))}
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="shrink-0 flex h-8 w-8 items-center justify-center rounded-full">
        <SenseiAvatar size="sm" pulse />
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-muted px-4 py-3">
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" />
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function Chat() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [optimisticMessages, setOptimisticMessages] = useState<(ChatMessage & { error?: boolean })[]>([])
  // What the agent is doing right now, and what it has said so far. Both live
  // only while a stream is open; once it closes the message is persisted and
  // comes back through the session query like any other.
  const [streamingText, setStreamingText] = useState('')
  const [liveSteps, setLiveSteps] = useState<string[]>([])
  const [streaming, setStreaming] = useState(false)
  // How many stored messages there were when the optimistic ones were added.
  // Until the stored list grows past it, the optimistic ones are shown after it.
  const [optimisticBase, setOptimisticBase] = useState(0)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const { data: sessionsData, isLoading: sessionsLoading } = useListChatSessionsQuery()
  const { data: sessionData, refetch: refetchSession } = useGetChatSessionQuery(
    activeSessionId ?? '',
    { skip: !activeSessionId },
  )
  const [createSession, { isLoading: creating }] = useCreateChatSessionMutation()
  const [archiveSession] = useArchiveChatSessionMutation()

  const sessions = sessionsData?.sessions ?? []
  const storedMessages: (ChatMessage & { error?: boolean })[] = sessionData?.session.messages ?? []

  // Stored messages, then any optimistic ones not yet persisted. Showing one or
  // the other made an existing conversation hide the question while it streamed,
  // and blank out the finished answer until the refetch came back.
  const persisted = storedMessages.length > optimisticBase
  const messages = persisted ? storedMessages : [...storedMessages, ...optimisticMessages]

  useEffect(() => {
    // The exchange is stored now; the optimistic copies have done their job.
    if (persisted && optimisticMessages.length > 0) setOptimisticMessages([])
  }, [persisted, optimisticMessages.length])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, streamingText])

  // Landing on /chat with history but no selection showed a zero-state asking
  // you to start a conversation you had already started. Open the most recent
  // one instead; the empty state is for people who genuinely have none.
  useEffect(() => {
    if (activeSessionId) return
    const latest = sessionsData?.sessions?.[0]
    if (latest) setActiveSessionId(latest.id)
  }, [sessionsData, activeSessionId])

  async function handleNewChat() {
    const res = await createSession().unwrap()
    setActiveSessionId(res.session.id)
    setOptimisticMessages([])
    inputRef.current?.focus()
  }

  async function handleArchive(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    await archiveSession(id)
    if (activeSessionId === id) {
      setActiveSessionId(null)
      setOptimisticMessages([])
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const question = input.trim()
    if (!question || streaming) return

    let sessionId = activeSessionId

    // Auto-create session on first send if none active
    if (!sessionId) {
      const res = await createSession().unwrap()
      sessionId = res.session.id
      setActiveSessionId(sessionId)
    }

    setInput('')

    // Optimistic user message (shows immediately while waiting for AI)
    const userMsg: ChatMessage & { error?: boolean } = {
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    }
    if (optimisticMessages.length === 0 || persisted) setOptimisticBase(storedMessages.length)
    setOptimisticMessages((prev) => (persisted ? [userMsg] : [...prev, userMsg]))

    setStreaming(true)
    setStreamingText('')
    setLiveSteps(['Reading your question'])

    try {
      const res = await fetch(`/api/chat/sessions/${sessionId}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ question }),
      })
      if (!res.ok || !res.body) throw new Error(`Request failed (${res.status})`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let answer = ''
      let citations: ChatCitation[] = []
      let artifacts: Artifact[] = []
      let steps: ChatStep[] = []
      let durationMs: number | null = null
      let failed: string | null = null
      const addStep = (label?: string) => {
        if (!label) return
        setLiveSteps((prev) => (prev[prev.length - 1] === label ? prev : [...prev, label]))
      }

      // Server-sent events arrive as `data: {...}\n\n`, and a chunk can split
      // an event in half — so hold the remainder until the next read.
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.split('\n').find((l) => l.startsWith('data: '))
          if (!line) continue
          const event = JSON.parse(line.slice(6))
          if (event.type === 'step' || event.type === 'tool') {
            addStep(event.label)
          } else if (event.type === 'reset') {
            // What was shown was narration, not the answer: take it back.
            answer = ''
            setStreamingText('')
          } else if (event.type === 'text') {
            if (!answer) addStep('Writing the answer')
            answer += event.delta
            setStreamingText(answer)
          } else if (event.type === 'done') {
            if (typeof event.answer === 'string') answer = event.answer
            citations = event.citations ?? []
            artifacts = event.artifacts ?? []
            steps = event.steps ?? []
            durationMs = event.duration_ms ?? null
          } else if (event.type === 'notice') {
            // Older servers sent plumbing here; show only that the turn is slower.
            addStep('Taking a little longer to check')
          } else if (event.type === 'error') {
            failed = event.message
          }
        }
      }

      setOptimisticMessages((prev) => [...prev, {
        role: 'assistant',
        content: failed ?? answer,
        citations,
        artifacts,
        steps: failed ? [] : steps,
        duration_ms: durationMs,
        error: !!failed,
        created_at: new Date().toISOString(),
      }])
      refetchSession?.()
    } catch (err: any) {
      setOptimisticMessages((prev) => [...prev, {
        role: 'assistant',
        content: err?.message || 'Something went wrong. Please try again.',
        error: true,
        created_at: new Date().toISOString(),
      }])
    } finally {
      setStreaming(false)
      setStreamingText('')
      setLiveSteps([])
    }

    inputRef.current?.focus()
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as FormEvent)
    }
  }

  return (
    <AppShell title="Chat">
      <div className="flex h-[calc(100vh-7rem)] gap-0 -mx-6 -mt-2">

        {/* ── Session sidebar ─────────────────────────────────────────────── */}
        <aside className="w-64 shrink-0 flex flex-col border-r bg-muted/20">
          <div className="p-3 border-b">
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 justify-start"
              onClick={handleNewChat}
              disabled={creating}
            >
              {creating ? <Spinner className="h-3.5 w-3.5" /> : <MessageSquarePlus className="h-3.5 w-3.5" />}
              New chat
            </Button>
          </div>

          <nav className="flex-1 overflow-y-auto py-2">
            {sessionsLoading ? (
              <div className="flex justify-center py-8"><Spinner className="h-5 w-5" /></div>
            ) : sessions.length === 0 ? (
              <p className="px-4 py-6 text-xs text-muted-foreground text-center">
                No chats yet. Start one above.
              </p>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.id}
                  onClick={() => { setActiveSessionId(s.id); setOptimisticMessages([]) }}
                  className={`group w-full flex items-start gap-2 px-3 py-2.5 text-left text-sm transition-colors hover:bg-muted/60 ${
                    activeSessionId === s.id ? 'bg-muted/80 font-medium' : ''
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="truncate leading-snug">{s.title}</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">{timeAgo(s.updated_at)}</p>
                  </div>
                  <button
                    onClick={(e) => handleArchive(s.id, e)}
                    className="shrink-0 mt-0.5 p-1 rounded opacity-0 group-hover:opacity-100 hover:text-destructive hover:bg-destructive/10 transition-all"
                    title="Archive chat"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </button>
              ))
            )}
          </nav>
        </aside>

        {/* ── Conversation panel ──────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 px-6">
          {!activeSessionId ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center">
              <SenseiAvatar size="lg" />
              <div>
                <p className="font-medium">Ask Sensei like a colleague</p>
                <p className="text-sm text-muted-foreground mt-1">
                  About the project, a person's work, a ticket's status — or hand it work.
                </p>
              </div>
              <Starters onPick={(q) => { setInput(q); handleNewChat() }} />
              <Button onClick={handleNewChat} disabled={creating} className="gap-2">
                {creating ? <Spinner className="h-4 w-4" /> : <MessageSquarePlus className="h-4 w-4" />}
                New chat
              </Button>
            </div>
          ) : (
            <>
              {/* Message list */}
              <div className="flex-1 overflow-y-auto flex flex-col gap-4 py-4">
                {messages.length === 0 && !streaming && (
                  <div className="flex h-full flex-col items-center justify-center gap-4">
                    <SenseiAvatar size="lg" />
                    <p className="text-sm text-muted-foreground">What would you ask a colleague who has read everything?</p>
                    <Starters onPick={(q) => { setInput(q); inputRef.current?.focus() }} />
                  </div>
                )}
                {messages.map((msg, i) => (
                  <MessageBubble key={i} msg={msg} />
                ))}

                {/* The agent working, rather than a spinner hiding it. */}
                {streaming && (
                  <div className="flex flex-col gap-2">
                    <LiveSteps steps={liveSteps} writing={!!streamingText} />
                    {streamingText ? (
                      <MessageBubble
                        live
                        msg={{
                          role: 'assistant',
                          content: streamingText,
                          created_at: new Date().toISOString(),
                        }}
                      />
                    ) : (
                      liveSteps.length === 0 && <TypingIndicator />
                    )}
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              {/* Input */}
              <form
                onSubmit={handleSubmit}
                className="flex gap-3 items-end border-t pt-4 bg-background"
              >
                <textarea
                  ref={inputRef}
                  rows={1}
                  className="flex-1 min-w-0 resize-none rounded-xl border bg-muted/40 px-4 py-2.5 text-sm leading-relaxed placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 max-h-40 overflow-y-auto"
                  placeholder="Ask anything… (Enter to send, Shift+Enter for newline)"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={streaming}
                />
                <Button
                  type="submit"
                  size="icon"
                  className="rounded-xl shrink-0 h-10 w-10"
                  disabled={!input.trim() || streaming}
                >
                  {streaming ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
