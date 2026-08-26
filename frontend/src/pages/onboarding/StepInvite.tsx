import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useGenerateInviteMutation } from '@/services/onboardingApi'
import { Copy, Check } from 'lucide-react'

interface Props {
  workspaceId: string
}

export default function StepInvite({ workspaceId }: Props) {
  const navigate = useNavigate()
  const [generateInvite, { data, isLoading, error }] = useGenerateInviteMutation()
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    generateInvite(workspaceId)
  }, [workspaceId])

  const inviteUrl = data?.invite?.invite_url ?? ''
  const errMsg = error && 'data' in error ? (error.data as { detail?: string })?.detail : undefined

  async function copy() {
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch { /* clipboard unavailable in http */ }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Invite your team 🎉</CardTitle>
        <CardDescription>
          Share this link with teammates. Anyone with the link can join your workspace.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Generating invite link…</p>
        ) : errMsg ? (
          <p className="text-sm text-destructive">{errMsg}</p>
        ) : (
          <div className="flex gap-2">
            <Input value={inviteUrl} readOnly className="font-mono text-xs" />
            <Button variant="outline" size="icon" onClick={copy} disabled={!inviteUrl}>
              {copied ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
            </Button>
          </div>
        )}
        <p className="text-xs text-muted-foreground">Link expires in 7 days. Generate a new one from your workspace settings.</p>
      </CardContent>
      <CardFooter>
        <Button className="w-full" onClick={() => navigate('/dashboard')}>
          Go to dashboard →
        </Button>
      </CardFooter>
    </Card>
  )
}
