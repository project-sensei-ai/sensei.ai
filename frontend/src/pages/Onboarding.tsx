import { useState } from 'react'
import { useGetMeQuery } from '@/services/authApi'
import StepWorkspace from './onboarding/StepWorkspace'
import StepSources from './onboarding/StepSources'
import StepReview from './onboarding/StepReview'
import StepInvite from './onboarding/StepInvite'

type WizardStep = 1 | 2 | 3 | 4

const STEPS = [
  { n: 1, label: 'Workspace' },
  { n: 2, label: 'Sources' },
  { n: 3, label: 'Review' },
  { n: 4, label: 'Invite' },
]

export default function Onboarding() {
  const { data: authData } = useGetMeQuery()
  const user = authData?.user

  const [step, setStep] = useState<WizardStep>(1)
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)

  return (
    <div className="min-h-svh bg-background flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-md bg-primary flex items-center justify-center text-primary-foreground text-sm font-bold select-none">
            S
          </div>
          <span className="font-semibold text-sm">Sensei</span>
        </div>
        {user && (
          <span className="text-xs text-muted-foreground">
            Setting up as <strong>{user.email}</strong>
          </span>
        )}
      </header>

      {/* Main content */}
      <main className="flex-1 flex items-start justify-center p-6 pt-10">
        <div className="w-full max-w-xl flex flex-col gap-6">
          {/* Step indicator */}
          <div className="flex items-center gap-0">
            {STEPS.map((s, i) => (
              <div key={s.n} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-colors ${
                      step === s.n
                        ? 'bg-primary border-primary text-primary-foreground'
                        : step > s.n
                        ? 'bg-primary/20 border-primary/40 text-primary'
                        : 'bg-muted border-border text-muted-foreground'
                    }`}
                  >
                    {step > s.n ? '✓' : s.n}
                  </div>
                  <span
                    className={`text-xs font-medium ${
                      step === s.n ? 'text-foreground' : 'text-muted-foreground'
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={`h-0.5 flex-1 mx-2 mb-5 transition-colors ${
                      step > s.n ? 'bg-primary/40' : 'bg-border'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>

          {/* Step content */}
          {step === 1 && (
            <StepWorkspace
              onDone={(id) => { setWorkspaceId(id); setStep(2) }}
            />
          )}
          {step === 2 && workspaceId && (
            <StepSources
              workspaceId={workspaceId}
              onDone={() => setStep(3)}
            />
          )}
          {step === 3 && (
            <StepReview onDone={() => setStep(4)} />
          )}
          {step === 4 && workspaceId && (
            <StepInvite />
          )}
        </div>
      </main>
    </div>
  )
}
