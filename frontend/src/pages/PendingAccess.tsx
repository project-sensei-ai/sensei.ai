import { Clock, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useGetMeQuery, useLogoutMutation } from '@/services/authApi'

/**
 * Where a member lands when they have an account but no project yet — either
 * they have not accepted an invite, or their access was revoked. Deliberately
 * not the onboarding wizard: members never set up projects.
 */
export default function PendingAccess() {
  const { data } = useGetMeQuery()
  const [logout] = useLogoutMutation()
  const navigate = useNavigate()

  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col items-center justify-center p-8">
      <div className="flex w-full max-w-md flex-col gap-4">
        <Card>
          <CardHeader>
            <Clock className="mb-1 h-5 w-5 text-muted-foreground" />
            <CardTitle>No project yet</CardTitle>
            <CardDescription>
              Your account is ready, but you're not on a project.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground leading-relaxed">
            <p>
              A project owner has to add{' '}
              <span className="text-foreground font-medium">{data?.user?.email}</span>{' '}
              before you can see anything. They'll send you a link.
            </p>
            <p className="mt-3">
              If you were on a project and this appeared, your access was removed.
            </p>
          </CardContent>
          <CardFooter className="flex-col items-stretch gap-2">
            <Button variant="outline" onClick={() => window.location.reload()}>
              Check again
            </Button>
            <Button
              variant="ghost"
              className="gap-2 text-muted-foreground"
              onClick={async () => {
                await logout()
                navigate('/login')
              }}
            >
              <LogOut className="h-4 w-4" /> Log out
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  )
}
