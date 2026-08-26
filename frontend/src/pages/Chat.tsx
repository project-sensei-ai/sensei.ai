import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Bot, ChevronDown, ChevronUp, Send, User } from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/Spinner'
import { useSendMessageMutation, type ChatCitation } from '@/services/onboardingApi'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: ChatCitation[]
  error?: boolean
}

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
              <span className="font-semibold text-primary mr-1.5">[{c.index}]</span>
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

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`shrink-0 flex h-8 w-8 items-center justify-center rounded-full text-sm ${
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-primary text-primary-foreground rounded-tr-sm'
            : msg.error
            ? 'bg-destructive/10 text-destructive border border-destructive/20 rounded-tl-sm'
            : 'bg-muted rounded-tl-sm'
        }`}
      >
        <p className="whitespace-pre-wrap">{msg.content}</p>
        {!isUser && msg.citations && <CitationList citations={msg.citations} />}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="shrink-0 flex h-8 w-8 items-center justify-center rounded-full bg-muted">
        <Bot className="h-4 w-4" />
      </div>
      <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-muted px-4 py-3">
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" />
      </div>
    </div>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hi! Ask me anything about your indexed sources. I'll answer with citations.",
    },
  ])
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [sendMessage, { isLoading }] = useSendMessageMutation()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const question = input.trim()
    if (!question || isLoading) return

    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content: question }
    setMessages((prev) => [...prev, userMsg])
    setInput('')

    try {
      const res = await sendMessage({ question }).unwrap()
      const aiMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
      }
      setMessages((prev) => [...prev, aiMsg])
    } catch (err: any) {
      const detail = err?.data?.detail || 'Something went wrong. Please try again.'
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'assistant', content: detail, error: true },
      ])
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
      <div className="flex flex-col h-[calc(100vh-7rem)]">
        {/* Message list */}
        <div className="flex-1 overflow-y-auto flex flex-col gap-4 pb-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
          {isLoading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <form
          onSubmit={handleSubmit}
          className="flex gap-3 items-end border-t pt-4 bg-background"
        >
          <textarea
            ref={inputRef}
            rows={1}
            className="flex-1 min-w-0 resize-none rounded-xl border bg-muted/40 px-4 py-2.5 text-sm leading-relaxed placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 max-h-40 overflow-y-auto"
            placeholder="Ask anything about your sources… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <Button
            type="submit"
            size="icon"
            className="rounded-xl shrink-0 h-10 w-10"
            disabled={!input.trim() || isLoading}
          >
            {isLoading ? <Spinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </AppShell>
  )
}
