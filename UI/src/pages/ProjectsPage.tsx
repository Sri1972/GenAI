import { AlertCircle, ArrowRight, FolderPlus, Layers, Play, Square, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../hooks/useApi'
import { useProjects } from '../hooks/useProjects'
import { Project } from '../types'
import ConfirmDialog from '../components/ConfirmDialog'

interface Props { refreshKey: number; onRefresh: () => void }

export default function ProjectsPage({ refreshKey, onRefresh }: Props) {
  const { projects, loading, refresh } = useProjects(refreshKey)
  const [newName,     setNewName]   = useState('')
  const [nameError,   setNameError] = useState('')
  const [creating,    setCreating]  = useState(false)
  const [busy,        setBusy]      = useState<Record<string, string>>({})
  const [confirmP,    setConfirmP]  = useState<Project | null>(null)
  const navigate = useNavigate()

  const validateName = (v: string) => {
    if (!v) return 'Project name is required'
    if (/\s/.test(v)) return 'No spaces allowed — use hyphens (e.g. my-project)'
    if (!/^[a-zA-Z0-9-]+$/.test(v)) return 'Only letters, numbers and hyphens'
    if (projects.find(p => p.name === v.toLowerCase())) return 'A project with this name already exists'
    return ''
  }

  const createProject = async () => {
    const err = validateName(newName)
    if (err) { setNameError(err); return }
    setCreating(true)
    try {
      await api.createProject(newName)
      setNewName(''); setNameError('')
      onRefresh()
      navigate(`/project/${newName.toLowerCase()}`)
    } catch (e: any) { setNameError(e.message) }
    finally { setCreating(false) }
  }

  const startP = async (p: Project) => {
    setBusy(b => ({ ...b, [p.name]: 'starting' }))
    try { await api.start(p.name); refresh() } catch {}
    setBusy(b => ({ ...b, [p.name]: '' }))
  }

  const stopP = async (p: Project) => {
    setBusy(b => ({ ...b, [p.name]: 'stopping' }))
    try { await api.stop(p.name); refresh() } catch {}
    setBusy(b => ({ ...b, [p.name]: '' }))
  }

  const doDelete = async (p: Project) => {
    setConfirmP(null)
    setBusy(b => ({ ...b, [p.name]: 'deleting' }))
    try { await api.delete(p.name); refresh(); onRefresh() } catch {}
    setBusy(b => ({ ...b, [p.name]: '' }))
  }

  return (
    <>
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-3xl mx-auto space-y-8">

        <div>
          <h1 className="text-2xl font-extrabold text-slate-800 flex items-center gap-3">
            <Layers size={22} className="text-indigo-400" /> Projects
          </h1>
          <p className="text-slate-500 text-sm mt-1">Create a project, then generate your app inside it</p>
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <FolderPlus size={16} className="text-indigo-400" />
            <span className="font-semibold text-sm text-slate-700">New Project</span>
          </div>
          <div className="flex gap-3 items-start">
            <div className="flex-1">
              <input
                className="input"
                placeholder="my-project (no spaces)"
                value={newName}
                onChange={e => { setNewName(e.target.value); setNameError('') }}
                onKeyDown={e => e.key === 'Enter' && createProject()}
              />
              {nameError && (
                <div className="flex items-center gap-1.5 mt-2 text-xs text-red-400">
                  <AlertCircle size={12} /> {nameError}
                </div>
              )}
              <p className="text-xs text-slate-600 mt-1.5">Use lowercase letters, numbers and hyphens only</p>
            </div>
            <button onClick={createProject} disabled={creating || !newName} className="btn-primary py-2 px-4">
              {creating
                ? <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                : <><FolderPlus size={14} /> Create</>
              }
            </button>
          </div>
        </div>

        {loading && <div className="text-slate-600 text-sm">Loading…</div>}

        {!loading && projects.length === 0 && (
          <div className="text-center py-16 text-slate-600">
            <FolderPlus size={40} className="mx-auto mb-3 opacity-30" />
            <div className="font-medium">No projects yet</div>
            <div className="text-sm mt-1">Create your first project above</div>
          </div>
        )}

        <div className="space-y-3">
          {projects.map(p => (
            <div key={p.name} className="card p-4 flex items-center gap-4 hover:border-slate-300 transition-colors">
              <div className="flex-1 min-w-0 cursor-pointer" onClick={() => navigate(`/project/${p.name}`)}>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-slate-800">{p.name}</span>
                  {p.hasApp
                    ? <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">app ready</span>
                    : <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">no app yet</span>
                  }
                  {p.running && <span className="badge-running"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />running</span>}
                </div>
                {p.url && p.running && <div className="text-xs text-indigo-400 mt-0.5">{p.url}</div>}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => navigate(`/project/${p.name}`)} className="btn-ghost text-xs gap-1">
                  Open <ArrowRight size={12} />
                </button>
                {p.hasApp && (
                  p.running
                    ? <button onClick={() => stopP(p)} disabled={!!busy[p.name]} className="btn-ghost text-xs">
                        {busy[p.name] === 'stopping' ? '…' : <><Square size={12} /> Stop</>}
                      </button>
                    : <button onClick={() => startP(p)} disabled={!!busy[p.name]} className="btn-success text-xs">
                        {busy[p.name] === 'starting' ? '…' : <><Play size={12} /> Start</>}
                      </button>
                )}
                <button onClick={() => setConfirmP(p)} disabled={!!busy[p.name]} className="btn-danger p-1.5" title="Delete">
                  {busy[p.name] === 'deleting' ? '…' : <Trash2 size={13} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>

    <ConfirmDialog
      open={!!confirmP}
      title={`Delete "${confirmP?.name}"?`}
      message="This project and all its files will be permanently removed."
      details={['Delete all generated files', 'Cannot be undone']}
      confirmLabel="Delete"
      danger
      onConfirm={() => confirmP && doDelete(confirmP)}
      onCancel={() => setConfirmP(null)}
    />
    </>
  )
}
