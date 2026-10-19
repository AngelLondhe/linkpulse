import { formatNumber, formatPercent } from '../../lib/format'
import type { Bucket } from '../../lib/types'
import { ChartCard, ChartEmpty } from './ChartCard'

/**
 * Horizontal bars in a single hue (one series => one colour, never a value ramp).
 * Bars are 20px thick with a 4px rounded data-end; the value sits at the tip.
 */
export function BarList({
  title,
  subtitle,
  buckets,
  total,
  labelFor = (raw) => raw,
  className,
}: {
  className?: string
  title: string
  subtitle?: string
  buckets: Bucket[]
  total: number
  labelFor?: (raw: string) => string
}) {
  const max = Math.max(1, ...buckets.map((b) => b.count))
  return (
    <ChartCard
      className={className}
      title={title}
      subtitle={subtitle}
      table={{
        columns: ['Source', 'Clicks', 'Share'],
        rows: buckets.map((b) => [labelFor(b.label), b.count, formatPercent(b.count, total)]),
      }}
    >
      {buckets.length === 0 ? (
        <ChartEmpty />
      ) : (
        <ul className="space-y-2">
          {buckets.map((b) => (
            <li
              key={b.label}
              className="group grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 sm:grid-cols-[minmax(0,12rem)_1fr]"
              title={`${labelFor(b.label)}: ${formatNumber(b.count)} clicks (${formatPercent(b.count, total)})`}
            >
              <span className="truncate text-sm">{labelFor(b.label)}</span>
              <span className="flex items-center gap-2">
                <span
                  className="h-5 rounded-r bg-[var(--series-1)] transition-opacity group-hover:opacity-80"
                  style={{ width: `${Math.max(2, (b.count / max) * 85)}%` }}
                />
                <span className="tabular text-xs text-ink-2">{formatNumber(b.count)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </ChartCard>
  )
}
