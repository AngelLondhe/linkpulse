import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { api, setAuthToken, setUnauthorizedHandler } from './api'
import { readStorage, writeStorage } from './storage'
import type { AuthResponse, User } from './types'

const TOKEN_KEY = 'linkpulse.token'
const USER_KEY = 'linkpulse.user'

interface AuthState {
  user: User | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

function loadUser(): User | null {
  const raw = readStorage(USER_KEY)
  if (!raw || !readStorage(TOKEN_KEY)) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

// Restore the token synchronously so the very first requests are authenticated.
setAuthToken(readStorage(TOKEN_KEY))

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(loadUser)
  const queryClient = useQueryClient()

  const persist = useCallback((auth: AuthResponse | null) => {
    setAuthToken(auth?.access_token ?? null)
    writeStorage(TOKEN_KEY, auth?.access_token ?? null)
    writeStorage(USER_KEY, auth ? JSON.stringify(auth.user) : null)
    setUser(auth?.user ?? null)
  }, [])

  const logout = useCallback(() => {
    persist(null)
    queryClient.clear()
  }, [persist, queryClient])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout()
      toast.error('Your session expired. Please sign in again.')
    })
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const value = useMemo<AuthState>(
    () => ({
      user,
      login: async (email, password) => persist(await api.login(email, password)),
      register: async (email, password) => persist(await api.register(email, password)),
      logout,
    }),
    [user, persist, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
