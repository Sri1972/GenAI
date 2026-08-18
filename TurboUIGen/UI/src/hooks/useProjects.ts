import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './useApi'
import { Project } from '../types'

export function useProjects(refreshKey: number) {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading]   = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try { setProjects(await api.listProjects()) } catch {}
    finally { setLoading(false) }
  }, [])

  // Refresh on key change
  useEffect(() => { refresh() }, [refresh, refreshKey])

  // Poll every 5s to keep running/stopped status current
  // This handles: API restart, external stops, port checks
  useEffect(() => {
    timerRef.current = setInterval(refresh, 5000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [refresh])

  return { projects, loading, refresh }
}
