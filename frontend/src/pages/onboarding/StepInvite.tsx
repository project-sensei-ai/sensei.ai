import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import TeamPanel from '@/components/TeamPanel'

export default function StepInvite() {
  const navigate = useNavigate()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Who can ask the agent?</CardTitle>
        <CardDescription>
          Add your teammates by email. This list is the whole access rule — anyone
          not on it cannot reach this project, even with a link.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <TeamPanel compact />
      </CardContent>
      <CardFooter className="flex-col items-stretch gap-2">
        <Button className="w-full" onClick={() => navigate('/dashboard')}>
          Finish setup →
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          You can add or remove people any time from the dashboard.
        </p>
      </CardFooter>
    </Card>
  )
}
