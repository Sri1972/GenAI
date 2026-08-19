import {
  AlertCircle, Check, ChevronDown, ChevronRight,
  ExternalLink, FolderPlus, Info, Pencil, Play, Square, Trash2, X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectsCtx } from '../App'
import { api } from '../hooks/useApi'
import ConfirmDialog from './ConfirmDialog'

// ── Source badge ──────────────────────────────────────────────────────────────
const SOURCE_STYLES: Record<string, string> = {
  'figma':        'bg-purple-50 text-purple-700 border-purple-200',
  'figma+prompt': 'bg-indigo-50 text-indigo-700 border-indigo-200',
  'prompt':       'bg-slate-100 text-slate-600 border-slate-200',
}

function SourceBadge({ source = 'prompt', label = 'Instructions', figmaUrl = '', prompt = '' }: {
  source?: string; label?: string; figmaUrl?: string; prompt?: string
}) {
  const style = SOURCE_STYLES[source] || SOURCE_STYLES['prompt']
  const tooltip = [
    source.includes('figma') && figmaUrl ? `Figma: ${figmaUrl.slice(0, 60)}…` : '',
    prompt ? `Prompt: ${prompt.slice(0, 80)}${prompt.length > 80 ? '…' : ''}` : '',
  ].filter(Boolean).join('\n')

  return (
    <div className="flex items-center gap-1.5 group relative w-fit">
      <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded border font-medium ${style}`}>
        {source.includes('figma') && <span style={{fontSize:9}}>▲</span>}
        {label}
      </span>
      {tooltip && (
        <>
          <Info size={10} className="text-slate-500 cursor-help flex-shrink-0" />
          <div className="absolute left-0 top-full mt-1 z-50 hidden group-hover:block
                          w-56 bg-white border border-slate-200 rounded-lg p-2.5
                          text-xs text-slate-600 leading-relaxed shadow-xl whitespace-pre-wrap">
            {tooltip}
          </div>
        </>
      )}
    </div>
  )
}

export default function Sidebar() {
  const { setPreviewUrl: onPreview } = useProjectsCtx()
  const { name: activeProject } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const { projects, busyMap, genMap, setBusy, refresh } = useProjectsCtx()
  const [expanded,     setExpanded]     = useState<string | null>(null)
  const [newName,      setNewName]      = useState('')
  const [nameErr,      setNameErr]      = useState('')
  const [creating,     setCreating]     = useState(false)
  const [confirmName,  setConfirmName]  = useState<string | null>(null)
  const [renaming,     setRenaming]     = useState<string | null>(null)
  const [renameValue,  setRenameValue]  = useState('')
  const [renameErr,    setRenameErr]    = useState('')

  // Auto-expand the active project
  useEffect(() => {
    if (activeProject) setExpanded(activeProject)
  }, [activeProject])

  const isProjectBusy = (name: string) => !!busyMap[name]

  const validateName = (v: string) => {
    if (!v) return 'Name required'
    if (/\s/.test(v)) return 'No spaces — use hyphens'
    if (!/^[a-zA-Z0-9-]+$/.test(v)) return 'Letters, numbers, hyphens only'
    if (projects.find((p: { name: string }) => p.name === v.toLowerCase())) return 'Name already exists'
    return ''
  }

  const createProject = async () => {
    const err = validateName(newName)
    if (err) { setNameErr(err); return }
    setCreating(true)
    try {
      await api.createProject(newName)
      const slug = newName.toLowerCase()
      setNewName(''); setNameErr('')
      await refresh()
      setExpanded(slug)
      navigate(`/project/${slug}`)
    } catch (e: any) { setNameErr(e.message) }
    finally { setCreating(false) }
  }

  const startP = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (isProjectBusy(name)) return
    setBusy(name, 'starting')
    try {
      const r = await api.start(name)
      if (r.url) onPreview(r.url)
    } catch {}
    setBusy(name, null)
  }

  const stopP = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (isProjectBusy(name)) return
    setBusy(name, 'stopping')
    try { await api.stop(name) } catch {}
    setBusy(name, null)
  }

  const deleteP = (name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (isProjectBusy(name)) return
    setConfirmName(name)
  }

  const doDelete = async (name: string) => {
    setConfirmName(null)
    setBusy(name, 'deleting')
    try {
      await api.delete(name)
      refresh()
      navigate('/')
    } catch {}
    setBusy(name, null)
  }

  const startRename = (name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setRenaming(name)
    setRenameValue(name)
    setRenameErr('')
  }

  const cancelRename = () => {
    setRenaming(null)
    setRenameValue('')
    setRenameErr('')
  }

  const doRename = async (oldName: string) => {
    const err = validateName(renameValue)
    if (err && renameValue.toLowerCase() !== oldName) { setRenameErr(err); return }
    if (renameValue.toLowerCase() === oldName) { cancelRename(); return }
    try {
      const res = await api.rename(oldName, renameValue)
      cancelRename()
      refresh()
      if (activeProject === oldName) {
        navigate(`/project/${res.name}`)
      }
    } catch (e: any) {
      setRenameErr(e.message)
    }
  }

  return (
    <>
    <aside className="w-56 flex-shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">

      {/* Section label */}
      <div className="px-3 pt-3 pb-1 flex-shrink-0">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
          App Projects
        </div>
      </div>

      {/* New project form */}
      <div className="px-3 pt-3 pb-2 border-b border-slate-200 flex-shrink-0">
        <div className="flex gap-1.5">
          <input
            className="flex-1 bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800
                       placeholder-slate-400 focus:outline-none focus:border-indigo-500 transition-colors min-w-0"
            placeholder="new-project"
            value={newName}
            onChange={e => { setNewName(e.target.value); setNameErr('') }}
            onKeyDown={e => e.key === 'Enter' && createProject()}
          />
          <button
            onClick={createProject}
            disabled={creating || !newName}
            title="Create project"
            className="flex-shrink-0 p-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40
                       disabled:cursor-not-allowed rounded-md transition-colors"
          >
            {creating
              ? <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin block" />
              : <FolderPlus size={14} className="text-white" />
            }
          </button>
        </div>
        {nameErr && (
          <div className="flex items-center gap-1 mt-1.5 text-xs text-red-400">
            <AlertCircle size={10} />{nameErr}
          </div>
        )}
      </div>

      {/* Project list */}
      <div className="flex-1 overflow-y-auto py-1">
        {projects.length === 0 && (
          <div className="px-4 py-6 text-xs text-slate-500 text-center">
            No projects yet.<br />Type a name above to create one.
          </div>
        )}

        {projects.map(p => {
          const isActive   = activeProject === p.name
          const isExpanded = expanded === p.name
          const isBusy     = busyMap[p.name] ?? null
          const isRenaming = renaming === p.name

          return (
            <div key={p.name}>
              {/* Project row */}
              <div
                onClick={() => {
                  if (isRenaming) return
                  setExpanded(isExpanded ? null : p.name)
                  if (activeProject !== p.name) {
                    navigate(`/project/${p.name}`)
                  }
                }}
                style={isActive ? {boxShadow:'inset -2px 0 0 #6366f1', background:'rgba(99,102,241,0.1)'} : undefined}
                className={`flex items-center h-8 px-3 cursor-pointer transition-colors
                  ${!isActive ? 'hover:bg-slate-100' : ''}`}
              >
                {/* Chevron */}
                <span className="w-4 flex-shrink-0 flex items-center justify-center text-slate-500">
                  {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                </span>

                {/* Name or rename input */}
                {isRenaming ? (
                  <div className="flex-1 flex items-center gap-1 ml-1.5 min-w-0" onClick={e => e.stopPropagation()}>
                    <input
                      className="flex-1 min-w-0 bg-white border border-indigo-400 rounded px-1.5 py-0.5 text-xs text-slate-800
                                 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      value={renameValue}
                      onChange={e => { setRenameValue(e.target.value); setRenameErr('') }}
                      onKeyDown={e => {
                        if (e.key === 'Enter') doRename(p.name)
                        if (e.key === 'Escape') cancelRename()
                      }}
                      autoFocus
                    />
                    <button onClick={() => doRename(p.name)} className="text-emerald-600 hover:text-emerald-700">
                      <Check size={12} />
                    </button>
                    <button onClick={cancelRename} className="text-slate-400 hover:text-slate-600">
                      <X size={12} />
                    </button>
                  </div>
                ) : (
                  <span className={`flex-1 min-w-0 text-xs font-medium truncate ml-1.5 ${isActive ? 'text-indigo-700' : 'text-slate-700'}`}>
                    {p.name}
                  </span>
                )}

                {/* Status indicator */}
                <span className="w-3 flex-shrink-0 flex items-center justify-center ml-1">
                  {genMap[p.name]?.loading
                    ? <span className="w-2 h-2 rounded-full border border-indigo-400 border-t-transparent animate-spin" />
                    : <span className={`w-1.5 h-1.5 rounded-full ${p.running ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                  }
                </span>
              </div>

              {/* Rename error */}
              {isRenaming && renameErr && (
                <div className="pl-7 pr-3 py-1 text-xs text-red-500 flex items-center gap-1">
                  <AlertCircle size={10} />{renameErr}
                </div>
              )}

              {/* Expanded details — same left indent as name column (pl-7 = 28px) */}
              {isExpanded && (
                <div className="bg-white border-b border-slate-200 pl-7 pr-3 py-2 space-y-2">

                  {/* Source badge */}
                  {p.hasApp && p.sourceLabel && (
                    <SourceBadge source={p.source} label={p.sourceLabel} figmaUrl={p.figmaUrl} prompt={p.prompt} />
                  )}

                  {/* Busy status message */}
                  {isBusy && (
                    <div className="flex items-center gap-1.5 text-xs font-medium
                      bg-amber-50 rounded px-2 py-1 text-amber-700 border border-amber-200">
                      <span className="w-2 h-2 rounded-full border border-amber-400 border-t-transparent animate-spin flex-shrink-0" />
                      {isBusy === 'starting'  && 'Starting server…'}
                      {isBusy === 'stopping'  && 'Stopping server…'}
                      {isBusy === 'deleting'  && 'Deleting project…'}
                    </div>
                  )}

                  {/* Status + URL */}
                  <div className="flex items-center gap-1.5">
                    {genMap[p.name]?.loading
                      ? <span className="text-xs text-indigo-600 flex items-center gap-1">
                          <span className="w-2 h-2 rounded-full border border-indigo-400 border-t-transparent animate-spin" />Building…
                        </span>
                      : p.running
                        ? <span className="text-xs text-emerald-600 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />Running
                          </span>
                        : <span className="text-xs text-slate-500">Stopped</span>
                    }
                    {p.hasApp && p.port && !genMap[p.name]?.loading && (
                      <span className="text-xs text-slate-500 ml-auto">:{p.port}</span>
                    )}
                  </div>

                  {/* URL — only show when ready, not during build */}
                  {p.running && p.url && !genMap[p.name]?.loading && (
                    <div className="flex items-center gap-1 min-w-0">
                      <span className="text-xs text-indigo-600 font-mono truncate flex-1">{p.url}</span>
                    </div>
                  )}

                  {/* Actions — app controls (only when app exists AND not building) */}
                  {p.hasApp && !genMap[p.name]?.loading && (
                    <div className="flex gap-1.5">
                      {p.running && p.url && (
                        <button
                          onClick={e => { e.stopPropagation(); onPreview(p.url!) }}
                          className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-indigo-50 hover:bg-indigo-100
                                     text-indigo-700 border border-indigo-200 transition-colors flex-1 justify-center"
                        >
                          <ExternalLink size={11} /> Preview
                        </button>
                      )}
                      {p.running
                        ? <button
                            onClick={e => stopP(p.name, e)}
                            disabled={!!isBusy}
                            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-slate-100 hover:bg-slate-200
                                       text-slate-600 hover:text-slate-800 transition-colors disabled:opacity-40 flex-1 justify-center"
                          >
                            {isBusy === 'stopping'
                              ? <span className="w-2.5 h-2.5 rounded-full border border-slate-400 border-t-transparent animate-spin" />
                              : <Square size={11} />}
                            Stop
                          </button>
                        : <button
                            onClick={e => startP(p.name, e)}
                            disabled={!!isBusy}
                            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-emerald-50 hover:bg-emerald-100
                                       text-emerald-700 hover:text-emerald-800 border border-emerald-200 transition-colors disabled:opacity-40 flex-1 justify-center"
                          >
                            {isBusy === 'starting'
                              ? <span className="w-2.5 h-2.5 rounded-full border border-emerald-400 border-t-transparent animate-spin" />
                              : <Play size={11} />}
                            Start
                          </button>
                      }
                    </div>
                  )}

                  {!p.hasApp && (
                    genMap[p.name]?.loading
                      ? <div className="flex items-center gap-1.5 text-xs text-indigo-700 bg-indigo-50 rounded px-2 py-1 border border-indigo-200">
                          <span className="w-2 h-2 rounded-full border border-indigo-400 border-t-transparent animate-spin flex-shrink-0" />
                          Building… {genMap[p.name]?.step ?? ''}
                        </div>
                      : <p className="text-xs text-slate-500 italic">No app generated yet</p>
                  )}

                  {/* Rename / Delete — always available */}
                  <div className="flex gap-1.5 pt-1">
                    <button
                      onClick={e => startRename(p.name, e)}
                      disabled={!!isBusy}
                      title="Rename project"
                      className="p-1.5 rounded bg-slate-50 hover:bg-slate-100 text-slate-500 hover:text-slate-700 border border-slate-200
                                 transition-colors disabled:opacity-40"
                    >
                      <Pencil size={11} />
                    </button>
                    <button
                      onClick={e => deleteP(p.name, e)}
                      disabled={!!isBusy}
                      title="Delete project"
                      className="p-1.5 rounded bg-red-50 hover:bg-red-100 text-red-600 hover:text-red-700 border border-red-200
                                 transition-colors disabled:opacity-40"
                    >
                      {isBusy === 'deleting'
                        ? <span className="w-2.5 h-2.5 rounded-full border border-red-400 border-t-transparent animate-spin block" />
                        : <Trash2 size={11} />}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-200 flex-shrink-0">
        <div className="text-xs text-slate-500">v1.0 · React + TypeScript</div>
      </div>
    </aside>

    <ConfirmDialog
      open={!!confirmName}
      title={`Delete "${confirmName}"?`}
      message="This project and all its files will be permanently removed."
      details={[
        'Stop the running dev server',
        `Delete all files in generated/${confirmName}/`,
        'Remove node_modules and all generated source files',
        'This cannot be undone',
      ]}
      confirmLabel="Delete"
      danger
      onConfirm={() => confirmName && doDelete(confirmName)}
      onCancel={() => setConfirmName(null)}
    />
    </>
  )
}
