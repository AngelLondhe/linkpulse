import countries from 'i18n-iso-countries'
import en from 'i18n-iso-countries/langs/en.json'

countries.registerLocale(en)

const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 })
const whole = new Intl.NumberFormat('en')

/** 1,284 / 12.9K / 4.2M */
export const formatCompact = (value: number) => (value < 10_000 ? whole.format(value) : compact.format(value))
export const formatNumber = (value: number) => whole.format(value)
export const formatPercent = (part: number, total: number) =>
  total === 0 ? '0%' : `${((part / total) * 100).toFixed(part / total < 0.1 ? 1 : 0)}%`

export function formatDay(isoDate: string): string {
  // Stats dates are calendar days (no time); parse as local noon to avoid TZ day shifts.
  return new Date(`${isoDate}T12:00:00`).toLocaleDateString('en', { month: 'short', day: 'numeric' })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en', { dateStyle: 'medium', timeStyle: 'short' })
}

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

export function formatRelative(iso: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000)
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['week', 604_800],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ]
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit)
  }
  return 'just now'
}

const regionNames = new Intl.DisplayNames(['en'], { type: 'region' })

/** "US" -> "United States" (short common names, from the browser's own data). */
export function countryName(code: string): string {
  if (code === 'Unknown') return 'Unknown'
  try {
    return regionNames.of(code) ?? code
  } catch {
    return code
  }
}

/** ISO alpha-2 -> ISO numeric (the ids used by world-atlas). */
export function countryNumericId(code: string): string | undefined {
  return countries.alpha2ToNumeric(code)
}

/** "https://www.example.com/a/b" -> "example.com/a/b" for compact display. */
export function prettyUrl(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')
}

export function deviceLabel(value: string): string {
  return value === 'Unknown' ? value : value.charAt(0).toUpperCase() + value.slice(1)
}
