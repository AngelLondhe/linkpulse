import { BarChart3, ChevronDown, ChevronLeft, ChevronRight, Link2, Lock, Pause, Play, Search, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link as RouterLink, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Button, Card, CopyButton, EmptyState, ErrorState, Skeleton, StatusBadge } from '../components/ui'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { PAGE_SIZE, useCreateLink, useDeleteLink, useLinkList, useUpdateLink } from '../hooks/useLinks'
import { ApiError } from '../lib/api'
import { copyText } from '../lib/clipboard'
import { formatDateTime, formatNumber, formatRelative, prettyUrl } from '../lib/format'
import type { Link, LinkCreateInput } from '../lib/types'

const inputClass = 'w-full rounded-lg border border-line bg-page px-3 py-2 text-sm'

function toLocalInputValue(date: Date): string {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return shifted.toISOString().slice(0, 16)
}

function CreateLinkForm() {
  const [url, setUrl] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [alias, setAlias] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [maxClicks, setMaxClicks] = useState('')
  const [password, setPassword] = useState('')
  const [minExpiry] = useState(() => toLocalInputValue(new Date()))
  const [error, setError] = useState<string | null>(null)
  const create = useCreateLink()

  function buildInput(): LinkCreateInput {
    const input: LinkCreateInput = { url: url.trim() }
    if (alias.trim()) input.custom_alias = alias.trim()
    // <input type="datetime-local"> is in local time; send an absolute, tz-aware instant.
    if (expiresAt) input.expires_at = new Date(expiresAt).toISOString()
    if (maxClicks) input.max_clicks = Number(maxClicks)
    if (password) input.password = password
    return input
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const link = await create.mutateAsync(buildInput())
      setUrl('')
      setAlias('')
      setExpiresAt('')
      setMaxClicks('')
      setPassword('')
      const copied = await copyText(link.short_url)
      toast.success(copied ? 'Short link created and copied' : 'Short link created', {
        description: link.short_url,
      })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the link.')
    }
  }

  return (
    <Card className="p-4 sm:p-5">
      <form onSubmit={onSubmit}>
        <div className="flex flex-col gap-3 sm:flex-row">
          <label className="sr-only" htmlFor="long-url">
            Long URL
          </label>
          <div className="relative flex-1">
            <Link2 className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              id="long-url"
              type="url"
              inputMode="url"
              required
              placeholder="Paste a long URL, e.g. https://example.com/a/very/long/path"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? 'create-error' : undefined}
              className="w-full rounded-lg border border-line bg-page py-2.5 pr-3 pl-9 text-sm"
            />
          </div>
          <Button type="submit" variant="primary" loading={create.isPending} disabled={!url.trim()}>
            Shorten
          </Button>
        </div>

        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
          aria-controls="advanced-options"
          className="mt-3 inline-flex items-center gap-1 text-sm text-ink-2 hover:text-ink"
        >
          <ChevronDown className={`size-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} aria-hidden />
          Advanced options
        </button>

        {showAdvanced && (
          <div id="advanced-options" className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block text-sm">
              <span className="font-medium">Custom alias</span>
              <input
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
                placeholder="my-launch"
                pattern="[a-zA-Z0-9_\-]{3,30}"
                title="3-30 letters, digits, - or _"
                className={`mt-1 ${inputClass}`}
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Expires at</span>
              <input
                type="datetime-local"
                value={expiresAt}
                min={minExpiry}
                onChange={(e) => setExpiresAt(e.target.value)}
                className={`mt-1 ${inputClass}`}
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Max clicks</span>
              <input
                type="number"
                min={1}
                inputMode="numeric"
                value={maxClicks}
                onChange={(e) => setMaxClicks(e.target.value)}
                placeholder="Unlimited"
                className={`mt-1 ${inputClass}`}
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Password</span>
              <input
                type="password"
                autoComplete="new-password"
                minLength={4}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="None"
                className={`mt-1 ${inputClass}`}
              />
            </label>
          </div>
        )}
      </form>
      {error && (
        <p id="create-error" role="alert" className="mt-2 text-sm text-danger">
          {error}
        </p>
      )}
    </Card>
  )
}

function ClickCount({ link }: { link: Link }) {
  return (
    <span className="tabular">
      {formatNumber(link.total_clicks)}
      {link.max_clicks !== null && <span className="text-muted"> / {formatNumber(link.max_clicks)}</span>}
    </span>
  )
}

function RowActions({ link, onDelete }: { link: Link; onDelete: (link: Link) => void }) {
  const update = useUpdateLink()
  const toggle = async () => {
    try {
      await update.mutateAsync({ id: link.id, is_active: !link.is_active })
      toast.success(link.is_active ? 'Link paused: it will return 404 until resumed' : 'Link resumed')
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Update failed')
    }
  }
  const iconButton = 'inline-flex size-8 items-center justify-center rounded-md text-ink-2 hover:bg-surface-2 hover:text-ink'
  return (
    <div className="flex items-center justify-end gap-0.5">
      <RouterLink to={`/links/${link.id}`} className={iconButton} title="Analytics" aria-label={`Analytics for ${link.short_code}`}>
        <BarChart3 className="size-4" aria-hidden />
      </RouterLink>
      <button
        type="button"
        className={iconButton}
        onClick={toggle}
        disabled={update.isPending}
        title={link.is_active ? 'Pause' : 'Resume'}
        aria-label={`${link.is_active ? 'Pause' : 'Resume'} ${link.short_code}`}
      >
        {link.is_active ? <Pause className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}
      </button>
      <button
        type="button"
        className={`${iconButton} hover:text-danger`}
        onClick={() => onDelete(link)}
        title="Delete"
        aria-label={`Delete ${link.short_code}`}
      >
        <Trash2 className="size-4" aria-hidden />
      </button>
    </div>
  )
}

function ShortLink({ link }: { link: Link }) {
  return (
    <div className="flex min-w-0 items-center gap-1">
      <a
        href={link.short_url}
        target="_blank"
        rel="noreferrer"
        className="truncate font-medium text-accent hover:underline"
        title={link.short_url}
      >
        {prettyUrl(link.short_url)}
      </a>
      {link.has_password && (
        <Lock className="size-3.5 shrink-0 text-muted" aria-label="Password protected" />
      )}
      <CopyButton text={link.short_url} label="Copy short link" />
    </div>
  )
}

function LinksTable({ links, onDelete }: { links: Link[]; onDelete: (link: Link) => void }) {
  return (
    <>
      {/* Desktop table */}
      <table className="hidden w-full table-fixed text-sm md:table">
        <thead className="text-left text-xs text-muted">
          <tr className="border-b border-line">
            <th scope="col" className="w-[26%] px-5 py-2.5 font-medium">Short link</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Destination</th>
            <th scope="col" className="w-24 px-3 py-2.5 text-right font-medium">Clicks</th>
            <th scope="col" className="w-32 px-3 py-2.5 font-medium">Created</th>
            <th scope="col" className="w-32 px-3 py-2.5 font-medium">Status</th>
            <th scope="col" className="w-32 px-5 py-2.5"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {links.map((link) => (
            <tr key={link.id} className="border-b border-line last:border-0 hover:bg-surface-2/50">
              <td className="px-5 py-2"><ShortLink link={link} /></td>
              <td className="truncate px-3 py-2 text-ink-2" title={link.original_url}>{prettyUrl(link.original_url)}</td>
              <td className="px-3 py-2 text-right"><ClickCount link={link} /></td>
              <td className="px-3 py-2 whitespace-nowrap text-ink-2" title={formatDateTime(link.created_at)}>{formatRelative(link.created_at)}</td>
              <td className="px-3 py-2"><StatusBadge status={link.status} /></td>
              <td className="px-5 py-2"><RowActions link={link} onDelete={onDelete} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Mobile cards */}
      <ul className="divide-y divide-line md:hidden">
        {links.map((link) => (
          <li key={link.id} className="space-y-1.5 px-4 py-3">
            <div className="flex items-center justify-between gap-2">
              <ShortLink link={link} />
              <StatusBadge status={link.status} />
            </div>
            <p className="truncate text-sm text-ink-2" title={link.original_url}>{prettyUrl(link.original_url)}</p>
            <div className="flex items-center justify-between text-xs text-muted">
              <span>
                <span className="font-medium text-ink"><ClickCount link={link} /></span> clicks ·{' '}
                {formatRelative(link.created_at)}
              </span>
              <RowActions link={link} onDelete={onDelete} />
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}

function TableSkeleton() {
  return (
    <div className="space-y-3 p-5" aria-label="Loading links">
      {Array.from({ length: 5 }, (_, i) => (
        <div key={i} className="flex items-center gap-4">
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-12" />
        </div>
      ))}
    </div>
  )
}

export function LinksPage() {
  const [params, setParams] = useSearchParams()
  const page = Math.max(1, Number(params.get('page')) || 1)
  const [search, setSearch] = useState(params.get('q') ?? '')
  const q = useDebouncedValue(search.trim(), 300)
  const { data, isPending, isError, error, refetch, isPlaceholderData } = useLinkList(q, page)
  const [toDelete, setToDelete] = useState<Link | null>(null)
  const remove = useDeleteLink()

  const updateParams = (next: { q?: string; page?: number }) => {
    const merged = new URLSearchParams(params)
    if (next.q) merged.set('q', next.q)
    else if (next.q !== undefined) merged.delete('q')
    if (next.page && next.page > 1) merged.set('page', String(next.page))
    else if (next.page !== undefined) merged.delete('page')
    setParams(merged, { replace: true })
  }

  async function confirmDelete() {
    if (!toDelete) return
    try {
      await remove.mutateAsync(toDelete.id)
      toast.success('Link deleted')
      setToDelete(null)
      if (data && data.items.length === 1 && page > 1) updateParams({ page: page - 1 })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Delete failed')
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const first = data && data.total > 0 ? (page - 1) * PAGE_SIZE + 1 : 0
  const last = data ? Math.min(page * PAGE_SIZE, data.total) : 0

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your links</h1>
        <p className="mt-1 text-sm text-ink-2">Create short links and track every click.</p>
      </div>

      <CreateLinkForm />

      <Card>
        <div className="flex flex-col gap-3 border-b border-line px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <h2 className="text-sm font-semibold">
            All links{data ? <span className="ml-1.5 font-normal text-muted">({formatNumber(data.total)})</span> : null}
          </h2>
          <div className="relative sm:w-72">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              type="search"
              placeholder="Search URL or code"
              aria-label="Search links"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                updateParams({ q: e.target.value.trim(), page: 1 })
              }}
              className="w-full rounded-lg border border-line bg-page py-2 pr-3 pl-9 text-sm"
            />
          </div>
        </div>

        <div className={`transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`} aria-busy={isPlaceholderData}>
          {isPending ? (
            <TableSkeleton />
          ) : isError ? (
            <ErrorState message={error.message} onRetry={() => void refetch()} />
          ) : data.items.length === 0 ? (
            q ? (
              <EmptyState icon={<Search className="size-5" />} title="No matching links" description={`Nothing matches “${q}”.`} />
            ) : (
              <EmptyState
                icon={<Link2 className="size-5" />}
                title="No links yet"
                description="Paste a long URL above to create your first short link."
              />
            )
          ) : (
            <LinksTable links={data.items} onDelete={setToDelete} />
          )}
        </div>

        {data && data.total > PAGE_SIZE && (
          <nav className="flex items-center justify-between border-t border-line px-4 py-3 text-sm sm:px-5" aria-label="Pagination">
            <span className="tabular text-ink-2">
              {first}–{last} of {formatNumber(data.total)}
            </span>
            <div className="flex gap-2">
              <Button onClick={() => updateParams({ page: page - 1 })} disabled={page <= 1} aria-label="Previous page">
                <ChevronLeft className="size-4" aria-hidden /> Prev
              </Button>
              <Button onClick={() => updateParams({ page: page + 1 })} disabled={page >= totalPages} aria-label="Next page">
                Next <ChevronRight className="size-4" aria-hidden />
              </Button>
            </div>
          </nav>
        )}
      </Card>

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this link?"
        confirmLabel="Delete link"
        loading={remove.isPending}
        onConfirm={() => void confirmDelete()}
        onClose={() => setToDelete(null)}
      >
        <span className="font-medium text-ink">{toDelete && prettyUrl(toDelete.short_url)}</span> will stop working
        immediately and its click history will be permanently removed.
      </ConfirmDialog>
    </div>
  )
}
