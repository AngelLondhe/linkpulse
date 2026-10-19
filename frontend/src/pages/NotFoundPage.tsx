import { Compass } from 'lucide-react'
import { Link } from 'react-router'
import { EmptyState } from '../components/ui'

export function NotFoundPage({ embedded = false }: { embedded?: boolean }) {
  return (
    <div className={embedded ? '' : 'flex min-h-dvh items-center justify-center'}>
      <EmptyState
        icon={<Compass className="size-5" />}
        title="Page not found"
        description="This page doesn't exist, or you don't have access to it."
        action={
          <Link to="/links" className="text-sm font-medium text-accent hover:underline">
            Back to your links
          </Link>
        }
      />
    </div>
  )
}
