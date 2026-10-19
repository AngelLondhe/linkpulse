import { AlertTriangle, Check, Copy, Loader2 } from 'lucide-react'
import { useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { toast } from 'sonner'
import { copyText } from '../lib/clipboard'
import type { LinkStatus } from '../lib/types'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent hover:bg-accent-hover',
  secondary: 'border border-line bg-surface text-ink hover:bg-surface-2',
  ghost: 'text-ink-2 hover:bg-surface-2 hover:text-ink',
  danger: 'bg-danger text-white hover:opacity-90',
}

export function Button({
  variant = 'secondary',
  loading = false,
  className = '',
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-line bg-surface ${className}`}>{children}</section>
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-surface-2 ${className}`} />
}

export function CopyButton({ text, label = 'Copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        if (await copyText(text)) {
          setCopied(true)
          toast.success('Copied to clipboard')
          window.setTimeout(() => setCopied(false), 1500)
        } else {
          toast.error('Could not copy. Select the link and copy it manually.')
        }
      }}
      className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-ink-2 hover:bg-surface-2 hover:text-ink"
      aria-label={`${label} ${text}`}
      title={label}
    >
      {copied ? <Check className="size-4 text-good" aria-hidden /> : <Copy className="size-4" aria-hidden />}
    </button>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-surface-2 p-3 text-ink-2">{icon}</div>
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-ink-2">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-12 text-center">
      <AlertTriangle className="mb-2 size-6 text-danger" aria-hidden />
      <p className="font-medium">Something went wrong</p>
      <p className="mt-1 text-sm text-ink-2">{message}</p>
      {onRetry && (
        <Button className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

const STATUS: Record<LinkStatus, { label: string; dot: string; text: string }> = {
  active: { label: 'Active', dot: 'bg-good', text: 'text-ink' },
  paused: { label: 'Paused', dot: 'bg-muted', text: 'text-muted' },
  expired: { label: 'Expired', dot: 'bg-danger', text: 'text-ink-2' },
  limit_reached: { label: 'Limit reached', dot: 'bg-danger', text: 'text-ink-2' },
}

/** Status is never colour-only: the dot always comes with a text label. */
export function StatusBadge({ status }: { status: LinkStatus }) {
  const { label, dot, text } = STATUS[status]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium whitespace-nowrap ${text}`}>
      <span aria-hidden className={`size-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  )
}
