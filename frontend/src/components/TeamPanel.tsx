import { useState, type FormEvent } from 'react'
import { Check, Copy, Loader2, Mail, Trash2, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  useAddMembersMutation,
  useGetMembersQuery,
  useRemoveMemberMutation,
  type AddMemberResult,
} from '@/services/onboardingApi'

/**
 * The project's allowlist. Rendered in two places — inside the onboarding
 * wizard and on the dashboard — so the rule lives in one component: nobody
 * reaches this project unless their address is on this list.
 */
export default function TeamPanel({ compact = false }: { compact?: boolean }) {
  const { data, isLoading } = useGetMembersQuery()
  const [addMembers, { isLoading: adding }] = useAddMembersMutation()
  const [removeMember] = useRemoveMemberMutation()

  const [emails, setEmails] = useState('')
  const [results, setResults] = useState<AddMemberResult[] | null>(null)
  const [emailConfigured, setEmailConfigured] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const members = data?.members ?? []
  const canManage = data?.can_manage ?? false

  async function onAdd(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setResults(null)
    const list = emails
      .split(/[\s,;]+/)
      .map((e) => e.trim())
      .filter(Boolean)
    if (!list.length) return
    try {
      const res = await addMembers({ emails: list }).unwrap()
      setResults(res.results)
      setEmailConfigured(res.email_configured)
      setEmails('')
    } catch (err) {
      const detail = (err as { data?: { detail?: unknown } })?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not add those people.')
    }
  }

  async function copy(url: string) {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(url)
      setTimeout(() => setCopied(null), 2000)
    } catch {
      /* clipboard unavailable over plain http */
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {canManage && (
        <form onSubmit={onAdd} className="flex flex-col gap-2">
          <div className="flex gap-2">
            <Input
              type="text"
              value={emails}
              onChange={(e) => setEmails(e.target.value)}
              placeholder="teammate@company.com, another@company.com"
              disabled={adding}
              className="flex-1"
            />
            <Button type="submit" disabled={adding || !emails.trim()} className="gap-1.5 shrink-0">
              {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
              Add
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Only people you add here can reach this project. They set their own
            password from a single-use link — no password is ever emailed.
          </p>
        </form>
      )}

      {error && (
        <p role="alert" className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      {results && (
        <div className="flex flex-col gap-2 rounded-lg border bg-muted/30 p-3">
          {!emailConfigured && results.some((r) => r.invite_url) && (
            <p className="text-xs text-muted-foreground">
              Email delivery isn't configured, so send these links yourself. Each
              one works once and expires in 7 days.
            </p>
          )}
          {results.map((r) => (
            <div key={r.email} className="flex items-center gap-2 text-sm">
              {r.status === 'skipped' ? (
                <>
                  <span className="text-muted-foreground truncate">{r.email}</span>
                  <span className="text-xs text-muted-foreground">— {r.detail}</span>
                </>
              ) : (
                <>
                  <Mail className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="truncate">{r.email}</span>
                  {r.emailed ? (
                    <Badge variant="secondary" className="text-xs">emailed</Badge>
                  ) : r.invite_url ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-6 gap-1 text-xs ml-auto shrink-0"
                      onClick={() => copy(r.invite_url!)}
                    >
                      {copied === r.invite_url ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                      {copied === r.invite_url ? 'Copied' : 'Copy link'}
                    </Button>
                  ) : null}
                </>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        {isLoading ? (
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading the team…
          </p>
        ) : members.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nobody yet.</p>
        ) : (
          members.map((m) => (
            <div
              key={m.id}
              className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium uppercase">
                {(m.name || m.email || '?').slice(0, 2)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{m.name || m.email}</p>
                {m.name && m.email && (
                  <p className="truncate text-xs text-muted-foreground">{m.email}</p>
                )}
              </div>

              <Badge variant={m.role === 'owner' ? 'default' : 'secondary'} className="text-xs shrink-0">
                {m.role === 'owner' ? 'Owner' : 'Member'}
              </Badge>
              {m.status === 'invited' && (
                <Badge variant="outline" className="text-xs shrink-0">Pending</Badge>
              )}

              {canManage && m.invite_url && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 gap-1 text-xs shrink-0"
                  onClick={() => copy(m.invite_url!)}
                >
                  {copied === m.invite_url ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
                </Button>
              )}
              {canManage && m.role !== 'owner' && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0 shrink-0 text-muted-foreground hover:text-destructive"
                  aria-label={`Remove ${m.email}`}
                  onClick={() => removeMember(m.user_id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          ))
        )}
      </div>

      {!compact && canManage && members.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Removing someone revokes their access immediately and cancels any
          unused invite link.
        </p>
      )}
    </div>
  )
}
