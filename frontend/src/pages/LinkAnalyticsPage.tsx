import { ArrowLeft, ExternalLink } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router'
import { BarList } from '../components/charts/BarList'
import { ClicksChart } from '../components/charts/ClicksChart'
import { DonutChart } from '../components/charts/DonutChart'
import { KpiCard } from '../components/charts/KpiCard'
import { Card, CopyButton, ErrorState, Skeleton, StatusBadge } from '../components/ui'
import { useLink, useLinkStats } from '../hooks/useLinks'
import { ApiError } from '../lib/api'
import { RANGES, type RangeKey } from '../lib/dates'
import { countryName, deviceLabel, formatCompact, formatDateTime, formatPercent, prettyUrl } from '../lib/format'
import type { LinkStats } from '../lib/types'
import { NotFoundPage } from './NotFoundPage'

// The map (topojson + projection) is the heaviest piece; load it on demand.
const WorldMap = lazy(() => import('../components/charts/WorldMap').then((m) => ({ default: m.WorldMap })))

function RangeSelector({ value, onChange }: { value: RangeKey; onChange: (key: RangeKey) => void }) {
  return (
    <div role="radiogroup" aria-label="Date range" className="inline-flex rounded-lg border border-line bg-surface p-0.5">
      {RANGES.map((range) => (
        <button
          key={range.key}
          type="button"
          role="radio"
          aria-checked={value === range.key}
          onClick={() => onChange(range.key)}
          className={`rounded-md px-3 py-1.5 text-sm ${
            value === range.key ? 'bg-surface-2 font-medium text-ink' : 'text-ink-2 hover:text-ink'
          }`}
        >
          {range.label}
        </button>
      ))}
    </div>
  )
}

function topLabel(stats: LinkStats, key: 'countries' | 'referrers'): { label: string; share: string } | null {
  const first = stats[key][0]
  if (!first) return null
  const label = key === 'countries' ? countryName(first.label) : first.label
  return { label, share: formatPercent(first.count, stats.total_clicks) }
}

function StatsSkeleton() {
  return (
    <div className="space-y-4" aria-label="Loading analytics">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-80" />
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-52" />
        ))}
      </div>
    </div>
  )
}

function Dashboard({ stats }: { stats: LinkStats }) {
  const topCountry = topLabel(stats, 'countries')
  const topReferrer = topLabel(stats, 'referrers')
  const days = stats.timeseries.length
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard hero label="Clicks" value={formatCompact(stats.total_clicks)} hint={`Last ${days} days`} />
        <KpiCard
          label="Unique visitors"
          value={formatCompact(stats.unique_visitors)}
          hint={stats.total_clicks ? `${(stats.total_clicks / Math.max(1, stats.unique_visitors)).toFixed(1)} clicks per visitor` : undefined}
        />
        <KpiCard label="Top country" value={topCountry?.label ?? '—'} hint={topCountry ? `${topCountry.share} of clicks` : undefined} />
        <KpiCard label="Top referrer" value={topReferrer?.label ?? '—'} hint={`${formatCompact(stats.all_time_clicks)} clicks all time`} />
      </div>

      <ClicksChart data={stats.timeseries} />

      <div className="grid gap-4 lg:grid-cols-3">
        <DonutChart title="By device" buckets={stats.devices} total={stats.total_clicks} labelFor={deviceLabel} />
        <DonutChart title="By browser" buckets={stats.browsers} total={stats.total_clicks} />
        <DonutChart title="By OS" buckets={stats.os} total={stats.total_clicks} />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-2">
        <BarList
          className="h-full"
          title="Top referrers"
          subtitle="Where clicks came from (Direct = no referrer)"
          buckets={stats.referrers}
          total={stats.total_clicks}
        />
        </div>
        <div className="lg:col-span-3">
          <Suspense fallback={<Skeleton className="h-80" />}>
            <WorldMap className="h-full" countries={stats.countries} total={stats.total_clicks} />
          </Suspense>
        </div>
      </div>
    </div>
  )
}

export function LinkAnalyticsPage() {
  const id = Number(useParams().id)
  const [range, setRange] = useState<RangeKey>('30d')
  const link = useLink(id)
  const stats = useLinkStats(id, range)

  if (!Number.isInteger(id) || id < 1) return <NotFoundPage embedded />
  const linkError = link.error instanceof ApiError ? link.error : null
  if (linkError && (linkError.status === 404 || linkError.status === 403)) return <NotFoundPage embedded />

  return (
    <div className="space-y-5">
      <RouterLink to="/links" className="inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> All links
      </RouterLink>

      <Card className="p-4 sm:p-5">
        {link.isPending ? (
          <div className="space-y-2">
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-4 w-80 max-w-full" />
          </div>
        ) : link.isError ? (
          <ErrorState message={link.error.message} onRetry={() => void link.refetch()} />
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-xl font-semibold tracking-tight">{prettyUrl(link.data.short_url)}</h1>
                <CopyButton text={link.data.short_url} label="Copy short link" />
                <StatusBadge active={link.data.is_active} />
              </div>
              <a
                href={link.data.original_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex max-w-full items-center gap-1 text-sm text-ink-2 hover:text-ink"
                title={link.data.original_url}
              >
                <span className="truncate">{link.data.original_url}</span>
                <ExternalLink className="size-3.5 shrink-0" aria-hidden />
              </a>
              <p className="mt-1 text-xs text-muted">Created {formatDateTime(link.data.created_at)}</p>
            </div>
          </div>
        )}
      </Card>

      {/* One filter row scopes every chart below it. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Analytics</h2>
        <RangeSelector value={range} onChange={setRange} />
      </div>

      {stats.isPending ? (
        <StatsSkeleton />
      ) : stats.isError ? (
        <Card>
          <ErrorState message={stats.error.message} onRetry={() => void stats.refetch()} />
        </Card>
      ) : (
        // Keep the previous render (dimmed) while a new range loads: no skeleton flash.
        <div className={`transition-opacity ${stats.isPlaceholderData ? 'opacity-60' : ''}`} aria-busy={stats.isPlaceholderData}>
          <Dashboard stats={stats.data} />
        </div>
      )}
    </div>
  )
}
