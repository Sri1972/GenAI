import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FolderPlus, Folder, Trash2, ArrowRight, Layers, Zap, Users, Clock, AlertCircle } from 'lucide-react'
import { workspaces, WorkspaceProject } from '../hooks/useApi'
import ConfirmDialog from '../components/ConfirmDialog'

function timeAgo(iso: string): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const secs = Math.max(0, (Date.now() - then) / 1000)
  if (secs < 60) return 'just now'
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}

export default function HomePage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<WorkspaceProject[]>([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const refresh = async () => {
    try { setProjects(await workspaces.list()) } catch {}
    finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, [])

  const create = async () => {
    const n = name.trim()
    if (!n) { setErr('Give your project a name'); return }
    setCreating(true); setErr('')
    try {
      const p = await workspaces.create(n, description.trim())
      navigate(`/p/${p.slug}`)
    } catch (e: any) {
      setErr(e?.message || 'Could not create project')
    } finally { setCreating(false) }
  }

  const doDelete = async (slug: string) => {
    setConfirmDelete(null)
    try { await workspaces.remove(slug); refresh() } catch {}
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Brand row */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-5xl mx-auto flex items-center gap-3 px-6 py-4">
          <img src="/logo.png" alt="Mobility Global" className="h-9 w-auto"
               onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
          <div className="w-px h-7 bg-slate-200" />
          <div>
            <div className="text-slate-800 font-bold text-sm tracking-tight leading-none">TurboUIGen</div>
            <div className="text-slate-500 text-xs mt-0.5">One workspace · brainstorm, prototype, and build</div>
          </div>
        </div>
      </header>

      <main className="flex-1 w-full max-w-5xl mx-auto px-6 py-10">
        {/* Create */}
        <section className="mb-10">
          <h1 className="text-2xl font-semibold text-slate-800 tracking-tight mb-1">Your projects</h1>
          <p className="text-sm text-slate-500 mb-5">
            A project is a shared workspace — the same files flow across the roundtable, the app builder, and everything else you do here.
          </p>
          <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="flex-1 min-w-0">
                <input
                  value={name} onChange={e => { setName(e.target.value); setErr('') }}
                  onKeyDown={e => e.key === 'Enter' && create()}
                  placeholder="New project name…"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-200"
                />
                <input
                  value={description} onChange={e => setDescription(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && create()}
                  placeholder="Short description (optional)"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm mt-2 focus:outline-none focus:ring-2 focus:ring-violet-200"
                />
              </div>
              <button
                onClick={create} disabled={creating || !name.trim()}
                className="flex items-center justify-center gap-2 px-5 py-2 h-[38px] rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-40 shrink-0"
              >
                <FolderPlus size={15} /> {creating ? 'Creating…' : 'Create project'}
              </button>
            </div>
            {err && (
              <div className="flex items-center gap-1.5 mt-2 text-xs text-red-500">
                <AlertCircle size={11} />{err}
              </div>
            )}
          </div>
        </section>

        {/* List */}
        <section>
          {loading ? (
            <div className="text-sm text-slate-400 py-10 text-center">Loading projects…</div>
          ) : projects.length === 0 ? (
            <div className="border border-dashed border-slate-300 rounded-xl py-14 text-center">
              <Folder className="w-8 h-8 mx-auto mb-3 text-slate-300" />
              <p className="text-sm text-slate-500">No projects yet. Create one above to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map(p => (
                <div key={p.slug}
                     className="group bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:border-violet-300 hover:shadow transition-all cursor-pointer"
                     onClick={() => navigate(`/p/${p.slug}`)}>
                  <div className="flex items-start gap-2.5">
                    <div className="w-9 h-9 rounded-lg bg-violet-50 grid place-items-center shrink-0">
                      <Folder className="w-4.5 h-4.5 text-violet-600" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-slate-800 text-sm truncate">{p.name}</div>
                      <div className="text-xs text-slate-400 truncate">{p.slug}</div>
                    </div>
                    <button
                      title="Delete project"
                      onClick={e => { e.stopPropagation(); setConfirmDelete(p.slug) }}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600 transition-all"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  {p.description && (
                    <p className="text-xs text-slate-500 mt-2.5 line-clamp-2">{p.description}</p>
                  )}
                  <div className="flex items-center gap-3 mt-3 pt-3 border-t border-slate-100 text-xs text-slate-400">
                    <span className="flex items-center gap-1"><Zap size={11} />{p.webapps.length} app{p.webapps.length === 1 ? '' : 's'}</span>
                    <span className="flex items-center gap-1"><Layers size={11} />{p.inputs.length} file{p.inputs.length === 1 ? '' : 's'}</span>
                    <span className="flex items-center gap-1 ml-auto"><Clock size={11} />{timeAgo(p.updated || p.created)}</span>
                  </div>
                  <div className="flex items-center gap-1 mt-3 text-xs font-medium text-violet-600 opacity-0 group-hover:opacity-100 transition-opacity">
                    Open <ArrowRight size={12} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Legacy access */}
        <section className="mt-12 pt-6 border-t border-slate-200">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Users size={12} />
            <span>Looking for apps built before projects existed?</span>
            <button onClick={() => navigate('/legacy')} className="text-violet-600 hover:underline font-medium">
              Open the legacy web-app workspace
            </button>
          </div>
        </section>
      </main>

      <ConfirmDialog
        open={!!confirmDelete}
        title={`Delete "${confirmDelete}"?`}
        message="This permanently removes the project workspace and everything in it — inputs, brainstorms, and app prototypes."
        details={[`Delete generated/projects/${confirmDelete}/ and all its contents`, 'This cannot be undone']}
        confirmLabel="Delete project"
        danger
        onConfirm={() => confirmDelete && doDelete(confirmDelete)}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  )
}
