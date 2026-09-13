import { useRef, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/services/authApi'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAddSourceMutation, useUploadFileMutation, useTriggerIngestMutation, type Source } from '@/services/onboardingApi'
import { CheckCircle, Clock, Loader2, AlertCircle, ShieldCheck } from 'lucide-react'
import FieldHelp from '@/components/FieldHelp'

type Tab = 'github' | 'file' | 'url' | 'confluence' | 'jira' | 'slack'

interface Props {
  workspaceId: string
  onDone: (sourceIds: string[]) => void
}

const STATUS_ICON = {
  pending: <Clock className="h-3 w-3" />,
  indexing: <Loader2 className="h-3 w-3 animate-spin" />,
  ready: <CheckCircle className="h-3 w-3 text-green-500" />,
  error: <AlertCircle className="h-3 w-3 text-destructive" />,
}

export default function StepSources({ onDone }: Props) {
  const [tab, setTab] = useState<Tab>('github')
  const [addedSources, setAddedSources] = useState<Source[]>([])

  const [addSource] = useAddSourceMutation()
  const [uploadFile] = useUploadFileMutation()
  const [triggerIngest] = useTriggerIngestMutation()

  async function afterAdd(source: Source) {
    setAddedSources((prev) => [...prev, source])
    try { await triggerIngest(source.id).unwrap() } catch { /* status shown in review step */ }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'github', label: 'GitHub' },
    { id: 'file', label: 'File Upload' },
    { id: 'url', label: 'URL' },
    { id: 'confluence', label: 'Confluence' },
    { id: 'jira', label: 'Jira' },
    { id: 'slack', label: 'Slack' },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connect sources</CardTitle>
        <CardDescription>Add the sources Sensei should learn from. You can add multiple.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {/* Tab bar */}
        <div className="flex gap-1 border-b">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === t.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'github' && <GithubTab onAdd={afterAdd} addSource={addSource} />}
        {tab === 'file' && <FileTab onAdd={afterAdd} uploadFile={uploadFile} />}
        {tab === 'url' && <UrlTab onAdd={afterAdd} addSource={addSource} />}
        {tab === 'confluence' && <ConfluenceTab onAdd={afterAdd} addSource={addSource} />}
        {tab === 'jira' && <JiraTab onAdd={afterAdd} addSource={addSource} />}
        {tab === 'slack' && <SlackTab onAdd={afterAdd} addSource={addSource} />}

        {/* Added sources list */}
        {addedSources.length > 0 && (
          <div className="flex flex-col gap-2 pt-2 border-t">
            <p className="text-xs font-medium text-muted-foreground">Added sources</p>
            <div className="flex flex-wrap gap-2">
              {addedSources.map((s) => (
                <Badge key={s.id} variant="secondary" className="gap-1">
                  {STATUS_ICON[s.status]} {s.label}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
      <CardFooter className="flex justify-between">
        <p className="text-sm text-muted-foreground">{addedSources.length} source(s) added</p>
        <Button onClick={() => onDone(addedSources.map((s) => s.id))} disabled={addedSources.length === 0}>
          Done adding sources →
        </Button>
      </CardFooter>
    </Card>
  )
}

// ── Sub-forms ────────────────────────────────────────────────────────────────

interface GithubRepo {
  full_name: string
  description: string | null
  private: boolean
  updated_at: string
}

function GithubTab({ onAdd, addSource }: any) {
  const [pat, setPat] = useState('')
  const [repos, setRepos] = useState<GithubRepo[]>([])
  const [repo, setRepo] = useState('')
  const [search, setSearch] = useState('')
  const [fetching, setFetching] = useState(false)
  const [fetchErr, setFetchErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const filtered = repos.filter((r) =>
    r.full_name.toLowerCase().includes(search.toLowerCase()) ||
    (r.description || '').toLowerCase().includes(search.toLowerCase())
  )

  async function fetchRepos() {
    if (!pat) return
    setFetching(true)
    setFetchErr('')
    setRepos([])
    setRepo('')
    setSearch('')
    try {
      const r = await fetch(
        'https://api.github.com/user/repos?type=all&sort=updated&per_page=100',
        { headers: { Authorization: `Bearer ${pat}`, Accept: 'application/vnd.github+json' } }
      )
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.message || `GitHub returned ${r.status}`)
      }
      const data: GithubRepo[] = await r.json()
      setRepos(data)
    } catch (e: any) {
      setFetchErr(e.message || 'Failed to fetch repositories')
    } finally {
      setFetching(false)
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const res = await addSource({ type: 'github', pat, repo, label: repo }).unwrap()
      onAdd(res.source)
      setPat('')
      setRepo('')
      setRepos([])
      setSearch('')
    } catch (e: any) {
      setErr(errorMessage(e) || 'Failed to add source')
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      {/* PAT field + fetch button */}
      <div className="flex flex-col gap-1.5">
        <Label className="flex items-center gap-1">
          Personal Access Token
          <FieldHelp text={'Create at github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)\nNeeds scopes: repo, user, project'} />
        </Label>
        <div className="flex gap-2">
          <Input
            type="password"
            placeholder="ghp_..."
            value={pat}
            onChange={(e) => { setPat(e.target.value); setRepos([]); setRepo(''); setFetchErr('') }}
            required
            disabled={busy}
            className="flex-1 min-w-0"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            disabled={!pat || fetching || busy}
            onClick={fetchRepos}
          >
            {fetching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Fetch repos'}
          </Button>
        </div>
        {fetchErr && <p className="text-sm text-destructive">{fetchErr}</p>}
      </div>

      {/* Progress indicator while fetching */}
      {fetching && (
        <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin shrink-0" />
          Fetching your repositories from GitHub…
        </div>
      )}

      {/* Repo selector — shown after fetch */}
      {repos.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <Label>
            Repository{' '}
            <span className="text-muted-foreground text-xs font-normal">({repos.length} found)</span>
          </Label>
          <Input
            placeholder="Search repos…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            disabled={busy}
            className="mb-1"
          />
          <div className="max-h-48 overflow-y-auto rounded-md border divide-y">
            {filtered.length === 0 && (
              <p className="px-3 py-2 text-sm text-muted-foreground">No repos match</p>
            )}
            {filtered.map((r) => (
              <button
                key={r.full_name}
                type="button"
                disabled={busy}
                onClick={() => setRepo(r.full_name)}
                className={`w-full text-left px-3 py-2 text-sm transition-colors hover:bg-muted ${
                  repo === r.full_name ? 'bg-primary/10 font-medium text-primary' : ''
                }`}
              >
                <span className="font-mono text-xs">{r.full_name}</span>
                {r.private && (
                  <span className="ml-1.5 text-xs text-muted-foreground">(private)</span>
                )}
                {r.description && (
                  <p className="text-xs text-muted-foreground truncate">{r.description}</p>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Manual fallback when no repos fetched yet */}
      {repos.length === 0 && !fetching && (
        <div className="flex flex-col gap-1.5">
          <Label className="flex items-center gap-1">
            Repository <span className="text-muted-foreground text-xs font-normal">or enter manually</span>
            <FieldHelp text="Which repository to index, as owner/repo (e.g. your-org/your-app). Pick from the list above or type it in." />
          </Label>
          <Input
            placeholder="owner/repo"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            required
            disabled={busy}
          />
        </div>
      )}

      {err && <p className="text-sm text-destructive">{err}</p>}
      <Button type="submit" disabled={busy || !pat || !repo} size="sm">
        {busy ? 'Adding…' : `Add ${repo || 'GitHub repo'}`}
      </Button>
    </form>
  )
}

function FileTab({ onAdd, uploadFile }: any) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setErr('')
    setBusy(true)
    for (const file of Array.from(files)) {
      const fd = new FormData()
      fd.append('file', file)
      try {
        const res = await uploadFile(fd).unwrap()
        onAdd(res.source)
      } catch (e: any) {
        setErr(errorMessage(e) || `Failed to upload ${file.name}`)
      }
    }
    setBusy(false)
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary transition-colors"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files) }}
      >
        <p className="text-sm text-muted-foreground">
          {busy ? 'Uploading…' : 'Drop files here or click to browse'}
        </p>
        <p className="text-xs text-muted-foreground mt-1">PDF, MD, TXT, DOCX — max 20 MB each</p>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.md,.txt,.docx"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {err && <p className="text-sm text-destructive">{err}</p>}
    </div>
  )
}

function UrlTab({ onAdd, addSource }: any) {
  const [raw, setRaw] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    const urls = raw.split('\n').map((u) => u.trim()).filter(Boolean)
    const invalid = urls.filter((u) => { try { new URL(u); return false } catch { return true } })
    if (invalid.length) { setErr(`Invalid URLs: ${invalid.join(', ')}`); return }
    setBusy(true)
    try {
      const res = await addSource({ type: 'url', urls, label: `${urls.length} URL(s)` }).unwrap()
      onAdd(res.source)
      setRaw('')
    } catch (e: any) {
      setErr(errorMessage(e) || 'Failed to add URLs')
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <Label className="flex items-center gap-1">
          URLs <span className="text-muted-foreground text-xs">(one per line)</span>
          <FieldHelp text="Paste the exact public pages to index — one URL per line. Each must be reachable without a login (it is checked before saving)." />
        </Label>
        <textarea
          className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[100px] w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-50"
          placeholder="https://docs.example.com&#10;https://example.com/readme"
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          disabled={busy}
        />
      </div>
      {err && <p className="text-sm text-destructive">{err}</p>}
      <Button type="submit" disabled={busy || !raw.trim()} size="sm">
        {busy ? 'Adding…' : 'Add URLs'}
      </Button>
    </form>
  )
}

function ConfluenceTab({ onAdd, addSource }: any) {
  const [form, setForm] = useState({ base_url: '', email: '', api_token: '', space_key: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const res = await addSource({ type: 'confluence', ...form, label: `Confluence:${form.space_key}` }).unwrap()
      onAdd(res.source)
      setForm({ base_url: '', email: '', api_token: '', space_key: '' })
    } catch (e: any) {
      setErr(errorMessage(e) || 'Failed to add Confluence source')
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5 col-span-2">
          <Label>Base URL</Label>
          <Input placeholder="https://your-org.atlassian.net/wiki" value={form.base_url} onChange={set('base_url')} required disabled={busy} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Email</Label>
          <Input type="email" placeholder="you@example.com" value={form.email} onChange={set('email')} required disabled={busy} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Space Key</Label>
          <Input placeholder="PROJ" value={form.space_key} onChange={set('space_key')} required disabled={busy} />
        </div>
        <div className="flex flex-col gap-1.5 col-span-2">
          <Label>API Token</Label>
          <Input type="password" placeholder="Your Confluence API token" value={form.api_token} onChange={set('api_token')} required disabled={busy} />
          <p className="text-xs text-muted-foreground">
            Create one at{' '}
            <a href="https://id.atlassian.com/manage-profile/security/api-tokens"
               target="_blank" rel="noreferrer"
               className="underline underline-offset-2 hover:text-foreground">
              id.atlassian.com → Security → API tokens
            </a>. Atlassian expires tokens after a year.
          </p>
        </div>
      </div>

      {/* Same disclosure as the Sources page — an owner should be told what a
          token actually authorises before they paste one in, not afterwards. */}
      <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed">
        <p className="flex items-center gap-1.5 font-medium text-foreground">
          <ShieldCheck className="h-3.5 w-3.5" /> What this grants
        </p>
        <ul className="mt-2 flex flex-col gap-1 text-muted-foreground">
          <li>
            <span className="text-foreground">Sensei reads:</span> pages in the{' '}
            <span className="font-mono">{form.space_key.trim().toUpperCase() || 'SPACE'}</span>{' '}
            space only.
          </li>
          <li>
            <span className="text-foreground">The token could reach:</span> anything
            that account can see — a token authorises as its owner, and Atlassian
            cannot narrow it to one space.
          </li>
          <li>
            <span className="text-foreground">So:</span> use an account invited only
            to the spaces this project needs.
          </li>
        </ul>
      </div>

      {err && <p className="text-sm text-destructive">{err}</p>}
      <Button type="submit" disabled={busy || !form.base_url || !form.email || !form.api_token || !form.space_key} size="sm">
        {busy ? 'Adding…' : 'Add Confluence space'}
      </Button>
    </form>
  )
}

function JiraTab({ onAdd, addSource }: any) {
  const [form, setForm] = useState({ base_url: '', email: '', api_token: '', project_key: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const res = await addSource({
        type: 'jira',
        ...form,
        project_key: form.project_key.trim().toUpperCase(),
        label: `Jira:${form.project_key.trim().toUpperCase()}`,
      }).unwrap()
      onAdd(res.source)
      setForm({ base_url: '', email: '', api_token: '', project_key: '' })
    } catch (e: any) {
      setErr(errorMessage(e) || 'Failed to add Jira source')
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5 col-span-2">
          <Label className="flex items-center gap-1">
            Base URL
            <FieldHelp text="Your site is the root address you log into — everything after the '?' is redirect noise. Example: https://your-org.atlassian.net" />
          </Label>
          <Input placeholder="https://your-org.atlassian.net" value={form.base_url} onChange={set('base_url')} required disabled={busy} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="flex items-center gap-1">
            Email
            <FieldHelp text="The Atlassian account email that owns the API token. Sensei authenticates with this same identity." />
          </Label>
          <Input type="email" placeholder="you@example.com" value={form.email} onChange={set('email')} required disabled={busy} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label className="flex items-center gap-1">
            Project Key
            <FieldHelp text="The short uppercase code identifying your Jira project (e.g. PD, SCRUM). Found on the board or in its URL after /projects/. Create one if you have none." />
          </Label>
          <Input placeholder="PROJ" value={form.project_key} onChange={set('project_key')} required disabled={busy} />
        </div>
        <div className="flex flex-col gap-1.5 col-span-2">
          <Label className="flex items-center gap-1">
            API Token
            <FieldHelp text={'1. Go to id.atlassian.com → Security → API tokens → Create token\n2. Copy it immediately (shown only once)\n3. Paste and pair with the account email above — the token authorises as that exact account'} />
          </Label>
          <Input type="password" placeholder="Your Atlassian API token" value={form.api_token} onChange={set('api_token')} required disabled={busy} />
          <p className="text-xs text-muted-foreground">
            The same Atlassian token works for both Confluence and Jira. Create one at{' '}
            <a href="https://id.atlassian.com/manage-profile/security/api-tokens"
               target="_blank" rel="noreferrer"
               className="underline underline-offset-2 hover:text-foreground">
              id.atlassian.com → Security → API tokens
            </a>. Atlassian expires tokens after a year.
          </p>
        </div>
      </div>

      <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed">
        <p className="flex items-center gap-1.5 font-medium text-foreground">
          <ShieldCheck className="h-3.5 w-3.5" /> What this grants
        </p>
        <ul className="mt-2 flex flex-col gap-1 text-muted-foreground">
          <li>
            <span className="text-foreground">Sensei reads:</span> issues in the{' '}
            <span className="font-mono">{form.project_key.trim().toUpperCase() || 'PROJ'}</span>{' '}
            project only.
          </li>
          <li>
            <span className="text-foreground">The token could reach:</span> anything
            that account can see — a token authorises as its owner, and Atlassian
            cannot narrow it to one project.
          </li>
          <li>
            <span className="text-foreground">So:</span> use an account invited only
            to the projects this work involves.
          </li>
        </ul>
      </div>

      {err && <p className="text-sm text-destructive">{err}</p>}
      <Button type="submit" disabled={busy || !form.base_url || !form.email || !form.api_token || !form.project_key} size="sm">
        {busy ? 'Adding…' : 'Add Jira project'}
      </Button>
    </form>
  )
}

function SlackTab({ onAdd, addSource }: any) {
  const [form, setForm] = useState({ token: '', channel: '' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    const channel = form.channel.trim().toLowerCase().replace(/^#/, '')
    try {
      const res = await addSource({
        type: 'slack',
        token: form.token,
        channel,
        label: `Slack: #${channel}`,
      }).unwrap()
      onAdd(res.source)
      setForm({ token: '', channel: '' })
    } catch (e: any) {
      setErr(errorMessage(e) || 'Failed to add Slack source')
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5 col-span-2">
          <Label className="flex items-center gap-1">
            Bot token
            <FieldHelp text={
              '1. Open api.slack.com/apps → Create New App → From scratch\n' +
              '2. Under OAuth & Permissions add scope channels:history, channels:read, groups:history, users:read\n' +
              '3. Install to Workspace → copy the xoxb-… OAuth token'
            } />
          </Label>
          <Input type="password" placeholder="xoxb-…" value={form.token} onChange={set('token')} required disabled={busy} />
        </div>
        <div className="flex flex-col gap-1.5 col-span-2">
          <Label className="flex items-center gap-1">
            Channel
            <FieldHelp text="The channel to index, e.g. general. The bot must be added to it — open the channel → Details → Add apps." />
          </Label>
          <Input placeholder="general" value={form.channel} onChange={set('channel')} required disabled={busy} />
        </div>
      </div>

      <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed">
        <p className="flex items-center gap-1.5 font-medium text-foreground">
          <ShieldCheck className="h-3.5 w-3.5" /> What this grants
        </p>
        <ul className="mt-2 flex flex-col gap-1 text-muted-foreground">
          <li>
            <span className="text-foreground">Sensei reads:</span> #{form.channel.trim().replace(/^#/, '') || 'channel'}{' '}
            only.
          </li>
          <li>
            <span className="text-foreground">The token could reach:</span> every channel
            this Slack app has been added to — Slack cannot narrow a bot token to one channel.
          </li>
          <li>
            <span className="text-foreground">So:</span> add the bot to only the channels
            this work involves. The invite is the grant; removing the app is the revocation.
          </li>
        </ul>
      </div>

      {err && <p className="text-sm text-destructive">{err}</p>}
      <Button type="submit" disabled={busy || !form.token || !form.channel.trim()} size="sm">
        {busy ? 'Adding…' : 'Add Slack channel'}
      </Button>
    </form>
  )
}
