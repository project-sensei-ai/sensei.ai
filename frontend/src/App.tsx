import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Chat from './pages/Chat'
import Dashboard from './pages/Dashboard'
import Onboarding from './pages/Onboarding'
import Sources from './pages/Sources'
import Join from './pages/Join'
import PendingAccess from './pages/PendingAccess'
import Brief from './pages/Brief'
import Gaps from './pages/Gaps'
import ProtectedRoute from './components/ProtectedRoute'
import OnboardingRoute from './components/OnboardingRoute'

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

function Router() {
  return (
    <BrowserRouter>
      <Routes>
        {/* PUBLIC */}
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* INVITE LANDING — public; the page itself handles sign-in */}
        <Route path="/join" element={<Join />} />

        {/* HOLDING STATE — signed in, but not on a project yet */}
        <Route
          path="/pending"
          element={
            <ProtectedRoute skipWorkspaceCheck>
              <PendingAccess />
            </ProtectedRoute>
          }
        />

        {/* ONBOARDING — redirects to /dashboard if workspace already exists */}
        <Route
          path="/onboarding"
          element={
            <OnboardingRoute>
              <Onboarding />
            </OnboardingRoute>
          }
        />

        {/* PROTECTED — redirects to /onboarding if no workspace */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/brief"
          element={
            <ProtectedRoute>
              <Brief />
            </ProtectedRoute>
          }
        />
        <Route
          path="/gaps"
          element={
            <ProtectedRoute>
              <Gaps />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sources"
          element={
            <ProtectedRoute>
              <Sources />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  if (!clientId) {
    return <Router />
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <Router />
    </GoogleOAuthProvider>
  )
}
