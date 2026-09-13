import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  Bot, CheckCircle2, ChevronDown, ChevronUp, Loader2, Mic, MicOff, Send, Square, Video, Volume2, VolumeX,
} from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useGetMeQuery } from '@/services/authApi'
import {
  useEndMeetingMutation,
  useGetMeetingQuery,
  useListMeetingsQuery,
  useStartMeetingMutation,
  type Meeting,
  type MeetingReply,
  type MeetingUtterance,
} from '@/services/onboardingApi'

type Line =
  | { kind: 'said'; u: MeetingUtterance }
  | { kind: 'reply'; r: MeetingReply }

// Browser speech recognition, where it exists. Chrome and Edge have it;
// Firefox does not. Typing is always available, so nothing is lost without it.
const Recognition: any =
  typeof window !== 'undefined' ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition : null

function speak(text: string, enabled: boolean) {
  if (!enabled || typeof window === 'undefined' || !('speechSynthesis' in window)) return
  try {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.rate = 1.02
    window.speechSynthesis.speak(u)
  } catch { /* the page still shows the text */ }
}

function ReplyBubble({ r }: { r: MeetingReply }) {
  const [open, setOpen] = useState(false)
  if (r.kind === 'silent') {
    return (
      <div className="ml-11 flex items-center gap-2 text-[11px] text-muted-foreground/70">
        <span className="inline-block h-1 w-1 rounded-full bg-muted-foreground/40" />
        stayed quiet — {r.reason}
      </div>
    )
  }
  const correction = r.kind === 'correction'
  return (
    <div className="flex gap-3">
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${correction ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400' : 'bg-primary/10 text-primary'}`}>
        <Bot className="h-4 w-4" />
      </div>
      <div className={`max-w-[85%] rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed ${correction ? 'border border-amber-500/30 bg-amber-500/[0.06]' : 'bg-muted'}`}>
        <div className="mb-1 flex items-center gap-2">
          <span className="text-xs font-semibold">Sensei</span>
          <Badge variant={correction ? 'outline' : 'secondary'} className={`h-5 text-[10px] ${correction ? 'border-amber-500/40 text-amber-700 dark:text-amber-400' : ''}`}>
            {correction ? `correction · ${Math.round(r.confidence * 100)}% sure` : 'answered'}
          </Badge>
        </div>
        <p className="whitespace-pre-wrap">{r.text}</p>
        {r.citations.length > 0 && (
          <div className="mt-2 border-t pt-2">
            <button className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground" onClick={() => setOpen((o) => !o)}>
              {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {r.citations.length} source{r.citations.length !== 1 ? 's' : ''}
            </button>
            {open && (
              <ul className="mt-1.5 flex flex-col gap-1">
                {r.citations.map((c) => (
                  <li key={c.index} className="rounded bg-background/60 px-2 py-1 text-[11px]">
                    <span className="font-medium">{c.source_label}</span>
                    <span className="text-muted-foreground"> — {c.excerpt}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function LiveMeeting({ meeting, onEnded }: { meeting: Meeting; onEnded: () => void }) {
  const { data: me } = useGetMeQuery()
  const { data, refetch } = useGetMeetingQuery(meeting.id, { pollingInterval: meeting.mode === 'meet_bot' ? 2500 : 0 })
  const [endMeeting, { isLoading: ending }] = useEndMeetingMutation()
  const [speaker, setSpeaker] = useState(me?.user.name ?? 'Me')
  const [text, setText] = useState('')
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [voice, setVoice] = useState(true)
  const [pending, setPending] = useState<string[]>([])
  const [lines, setLines] = useState<Line[]>([])
  const recRef = useRef<any>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const seenReplies = useRef<Set<string>>(new Set())

  const live = data?.meeting ?? meeting

  // Rebuild the timeline from the server copy whenever it changes (the bot
  // mode appends there; the companion mode appends locally and confirms).
  useEffect(() => {
    if (!data?.meeting) return
    const t = data.meeting.transcript ?? []
    const rs = data.meeting.replies ?? []
    const merged: Line[] = []
    let ri = 0
    for (let i = 0; i < t.length; i++) {
      merged.push({ kind: 'said', u: t[i] })
      if (rs[ri]) { merged.push({ kind: 'reply', r: rs[ri] }); ri++ }
    }
    for (; ri < rs.length; ri++) merged.push({ kind: 'reply', r: rs[ri] })
    setLines(merged)
    if (meeting.mode === 'meet_bot') {
      for (const r of rs) {
        if (r.kind !== 'silent' && !seenReplies.current.has(r.id)) {
          seenReplies.current.add(r.id)
          speak(r.text, voice)
        }
      }
    }
  }, [data, meeting.mode, voice])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [lines, pending, interim])
  useEffect(() => { if (me?.user.name) setSpeaker(me.user.name) }, [me])

  async function say(utteranceText: string) {
    const clean = utteranceText.trim()
    if (!clean) return
    setPending((p) => [...p, clean])
    try {
      const res = await fetch(`/api/meetings/${meeting.id}/utterances`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
        body: JSON.stringify({ speaker, text: clean }),
      })
      if (res.ok) {
        const body = await res.json()
        setLines((l) => [...l, { kind: 'said', u: body.utterance }, { kind: 'reply', r: body.reply }])
        if (body.reply.kind !== 'silent') {
          seenReplies.current.add(body.reply.id)
          speak(body.reply.text, voice)
        }
      } else {
        const detail = (await res.json().catch(() => ({})))?.detail
        setLines((l) => [...l, { kind: 'reply', r: {
          id: `err-${Date.now()}`, at: new Date().toISOString(), kind: 'silent', trigger: clean,
          text: '', citations: [], confidence: 0, reason: detail || `could not reach Sensei (${res.status})`,
        } }])
      }
    } catch {
      setLines((l) => [...l, { kind: 'reply', r: {
        id: `err-${Date.now()}`, at: new Date().toISOString(), kind: 'silent', trigger: clean,
        text: '', citations: [], confidence: 0, reason: 'could not reach Sensei — is the server up?',
      } }])
    } finally {
      setPending((p) => p.filter((x) => x !== clean))
    }
  }

  function startListening() {
    if (!Recognition) return
    const rec = new Recognition()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = 'en-US'
    rec.onresult = (ev: any) => {
      let finalText = ''
      let interimText = ''
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i]
        if (r.isFinal) finalText += r[0].transcript
        else interimText += r[0].transcript
      }
      setInterim(interimText)
      if (finalText.trim()) { setInterim(''); say(finalText) }
    }
    rec.onend = () => { if (recRef.current === rec) { try { rec.start() } catch { setListening(false) } } }
    rec.onerror = (e: any) => { if (e.error === 'not-allowed') { setListening(false); recRef.current = null } }
    recRef.current = rec
    rec.start()
    setListening(true)
  }

  function stopListening() {
    const rec = recRef.current
    recRef.current = null
    try { rec?.stop() } catch { /* already stopped */ }
    setListening(false)
    setInterim('')
  }

  useEffect(() => () => stopListening(), [])

  async function handleEnd() {
    stopListening()
    await endMeeting(meeting.id).unwrap()
    onEnded()
    refetch()
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    const t = text
    setText('')
    say(t)
  }

  return (
    <div className="flex h-[calc(100vh-9rem)] flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
        </span>
        <h2 className="text-base font-semibold">{live.title}</h2>
        <Badge variant="secondary" className="text-xs">{live.mode === 'meet_bot' ? 'Google Meet bot' : 'companion'}</Badge>
        {live.mode === 'meet_bot' && live.bot_status && (
          <Badge variant="outline" className="text-xs">bot: {live.bot_status}</Badge>
        )}
        <span className="text-xs text-muted-foreground">{live.utterance_count} heard · {live.reply_count} spoke</span>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" variant="ghost" className="h-8 gap-1 text-xs" onClick={() => setVoice((v) => !v)} title="Read replies aloud">
            {voice ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />}
          </Button>
          <Button size="sm" variant="destructive" className="h-8 gap-1 text-xs" disabled={ending} onClick={handleEnd}>
            {ending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Square className="h-3.5 w-3.5" />} End & write notes
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto rounded-xl border bg-card/40 p-4">
        {lines.length === 0 && pending.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
            <Bot className="h-8 w-8 opacity-30" />
            {live.mode === 'meet_bot' ? (
              <p>Sensei is joining the call. Admit it when Meet asks, and it will start reading the captions.</p>
            ) : (
              <>
                <p>Sensei is in the room and listening.</p>
                <p className="text-xs">Say <span className="font-medium text-foreground">"Sensei, …"</span> to ask it something. State something wrong about the project and see whether it corrects you — it only will when a source says so.</p>
              </>
            )}
          </div>
        )}
        <div className="flex flex-col gap-3">
          {lines.map((ln, i) =>
            ln.kind === 'said' ? (
              <div key={i} className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">
                  {ln.u.speaker.slice(0, 2).toUpperCase()}
                </div>
                <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-background px-4 py-2.5 text-sm">
                  <span className="mr-2 text-xs font-medium text-muted-foreground">{ln.u.speaker}</span>
                  {ln.u.text}
                </div>
              </div>
            ) : (
              <ReplyBubble key={i} r={ln.r} />
            ),
          )}
          {pending.map((p) => (
            <div key={p} className="ml-11 flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Sensei is deciding whether to say anything…
            </div>
          ))}
          {interim && <p className="ml-11 text-xs italic text-muted-foreground">{interim}</p>}
          <div ref={bottomRef} />
        </div>
      </div>

      {live.mode === 'companion' && (
        <form onSubmit={submit} className="flex items-end gap-2">
          <Input value={speaker} onChange={(e) => setSpeaker(e.target.value)} className="w-32 shrink-0" placeholder="Speaker" title="Who is talking" />
          <Input
            value={text} onChange={(e) => setText(e.target.value)}
            placeholder={listening ? 'Listening… or type what was said' : 'Type what was said, or turn the mic on'}
            className="flex-1"
          />
          {Recognition && (
            <Button type="button" size="icon" variant={listening ? 'default' : 'outline'} onClick={listening ? stopListening : startListening} title={listening ? 'Stop listening' : 'Listen to the room'}>
              {listening ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
            </Button>
          )}
          <Button type="submit" size="icon" disabled={!text.trim()}><Send className="h-4 w-4" /></Button>
        </form>
      )}
    </div>
  )
}

function PastMeeting({ m }: { m: Meeting }) {
  const [open, setOpen] = useState(false)
  const { data } = useGetMeetingQuery(m.id, { skip: !open })
  const full = data?.meeting
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">{m.title}</CardTitle>
          <Badge variant="secondary" className="text-xs">{m.mode === 'meet_bot' ? 'Google Meet' : 'companion'}</Badge>
          <span className="text-xs text-muted-foreground">
            {m.started_at ? new Date(m.started_at).toLocaleString() : ''} · {m.utterance_count} lines · Sensei spoke {m.reply_count}×
          </span>
          {m.source_id && (
            <Badge variant="outline" className="gap-1 text-xs"><CheckCircle2 className="h-3 w-3 text-green-500" /> indexed, citable</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm">
        {m.summary ? (
          <>
            <p>{(m.summary as any).summary}</p>
            {((m.summary as any).decisions?.length > 0) && (
              <div><p className="text-xs font-medium text-muted-foreground">Decisions</p>
                <ul className="list-disc pl-5 text-sm">{(m.summary as any).decisions.map((d: string) => <li key={d}>{d}</li>)}</ul></div>
            )}
            {((m.summary as any).action_items?.length > 0) && (
              <div><p className="text-xs font-medium text-muted-foreground">Action items</p>
                <ul className="list-disc pl-5 text-sm">{(m.summary as any).action_items.map((d: string) => <li key={d}>{d}</li>)}</ul></div>
            )}
          </>
        ) : (
          <p className="text-xs text-muted-foreground">{m.status === 'ended' ? 'Writing the notes…' : 'No notes yet.'}</p>
        )}
        <button className="flex items-center gap-1 self-start text-xs text-muted-foreground hover:text-foreground" onClick={() => setOpen((o) => !o)}>
          {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />} transcript
        </button>
        {open && full && (
          <div className="max-h-72 overflow-y-auto rounded-md border bg-muted/20 p-3 text-xs">
            {(full.transcript ?? []).map((u, i) => <p key={i}><span className="font-medium">{u.speaker}:</span> {u.text}</p>)}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Meetings.
 *
 * The colleague in the room. It listens, answers when someone says its name,
 * and corrects a wrong claim only when a source says so — with the source.
 * Afterwards it writes the notes and indexes them, so next week's "what did we
 * decide" has a citation.
 */
export default function Meetings() {
  const { data, isLoading, refetch } = useListMeetingsQuery(undefined, { pollingInterval: 6000 })
  const [startMeeting, { isLoading: starting }] = useStartMeetingMutation()
  const [title, setTitle] = useState('')
  const [mode, setMode] = useState<'companion' | 'meet_bot'>('companion')
  const [meetUrl, setMeetUrl] = useState('')
  const [err, setErr] = useState('')
  const [active, setActive] = useState<Meeting | null>(null)

  const meetings = data?.meetings ?? []
  const liveOnServer = meetings.find((m) => m.status === 'live')

  useEffect(() => {
    if (!active && liveOnServer) setActive(liveOnServer)
  }, [liveOnServer, active])

  async function start(e: FormEvent) {
    e.preventDefault()
    setErr('')
    try {
      const res = await startMeeting({ title: title || 'Team sync', mode, meet_url: mode === 'meet_bot' ? meetUrl : undefined }).unwrap()
      setActive(res.meeting)
      setTitle('')
    } catch (e: any) {
      setErr(e?.data?.detail || 'Could not start the meeting')
    }
  }

  if (active && active.status === 'live') {
    return (
      <AppShell title="Meetings">
        <LiveMeeting meeting={active} onEnded={() => { setActive(null); refetch() }} />
      </AppShell>
    )
  }

  return (
    <AppShell title="Meetings">
      <div className="flex max-w-3xl flex-col gap-6">
        <div>
          <h1 className="text-xl font-semibold">Sensei in the room</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            It listens, answers when addressed, and corrects a claim only when a source contradicts it. Then it writes the notes.
          </p>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base"><Video className="h-4 w-4 text-muted-foreground" /> Bring it into a meeting</CardTitle>
            <CardDescription>
              Companion mode transcribes this browser's microphone — works beside any call. Bot mode sends Sensei into a Google Meet as a participant that reads the captions and replies in the chat.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={start} className="flex flex-col gap-3">
              <div className="flex gap-1.5">
                {(['companion', 'meet_bot'] as const).map((m) => (
                  <button key={m} type="button" onClick={() => setMode(m)}
                    className={`rounded-full border px-3 py-1 text-xs ${mode === m ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'}`}>
                    {m === 'companion' ? 'Companion (this device)' : 'Join a Google Meet'}
                  </button>
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input placeholder="Meeting title, e.g. Sprint planning" value={title} onChange={(e) => setTitle(e.target.value)} />
                {mode === 'meet_bot' && (
                  <Input placeholder="https://meet.google.com/abc-defg-hij" value={meetUrl} onChange={(e) => setMeetUrl(e.target.value)} required />
                )}
              </div>
              {mode === 'meet_bot' && (
                <p className="text-xs text-muted-foreground">
                  Sensei joins as a guest named "Sensei (AI colleague)". The host admits it, it turns on captions, and posts replies in the meeting chat. Google changes Meet often — the bot reports each step here so a failure is visible, not silent.
                </p>
              )}
              {err && <p className="text-xs text-destructive">{err}</p>}
              <Button type="submit" size="sm" className="self-start gap-1.5" disabled={starting}>
                {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
                {mode === 'companion' ? 'Start listening' : 'Send Sensei to the meeting'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-medium">Past meetings</p>
          {isLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</p>
          ) : meetings.filter((m) => m.status === 'ended').length === 0 ? (
            <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              Nothing yet. After a meeting ends, its notes land here and become a source the agent can cite in <Link to="/chat" className="underline underline-offset-2">chat</Link>.
            </p>
          ) : (
            meetings.filter((m) => m.status === 'ended').map((m) => <PastMeeting key={m.id} m={m} />)
          )}
        </div>
      </div>
    </AppShell>
  )
}
