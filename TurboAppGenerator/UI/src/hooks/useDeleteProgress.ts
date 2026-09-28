import { useCallback, useRef, useState } from 'react'
import { api } from './useApi'

/**
 * Wraps api.delete() with live progress polling. delete_project() can take
 * up to ~90s (subprocess calls, retries, sleeps for OneDrive/Vite file-lock
 * release) — without this, that wait looks identical to "nothing is
 * happening", which is what made it easy to assume a delete had finished (or
 * hung) and fire another action against the same project name too early.
 */
export function useDeleteProgress() {
  const [deletingName, setDeletingName] = useState<string | null>(null)
  const [deleteLog, setDeleteLog]       = useState<string[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
  }, [])

  const deleteProject = useCallback(async (name: string) => {
    setDeletingName(name)
    setDeleteLog([])
    timerRef.current = setInterval(async () => {
      try { setDeleteLog((await api.getDeleteProgress(name)).log) } catch {}
    }, 500)
    try {
      await api.delete(name)
    } finally {
      stopPolling()
      setDeletingName(null)
      setDeleteLog([])
    }
  }, [stopPolling])

  return { deletingName, deleteLog, deleteProject }
}
