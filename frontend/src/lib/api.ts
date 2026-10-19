import type { ApiErrorBody, AuthResponse, Link, LinkCreateInput, LinkPage, LinkStats, User } from './types'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
)

/** A non-2xx response, carrying the backend's error envelope. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: unknown

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

let authToken: string | null = null
let onUnauthorized: (() => void) | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

/** Called when an authenticated request is rejected (expired/invalid token). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

function messageFor(status: number, body: unknown): { code: string; message: string; details: unknown } {
  const envelope = body as Partial<ApiErrorBody> | null
  if (envelope?.error) {
    const { code, message, details } = envelope.error
    // Turn field validation errors into something readable.
    if (code === 'validation_error' && Array.isArray(details) && details.length > 0) {
      const first = details[0] as { msg?: string }
      return { code, message: first.msg?.replace(/^Value error, /, '') ?? message, details }
    }
    return { code, message, details }
  }
  return { code: 'http_error', message: `Request failed (${status})`, details: null }
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')
  if (authToken) headers.set('Authorization', `Bearer ${authToken}`)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the server. Check your connection.')
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const { code, message, details } = messageFor(response.status, body)
    if (response.status === 401 && authToken) onUnauthorized?.()
    if (response.status === 429) {
      const wait = response.headers.get('Retry-After')
      throw new ApiError(429, code, wait ? `${message} Try again in ${wait}s.` : message, details)
    }
    throw new ApiError(response.status, code, message, details)
  }
  return response
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await send(path, init)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const json = (data: unknown) => JSON.stringify(data)

export const api = {
  register: (email: string, password: string) =>
    request<AuthResponse>('/api/auth/register', { method: 'POST', body: json({ email, password }) }),
  login: (email: string, password: string) =>
    request<AuthResponse>('/api/auth/login', { method: 'POST', body: json({ email, password }) }),
  me: () => request<User>('/api/auth/me'),

  listLinks: (params: { q?: string; page: number; pageSize: number }) => {
    const search = new URLSearchParams({ page: String(params.page), page_size: String(params.pageSize) })
    if (params.q) search.set('q', params.q)
    return request<LinkPage>(`/api/links?${search}`)
  },
  getLink: (id: number) => request<Link>(`/api/links/${id}`),
  createLink: (input: LinkCreateInput) => request<Link>('/api/links', { method: 'POST', body: json(input) }),
  updateLink: (id: number, changes: { url?: string; is_active?: boolean }) =>
    request<Link>(`/api/links/${id}`, { method: 'PATCH', body: json(changes) }),
  deleteLink: (id: number) => request<void>(`/api/links/${id}`, { method: 'DELETE' }),
  linkStats: (id: number, range: { from: string; to: string; tz: string }, includeBots: boolean) =>
    request<LinkStats>(
      `/api/links/${id}/stats?${new URLSearchParams({ ...range, include_bots: String(includeBots) })}`,
    ),
  /** QR image as a Blob (needs the auth header, so it can't be a plain <img src>). */
  linkQr: async (id: number, format: 'png' | 'svg') =>
    (await send(`/api/links/${id}/qr?format=${format}&scale=10`)).blob(),
}
