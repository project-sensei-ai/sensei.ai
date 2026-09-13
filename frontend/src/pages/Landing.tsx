import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { CTASection } from '@/components/ui/hero-dithering-card'
import { useGetMeQuery } from '../services/authApi'
import { Spinner } from '@/components/Spinner'

export default function Landing() {
  const { data: authData, isLoading: authLoading } = useGetMeQuery()
  const signedIn = !authLoading && !!authData?.user

  return (
    <div className="bg-background text-foreground relative min-h-svh">
      <CTASection
        ctaHref={signedIn ? '/dashboard' : '/register'}
        ctaLabel={signedIn ? 'Open dashboard' : 'Get started'}
        secondaryHref={signedIn ? undefined : '/login'}
        secondaryLabel={signedIn ? undefined : 'Log in'}
      />

      <header className="absolute inset-x-0 top-0 z-20 mx-auto flex w-full max-w-7xl items-center justify-between px-4 pt-6 md:px-6">
        <Link to="/" aria-label="Sensei home" className="flex items-center">
          <img
            src="/lightLogo.png"
            alt="Sensei"
            className="h-8 w-auto dark:hidden"
          />
          <img
            src="/darkLogo.png"
            alt="Sensei"
            className="hidden h-8 w-auto dark:block"
          />
        </Link>
        <nav className="flex items-center gap-2">
          {authLoading ? (
            <Spinner />
          ) : signedIn ? (
            <Button asChild variant="outline" size="sm">
              <Link to="/dashboard">Open dashboard</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm">
                <Link to="/login">Log in</Link>
              </Button>
              <Button asChild size="sm">
                <Link to="/register">Get started</Link>
              </Button>
            </>
          )}
        </nav>
      </header>
    </div>
  )
}