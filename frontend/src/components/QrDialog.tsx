import { Download, QrCode } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { api } from '../lib/api'
import type { Link } from '../lib/types'
import { Button, Skeleton } from './ui'

async function download(link: Link, format: 'png' | 'svg') {
  try {
    const blob = await api.linkQr(link.id, format)
    const url = URL.createObjectURL(blob)
    const anchor = Object.assign(document.createElement('a'), { href: url, download: `${link.short_code}-qr.${format}` })
    anchor.click()
    URL.revokeObjectURL(url)
  } catch {
    toast.error('Could not download the QR code')
  }
}

export function QrButton({ link }: { link: Link }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [open, setOpen] = useState(false)
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let url: string | null = null
    api
      .linkQr(link.id, 'svg')
      .then((blob) => {
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      .catch(() => toast.error('Could not load the QR code'))
    dialog.current?.showModal()
    return () => {
      if (url) URL.revokeObjectURL(url)
      setSrc(null)
    }
  }, [open, link.id])

  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <QrCode className="size-4" aria-hidden /> QR code
      </Button>
      <dialog
        ref={dialog}
        onClose={() => setOpen(false)}
        onClick={(e) => e.target === dialog.current && dialog.current?.close()}
        aria-label="QR code"
        className="m-auto w-[min(92vw,22rem)] rounded-xl border border-line bg-surface p-0 text-ink backdrop:bg-black/40"
      >
        <div className="p-5">
          <h2 className="font-semibold">QR code</h2>
          <p className="mt-1 truncate text-sm text-ink-2">{link.short_url}</p>
          {/* QR codes need dark modules on a light background to scan, in either theme. */}
          <div className="mt-4 rounded-lg bg-white p-3">
            {src ? (
              <img src={src} alt={`QR code for ${link.short_url}`} className="mx-auto aspect-square w-full max-w-64" />
            ) : (
              <Skeleton className="mx-auto aspect-square w-full max-w-64" />
            )}
          </div>
          <div className="mt-4 flex gap-2">
            <Button className="flex-1" onClick={() => void download(link, 'png')}>
              <Download className="size-4" aria-hidden /> PNG
            </Button>
            <Button className="flex-1" onClick={() => void download(link, 'svg')}>
              <Download className="size-4" aria-hidden /> SVG
            </Button>
          </div>
          <Button variant="ghost" className="mt-2 w-full" onClick={() => dialog.current?.close()}>
            Close
          </Button>
        </div>
      </dialog>
    </>
  )
}
