import { useState } from 'react'
import { Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { formatCompact, formatNumber, formatPercent } from '../../lib/format'
import type { Bucket } from '../../lib/types'
import { ChartCard, ChartEmpty, TooltipBox } from './ChartCard'

// Fixed categorical order (validated palette). Max 5 named slices; the tail folds into "Other".
const SLOTS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)', 'var(--series-5)']
const OTHER = 'var(--series-other)'
const MAX_SLICES = SLOTS.length

interface Slice {
  label: string
  count: number
  fill: string
}

/** Top 5 named slices + "Other" = total minus their sum (every click has a value per dimension). */
function toSlices(buckets: Bucket[], total: number, labelFor: (raw: string) => string): Slice[] {
  const top = buckets.slice(0, MAX_SLICES)
  const slices = top.map((b, i) => ({ label: labelFor(b.label), count: b.count, fill: SLOTS[i] }))
  const rest = total - top.reduce((sum, b) => sum + b.count, 0)
  if (rest > 0) slices.push({ label: 'Other', count: rest, fill: OTHER })
  return slices
}

interface TooltipProps {
  active?: boolean
  payload?: { payload: Slice }[]
  total: number
}

function SliceTooltip({ active, payload, total }: TooltipProps) {
  const slice = payload?.[0]?.payload
  if (!active || !slice) return null
  return (
    <TooltipBox
      title={slice.label}
      rows={[{ color: slice.fill, label: formatPercent(slice.count, total), value: formatNumber(slice.count) }]}
    />
  )
}

export function DonutChart({
  title,
  buckets,
  total,
  labelFor = (raw) => raw,
}: {
  title: string
  buckets: Bucket[]
  total: number
  labelFor?: (raw: string) => string
}) {
  const slices = toSlices(buckets, total, labelFor)
  const [active, setActive] = useState<string | null>(null)

  return (
    <ChartCard
      title={title}
      table={{
        columns: [title.replace(/^By /, ''), 'Clicks', 'Share'],
        rows: slices.map((s) => [s.label, s.count, formatPercent(s.count, total)]),
      }}
    >
      {total === 0 ? (
        <ChartEmpty />
      ) : (
        <div className="flex items-center gap-4">
          <div className="relative size-36 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="count"
                  nameKey="label"
                  innerRadius="66%"
                  outerRadius="100%"
                  startAngle={90}
                  endAngle={-270}
                  stroke="var(--surface)"
                  strokeWidth={2}
                  isAnimationActive={false}
                  onMouseEnter={(_, index) => setActive(slices[index]?.label ?? null)}
                  onMouseLeave={() => setActive(null)}
                />
                <Tooltip content={<SliceTooltip total={total} />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-lg font-semibold">{formatCompact(total)}</span>
              <span className="text-[10px] text-muted">clicks</span>
            </div>
          </div>
          {/* Legend doubles as direct labels: identity never relies on colour alone. */}
          <ul className="min-w-0 flex-1 space-y-1.5 text-sm">
            {slices.map((s) => (
              <li
                key={s.label}
                className={`flex items-center gap-2 rounded px-1 transition-opacity ${
                  active && active !== s.label ? 'opacity-50' : ''
                }`}
              >
                <span aria-hidden className="size-2.5 shrink-0 rounded-sm" style={{ background: s.fill }} />
                <span className="truncate" title={s.label}>
                  {s.label}
                </span>
                <span className="tabular ml-auto text-ink-2">{formatPercent(s.count, total)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </ChartCard>
  )
}
