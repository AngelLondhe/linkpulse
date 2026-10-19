import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { LinkCreateInput } from '../lib/types'
import type { RangeKey } from '../lib/dates'
import { rangeParams } from '../lib/dates'

export const PAGE_SIZE = 10

export const linkKeys = {
  all: ['links'] as const,
  list: (q: string, page: number) => ['links', 'list', { q, page }] as const,
  detail: (id: number) => ['links', 'detail', id] as const,
  stats: (id: number, range: RangeKey, bots: boolean) => ['links', 'stats', id, range, bots] as const,
}

export function useLinkList(q: string, page: number) {
  return useQuery({
    queryKey: linkKeys.list(q, page),
    queryFn: () => api.listLinks({ q: q || undefined, page, pageSize: PAGE_SIZE }),
    placeholderData: keepPreviousData, // no skeleton flash while paging/searching
  })
}

export function useLink(id: number) {
  return useQuery({ queryKey: linkKeys.detail(id), queryFn: () => api.getLink(id) })
}

export function useLinkStats(id: number, range: RangeKey, includeBots: boolean) {
  return useQuery({
    queryKey: linkKeys.stats(id, range, includeBots),
    queryFn: () => api.linkStats(id, rangeParams(range), includeBots),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000, // "real-time": new clicks show up without a reload
  })
}

function useInvalidateLinks() {
  const client = useQueryClient()
  return () => client.invalidateQueries({ queryKey: linkKeys.all })
}

export function useCreateLink() {
  const invalidate = useInvalidateLinks()
  return useMutation({ mutationFn: (input: LinkCreateInput) => api.createLink(input), onSuccess: invalidate })
}

export function useUpdateLink() {
  const invalidate = useInvalidateLinks()
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: number; url?: string; is_active?: boolean }) =>
      api.updateLink(id, changes),
    onSuccess: invalidate,
  })
}

export function useDeleteLink() {
  const invalidate = useInvalidateLinks()
  return useMutation({ mutationFn: (id: number) => api.deleteLink(id), onSuccess: invalidate })
}
