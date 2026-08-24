import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

const features = [
  { title: 'Sources', description: 'Confluence, GitHub, Jira, Teams' },
  { title: 'Memory', description: 'Project context & decisions' },
  { title: 'Chat', description: 'Cited, grounded answers' },
]

export default function Landing() {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col items-center justify-center p-8">
      <div className="flex w-full max-w-lg flex-col gap-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold tracking-tight">Sensei</h1>
          <p className="text-muted-foreground mt-2">
            Permission-aware project context platform
          </p>
        </div>

        <div className="flex items-center justify-center gap-3">
          <Button asChild variant="outline">
            <Link to="/login">Log in</Link>
          </Button>
          <Button asChild>
            <Link to="/register">Get started</Link>
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {features.map((card) => (
            <Card key={card.title} className="text-center">
              <CardHeader>
                <CardTitle>{card.title}</CardTitle>
                <CardDescription>{card.description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
