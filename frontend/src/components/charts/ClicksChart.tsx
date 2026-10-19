import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { formatCompact, formatDay, formatNumber } from '../../lib/format'
import type { TimeseriesPoint } from '../../lib/types'
import { ChartCard, ChartEmpty, TooltipBox } from './ChartCard'

const CLICKS = 'var(--series-1)'
const UNIQUES = 'var(--series-2)'

interface TooltipProps {
  active?: boolean
  label?: string
  payload?: { payload: TimeseriesPoint }[]
}

function TimeTooltip({ active, payload }: TooltipProps) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <TooltipBox
      title={formatDay(point.date)}
      rows={[
        { color: CLICKS, label: 'Clicks', value: formatNumber(point.clicks) },
        { color: UNIQUES, label: 'Unique visitors', value: formatNumber(point.unique_visitors) },
      ]}
    />
  )
}

function LegendKey({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
      <span aria-hidden className="h-0.5 w-3.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}

export function ClicksChart({ data }: { data: TimeseriesPoint[] }) {
  const hasClicks = data.some((d) => d.clicks > 0)
  return (
    <ChartCard
      title="Clicks over time"
      subtitle="Daily clicks and unique visitors"
      table={{
        columns: ['Date', 'Clicks', 'Unique visitors'],
        rows: data.map((d) => [formatDay(d.date), d.clicks, d.unique_visitors]),
      }}
    >
      <div className="mb-2 flex gap-4">
        <LegendKey color={CLICKS} label="Clicks" />
        <LegendKey color={UNIQUES} label="Unique visitors" />
      </div>
      {hasClicks ? (
        <div className="h-64 sm:h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid vertical={false} stroke="var(--grid)" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDay}
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={{ stroke: 'var(--axis)' }}
                minTickGap={24}
              />
              <YAxis
                allowDecimals={false}
                tickFormatter={formatCompact}
                tick={{ fill: 'var(--muted)', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <Tooltip content={<TimeTooltip />} cursor={{ stroke: 'var(--axis)', strokeWidth: 1 }} />
              <Area
                type="monotone"
                dataKey="clicks"
                name="Clicks"
                stroke={CLICKS}
                strokeWidth={2}
                fill={CLICKS}
                fillOpacity={0.1}
                dot={false}
                activeDot={{ r: 4, fill: CLICKS, stroke: 'var(--surface)', strokeWidth: 2 }}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="unique_visitors"
                name="Unique visitors"
                stroke={UNIQUES}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: UNIQUES, stroke: 'var(--surface)', strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-64 sm:h-72">
          <ChartEmpty />
        </div>
      )}
    </ChartCard>
  )
}
