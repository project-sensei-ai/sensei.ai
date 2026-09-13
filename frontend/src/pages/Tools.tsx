import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle, Check, ChevronDown, ChevronUp, Loader2, Lock, PenLine, Plug, Plus,
  RefreshCw, ShieldCheck, Trash2, Unlock, X, Wrench,
} from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { errorMessage } from '@/services/authApi'
import {
  useConnectToolMutation,
  useGetOAuthPresetsQuery,
  useGetToolsQuery,
  useStartOAuthMutation,
  useRevokeToolMutation,
  useTestToolMutation,
  useUpdateToolMutation,
  type GrantKind,
  type ToolGrant,
} from '@/services/onboardingApi'

// Servers people actually have. Picking one fills the form; the credential is
// still theirs to paste. Nothing here is connected until they say so.
const PRESETS: { id: string; name: string; kind: GrantKind; url: string; authHint: string; note: string }[] = [
  {
    id: 'github', name: 'GitHub', kind: 'mcp_http', url: 'https://api.githubcopilot.com/mcp/',
    authHint: 'Bearer ghp_…  (a personal access token)',
    note: 'Issues, pull requests, code search, actions. Writes (create issue, comment, merge) stay off until you allow them.',
  },
  {
    id: 'zapier', name: 'Zapier', kind: 'mcp_http', url: 'https://mcp.zapier.com/api/mcp/mcp',
    authHint: 'Bearer <your Zapier MCP token>',
    note: 'Gmail, Google Sheets, Calendar, Slack, Notion, HubSpot — whatever you enabled in Zapier. One connection, many tools.',
  },
  {
    id: 'sentry', name: 'Sentry', kind: 'mcp_http', url: 'https://mcp.sentry.dev/mcp',
    authHint: 'Bearer <Sentry user auth token>',
    note: 'Errors, issues, releases. Read-only by nature of what it exposes.',
  },
  {
    id: 'custom', name: 'Custom MCP server', kind: 'mcp_http', url: '',
    authHint: 'Bearer … or a raw API key, whatever the server expects',
    note: 'Any server that speaks the Model Context Protocol over HTTP or SSE — an internal API, a vendor, a homegrown one.',
  },
]

function when(iso: string | null): string {
  if (!iso) return 'never'
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

function ToolList({ grant, canManage }: { grant: ToolGrant; canManage: boolean }) {
  const [open, setOpen] = useState(false)
  const [updateTool] = useUpdateToolMutation()
  const disabled = new Set(grant.disabled_tools)

  function toggle(name: string) {
    const next = disabled.has(name)
      ? grant.disabled_tools.filter((n) => n !== name)
      : [...grant.disabled_tools, name]
    updateTool({ id: grant.id, disabled_tools: next })
  }

  return (
    <div>
      <button
        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        {grant.tools.length} tools — {grant.read_count} read, {grant.write_count} write
      </button>
      {open && (
        <ul className="mt-2 max-h-72 divide-y overflow-y-auto rounded-md border">
          {grant.tools.map((t) => {
            const off = disabled.has(t.name)
            const blocked = t.access === 'write' && !grant.allow_write
            return (
              <li key={t.name} className={`flex items-start gap-2 px-3 py-2 text-xs ${off ? 'opacity-50' : ''}`}>
                <Badge
                  variant={t.access === 'write' ? 'destructive' : 'secondary'}
                  className="mt-0.5 h-5 shrink-0 text-[10px]"
                >
                  {t.access}
                </Badge>
                <div className="min-w-0 flex-1">
                  <p className="font-mono">{t.server_name}</p>
                  {t.description && <p className="text-muted-foreground line-clamp-2">{t.description}</p>}
                  {blocked && !off && (
                    <p className="mt-0.5 text-[11px] text-amber-600 dark:text-amber-500">
                      refused until writes are allowed
                    </p>
                  )}
                </div>
                {canManage && (
                  <button
                    onClick={() => toggle(t.name)}
                    className="shrink-0 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
                    title={off ? 'Enable this tool' : 'Disable this tool'}
                  >
                    {off ? 'enable' : 'disable'}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function GrantCard({ grant, canManage }: { grant: ToolGrant; canManage: boolean }) {
  const [updateTool, { isLoading: saving }] = useUpdateToolMutation()
  const [testTool, { isLoading: testing }] = useTestToolMutation()
  const [revokeTool, { isLoading: revoking }] = useRevokeToolMutation()
  const [confirm, setConfirm] = useState(false)
  const [testErr, setTestErr] = useState('')

  async function handleTest() {
    setTestErr('')
    try { await testTool(grant.id).unwrap() } catch (e) { setTestErr(errorMessage(e)) }
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="text-xs">{grant.kind === 'mcp_stdio' ? 'local process' : grant.kind === 'mcp_oauth' ? 'OAuth connection' : 'MCP server'}</Badge>
          {grant.status === 'error' ? (
            <Badge variant="destructive" className="gap-1 text-xs"><AlertCircle className="h-3 w-3" /> not answering</Badge>
          ) : grant.status === 'authorizing' ? (
            <Badge variant="secondary" className="gap-1 text-xs"><Loader2 className="h-3 w-3 animate-spin" /> waiting for sign-in</Badge>
          ) : grant.needs_reauth ? (
            <Badge variant="outline" className="gap-1 border-amber-500/40 text-xs text-amber-600"><AlertCircle className="h-3 w-3" /> sign in again</Badge>
          ) : (
            <Badge variant="outline" className="gap-1 text-xs"><Check className="h-3 w-3 text-green-500" /> connected</Badge>
          )}
          {grant.auth === 'oauth' && (
            <Badge variant="secondary" className="text-xs">signed in</Badge>
          )}
          {grant.credential_state === 'encrypted' && (
            <Badge variant="outline" className="gap-1 text-xs"><Lock className="h-3 w-3" /> credential encrypted</Badge>
          )}
          <span className="ml-auto text-xs text-muted-foreground">
            used {grant.uses}× · last {when(grant.last_used_at)}
          </span>
        </div>
        <CardTitle className="text-base">{grant.name}</CardTitle>
        {grant.url && <CardDescription className="font-mono text-xs">{grant.url}</CardDescription>}
        {grant.command && (
          <CardDescription className="font-mono text-xs">{grant.command} {grant.args.join(' ')}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {/* The decision this page exists for. Reads are free; writes are a
            choice the owner makes with the consequence spelled out. */}
        <div className={`flex items-start gap-3 rounded-lg border p-3 ${grant.allow_write ? 'border-amber-500/40 bg-amber-500/[0.06]' : 'bg-muted/20'}`}>
          {grant.allow_write ? <Unlock className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" /> : <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">
              {grant.allow_write ? 'Write actions allowed' : 'Read-only'}
            </p>
            <p className="text-xs text-muted-foreground">
              {grant.allow_write
                ? `The agent may use the ${grant.write_count} tool(s) that change state in ${grant.name} — but only when a person asks it to, never on its own.`
                : `The ${grant.write_count} tool(s) that change state are visible to the agent but refused if it tries. It will tell the person to ask you.`}
            </p>
          </div>
          {canManage && (
            <Button
              size="sm" variant={grant.allow_write ? 'outline' : 'default'} className="shrink-0 text-xs"
              disabled={saving || grant.write_count === 0}
              onClick={() => updateTool({ id: grant.id, allow_write: !grant.allow_write })}
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : grant.allow_write ? 'Make read-only' : 'Allow writes'}
            </Button>
          )}
        </div>

        <ToolList grant={grant} canManage={canManage} />

        {grant.error_message && <p className="text-xs text-destructive">{grant.error_message}</p>}
        {testErr && <p className="text-xs text-destructive">{testErr}</p>}

        {canManage && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button size="sm" variant="outline" className="h-7 gap-1 text-xs" disabled={testing} onClick={handleTest}>
              <RefreshCw className={`h-3 w-3 ${testing ? 'animate-spin' : ''}`} /> Reconnect & refresh tools
            </Button>
            <Button
              size="sm" variant={confirm ? 'destructive' : 'ghost'} className="h-7 gap-1 text-xs"
              disabled={revoking} onBlur={() => setConfirm(false)}
              onClick={() => (confirm ? revokeTool(grant.id) : setConfirm(true))}
            >
              {revoking ? <Loader2 className="h-3 w-3 animate-spin" /> : confirm ? 'Confirm revoke' : <><Trash2 className="h-3 w-3" /> Revoke</>}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Sign-in connections. The owner clicks a service, logs in on the vendor's
 * page, and Sensei receives a token it can refresh. Nothing is pasted.
 */
export function OAuthConnect({ onStarted, allowWrite = false }: { onStarted?: (name: string) => void; allowWrite?: boolean }) {
  const { data } = useGetOAuthPresetsQuery()
  const [startOAuth] = useStartOAuthMutation()
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState('')
  const [custom, setCustom] = useState('')

  async function connect(name: string, url: string) {
    setErr(''); setBusy(name)
    // Open the window first, in the click, so popup blockers allow it.
    const win = window.open('', 'sensei-oauth', 'width=640,height=780')
    try {
      const res = await startOAuth({ name, url, allow_write: allowWrite }).unwrap()
      if (win) win.location.href = res.auth_url
      else window.open(res.auth_url, 'sensei-oauth', 'width=640,height=780')
      onStarted?.(name)
    } catch (e) {
      win?.close()
      setErr(errorMessage(e))
    } finally { setBusy(null) }
  }

  const presets = data?.presets ?? []
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-2 sm:grid-cols-2">
        {presets.map((p) => (
          <button
            key={p.id} type="button" disabled={!!busy} onClick={() => connect(p.name, p.url)}
            className="group flex items-start gap-3 rounded-lg border bg-background px-3 py-2.5 text-left transition-colors hover:border-primary/60 hover:bg-muted/40 disabled:opacity-60"
          >
            <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-sm font-semibold">
              {p.name.slice(0, 1)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2 text-sm font-medium">
                {busy === p.name ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plug className="h-3.5 w-3.5 text-muted-foreground group-hover:text-primary" />}
                Sign in with {p.name}
              </span>
              <span className="block text-xs text-muted-foreground line-clamp-2">{p.blurb}</span>
            </span>
          </button>
        ))}
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => { e.preventDefault(); if (custom.trim()) connect(new URL(custom.trim()).hostname.replace(/^mcp\./, ''), custom.trim()) }}
      >
        <Input placeholder="Any other MCP server with sign-in: https://mcp.example.com/mcp" value={custom} onChange={(e) => setCustom(e.target.value)} disabled={!!busy} />
        <Button type="submit" size="sm" variant="outline" disabled={!!busy || !custom.trim()}>Sign in</Button>
      </form>
      {err && <p className="text-xs text-destructive">{err}</p>}
      <p className="text-xs text-muted-foreground">
        A window opens on the service's own login page. Sensei never sees your password; it receives a token scoped to what you approve, encrypted at rest and refreshed on its own.
      </p>
    </div>
  )
}

/** Refetch tools when a sign-in window reports back, and while any grant is still authorizing. */
export function useOAuthCompletion(refetch: () => void, authorizing: boolean) {
  useEffect(() => {
    const onMsg = (ev: MessageEvent) => { if (ev.data?.type === 'sensei-oauth') refetch() }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [refetch])
  useEffect(() => {
    if (!authorizing) return
    const t = setInterval(refetch, 3000)
    return () => clearInterval(t)
  }, [authorizing, refetch])
}

export function ConnectPanel({ onClose, embedded = false }: { onClose: () => void; embedded?: boolean }) {
  const [connectTool] = useConnectToolMutation()
  const [preset, setPreset] = useState(PRESETS[0])
  const [name, setName] = useState(PRESETS[0].name)
  const [kind, setKind] = useState<GrantKind>('mcp_http')
  const [url, setUrl] = useState(PRESETS[0].url)
  const [auth, setAuth] = useState('')
  const [command, setCommand] = useState('')
  const [args, setArgs] = useState('')
  const [allowWrite, setAllowWrite] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  function pick(p: typeof PRESETS[number]) {
    setPreset(p); setName(p.name); setKind(p.kind); setUrl(p.url); setErr('')
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      await connectTool({
        name, kind,
        url: kind === 'mcp_stdio' ? undefined : url,
        authorization: auth || undefined,
        command: kind === 'mcp_stdio' ? command : undefined,
        args: kind === 'mcp_stdio' ? args.split(/\s+/).filter(Boolean) : undefined,
        allow_write: allowWrite,
      }).unwrap()
      onClose()
    } catch (e) {
      setErr(errorMessage(e))
    } finally { setBusy(false) }
  }

  return (
    <div className={embedded ? "flex flex-col gap-4" : "flex flex-col gap-4 rounded-xl border bg-card p-5 shadow-lg"}>
      {!embedded && (
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Give the agent a tool</h3>
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>
      )}

      <div>
        <p className="mb-2 text-xs font-medium text-muted-foreground">Sign in — nothing to paste</p>
        <OAuthConnect onStarted={() => { if (!embedded) onClose() }} allowWrite={allowWrite} />
      </div>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" /> or connect with a token <span className="h-px flex-1 bg-border" />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button key={p.id} type="button" onClick={() => pick(p)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              preset.id === p.id ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'
            }`}>
            {p.name}
          </button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{preset.note}</p>

      <form onSubmit={submit} className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs">Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} required disabled={busy} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs">Transport</Label>
            <select
              className="border-input bg-background h-9 rounded-md border px-3 text-sm"
              value={kind} onChange={(e) => setKind(e.target.value as GrantKind)} disabled={busy}
            >
              <option value="mcp_http">Streamable HTTP</option>
              <option value="mcp_sse">SSE</option>
              <option value="mcp_stdio">Local process (stdio)</option>
            </select>
          </div>
          {kind === 'mcp_stdio' ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs">Command</Label>
                <Input placeholder="npx" value={command} onChange={(e) => setCommand(e.target.value)} required disabled={busy} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label className="text-xs">Arguments</Label>
                <Input placeholder="-y @modelcontextprotocol/server-filesystem /data" value={args} onChange={(e) => setArgs(e.target.value)} disabled={busy} />
              </div>
            </>
          ) : (
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label className="text-xs">Server URL</Label>
              <Input placeholder="https://…/mcp" value={url} onChange={(e) => setUrl(e.target.value)} required disabled={busy} />
            </div>
          )}
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label className="text-xs">Authorization header <span className="font-normal text-muted-foreground">(optional)</span></Label>
            <Input type="password" placeholder={preset.authHint} value={auth} onChange={(e) => setAuth(e.target.value)} disabled={busy} />
            <p className="text-xs text-muted-foreground">Stored encrypted. Never shown again, never sent anywhere but this server.</p>
          </div>
        </div>

        <label className="flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-xs">
          <input type="checkbox" className="mt-0.5" checked={allowWrite} onChange={(e) => setAllowWrite(e.target.checked)} disabled={busy} />
          <span>
            <span className="font-medium text-foreground">Allow write actions</span>
            <span className="block text-muted-foreground">
              Off by default. Every tool is classified read or write when it connects; with this off, the agent
              can see write tools but is refused if it tries one. You can change this later.
            </span>
          </span>
        </label>

        <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed">
          <p className="flex items-center gap-1.5 font-medium"><ShieldCheck className="h-3.5 w-3.5" /> What this grants</p>
          <ul className="mt-1.5 flex flex-col gap-1 text-muted-foreground">
            <li><span className="text-foreground">Sensei uses:</span> the tools this server lists, with writes gated as above.</li>
            <li><span className="text-foreground">The credential could reach:</span> whatever the token's account can. Use a token scoped to this project where the service allows it.</li>
            <li><span className="text-foreground">Connecting now:</span> we connect once to list the tools, so a wrong URL or token fails here, not in someone's chat.</li>
          </ul>
        </div>

        {err && <p className="text-xs text-destructive">{err}</p>}
        <Button type="submit" size="sm" disabled={busy || !name || (kind === 'mcp_stdio' ? !command : !url)}>
          {busy ? <><Loader2 className="mr-1 h-4 w-4 animate-spin" /> Connecting and listing tools…</> : <><Plug className="mr-1 h-4 w-4" /> Connect</>}
        </Button>
      </form>
    </div>
  )
}

/**
 * Tools.
 *
 * Sources are what the agent reads. Tools are what it can do. A colleague is
 * onboarded with accounts, not a folder of PDFs — this is where those accounts
 * are handed over, and where every one of them is listed with a read/write
 * class next to it.
 */
export default function Tools() {
  const { data, isLoading, refetch } = useGetToolsQuery()
  const [showAdd, setShowAdd] = useState(false)
  const grants = data?.grants ?? []
  useOAuthCompletion(refetch, grants.some((g) => g.status === 'authorizing'))
  const canManage = data?.can_manage ?? false
  const totalTools = grants.reduce((n, g) => n + g.tools.length, 0)

  return (
    <AppShell title="Tools">
      <div className="flex max-w-3xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">What the agent can do</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {grants.length} connection{grants.length !== 1 ? 's' : ''} · {totalTools} tool{totalTools !== 1 ? 's' : ''}
              {' '}beyond reading the sources.
            </p>
          </div>
          {canManage ? (
            <Button size="sm" className="gap-1.5" onClick={() => setShowAdd((s) => !s)}>
              <Plus className="h-4 w-4" /> Connect a tool
            </Button>
          ) : (
            <Badge variant="secondary" className="text-xs">Read-only</Badge>
          )}
        </div>

        {canManage && showAdd && <ConnectPanel onClose={() => setShowAdd(false)} />}

        <Card className="border-dashed">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Wrench className="h-4 w-4 text-muted-foreground" /> Built in, no credential needed
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
            {[
              ['Search the sources', 'Everything the owner connected, cited'],
              ['Who did what', 'Commits, PRs, tickets by person'],
              ['Jira, live', 'Ticket status right now — needs an Atlassian source'],
              ['Spreadsheets & documents', 'Hands back .xlsx and .docx files'],
            ].map(([t, d]) => (
              <div key={t} className="rounded-md border px-3 py-2">
                <p className="text-sm font-medium">{t}</p>
                <p className="text-xs text-muted-foreground">{d}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        {isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</p>
        ) : grants.length === 0 ? (
          <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
            <PenLine className="mx-auto mb-2 h-6 w-6 opacity-40" />
            {canManage
              ? 'No tools connected. The agent can read and cite, but cannot act in any system yet.'
              : 'No tools connected. Your project owner decides what the agent may use.'}
            <p className="mt-2 text-xs">
              Everything connected here shows on the <Link to="/trust" className="underline underline-offset-2">Trust</Link> page too.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {grants.map((g) => <GrantCard key={g.id} grant={g} canManage={canManage} />)}
          </div>
        )}
      </div>
    </AppShell>
  )
}
