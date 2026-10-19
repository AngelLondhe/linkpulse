import type { ReactNode } from 'react'
import { Card } from '../ui'

export function KpiCard({
  label,
  value,
  hint,
  hero = false,
}: {
  label: string
  value: ReactNode
  hint?: string
  hero?: boolean
}) {
  return (
    <Card className="p-4 sm:p-5">
      <p className="text-xs font-medium text-ink-2">{label}</p>
      <p className={`mt-1 truncate font-semibold tracking-tight ${hero ? 'text-4xl sm:text-5xl' : 'text-2xl'}`}>
        {value}
      </p>
      {hint && <p className="mt-1 truncate text-xs text-muted">{hint}</p>}
    </Card>
  )
}
