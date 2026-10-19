export type RangeKey = '7d' | '30d' | '90d'

export const RANGES: { key: RangeKey; label: string; days: number }[] = [
  { key: '7d', label: '7 days', days: 7 },
  { key: '30d', label: '30 days', days: 30 },
  { key: '90d', label: '90 days', days: 90 },
]

const pad = (n: number) => String(n).padStart(2, '0')
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

/** Inclusive local-day window ending today, plus the viewer's IANA zone for day buckets. */
export function rangeParams(key: RangeKey, today = new Date()): { from: string; to: string; tz: string } {
  const days = RANGES.find((r) => r.key === key)?.days ?? 30
  const start = new Date(today)
  start.setDate(start.getDate() - (days - 1))
  return {
    from: isoDay(start),
    to: isoDay(today),
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  }
}
