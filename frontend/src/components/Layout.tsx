import { LogOut, Monitor, Moon, Sun } from 'lucide-react'
import { Link, Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../lib/auth'
import { useTheme, type ThemePreference } from '../lib/theme'

export function Logo() {
  return (
    <Link to="/links" className="flex items-center gap-2 font-semibold tracking-tight">
      <img src="/favicon.svg" alt="" className="size-7" />
      Linkpulse
    </Link>
  )
}

const THEMES: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'dark', label: 'Dark theme', icon: Moon },
  { value: 'system', label: 'System theme', icon: Monitor },
]

export function ThemeToggle() {
  const { preference, setPreference } = useTheme()
  return (
    <div role="radiogroup" aria-label="Theme" className="flex rounded-lg border border-line p-0.5">
      {THEMES.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={preference === value}
          aria-label={label}
          title={label}
          onClick={() => setPreference(value)}
          className={`rounded-md p-1.5 ${
            preference === value ? 'bg-surface-2 text-ink' : 'text-muted hover:text-ink'
          }`}
        >
          <Icon className="size-4" aria-hidden />
        </button>
      ))}
    </div>
  )
}

/** Shell for signed-in pages; bounces anonymous visitors to /login. */
export function AppLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4">
          <Logo />
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <span className="hidden max-w-48 truncate text-sm text-ink-2 sm:inline" title={user.email}>
              {user.email}
            </span>
            <button
              type="button"
              onClick={logout}
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              <LogOut className="size-4" aria-hidden />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}

/** Signed-in users skip the auth pages. */
export function GuestOnly() {
  const { user } = useAuth()
  return user ? <Navigate to="/links" replace /> : <Outlet />
}
