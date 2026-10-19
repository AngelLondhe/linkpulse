import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Logo, ThemeToggle } from '../components/Layout'
import { Button, Card } from '../components/ui'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

const DEMO = { email: 'demo@linkpulse.dev', password: 'demo-password-123' }
const SHOW_DEMO = import.meta.env.VITE_SHOW_DEMO_LOGIN !== 'false'

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const isLogin = mode === 'login'
  const redirectTo = (location.state as { from?: string } | null)?.from ?? '/links'

  async function submit(credentials: { email: string; password: string }) {
    setSubmitting(true)
    setError(null)
    try {
      await (isLogin ? login : register)(credentials.email, credentials.password)
      if (!isLogin) toast.success('Welcome to Linkpulse!')
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void submit({ email, password })
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between px-4 py-4 sm:px-8">
        <Logo />
        <ThemeToggle />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold tracking-tight">
            {isLogin ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="mt-1 text-sm text-ink-2">
            {isLogin ? 'Sign in to see how your links are performing.' : 'Shorten links and watch the clicks roll in.'}
          </p>
          <Card className="mt-6 p-5">
            <form onSubmit={onSubmit} className="space-y-4" noValidate>
              <label className="block">
                <span className="text-sm font-medium">Email</span>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-line bg-page px-3 py-2 text-sm"
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium">Password</span>
                <input
                  type="password"
                  autoComplete={isLogin ? 'current-password' : 'new-password'}
                  required
                  minLength={isLogin ? undefined : 8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-line bg-page px-3 py-2 text-sm"
                />
                {!isLogin && <span className="mt-1 block text-xs text-muted">At least 8 characters.</span>}
              </label>
              {error && (
                <p role="alert" className="rounded-lg bg-surface-2 px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              )}
              <Button type="submit" variant="primary" loading={submitting} className="w-full">
                {isLogin ? 'Sign in' : 'Create account'}
              </Button>
            </form>
            {isLogin && SHOW_DEMO && (
              <Button
                variant="ghost"
                className="mt-2 w-full"
                disabled={submitting}
                onClick={() => {
                  setEmail(DEMO.email)
                  setPassword(DEMO.password)
                  void submit(DEMO)
                }}
              >
                Explore the demo account
              </Button>
            )}
          </Card>
          <p className="mt-4 text-center text-sm text-ink-2">
            {isLogin ? "Don't have an account? " : 'Already have an account? '}
            <Link to={isLogin ? '/register' : '/login'} className="font-medium text-accent hover:underline">
              {isLogin ? 'Sign up' : 'Sign in'}
            </Link>
          </p>
        </div>
      </main>
    </div>
  )
}
