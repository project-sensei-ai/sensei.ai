import { useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle,
  CircleDot,
  Clock,
  FolderGit2,
  Globe,
  Loader2,
  MessageSquare,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { errorMessage } from '@/services/authApi'
import { parseConfluenceUrl } from '@/lib/confluence'
import FieldHelp from '@/components/FieldHelp'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import {
  useAddSourceMutation,
  useDeleteSourceMutation,
  useGetSourcesQuery,
  useGetMyWorkspaceQuery,
  useTriggerIngestMutation,
  useUpdateSourceMutation,
  useUploadFileMutation,
  type Source,
  type UpdateSourceInput,
} from '@/services/onboardingApi'

// ── Status config ──────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  pending:  { label: 'Pending',  icon: <Clock className="h-3 w-3" />,                       variant: 'secondary' as const },
  indexing: { label: 'Indexing', icon: <Loader2 className="h-3 w-3 animate-spin" />,         variant: 'secondary' as const },
  ready:    { label: 'Ready',    icon: <CheckCircle className="h-3 w-3 text-green-500" />,   variant: 'outline' as const },
  error:    { label: 'Error',    icon: <AlertCircle className="h-3 w-3 text-destructive" />, variant: 'destructive' as const },
}

const TYPE_ICON: Record<string, React.ReactNode> = {
  github:     <FolderGit2 className="h-4 w-4 text-muted-foreground" />,
  url:        <Globe className="h-4 w-4 text-muted-foreground" />,
  file:       <Upload className="h-4 w-4 text-muted-foreground" />,
  confluence: <Globe className="h-4 w-4 text-muted-foreground" />,
  jira:       <CircleDot className="h-4 w-4 text-muted-foreground" />,
  slack:      <MessageSquare className="h-4 w-4 text-muted-foreground" />,
  meeting:    <Globe className="h-4 w-4 text-muted-foreground" />,
}

// ── Source card ────────────────────────────────────────────────────────────────

function EditSourceDialog({ source, onClose }: { source: Source; onClose: () => void }) {
  const [updateSource, { isLoading }] = useUpdateSourceMutation()
  const [triggerIngest] = useTriggerIngestMutation()
  const [err, setErr] = useState('')
  const cfg = source.config as Record<string, any>

  // Secrets are never returned by the API, so the secret field starts blank
  // and a blank one means "keep what is stored".
  const [form, setForm] = useState(() =>
    source.type === 'jira'
      ? { base_url: cfg.base_url ?? '', email: cfg.email ?? '', project_key: cfg.project_key ?? '', api_token: '' }
      : { channel: cfg.channel_name ?? '', token: '' },
  )

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    const body: UpdateSourceInput =
      source.type === 'jira'
        ? {
            type: 'jira',
            base_url: form.base_url.trim(),
            email: form.email.trim(),
            project_key: form.project_key.trim().toUpperCase(),
            api_token: form.api_token || undefined,
          }
        : {
            type: 'slack',
            channel: form.channel,
            token: form.token || undefined,
          }
    try {
      await updateSource({ id: source.id, body }).unwrap()
      await triggerIngest(source.id).unwrap().catch(() => {})
      onClose()
    } catch (e: any) {
      setErr(errorMessage(e))
    }
  }

  const setField = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...(f as any), [k]: e.target.value }))

  return (
    <Sheet open onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full">
        <SheetHeader>
          <SheetTitle>{source.type === 'jira' ? 'Edit Jira source' : 'Edit Slack source'}</SheetTitle>
          <SheetDescription>
            {source.type === 'jira'
              ? 'Change the site, project, or credentials. The source will be re-indexed after saving.'
              : 'Change the channel or bot token. The source will be re-indexed after saving.'}
          </SheetDescription>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 px-4">
          {source.type === 'jira' ? (
            <>
              <div className="flex flex-col gap-1.5">
                <Label>Jira site</Label>
                <Input placeholder="https://your-org.atlassian.net"
                  value={form.base_url} onChange={setField('base_url')} required disabled={isLoading} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Account email</Label>
                <Input type="email" placeholder="agent@your-org.com"
                  value={form.email} onChange={setField('email')} required disabled={isLoading} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Project key</Label>
                <Input placeholder="PROJ"
                  value={form.project_key} onChange={setField('project_key')} required disabled={isLoading} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>API token <span className="text-xs font-normal text-muted-foreground">(blank = keep stored)</span></Label>
                <Input type="password" placeholder="Paste only if it changed"
                  value={form.api_token} onChange={setField('api_token')} disabled={isLoading} />
              </div>
            </>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label>Channel</Label>
                <Input placeholder="general"
                  value={form.channel} onChange={setField('channel')} required disabled={isLoading} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Bot token <span className="text-xs font-normal text-muted-foreground">(blank = keep stored)</span></Label>
                <Input type="password" placeholder="xoxb-… — only if it changed"
                  value={form.token} onChange={setField('token')} disabled={isLoading} />
              </div>
            </>
          )}

          {err && <p className="text-sm text-destructive">{err}</p>}

          <div className="flex justify-end gap-2 mt-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isLoading}>
              {isLoading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving…</> : 'Save & Re-index'}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  )
}

function SourceCard({ source, canManage }: { source: Source; canManage: boolean }) {
  const [triggerIngest, { isLoading: ingesting }] = useTriggerIngestMutation()
  const [deleteSource, { isLoading: deleting }] = useDeleteSourceMutation()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [editing, setEditing] = useState(false)
  const cfg = STATUS_CONFIG[source.status] ?? STATUS_CONFIG.pending
  const editable = source.type === 'jira' || source.type === 'slack'

  async function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return }
    await deleteSource(source.id)
  }

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border bg-card px-4 py-3">
      <div className="flex items-center gap-3 min-w-0">
        {TYPE_ICON[source.type] ?? TYPE_ICON.url}
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{source.label}</p>
          <p className="text-xs text-muted-foreground capitalize">{source.type}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
        {source.status === 'ready' && source.stats.chunks_count != null && (
          <span className="text-xs text-muted-foreground hidden sm:block">
            {source.stats.chunks_count} chunks · {source.stats.pages_crawled} pages
          </span>
        )}
        {source.status === 'error' && source.error_message && (
          <span className="text-xs text-destructive max-w-[160px] truncate hidden sm:block" title={source.error_message}>
            {source.error_message}
          </span>
        )}

        <Badge variant={cfg.variant} className="gap-1 text-xs">
          {cfg.icon} {cfg.label}
        </Badge>

        {canManage && editable && (
          <Button size="sm" variant="outline" className="h-7 gap-1 text-xs" onClick={() => setEditing(true)}>
            <Pencil className="h-3 w-3" /> Edit
          </Button>
        )}

        {canManage && (
          <Button size="sm" variant="outline" className="h-7 gap-1 text-xs"
            disabled={ingesting} onClick={() => triggerIngest(source.id)}>
            <RefreshCw className={`h-3 w-3 ${ingesting ? 'animate-spin' : ''}`} />
            {source.status === 'ready' ? 'Re-index' : 'Ingest'}
          </Button>
        )}

        {canManage && (
          <Button
            size="sm"
            variant={confirmDelete ? 'destructive' : 'ghost'}
            className="h-7 gap-1 text-xs"
            disabled={deleting}
            onClick={handleDelete}
            onBlur={() => setConfirmDelete(false)}
          >
            {deleting
              ? <Loader2 className="h-3 w-3 animate-spin" />
              : confirmDelete
              ? 'Confirm delete'
              : <Trash2 className="h-3 w-3" />}
          </Button>
        )}
      </div>

      {editing && canManage && editable && (
        <EditSourceDialog source={source} onClose={() => setEditing(false)} />
      )}
    </div>
  )
}

// ── Add-source panel ───────────────────────────────────────────────────────────

type Tab = 'file' | 'url' | 'github' | 'confluence' | 'jira' | 'slack'

/** Personal space keys are case-sensitive and start with ~; only shout the rest. */
function normaliseSpaceKey(v: string): string {
  const k = v.trim()
  return k.startsWith('~') ? k : k.toUpperCase()
}

function labelForSpace(v: string): string {
  const k = normaliseSpaceKey(v)
  return k.startsWith('~') ? 'personal space' : k
}

interface GithubRepo { full_name: string; description: string | null; private: boolean }

export function AddSourcePanel({ onClose, embedded = false }: { onClose: () => void; embedded?: boolean }) {
  const [tab, setTab] = useState<Tab>('file')
  const [addSource] = useAddSourceMutation()
  const [uploadFile] = useUploadFileMutation()
  const [triggerIngest] = useTriggerIngestMutation()
  const fileRef = useRef<HTMLInputElement>(null)

  // File upload
  const [uploading, setUploading] = useState(false)
  const [fileErr, setFileErr] = useState('')

  // URL
  const [urlRaw, setUrlRaw] = useState('')
  const [urlBusy, setUrlBusy] = useState(false)
  const [urlErr, setUrlErr] = useState('')

  // Confluence
  const [conf, setConf] = useState({ base_url: '', email: '', api_token: '', space_key: '' })
  const [confBusy, setConfBusy] = useState(false)
  const [confErr, setConfErr] = useState('')

  // Jira
  const [jira, setJira] = useState({ base_url: '', email: '', api_token: '', project_key: '' })
  const [jiraBusy, setJiraBusy] = useState(false)
  const [jiraErr, setJiraErr] = useState('')

  // Slack
  const [slack, setSlack] = useState({ token: '', channel: '' })
  const [slackBusy, setSlackBusy] = useState(false)
  const [slackErr, setSlackErr] = useState('')

  // GitHub
  const [pat, setPat] = useState('')
  const [repos, setRepos] = useState<GithubRepo[]>([])
  const [repoSearch, setRepoSearch] = useState('')
  const [selectedRepo, setSelectedRepo] = useState('')
  const [fetchingRepos, setFetchingRepos] = useState(false)
  const [fetchRepoErr, setFetchRepoErr] = useState('')
  const [ghBusy, setGhBusy] = useState(false)
  const [ghErr, setGhErr] = useState('')

  const filteredRepos = repos.filter(
    (r) =>
      r.full_name.toLowerCase().includes(repoSearch.toLowerCase()) ||
      (r.description || '').toLowerCase().includes(repoSearch.toLowerCase()),
  )

  async function handleFiles(files: FileList | null) {
    if (!files || !files.length) return
    setFileErr('')
    setUploading(true)
    for (const file of Array.from(files)) {
      const fd = new FormData()
      fd.append('file', file)
      try {
        const res = await uploadFile(fd).unwrap()
        await triggerIngest(res.source.id).unwrap().catch(() => {})
      } catch (e: any) {
        setFileErr(errorMessage(e) || `Failed to upload ${file.name}`)
      }
    }
    setUploading(false)
    if (!fileErr) onClose()
  }

  async function handleUrl(e: React.FormEvent) {
    e.preventDefault()
    const urls = urlRaw.split('\n').map((u) => u.trim()).filter(Boolean)
    if (!urls.length) return
    const bad = urls.filter((u) => { try { new URL(u); return false } catch { return true } })
    if (bad.length) { setUrlErr(`Invalid: ${bad.join(', ')}`); return }
    setUrlErr('')
    setUrlBusy(true)
    try {
      const res = await addSource({ type: 'url', urls, label: `${urls.length} URL(s)` }).unwrap()
      await triggerIngest(res.source.id).unwrap().catch(() => {})
      onClose()
    } catch (e: any) {
      setUrlErr(errorMessage(e))
    } finally { setUrlBusy(false) }
  }

  async function fetchRepos() {
    setFetchingRepos(true)
    setFetchRepoErr('')
    setRepos([])
    setSelectedRepo('')
    try {
      const r = await fetch('https://api.github.com/user/repos?type=all&sort=updated&per_page=100', {
        headers: { Authorization: `Bearer ${pat}`, Accept: 'application/vnd.github+json' },
      })
      if (!r.ok) { const b = await r.json().catch(() => ({})); throw new Error(b.message || `GitHub ${r.status}`) }
      setRepos(await r.json())
    } catch (e: any) {
      setFetchRepoErr(e.message || 'Failed to fetch repos')
    } finally { setFetchingRepos(false) }
  }

  async function handleGithub(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedRepo) return
    setGhErr('')
    setGhBusy(true)
    try {
      const res = await addSource({ type: 'github', pat, repo: selectedRepo, label: selectedRepo }).unwrap()
      await triggerIngest(res.source.id).unwrap().catch(() => {})
      onClose()
    } catch (e: any) {
      setGhErr(errorMessage(e))
    } finally { setGhBusy(false) }
  }

  async function handleConfluence(e: React.FormEvent) {
    e.preventDefault()
    setConfErr('')
    setConfBusy(true)
    try {
      const res = await addSource({
        type: 'confluence',
        ...conf,
        base_url: conf.base_url.trim().replace(/\/+$/, ''),
        space_key: normaliseSpaceKey(conf.space_key),
        label: `Confluence: ${labelForSpace(conf.space_key)}`,
      }).unwrap()
      await triggerIngest(res.source.id).unwrap().catch(() => {})
      onClose()
    } catch (e: any) {
      setConfErr(errorMessage(e))
    } finally { setConfBusy(false) }
  }

  const setConfField = (k: keyof typeof conf) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    if (k === 'base_url') {
      // Pasting a page URL fills the space key too, rather than making them
      // pick the site and the key out of the same string themselves.
      const { site, spaceKey } = parseConfluenceUrl(value)
      setConf((c) => ({ ...c, base_url: site, space_key: spaceKey ?? c.space_key }))
      return
    }
    setConf((c) => ({ ...c, [k]: value }))
  }

  async function handleJira(e: React.FormEvent) {
    e.preventDefault()
    setJiraErr('')
    setJiraBusy(true)
    try {
      const res = await addSource({
        type: 'jira',
        ...jira,
        base_url: jira.base_url.trim().replace(/\/+$/, ''),
        project_key: jira.project_key.trim().toUpperCase(),
        label: `Jira: ${jira.project_key.trim().toUpperCase()}`,
      }).unwrap()
      await triggerIngest(res.source.id).unwrap().catch(() => {})
      onClose()
    } catch (e: any) {
      setJiraErr(errorMessage(e))
    } finally { setJiraBusy(false) }
  }

  const setJiraField = (k: keyof typeof jira) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    if (k === 'base_url') {
      // Pasting a ticket URL drops everything after /browse/ — the site is all we need.
      const site = value.trim().replace(/\/browse\/.*$/, '').replace(/\/+$/, '')
      setJira((c) => ({ ...c, base_url: site }))
      return
    }
    setJira((c) => ({ ...c, [k]: value }))
  }

  async function handleSlack(e: React.FormEvent) {
    e.preventDefault()
    setSlackErr('')
    setSlackBusy(true)
    try {
      const channel = slack.channel.trim().toLowerCase().replace(/^#/, '')
      const res = await addSource({
        type: 'slack',
        token: slack.token,
        channel,
        label: `Slack: #${channel}`,
      }).unwrap()
      await triggerIngest(res.source.id).unwrap().catch(() => {})
      onClose()
    } catch (e: any) {
      setSlackErr(errorMessage(e))
    } finally { setSlackBusy(false) }
  }

  const setSlackField = (k: keyof typeof slack) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setSlack((c) => ({ ...c, [k]: e.target.value }))
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: 'file', label: 'File Upload' },
    { id: 'url', label: 'URL' },
    { id: 'github', label: 'GitHub' },
    { id: 'confluence', label: 'Confluence' },
    { id: 'jira', label: 'Jira' },
    { id: 'slack', label: 'Slack' },
  ]

  return (
    <div className={embedded ? "flex flex-col gap-4" : "rounded-xl border bg-card shadow-lg p-5 flex flex-col gap-4"}>
      {!embedded && (
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-sm">Add a new source</h3>
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {TABS.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.id ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── File tab ── */}
      {tab === 'file' && (
        <div className="flex flex-col gap-3">
          <div
            className="border-2 border-dashed rounded-xl p-8 text-center cursor-pointer hover:border-primary transition-colors"
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files) }}
          >
            {uploading ? (
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin" />
                <p className="text-sm">Uploading and indexing…</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <Upload className="h-8 w-8" />
                <p className="text-sm font-medium">Drop files here or click to browse</p>
                <p className="text-xs">PDF, MD, TXT, DOCX — max 20 MB each</p>
              </div>
            )}
          </div>
          <input ref={fileRef} type="file" multiple accept=".pdf,.md,.txt,.docx"
            className="hidden" onChange={(e) => handleFiles(e.target.files)} />
          {fileErr && <p className="text-sm text-destructive">{fileErr}</p>}
        </div>
      )}

      {/* ── URL tab ── */}
      {tab === 'url' && (
        <form onSubmit={handleUrl} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label className="flex items-center gap-1">
              URLs <span className="text-muted-foreground text-xs">(one per line)</span>
              <FieldHelp text="Paste the exact public pages to index — one URL per line. Each must be reachable without a login (it is checked before saving)." />
            </Label>
            <textarea
              className="border-input bg-background placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[100px] w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-50"
              placeholder="https://docs.example.com"
              value={urlRaw}
              onChange={(e) => setUrlRaw(e.target.value)}
              disabled={urlBusy}
            />
          </div>
          {urlErr && <p className="text-sm text-destructive">{urlErr}</p>}
          <Button type="submit" size="sm" disabled={urlBusy || !urlRaw.trim()}>
            {urlBusy ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Adding…</> : 'Add & Index'}
          </Button>
        </form>
      )}

      {/* ── GitHub tab ── */}
      {tab === 'github' && (
        <form onSubmit={handleGithub} className="flex flex-col gap-3">
          {/* PAT + Fetch */}
          <div className="flex flex-col gap-1.5">
            <Label className="flex items-center gap-1">
              Personal Access Token
              <FieldHelp text={'Create at github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)\nNeeds scopes: repo, user, project'} />
            </Label>
            <div className="flex gap-2">
              <Input
                type="password" placeholder="ghp_..." value={pat}
                onChange={(e) => { setPat(e.target.value); setRepos([]); setSelectedRepo('') }}
                required disabled={ghBusy} className="flex-1 min-w-0"
              />
              <Button type="button" variant="outline" size="sm" className="shrink-0"
                disabled={!pat || fetchingRepos || ghBusy} onClick={fetchRepos}>
                {fetchingRepos ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Fetch repos'}
              </Button>
            </div>
            {fetchRepoErr && <p className="text-sm text-destructive">{fetchRepoErr}</p>}
          </div>

          {fetchingRepos && (
            <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              Fetching your repositories…
            </div>
          )}

          {repos.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label className="flex items-center gap-1">Repository <span className="text-muted-foreground text-xs font-normal">({repos.length} found)</span></Label>
              <Input placeholder="Search…" value={repoSearch}
                onChange={(e) => setRepoSearch(e.target.value)} className="mb-1" />
              <div className="max-h-44 overflow-y-auto rounded-md border divide-y">
                {filteredRepos.length === 0
                  ? <p className="px-3 py-2 text-sm text-muted-foreground">No match</p>
                  : filteredRepos.map((r) => (
                    <button key={r.full_name} type="button" disabled={ghBusy}
                      onClick={() => setSelectedRepo(r.full_name)}
                      className={`w-full text-left px-3 py-2 text-sm transition-colors hover:bg-muted ${
                        selectedRepo === r.full_name ? 'bg-primary/10 font-medium text-primary' : ''
                      }`}>
                      <span className="font-mono text-xs">{r.full_name}</span>
                      {r.private && <span className="ml-1.5 text-xs text-muted-foreground">(private)</span>}
                      {r.description && <p className="text-xs text-muted-foreground truncate">{r.description}</p>}
                    </button>
                  ))}
              </div>
            </div>
          )}

          {repos.length === 0 && !fetchingRepos && (
            <div className="flex flex-col gap-1.5">
              <Label className="flex items-center gap-1">Repository <span className="text-muted-foreground text-xs font-normal">or enter manually</span>
                <FieldHelp text="Which repository to index, as owner/repo (e.g. your-org/your-app). Pick from the list above or type it in." />
              </Label>
              <Input placeholder="owner/repo" value={selectedRepo}
                onChange={(e) => setSelectedRepo(e.target.value)} required disabled={ghBusy} />
            </div>
          )}

          {ghErr && <p className="text-sm text-destructive">{ghErr}</p>}
          <Button type="submit" size="sm" disabled={ghBusy || !pat || !selectedRepo}>
            {ghBusy ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Adding…</> : `Add ${selectedRepo || 'repo'}`}
          </Button>
        </form>
      )}

      {/* ── Confluence tab ──
          The copy matters as much as the fields. An API token authorises as the
          person who made it, so the agent inherits that account's whole view of
          the site. Naming a space narrows what Sensei *reads*, not what the
          token *could* read — and saying so plainly is the point. */}
      {tab === 'confluence' && (
        <form onSubmit={handleConfluence} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-medium flex items-center gap-1">
                Confluence site
                <FieldHelp text="Your wiki address, ending in /wiki — e.g. https://your-org.atlassian.net/wiki. Pasting any page URL fills the site and space key for you." />
              </label>
              <Input placeholder="https://your-org.atlassian.net/wiki"
                value={conf.base_url} onChange={setConfField('base_url')} required disabled={confBusy} />
              <p className="text-xs text-muted-foreground">
                Paste any Confluence page URL — the site and space key are pulled out of it.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium flex items-center gap-1">
                Account email
                <FieldHelp text="The Atlassian account email that owns the API token. Sensei authenticates with this same identity." />
              </label>
              <Input type="email" placeholder="agent@your-org.com"
                value={conf.email} onChange={setConfField('email')} required disabled={confBusy} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium flex items-center gap-1">
                Space key
                <FieldHelp text="The 2-4 letter code identifying the space to index (e.g. ENG). Pasting a page URL fills it automatically." />
              </label>
              <Input placeholder="ENG" value={conf.space_key}
                onChange={setConfField('space_key')} required disabled={confBusy} />
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-medium flex items-center gap-1">
                API token
                <FieldHelp text={
                  '1. Go to id.atlassian.com → Security → API tokens → Create token\n' +
                  '2. Copy it immediately (shown only once)\n' +
                  '3. Paste and pair with the account email above — the token authorises as that exact account'
                } />
              </label>
              <Input type="password" placeholder="Paste the token"
                value={conf.api_token} onChange={setConfField('api_token')} required disabled={confBusy} />
              <p className="text-xs text-muted-foreground">
                Create one at{' '}
                <a href="https://id.atlassian.com/manage-profile/security/api-tokens"
                   target="_blank" rel="noreferrer"
                   className="underline underline-offset-2 hover:text-foreground">
                  id.atlassian.com → Security → API tokens
                </a>. Atlassian expires tokens after a year, so this needs rotating.
              </p>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed">
            <p className="flex items-center gap-1.5 font-medium text-foreground">
              <ShieldCheck className="h-3.5 w-3.5" /> What this grants
            </p>
            <ul className="mt-2 flex flex-col gap-1 text-muted-foreground">
              <li>
                <span className="text-foreground">Sensei reads:</span> pages in the{' '}
                <span className="font-mono">{labelForSpace(conf.space_key) || 'SPACE'}</span>{' '}
                space only. Nothing else is fetched or indexed.
              </li>
              <li>
                <span className="text-foreground">The token could reach:</span> everything
                that account can see in Confluence. A token authorises as its owner —
                Atlassian has no way to narrow it to one space.
              </li>
              <li>
                <span className="text-foreground">So:</span> use a dedicated Atlassian
                account invited only to the spaces this project needs. Then the limit
                is enforced by Confluence, not just by us.
              </li>
            </ul>
          </div>

          {confErr && <p className="text-xs text-destructive">{confErr}</p>}
          <Button type="submit" size="sm"
            disabled={confBusy || !conf.base_url || !conf.email || !conf.api_token || !conf.space_key}>
            {confBusy ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Connecting…</> : 'Connect space'}
          </Button>
        </form>
      )}

      {/* ── Jira tab ──
          Same Atlassian identity as Confluence, a different endpoint. A project
          key narrows what Sensei *reads*, but the token authorises as its owner —
          identical ceiling/floor story. */}
      {tab === 'jira' && (
        <form onSubmit={handleJira} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-medium flex items-center gap-1">
                Jira site
                <FieldHelp text="Your site is the root address you log into — everything after the '?' is redirect noise. Example: https://your-org.atlassian.net" />
              </label>
              <Input placeholder="https://your-org.atlassian.net"
                value={jira.base_url} onChange={setJiraField('base_url')} required disabled={jiraBusy} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium flex items-center gap-1">
                Account email
                <FieldHelp text="The Atlassian account email that owns the API token. Sensei authenticates with this same identity." />
              </label>
              <Input type="email" placeholder="agent@your-org.com"
                value={jira.email} onChange={setJiraField('email')} required disabled={jiraBusy} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium flex items-center gap-1">
                Project key
                <FieldHelp text="The short uppercase code identifying your Jira project (e.g. PD, SCRUM). Found on the board or in its URL after /projects/. Create one if you have none." />
              </label>
              <Input placeholder="PROJ" value={jira.project_key}
                onChange={(e) => setJira((c) => ({ ...c, project_key: e.target.value.toUpperCase() }))}
                required disabled={jiraBusy} />
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-medium flex items-center gap-1">
                API token
                <FieldHelp text={
                  '1. Go to id.atlassian.com → Security → API tokens → Create token\n' +
                  '2. Copy it immediately (shown only once)\n' +
                  '3. Paste and pair with the account email above — the token authorises as that exact account'
                } />
              </label>
              <Input type="password" placeholder="Paste the token"
                value={jira.api_token} onChange={setJiraField('api_token')} required disabled={jiraBusy} />
              <p className="text-xs text-muted-foreground">
                The same Atlassian token works for both Confluence and Jira. Create one at{' '}
                <a href="https://id.atlassian.com/manage-profile/security/api-tokens"
                   target="_blank" rel="noreferrer"
                   className="underline underline-offset-2 hover:text-foreground">
                  id.atlassian.com → Security → API tokens
                </a>.
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
                <span className="font-mono">{jira.project_key.trim().toUpperCase() || 'PROJ'}</span>{' '}
                project only. Nothing else is fetched or indexed.
              </li>
              <li>
                <span className="text-foreground">The token could reach:</span> everything
                that account can see in Jira. A token authorises as its owner —
                Atlassian has no way to narrow it to one project.
              </li>
              <li>
                <span className="text-foreground">So:</span> use a dedicated Atlassian
                account invited only to the projects this work involves. Then the limit
                is enforced by Jira, not just by us.
              </li>
            </ul>
          </div>

          {jiraErr && <p className="text-xs text-destructive">{jiraErr}</p>}
          <Button type="submit" size="sm"
            disabled={jiraBusy || !jira.base_url || !jira.email || !jira.api_token || !jira.project_key}>
            {jiraBusy ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Connecting…</> : 'Connect project'}
          </Button>
        </form>
      )}

      {/* ── Slack tab ──
          The cleanest consent story of any connector: adding the bot to a
          channel IS the grant, removing it IS the revocation. The floor is the
          one channel we read; the ceiling is every channel the app is in. */}
      {tab === 'slack' && (
        <form onSubmit={handleSlack} className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-medium flex items-center gap-1">
                Bot token
                <FieldHelp text={
                  '1. Open api.slack.com/apps → Create New App → From scratch\n' +
                  '2. Under OAuth & Permissions add scope channels:history, channels:read, groups:history, users:read\n' +
                  '3. Install to Workspace → copy the xoxb-… OAuth token'
                } />
              </label>
              <Input type="password" placeholder="xoxb-…"
                value={slack.token} onChange={setSlackField('token')} required disabled={slackBusy} />
            </div>
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <label className="text-xs font-medium flex items-center gap-1">
                Channel
                <FieldHelp text="The channel to index, e.g. general. The bot must be added to it — open the channel → Details → Add apps." />
              </label>
              <Input placeholder="general"
                value={slack.channel} onChange={setSlackField('channel')} required disabled={slackBusy} />
            </div>
          </div>

          <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed">
            <p className="flex items-center gap-1.5 font-medium text-foreground">
              <ShieldCheck className="h-3.5 w-3.5" /> What this grants
            </p>
            <ul className="mt-2 flex flex-col gap-1 text-muted-foreground">
              <li>
                <span className="text-foreground">Sensei reads:</span> #{slack.channel.trim().replace(/^#/, '') || 'channel'}{' '}
                only. Nothing else is fetched or indexed.
              </li>
              <li>
                <span className="text-foreground">The token could reach:</span> every channel
                this Slack app has been added to — Slack cannot narrow a bot token
                to one channel.
              </li>
              <li>
                <span className="text-foreground">So:</span> add the bot to only the channels
                this work involves. The invite is the grant; removing the app is
                the revocation.
              </li>
            </ul>
          </div>

          {slackErr && <p className="text-xs text-destructive">{slackErr}</p>}
          <Button type="submit" size="sm"
            disabled={slackBusy || !slack.token || !slack.channel.trim()}>
            {slackBusy ? <><Loader2 className="h-4 w-4 animate-spin mr-1" /> Connecting…</> : 'Connect channel'}
          </Button>
        </form>
      )}

    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function Sources() {
  const [showAdd, setShowAdd] = useState(false)
  const { data, isLoading } = useGetSourcesQuery(undefined, { pollingInterval: 4000 })
  const { data: wsData } = useGetMyWorkspaceQuery()
  // Members can see what the agent knows, but only owners change it.
  const canManage = wsData?.workspace?.role !== 'member'
  const sources = data?.sources ?? []
  const hasActive = sources.some((s) => s.status === 'indexing' || s.status === 'pending')

  return (
    <AppShell title="Sources">
      <div className="flex flex-col gap-6 max-w-3xl">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Sources</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {sources.length} source{sources.length !== 1 ? 's' : ''} in this workspace
              {hasActive && ' · indexing in progress…'}
            </p>
          </div>
          {canManage ? (
            <Button size="sm" className="gap-1.5" onClick={() => setShowAdd((s) => !s)}>
              <Plus className="h-4 w-4" />
              Add source
            </Button>
          ) : (
            <Badge variant="secondary" className="text-xs">Read-only</Badge>
          )}
        </div>

        {canManage && showAdd && <AddSourcePanel onClose={() => setShowAdd(false)} />}

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : sources.length === 0 ? (
          <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground text-sm">
            {canManage
              ? 'No sources yet. Add a file, URL, or GitHub repo to get started.'
              : 'No sources yet. Your project owner needs to connect some.'}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {sources.map((s) => <SourceCard key={s.id} source={s} canManage={canManage} />)}
          </div>
        )}
      </div>
    </AppShell>
  )
}
