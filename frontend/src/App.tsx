import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { GoogleOAuthProvider } from '@react-oauth/google'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import ProtectedRoute from './components/ProtectedRoute'

const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

function Router() {
  return (
    <BrowserRouter>
      <Routes>
        {/* PUBLIC */}
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* PROTECTED */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
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
    // Google sign-in disabled until VITE_GOOGLE_CLIENT_ID is set;
    // email/password auth still works.
    return <Router />
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      <Router />
    </GoogleOAuthProvider>
  )
}
