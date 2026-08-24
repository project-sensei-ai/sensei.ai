import { GoogleLogin, type CredentialResponse } from '@react-oauth/google'
import { Separator } from '@/components/ui/separator'
import {
  errorMessage,
  useGoogleAuthMutation,
} from '../services/authApi'

export default function GoogleButton({
  onSuccess,
  onError,
}: {
  onSuccess: () => void
  onError: (msg: string) => void
}) {
  const [googleAuth] = useGoogleAuthMutation()
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

  if (!clientId) return null

  return (
    <div className="flex flex-col gap-4">
      <div className="text-muted-foreground flex items-center gap-3 text-xs uppercase tracking-wide">
        <Separator className="flex-1" />
        or
        <Separator className="flex-1" />
      </div>
      <div className="flex justify-center">
        <GoogleLogin
          theme="filled_black"
          size="large"
          shape="pill"
          text="continue_with"
          onSuccess={(res: CredentialResponse) => {
            if (!res.credential) return
            googleAuth({ credential: res.credential })
              .unwrap()
              .then(onSuccess)
              .catch((err) => onError(errorMessage(err)))
          }}
          onError={() => onError('Google sign-in failed')}
        />
      </div>
    </div>
  )
}
