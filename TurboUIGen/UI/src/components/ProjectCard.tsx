import { ExternalLink, Play, Square, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '../hooks/useApi'
import { Project } from '../types'
import ConfirmDialog from './ConfirmDialog'

interface Props {
  project: Project
  onPreview: (url: string) => void
  onRefresh: () => void
}

type Busy = 'starting' | 'stopping' | 'deleting' | null

export default function ProjectCard({ project, onPreview, onRefresh }: Props) {
  const [busy,          setBusy]          = useState<Busy>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const start = async () => {
    setBusy('starting')
    try { const r = await api.start(project.name); onRefresh(); if (r.url) onPreview(r.url) }
    catch (e: any) { alert(e.message) }
    finally { setBusy(null) }
  }

  const stop = async () => {
    setBusy('stopping')
    try { await api.stop(project.name); onRefresh() }
    catch (e: any) { alert(e.message) }
    finally { setBusy(null) }
  }

  const doDelete = async () => {
    setConfirmDelete(false)
    setBusy('deleting')
    try { await api.delete(project.name); onRefresh() }
    catch (e: any) { alert(e.message) }
    finally { setBusy(null) }
  }

  return (
    <>
    <div className="card p-4 flex flex-col gap-3 animate-fade-in">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-semibold text-sm text-slate-900 truncate">{project.title || project.name}</div>
          <div className="text-xs text-slate-500 font-mono mt-0.5 truncate">{project.name}</div>
        </div>
        {project.running
          ? <span className="badge-running flex-shrink-0"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />Running</span>
          : <span className="badge-stopped flex-shrink-0"><span className="w-1.5 h-1.5 rounded-full bg-slate-600" />Stopped</span>
        }
      </div>

      {project.running && project.url && (
        <div className="text-xs text-indigo-600 hover:text-indigo-700 cursor-pointer truncate flex items-center gap-1"
          onClick={() => onPreview(project.url!)}>
          <ExternalLink size={11} />{project.url}
        </div>
      )}

      <div className="flex gap-3 text-xs text-slate-600">
        <span>{project.files} files</span>
        {project.port && <span>port {project.port}</span>}
      </div>

      <div className="flex gap-2">
        {project.running ? (
          <>
            <button onClick={() => onPreview(project.url!)} className="btn-primary flex-1 justify-center text-xs">
              <ExternalLink size={13} /> Preview
            </button>
            <button onClick={stop} disabled={!!busy} className="btn-ghost flex-1 justify-center text-xs">
              {busy === 'stopping' ? <span className="w-3 h-3 rounded-full border border-slate-400 border-t-transparent animate-spin" /> : <Square size={13} />}
              {busy === 'stopping' ? 'Stopping…' : 'Stop'}
            </button>
          </>
        ) : (
          <button onClick={start} disabled={!!busy} className="btn-success flex-1 justify-center text-xs">
            {busy === 'starting' ? <span className="w-3 h-3 rounded-full border border-emerald-400 border-t-transparent animate-spin" /> : <Play size={13} />}
            {busy === 'starting' ? 'Starting…' : 'Start'}
          </button>
        )}
        <button onClick={() => setConfirmDelete(true)} disabled={!!busy} className="btn-danger px-2.5" title="Delete project">
          {busy === 'deleting' ? <span className="w-3 h-3 rounded-full border border-red-400 border-t-transparent animate-spin" /> : <Trash2 size={13} />}
        </button>
      </div>
    </div>

    <ConfirmDialog
      open={confirmDelete}
      title={`Delete "${project.name}"?`}
      message="This project and all its files will be permanently removed."
      details={['Delete all generated files', 'Cannot be undone']}
      confirmLabel="Delete"
      danger
      onConfirm={doDelete}
      onCancel={() => setConfirmDelete(false)}
    />
    </>
  )
}
