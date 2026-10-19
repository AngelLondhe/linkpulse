import { useMemo, useState } from 'react'
import { ComposableMap, Geographies, Geography } from 'react-simple-maps'
import world from 'world-atlas/countries-110m.json'
import { countryName, countryNumericId, formatNumber, formatPercent } from '../../lib/format'
import type { Bucket } from '../../lib/types'
import { ChartCard, ChartEmpty, TooltipBox } from './ChartCard'

// One-hue sequential ramp (light -> dark in light mode, dim -> bright in dark mode).
const STEPS = ['var(--seq-1)', 'var(--seq-2)', 'var(--seq-3)', 'var(--seq-4)', 'var(--seq-5)']

/** Square-root binning so one dominant country doesn't wash every other one out. */
function stepFor(count: number, max: number): string {
  const index = Math.min(STEPS.length - 1, Math.floor(Math.sqrt(count / max) * STEPS.length))
  return STEPS[Math.max(0, index)]
}

interface Hover {
  name: string
  count: number
  x: number
  y: number
}

export function WorldMap({
  countries,
  total,
  className,
}: {
  countries: Bucket[]
  total: number
  className?: string
}) {
  const [hover, setHover] = useState<Hover | null>(null)
  const known = countries.filter((c) => c.label !== 'Unknown')
  const max = Math.max(1, ...known.map((c) => c.count))
  const byNumericId = useMemo(() => {
    const map = new Map<string, Bucket>()
    for (const bucket of known) {
      const id = countryNumericId(bucket.label)
      if (id) map.set(id, bucket)
    }
    return map
  }, [known])

  return (
    <ChartCard
      className={className}
      title="Countries"
      subtitle="Top 10 countries by clicks"
      table={{
        columns: ['Country', 'Clicks', 'Share'],
        rows: countries.map((c) => [countryName(c.label), c.count, formatPercent(c.count, total)]),
      }}
    >
      {countries.length === 0 ? (
        <ChartEmpty />
      ) : (
        <div className="relative" onMouseLeave={() => setHover(null)}>
          <ComposableMap
            projection="geoEqualEarth"
            projectionConfig={{ scale: 150 }}
            width={800}
            height={380}
            className="h-auto w-full"
            aria-label="World map of clicks by country"
          >
            <Geographies geography={world as unknown as Parameters<typeof Geographies>[0]['geography']}>
              {({ geographies }) =>
                geographies
                  .filter((geo) => geo.properties?.name !== 'Antarctica')
                  .map((geo) => {
                    const bucket = byNumericId.get(String(geo.id))
                    const name = bucket ? countryName(bucket.label) : String(geo.properties?.name ?? '')
                    const show = (x: number, y: number) =>
                      bucket ? setHover({ name, count: bucket.count, x, y }) : setHover(null)
                    return (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        tabIndex={bucket ? 0 : -1}
                        aria-label={bucket ? `${name}: ${bucket.count} clicks` : undefined}
                        fill={bucket ? stepFor(bucket.count, max) : 'var(--seq-empty)'}
                        stroke="var(--surface)"
                        strokeWidth={0.5}
                        onMouseMove={(e) => {
                          const rect = e.currentTarget.ownerSVGElement?.parentElement?.getBoundingClientRect()
                          if (rect) show(e.clientX - rect.left, e.clientY - rect.top)
                        }}
                        onFocus={() => show(16, 16)}
                        onBlur={() => setHover(null)}
                        className={`outline-none ${bucket ? 'cursor-pointer hover:opacity-80 focus-visible:opacity-80' : ''}`}
                      />
                    )
                  })
              }
            </Geographies>
          </ComposableMap>
          {hover && (
            <div
              className="pointer-events-none absolute z-10"
              style={{ left: Math.min(hover.x + 12, 9999), top: hover.y + 12 }}
            >
              <TooltipBox
                title={hover.name}
                rows={[{ color: 'var(--seq-4)', label: formatPercent(hover.count, total), value: formatNumber(hover.count) }]}
              />
            </div>
          )}
          <div className="mt-2 flex items-center justify-end gap-2 text-xs text-muted" aria-hidden>
            <span>Fewer</span>
            {STEPS.map((step) => (
              <span key={step} className="h-2 w-5 rounded-sm" style={{ background: step }} />
            ))}
            <span>More</span>
          </div>
        </div>
      )}
    </ChartCard>
  )
}
