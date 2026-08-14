import { useState, useEffect, useCallback, useRef } from 'react'

interface ApiResponse<T> {
  data: T[]
  total: number
  limit: number
  offset: number
  hasMore: boolean
}

interface AggregateResponse {
  data?: { group: string; value: number }[]
  value?: number
}

interface UseApiOptions {
  limit?: number
  offset?: number
  sort?: string
  order?: 'asc' | 'desc'
  filter?: string
  autoFetch?: boolean
}

interface UseApiResult<T> {
  data: T[]
  total: number
  loading: boolean
  error: string | null
  hasMore: boolean
  refetch: () => void
  fetchMore: () => void
}

const _API_BASE = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

export function useApi<T = Record<string, unknown>>(
  table: string,
  options: UseApiOptions = {}
): UseApiResult<T> {
  const { limit = 100, offset = 0, sort, order = 'asc', filter, autoFetch = true } = options
  const [data, setData] = useState<T[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const currentOffset = useRef(offset)

  const buildUrl = useCallback((off: number) => {
    const params = new URLSearchParams()
    params.set('limit', String(limit))
    params.set('offset', String(off))
    if (sort) params.set('sort', sort)
    if (order) params.set('order', order)
    if (filter) params.set('filter', filter)
    return `${_API_BASE}/api/data/${table}?${params.toString()}`
  }, [table, limit, sort, order, filter])

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(buildUrl(offset))
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const json: ApiResponse<T> = await res.json()
      setData(json.data)
      setTotal(json.total)
      setHasMore(json.hasMore)
      currentOffset.current = offset + json.data.length
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [buildUrl, offset])

  const fetchMore = useCallback(async () => {
    if (!hasMore || loading) return
    setLoading(true)
    try {
      const res = await fetch(buildUrl(currentOffset.current))
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const json: ApiResponse<T> = await res.json()
      setData(prev => [...prev, ...json.data])
      setHasMore(json.hasMore)
      currentOffset.current += json.data.length
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [buildUrl, hasMore, loading])

  useEffect(() => {
    if (autoFetch) fetchData()
  }, [fetchData, autoFetch])

  return { data, total, loading, error, hasMore, refetch: fetchData, fetchMore }
}

export async function apiAggregate(
  table: string,
  options: { groupBy?: string; metric?: string; column?: string; filter?: string; limit?: number } = {}
): Promise<AggregateResponse> {
  const params = new URLSearchParams()
  if (options.groupBy) params.set('groupBy', options.groupBy)
  if (options.metric) params.set('metric', options.metric)
  if (options.column) params.set('column', options.column)
  if (options.filter) params.set('filter', options.filter)
  if (options.limit) params.set('limit', String(options.limit))
  const res = await fetch(`${_API_BASE}/api/data/${table}/aggregate?${params.toString()}`)
  if (!res.ok) throw new Error(`Aggregate API error: ${res.status}`)
  return res.json()
}

export async function apiMetadata(): Promise<{ tables: Array<{ table: string; rowCount: number; columns: Array<{ name: string; type: string }> }> }> {
  const res = await fetch(`${_API_BASE}/api/metadata`)
  if (!res.ok) throw new Error(`Metadata API error: ${res.status}`)
  return res.json()
}
