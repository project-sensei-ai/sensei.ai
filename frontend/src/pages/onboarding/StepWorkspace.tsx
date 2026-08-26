import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCreateWorkspaceMutation } from '@/services/onboardingApi'

interface Props {
  onDone: (workspaceId: string) => void
}

export default function StepWorkspace({ onDone }: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [createWorkspace, { isLoading, error }] = useCreateWorkspaceMutation()

  const errMsg = error && 'data' in error ? (error.data as { detail?: string })?.detail : undefined

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const res = await createWorkspace({ name: name.trim(), description: description.trim() }).unwrap()
      onDone(res.workspace.id)
    } catch {
      // error displayed below
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Name your workspace</CardTitle>
        <CardDescription>Give your project a name so your team knows what Sensei is about.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ws-name">Workspace name *</Label>
            <Input
              id="ws-name"
              placeholder="e.g. Project Atlas"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              required
              disabled={isLoading}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ws-desc">Description <span className="text-muted-foreground">(optional)</span></Label>
            <textarea
              id="ws-desc"
              className="border-input bg-background ring-offset-background placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[80px] w-full rounded-md border px-3 py-2 text-sm focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
              placeholder="What is this project about?"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              disabled={isLoading}
            />
          </div>
          {errMsg && <p className="text-sm text-destructive" role="alert">{errMsg}</p>}
        </CardContent>
        <CardFooter>
          <Button type="submit" className="w-full" disabled={isLoading || !name.trim()}>
            {isLoading ? 'Creating…' : 'Create workspace →'}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}
