import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { AppLayout, GuestOnly } from './components/Layout'
import { ThemedToaster } from './components/ThemedToaster'
import './index.css'
import { ApiError } from './lib/api'
import { AuthProvider } from './lib/auth'
import { ThemeProvider } from './lib/theme'
import { AuthPage } from './pages/AuthPage'
import { LinkAnalyticsPage } from './pages/LinkAnalyticsPage'
import { LinksPage } from './pages/LinksPage'
import { NotFoundPage } from './pages/NotFoundPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: true,
      // Client errors (4xx) won't fix themselves; only retry network/5xx failures.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
    },
  },
})

const router = createBrowserRouter([
  {
    element: <GuestOnly />,
    children: [
      { path: '/login', element: <AuthPage mode="login" /> },
      { path: '/register', element: <AuthPage mode="register" /> },
    ],
  },
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <Navigate to="/links" replace /> },
      { path: '/links', element: <LinksPage /> },
      { path: '/links/:id', element: <LinkAnalyticsPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <RouterProvider router={router} />
          <ThemedToaster />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
)
