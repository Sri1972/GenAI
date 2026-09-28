import { useEffect, useState } from 'react'
import { AlertCircle, Check, ChevronDown, ChevronRight, ExternalLink, FolderPlus, Pencil, Play, Square, Trash2, BookOpen, X } from 'lucide-react'
import { api } from '../hooks/useApi'
import { McpProjectEntry } from '../types'
import ConfirmDialog from './ConfirmDialog'

const STATUS_DOT: Record<string, string> = {
  draft: 'bg-slate-300',
  running: 'bg-emerald-500',
  stopped: 'bg-slate-300',
  start_failed: 'bg-red-500',
}

interface Props {
  activeProject: string | null
  onSelect: (name: string | null) => void
}

export default function McpSidebar({ activeProject, onSelect }: Props) {
  const [projects, setProjects] = useState<McpProjectEntry[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmName, setConfirmName] = useState<string | null>(null)
  const [deleteErr, setDeleteErr] = useState<{ name: string; message: string } | null>(null)
  const [newName, setNewName] = useState('')
  const [nameErr, setNameErr] = useState('')
  const [creating, setCreating] = useState(false)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [renameErr, setRenameErr] = useState('')

  const refresh = () => { api.listMcpProjects().then(setProjects).catch(() => {}) }

  const validateName = (v: string) => {
    if (!v) return 'Name required'
    if (/\s/.test(v)) return 'No spaces — use hyphens'
    if (!/^[a-zA-Z0-9-]+$/.test(v)) return 'Letters, numbers, hyphens only'
    if (projects.find(p => p.name === v.toLowerCase())) return 'Name already exists'
    return ''
  }

  const createProject = async () => {
    const err = validateName(newName)
    if (err) { setNameErr(err); return }
    setCreating(true)
    try {
      const { name } = await api.createMcpProject(newName)
      setNewName(''); setNameErr('')
      refresh()
      setExpanded(name)
      onSelect(name)
    } catch (e: any) { setNameErr(e.message) }
    finally { setCreating(false) }
  }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (activeProject) setExpanded(activeProject)
  }, [activeProject])

  const start = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setBusy(name)
    try { await api.startMcpProject(name) } finally { setBusy(null); refresh() }
  }
  const stop = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setBusy(name)
    try { await api.stopMcpProject(name) } finally { setBusy(null); refresh() }
  }
  const doDelete = async (name: string) => {
    setConfirmName(null)
    setBusy(name)
    setDeleteErr(null)
    try {
      await api.deleteMcpProject(name)
      if (activeProject === name) onSelect(null)
    } catch (e: any) {
      setDeleteErr({ name, message: e?.message || 'Delete failed.' })
    } finally { setBusy(null); refresh() }
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
      const res = await api.renameMcpProject(oldName, renameValue)
      cancelRename()
      refresh()
      if (activeProject === oldName) onSelect(res.name)
    } catch (e: any) {
      setRenameErr(e.message)
    }
  }

  return (
    <>
      <aside className="w-56 flex-shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">
        <div className="px-3 pt-3 pb-1 flex-shrink-0">
          <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
            MCP Servers
          </div>
        </div>

        <div className="px-3 pt-3 pb-2 border-b border-slate-200 flex-shrink-0">
          <div className="flex gap-1.5">
            <input
              className="flex-1 bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800
                         placeholder-slate-400 focus:outline-none focus:border-amber-500 transition-colors min-w-0"
              placeholder="new-mcp-name"
              value={newName}
              onChange={e => { setNewName(e.target.value); setNameErr('') }}
              onKeyDown={e => e.key === 'Enter' && createProject()}
            />
            <button
              onClick={createProject}
              disabled={creating || !newName}
              title="Create MCP project"
              className="flex-shrink-0 p-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40
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

        <div className="flex-1 overflow-y-auto py-1">
          {projects.length === 0 && (
            <div className="px-4 py-6 text-xs text-slate-500 text-center">
              No MCP servers yet.<br />Type a name above to create one.
            </div>
          )}

          {projects.map(p => {
            const isActive = activeProject === p.name
            const isExpanded = expanded === p.name
            const isBusy = busy === p.name
            const isRenaming = renaming === p.name

            return (
              <div key={p.name}>
                <div
                  onClick={() => {
                    if (isRenaming) return
                    setExpanded(isExpanded ? null : p.name); onSelect(p.name)
                  }}
                  style={isActive ? { boxShadow: 'inset -2px 0 0 #d97706', background: 'rgba(217,119,6,0.1)' } : undefined}
                  className={`flex items-center h-8 px-3 cursor-pointer transition-colors ${!isActive ? 'hover:bg-slate-100' : ''}`}
                >
                  <span className="w-4 flex-shrink-0 flex items-center justify-center text-slate-500">
                    {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                  </span>
                  {isRenaming ? (
                    <div className="flex-1 flex items-center gap-1 ml-1.5 min-w-0" onClick={e => e.stopPropagation()}>
                      <input
                        className="flex-1 min-w-0 bg-white border border-amber-400 rounded px-1.5 py-0.5 text-xs text-slate-800
                                   focus:outline-none focus:ring-1 focus:ring-amber-500"
                        value={renameValue}
                        onChange={e => { setRenameValue(e.target.value); setRenameErr('') }}
                        onKeyDown={e => {
                          if (e.key === 'Enter') doRename(p.name)
                          if (e.key === 'Escape') cancelRename()
                        }}
                        autoFocus
                      />
                      <button onClick={() => doRename(p.name)} className="text-amber-600 hover:text-amber-700">
                        <Check size={12} />
                      </button>
                      <button onClick={cancelRename} className="text-slate-400 hover:text-slate-600">
                        <X size={12} />
                      </button>
                    </div>
                  ) : (
                    <span className={`flex-1 min-w-0 text-xs font-medium truncate ml-1.5 ${isActive ? 'text-amber-700' : 'text-slate-700'}`}>
                      {p.title || p.name}
                    </span>
                  )}
                  <span className="w-3 flex-shrink-0 flex items-center justify-center ml-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[p.status] || 'bg-slate-300'}`} />
                  </span>
                </div>

                {isRenaming && renameErr && (
                  <div className="pl-7 pr-3 py-1 text-xs text-red-500 flex items-center gap-1">
                    <AlertCircle size={10} />{renameErr}
                  </div>
                )}

                {isExpanded && (
                  <div className="bg-white border-b border-slate-200 pl-7 pr-3 py-2 space-y-2">
                    {p.status === 'draft' ? (
                      <p className="text-xs text-slate-500 italic">Not generated yet — configure and generate in the panel on the right.</p>
                    ) : (
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 flex-wrap">
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200">
                          {p.sourceType === 'datastore' ? 'SQLite datastore' : 'External API'}
                        </span>
                        {p.backingApiProject && (
                          <span className="px-1.5 py-0.5 rounded bg-slate-100 border border-slate-200 truncate" title="Backing API — see the Web API tab">
                            API: {p.backingApiProject}
                          </span>
                        )}
                      </div>
                    )}

                    {p.status !== 'draft' && (
                      <div className="flex items-center gap-1.5">
                        {p.status === 'running'
                          ? <span className="text-xs text-emerald-600 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />Running
                            </span>
                          : <span className="text-xs text-slate-500">{p.status === 'start_failed' ? 'Failed to start' : 'Stopped'}</span>
                        }
                        {p.port && <span className="text-xs text-slate-500 ml-auto">:{p.port}</span>}
                      </div>
                    )}

                    {p.status === 'running' && p.port && (
                      <div className="flex gap-1.5">
                        <a href={`http://localhost:${p.port}/mcp`} target="_blank" rel="noreferrer"
                           onClick={e => e.stopPropagation()}
                           className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-amber-50 hover:bg-amber-100
                                      text-amber-700 border border-amber-200 transition-colors flex-1 justify-center">
                          <ExternalLink size={11} /> MCP endpoint
                        </a>
                        <a href={`http://localhost:${p.port}/docs`} target="_blank" rel="noreferrer"
                           onClick={e => e.stopPropagation()}
                           className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-indigo-50 hover:bg-indigo-100
                                      text-indigo-700 border border-indigo-200 transition-colors flex-1 justify-center">
                          <BookOpen size={11} /> Docs
                        </a>
                      </div>
                    )}

                    <div className="flex gap-1.5">
                      {p.status === 'draft' ? null : p.status === 'running'
                        ? <button onClick={e => stop(p.name, e)} disabled={isBusy}
                            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-slate-100 hover:bg-slate-200
                                       text-slate-600 hover:text-slate-800 transition-colors disabled:opacity-40 flex-1 justify-center">
                            {isBusy ? <span className="w-2.5 h-2.5 rounded-full border border-slate-400 border-t-transparent animate-spin" /> : <Square size={11} />}
                            Stop
                          </button>
                        : <button onClick={e => start(p.name, e)} disabled={isBusy}
                            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-amber-50 hover:bg-amber-100
                                       text-amber-700 hover:text-amber-800 border border-amber-200 transition-colors disabled:opacity-40 flex-1 justify-center">
                            {isBusy ? <span className="w-2.5 h-2.5 rounded-full border border-amber-400 border-t-transparent animate-spin" /> : <Play size={11} />}
                            Start
                          </button>
                      }
                      <button onClick={e => startRename(p.name, e)} disabled={isBusy}
                        title="Rename project"
                        className="p-1.5 rounded bg-slate-50 hover:bg-slate-100 text-slate-500 hover:text-slate-700 border border-slate-200
                                   transition-colors disabled:opacity-40">
                        <Pencil size={11} />
                      </button>
                      <button onClick={e => { e.stopPropagation(); setConfirmName(p.name) }} disabled={isBusy}
                        title="Delete project"
                        className="p-1.5 rounded bg-red-50 hover:bg-red-100 text-red-600 hover:text-red-700 border border-red-200
                                   transition-colors disabled:opacity-40">
                        <Trash2 size={11} />
                      </button>
                    </div>

                    {deleteErr?.name === p.name && (
                      <div className="flex items-start gap-1 text-xs text-red-500">
                        <AlertCircle size={10} className="flex-shrink-0 mt-0.5" />{deleteErr.message}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="px-4 py-3 border-t border-slate-200 flex-shrink-0">
          <div className="text-xs text-slate-500">v1.0 · FastMCP / Streamable HTTP</div>
        </div>
      </aside>

      <ConfirmDialog
        open={!!confirmName}
        title={`Delete "${confirmName}"?`}
        message="This MCP server project and all its files will be permanently removed."
        details={[
          'Stop the running dev server',
          'Delete all files in mcp-servers/<project>/',
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
