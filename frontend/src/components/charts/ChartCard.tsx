import { BarChart3, Table2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Card } from '../ui'

export interface TableView {
  columns: [string, string, ...string[]]
  rows: (string | number)[][]
}

/**
 * Card wrapper every chart sits in. The table toggle is the accessible twin of the chart:
 * every value is readable without hovering or relying on colour.
 */
export function ChartCard({
  title,
  subtitle,
  table,
  children,
  className = '',
}: {
  title: string
  subtitle?: string
  table: TableView
  children: ReactNode
  className?: string
}) {
  const [showTable, setShowTable] = useState(false)
  return (
    <Card className={`flex flex-col p-4 sm:p-5 ${className}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          aria-pressed={showTable}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-ink-2 hover:bg-surface-2 hover:text-ink"
        >
          {showTable ? <BarChart3 className="size-3.5" aria-hidden /> : <Table2 className="size-3.5" aria-hidden />}
          {showTable ? 'Chart' : 'Table'}
        </button>
      </div>
      {showTable ? <DataTable table={table} /> : children}
    </Card>
  )
}

function DataTable({ table }: { table: TableView }) {
  if (table.rows.length === 0) return <p className="py-6 text-center text-sm text-muted">No data</p>
  return (
    <div className="max-h-80 overflow-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-surface text-left text-xs text-muted">
          <tr>
            {table.columns.map((column, i) => (
              <th key={column} scope="col" className={`py-1.5 font-medium ${i > 0 ? 'text-right' : ''}`}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="tabular">
          {table.rows.map((row) => (
            <tr key={String(row[0])} className="border-t border-line">
              {row.map((cell, i) => (
                <td key={i} className={`py-1.5 ${i > 0 ? 'text-right text-ink-2' : ''}`}>
                  {typeof cell === 'number' ? cell.toLocaleString('en') : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ChartEmpty({ message = 'No clicks in this period' }: { message?: string }) {
  return (
    <div className="flex h-full min-h-40 items-center justify-center rounded-lg border border-dashed border-line text-sm text-muted">
      {message}
    </div>
  )
}

/** Shared tooltip surface. Text uses ink tokens; colour lives only in the swatch. */
export function TooltipBox({ title, rows }: { title: string; rows: { color: string; label: string; value: string }[] }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-ink">{title}</p>
      {rows.map((row) => (
        <p key={row.label} className="flex items-center gap-2 text-ink-2">
          <span aria-hidden className="size-2 rounded-full" style={{ background: row.color }} />
          <span>{row.label}</span>
          <span className="tabular ml-auto pl-3 font-medium text-ink">{row.value}</span>
        </p>
      ))}
    </div>
  )
}
