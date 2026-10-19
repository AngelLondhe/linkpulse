// Mirrors the backend Pydantic schemas (backend/app/schemas).

export interface User {
  id: number
  email: string
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

export interface Link {
  id: number
  short_code: string
  short_url: string
  original_url: string
  is_custom: boolean
  is_active: boolean
  expires_at: string | null
  max_clicks: number | null
  has_password: boolean
  total_clicks: number
  created_at: string
}

export interface LinkPage {
  items: Link[]
  total: number
  page: number
  page_size: number
}

export interface TimeseriesPoint {
  date: string
  clicks: number
  unique_visitors: number
}

export interface Bucket {
  label: string
  count: number
}

export interface LinkStats {
  link_id: number
  start: string
  end: string
  timezone: string
  total_clicks: number
  unique_visitors: number
  all_time_clicks: number
  timeseries: TimeseriesPoint[]
  referrers: Bucket[]
  devices: Bucket[]
  browsers: Bucket[]
  os: Bucket[]
  countries: Bucket[]
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown }
}
