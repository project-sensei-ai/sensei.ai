import { Link } from 'react-router-dom'
import {
  ArrowUpRight, Ban, KeyRound, Loader2, Lock, ShieldCheck, Unlock, Users,
} from 'lucide-react'
import { AppShell } from '@/components/AppShell'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useGetTrustQuery, useDeleteSourceMutation, type Grant } from '@/services/onboardingApi'

function GrantCard({ grant, canManage }: { grant: Grant; canManage: boolean }) {
  const [deleteSource, { isLoading }] = useDeleteSourceMutation()
  const encrypted = grant.credential_state === 'encrypted'
  const plaintext = grant.credential_state === 'plaintext'

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className="text-xs capitalize">{grant.type}</Badge>
          {grant.chunks > 0 && (
            <span className="text-xs text-muted-foreground">{grant.chunks} chunks indexed</span>
          )}
          {encrypted && (
            <Badge variant="outline" className="gap-1 text-xs">
              <Lock className="h-3 w-3" /> credential encrypted
            </Badge>
          )}
          {plaintext && (
            <Badge variant="outline" className="gap-1 border-amber-500/40 text-xs text-amber-600 dark:text-amber-500">
              <Unlock className="h-3 w-3" /> stored before encryption
            </Badge>
          )}
        </div>
        <CardTitle className="text-base">{grant.label}</CardTitle>
        {grant.credential && (
          <CardDescription className="flex items-center gap-1.5">
            <KeyRound className="h-3.5 w-3.5" /> {grant.credential}
          </CardDescription>
        )}
      </CardHeader>

      <CardContent className="flex flex-col gap-3 text-sm">
        {/* The two limits, side by side. A product that shows only the floor is
            telling a comfortable half-truth. */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border bg-muted/20 p-3">
            <p className="text-xs font-medium text-muted-foreground">Sensei reads</p>
            <p className="mt-1 text-sm leading-snug">{grant.floor}</p>
          </div>
          <div className="rounded-lg border bg-muted/20 p-3">
            <p className="text-xs font-medium text-muted-foreground">The credential could reach</p>
            <p className="mt-1 text-sm leading-snug">{grant.ceiling}</p>
          </div>
        </div>

        {grant.cannot && grant.cannot.length > 0 && (
          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium">
              <Ban className="h-3.5 w-3.5 text-muted-foreground" /> It cannot
            </p>
            <ul className="flex flex-col gap-1">
              {grant.cannot.map((c) => (
                <li key={c} className="text-xs text-muted-foreground">— {c}</li>
              ))}
            </ul>
          </div>
        )}

        {grant.improve && (
          <p className="rounded-md border border-dashed p-2.5 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">Tighter still:</span> {grant.improve}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-1">
          {canManage && (
            <Button
              size="sm" variant="outline" disabled={isLoading}
              onClick={() => deleteSource(grant.id)}
            >
              {isLoading ? 'Revoking…' : 'Revoke access'}
            </Button>
          )}
          <span className="text-xs text-muted-foreground">{grant.revoke}</span>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Trust & access.
 *
 * Every other screen answers "what does the agent know". This answers the
 * question people actually hesitate over before connecting anything: what did I
 * just give it, and can I take it back.
 */
export default function Trust() {
  const { data, isLoading } = useGetTrustQuery()

  if (isLoading || !data) {
    return (
      <AppShell title="Trust">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </p>
      </AppShell>
    )
  }

  const { coverage } = data

  return (
    <AppShell title="Trust">
      <div className="flex max-w-3xl flex-col gap-6">
        <div>
          <h1 className="text-xl font-semibold">What the agent can reach</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Everything it has been given, who gave it, and how to take it back.
          </p>
        </div>

        <Card>
          <CardContent className="flex flex-wrap gap-x-10 gap-y-4 pt-6">
            {[
              ['Sources connected', coverage.sources],
              ['Passages indexed', coverage.indexed_chunks],
              ['People who can ask', coverage.people_with_access],
              ['Invites pending', coverage.pending_invites],
            ].map(([label, value]) => (
              <div key={label as string}>
                <p className="text-2xl font-semibold tabular-nums">{value as number}</p>
                <p className="text-xs text-muted-foreground">{label as string}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* The negative half is what earns the trust. */}
        <Card className="border-dashed">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-4 w-4 text-muted-foreground" />
              What it never does
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-1.5">
              {data.never.map((n) => (
                <li key={n} className="flex gap-2 text-sm text-muted-foreground">
                  <span className="text-muted-foreground/50">—</span>
                  <span>{n}</span>
                </li>
              ))}
            </ul>
            {!data.encryption_configured && (
              <p className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/[0.06] p-2.5 text-xs text-amber-700 dark:text-amber-500">
                SECRET_ENCRYPTION_KEY is not set, so new credentials are stored
                unencrypted. Set it and reconnect any source.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-3">
          <p className="text-sm font-medium">Access granted ({data.grants.length})</p>
          {data.grants.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Nothing connected</CardTitle>
                <CardDescription>
                  The agent can't reach anything yet.{' '}
                  <Link to="/sources" className="underline underline-offset-2">Connect a source</Link>.
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            data.grants.map((g) => <GrantCard key={g.id} grant={g} canManage={data.can_manage} />)
          )}
        </div>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4 text-muted-foreground" />
              Who can ask it ({data.people.length})
            </CardTitle>
            <CardDescription>
              Nobody else reaches this project, with or without a link.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {data.people.map((p) => (
              <div key={p.email ?? p.name} className="flex items-center gap-2 text-sm">
                <span className="min-w-0 flex-1 truncate">{p.name || p.email}</span>
                <Badge variant={p.role === 'owner' ? 'default' : 'secondary'} className="text-xs">
                  {p.role === 'owner' ? 'Owner' : 'Member'}
                </Badge>
                {p.status !== 'active' && (
                  <Badge variant="outline" className="text-xs">pending</Badge>
                )}
              </div>
            ))}
            {data.can_manage && (
              <Button variant="outline" size="sm" className="mt-2 gap-1.5 self-start" asChild>
                <Link to="/dashboard">Manage the team <ArrowUpRight className="h-3.5 w-3.5" /></Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
