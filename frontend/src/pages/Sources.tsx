import { useRef, useState } from 'react'
import {
  AlertCircle,
  CheckCircle,
  Clock,
  FolderGit2,
  Globe,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  useAddSourceMutation,
  useDeleteSourceMutation,
  useGetSourcesQuery,
  useGetMyWorkspaceQuery,
  useTriggerIngestMutation,
  useUploadFileMutation,
  type Source,
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
}

// ── Source card ────────────────────────────────────────────────────────────────

function SourceCard({ source, canManage }: { source: Source; canManage: boolean }) {
  const [triggerIngest, { isLoading: ingesting }] = useTriggerIngestMutation()
  const [deleteSource, { isLoading: deleting }] = useDeleteSourceMutation()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const cfg = STATUS_CONFIG[source.status] ?? STATUS_CONFIG.pending

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

        {canManage && (source.status === 'pending' || source.status === 'error') && (
          <Button size="sm" variant="outline" className="h-7 gap-1 text-xs"
            disabled={ingesting} onClick={() => triggerIngest(source.id)}>
            <RefreshCw className={`h-3 w-3 ${ingesting ? 'animate-spin' : ''}`} />
            Ingest
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
    </div>
  )
}

// ── Add-source panel ───────────────────────────────────────────────────────────

type Tab = 'file' | 'url' | 'github'

interface GithubRepo { full_name: string; description: string | null; private: boolean }

function AddSourcePanel({ onClose }: { onClose: () => void }) {
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
        setFileErr(e?.data?.detail || `Failed to upload ${file.name}`)
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
      setUrlErr(e?.data?.detail || 'Failed to add URLs')
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
      setGhErr(e?.data?.detail || 'Failed to add GitHub repo')
    } finally { setGhBusy(false) }
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: 'file', label: 'File Upload' },
    { id: 'url', label: 'URL' },
    { id: 'github', label: 'GitHub' },
  ]

  return (
    <div className="rounded-xl border bg-card shadow-lg p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">Add a new source</h3>
        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

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
            <Label>URLs <span className="text-muted-foreground text-xs">(one per line)</span></Label>
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
            <Label>Personal Access Token</Label>
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
              <Label>Repository <span className="text-muted-foreground text-xs font-normal">({repos.length} found)</span></Label>
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
              <Label>Repository <span className="text-muted-foreground text-xs font-normal">or enter manually</span></Label>
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
