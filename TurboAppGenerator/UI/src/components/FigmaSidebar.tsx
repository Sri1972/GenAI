import {
  AlertCircle, ExternalLink, FolderPlus, Layers, Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { useFigmaProjectsCtx } from '../App'
import { api } from '../hooks/useApi'
import { FigmaProject } from '../types'
import ConfirmDialog from './ConfirmDialog'

export default function FigmaSidebar({ activeProject, onSelect }: {
  activeProject: string | null
  onSelect: (name: string | null) => void
}) {
  const { figmaProjects, refreshFigmaProjects } = useFigmaProjectsCtx()
  const [newName,   setNewName]   = useState('')
  const [nameErr,   setNameErr]   = useState('')
  const [creating,  setCreating]  = useState(false)
  const [deletingName, setDeleting] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const validateName = (v: string) => {
    if (!v) return 'Name required'
    if (/\s/.test(v)) return 'No spaces — use hyphens'
    if (!/^[a-zA-Z0-9-]+$/.test(v)) return 'Letters, numbers, hyphens only'
    if (figmaProjects.find(p => p.name === v.toLowerCase())) return 'Name already exists'
    return ''
  }

  const createProject = async () => {
    const err = validateName(newName)
    if (err) { setNameErr(err); return }
    setCreating(true)
    try {
      const p = await api.createFigmaProject(newName)
      setNewName(''); setNameErr('')
      await refreshFigmaProjects()
      onSelect(p.name)
    } catch (e: any) { setNameErr(e.message) }
    finally { setCreating(false) }
  }

  const doDeleteProject = async (name: string) => {
    setConfirmDelete(null)
    setDeleting(name)
    try {
      await api.deleteFigmaProject(name)
      await refreshFigmaProjects()
      if (activeProject === name) onSelect(null)
    } catch {}
    finally { setDeleting(null) }
  }

  return (
    <>
    <aside className="w-52 flex-shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">

      {/* New project form */}
      <div className="px-3 pt-3 pb-2 border-b border-slate-200 flex-shrink-0">
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Layers size={10} className="text-violet-500" /> Mockup Projects
        </div>
        <div className="flex gap-1.5">
          <input
            className="flex-1 bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800
                       placeholder-slate-400 focus:outline-none focus:border-violet-500 transition-colors min-w-0"
            placeholder="new-mockup"
            value={newName}
            onChange={e => { setNewName(e.target.value); setNameErr('') }}
            onKeyDown={e => e.key === 'Enter' && createProject()}
          />
          <button
            onClick={createProject}
            disabled={creating || !newName}
            title="Create mockup project"
            className="flex-shrink-0 p-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40
                       disabled:cursor-not-allowed rounded-md transition-colors"
          >
            {creating
              ? <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin block" />
              : <FolderPlus size={14} className="text-white" />
            }
          </button>
        </div>
        {nameErr && (
          <div className="flex items-center gap-1 mt-1.5 text-xs text-red-600">
            <AlertCircle size={10} />{nameErr}
          </div>
        )}
      </div>

      {/* Project list — minimal rows, details shown in main panel */}
      <div className="flex-1 overflow-y-auto py-1">
        {figmaProjects.length === 0 && (
          <div className="px-4 py-6 text-xs text-slate-500 text-center">
            No mockup projects yet.<br />Type a name above to create one.
          </div>
        )}

        {figmaProjects.map((p: FigmaProject) => {
          const isActive   = activeProject === p.name
          const isDeleting = deletingName === p.name

          return (
            <div
              key={p.name}
              onClick={() => onSelect(p.name)}
              style={isActive ? {boxShadow:'inset -2px 0 0 #7c3aed', background:'rgba(124,58,237,0.08)'} : undefined}
              className={`flex items-center h-9 px-3 cursor-pointer transition-colors group
                ${!isActive ? 'hover:bg-slate-100' : ''}`}
            >
              <span className={`flex-1 min-w-0 text-xs font-medium truncate ${isActive ? 'text-violet-700' : 'text-slate-700'}`}>
                {p.title || p.name}
              </span>

              {/* Screen count badge */}
              {p.screens.length > 0 && (
                <span className="flex-shrink-0 text-xs text-slate-500 mr-1">{p.screens.length}sc</span>
              )}

              {/* Figma link icon — always visible if URL exists */}
              {p.figma_url && (
                <a
                  href={p.figma_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={e => e.stopPropagation()}
                  title="Open in Figma"
                  className="flex-shrink-0 text-slate-500 hover:text-violet-600 transition-colors mr-1"
                >
                  <ExternalLink size={11} />
                </a>
              )}

              {/* Delete — shows on hover */}
              <button
                onClick={e => { e.stopPropagation(); setConfirmDelete(p.name) }}
                disabled={isDeleting}
                title="Delete project"
                className="flex-shrink-0 opacity-0 group-hover:opacity-100 p-0.5 rounded
                           text-slate-400 hover:text-red-600 transition-all disabled:opacity-40"
              >
                {isDeleting
                  ? <span className="w-2.5 h-2.5 rounded-full border border-red-400 border-t-transparent animate-spin block" />
                  : <Trash2 size={11} />}
              </button>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-slate-200 flex-shrink-0">
        <div className="text-xs text-slate-500">{figmaProjects.length} project{figmaProjects.length !== 1 ? 's' : ''}</div>
      </div>
    </aside>

    <ConfirmDialog
      open={!!confirmDelete}
      title={`Delete "${confirmDelete}"?`}
      message="This Figma mockup project will be permanently removed."
      details={[
        'All saved prompts and build history will be deleted',
        'Cannot be undone',
      ]}
      confirmLabel="Delete"
      danger
      onConfirm={() => confirmDelete && doDeleteProject(confirmDelete)}
      onCancel={() => setConfirmDelete(null)}
    />
    </>
  )
}
