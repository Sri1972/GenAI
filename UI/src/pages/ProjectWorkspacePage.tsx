import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Users, Zap, Layers, Upload, FileText, Trash2, Loader2, Sparkles,
} from 'lucide-react'
import { workspaces, WorkspaceProject, WorkspaceWebapp, EngagementMode } from '../hooks/useApi'
import WebAppLens from '../components/project/WebAppLens'
import BrainstormLens from '../components/brainstorm/BrainstormLens'

type Lens = 'brainstorm' | 'webapp' | 'figma'

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function ProjectWorkspacePage() {
  const { project } = useParams<{ project: string }>()
  const navigate = useNavigate()
  const [proj, setProj] = useState<WorkspaceProject | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [lens, setLens] = useState<Lens>('brainstorm')
  const [handoff, setHandoff] = useState<{ app: WorkspaceWebapp; seed: string } | null>(null)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  const refresh = useCallback(async () => {
    if (!project) return
    try { setProj(await workspaces.get(project)); setNotFound(false) }
    catch { setNotFound(true) }
    finally { setLoading(false) }
  }, [project])

  useEffect(() => { refresh() }, [refresh])

  const upload = useCallback(async (files: FileList | File[]) => {
    if (!project || !files.length) return
    setUploading(true)
    try {
      for (const f of Array.from(files)) await workspaces.uploadInput(project, f)
      await refresh()
    } catch {}
    finally { setUploading(false) }
  }, [project, refresh])

  const removeInput = async (filename: string) => {
    if (!project) return
    try { await workspaces.deleteInput(project, filename); refresh() } catch {}
  }

  const changeDefaultMode = async (mode: EngagementMode) => {
    if (!project) return
    try { setProj(await workspaces.setDefaultMode(project, mode)) } catch {}
  }

  // Phase E handoff: brainstorm decision → new web-app prototype, seeded with the decision.
  const buildFromBrainstorm = useCallback(async (seed: string) => {
    if (!project) return
    try {
      const app = await workspaces.createWebapp(project)
      setHandoff({ app, seed })
      setLens('webapp')
      refresh()
    } catch {}
  }, [project, refresh])

  if (loading) {
    return <div className="min-h-screen grid place-items-center bg-slate-50 text-slate-400">
      <Loader2 className="w-6 h-6 animate-spin" />
    </div>
  }
  if (notFound || !proj) {
    return (
      <div className="min-h-screen grid place-items-center bg-slate-50">
        <div className="text-center">
          <p className="text-slate-600 mb-3">Project not found.</p>
          <button onClick={() => navigate('/')} className="text-violet-600 text-sm font-medium hover:underline">← Back to projects</button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen overflow-hidden flex flex-col bg-slate-50">
      {/* Header (pinned) */}
      <header className="flex-shrink-0 bg-white border-b border-slate-200">
        <div className="flex items-center gap-3 px-5 py-3">
          <button onClick={() => navigate('/')} title="All projects"
                  className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500"><ArrowLeft size={16} /></button>
          <div className="min-w-0">
            <div className="font-semibold text-slate-800 text-sm truncate">{proj.name}</div>
            <div className="text-xs text-slate-400 truncate">{proj.description || proj.slug}</div>
          </div>
          {/* Project default engagement mode */}
          <div className="ml-auto flex items-center gap-1.5 shrink-0">
            <span className="text-xs text-slate-400">Default:</span>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
              {(['collaborate', 'autopilot'] as const).map(m => (
                <button key={m} onClick={() => changeDefaultMode(m)}
                  className={`px-2.5 py-1 font-medium transition-colors ${proj.defaultMode === m ? 'bg-violet-600 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>
                  {m === 'collaborate' ? 'Collaborate' : 'Autopilot'}
                </button>
              ))}
            </div>
          </div>
        </div>
        {/* Lens tabs */}
        <div className="flex px-3">
          <LensTab active={lens === 'brainstorm'} onClick={() => setLens('brainstorm')} icon={<Users size={13} />} label="Brainstorming" />
          <LensTab active={lens === 'webapp'}    onClick={() => setLens('webapp')}    icon={<Zap size={13} />}   label="UI App" />
          <LensTab active={lens === 'figma'}     onClick={() => setLens('figma')}     icon={<Layers size={13} />} label="Figma" />
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Left: shared inputs (read-only reference material) */}
        <aside className="w-72 shrink-0 border-r border-slate-200 bg-white flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200">
            <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Reference files</div>
            <div className="text-xs text-slate-400 mt-0.5">Shared, read-only across every lens</div>
          </div>

          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); upload(e.dataTransfer.files) }}
            onClick={() => fileInput.current?.click()}
            className={`mx-4 mt-4 rounded-lg border-2 border-dashed px-3 py-6 text-center cursor-pointer transition-colors
              ${dragOver ? 'border-violet-400 bg-violet-50' : 'border-slate-200 hover:border-slate-300'}`}
          >
            {uploading
              ? <Loader2 className="w-5 h-5 mx-auto text-violet-500 animate-spin" />
              : <Upload className="w-5 h-5 mx-auto text-slate-400" />}
            <p className="text-xs text-slate-500 mt-2">{uploading ? 'Uploading…' : 'Drop files or click to upload'}</p>
            <input ref={fileInput} type="file" multiple className="hidden"
                   onChange={e => { if (e.target.files) upload(e.target.files); e.target.value = '' }} />
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1.5">
            {proj.inputs.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">No files yet.</p>
            ) : proj.inputs.map(f => (
              <div key={f.name} className="group flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-50">
                <FileText size={13} className="text-slate-400 shrink-0" />
                <span className="text-xs text-slate-700 truncate flex-1" title={f.name}>{f.name}</span>
                <span className="text-[10px] text-slate-400">{fmtSize(f.size)}</span>
                <button onClick={() => removeInput(f.name)}
                        className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-500 transition-opacity">
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* Main: the active lens (each lens manages its own scrolling) */}
        <main className="flex-1 min-w-0 min-h-0 overflow-hidden">
          {lens === 'brainstorm' && <BrainstormLens project={proj.slug} onBuildApp={buildFromBrainstorm} defaultMode={proj.defaultMode} />}
          {lens === 'webapp' && <WebAppLens project={proj.slug} incoming={handoff} onConsumed={() => setHandoff(null)} defaultMode={proj.defaultMode} />}
          {lens === 'figma' && <ComingSoon icon={<Layers className="w-8 h-8" />} title="Figma"
            body="The Figma lens stays on the current standalone workspace for now; it folds into projects in a later round." />}
        </main>
      </div>
    </div>
  )
}

function LensTab({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        active ? 'border-violet-600 text-violet-700' : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
      }`}>
      {icon} {label}
    </button>
  )
}

function ComingSoon({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="h-full grid place-items-center text-center px-8 py-16">
      <div className="max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-white border border-slate-200 grid place-items-center mx-auto mb-4 text-violet-400">
          {icon}
        </div>
        <div className="flex items-center justify-center gap-1.5 text-violet-500 text-xs font-medium mb-1">
          <Sparkles size={12} /> Coming in this feature
        </div>
        <h2 className="text-lg font-semibold text-slate-800 mb-2">{title}</h2>
        <p className="text-sm text-slate-500 leading-relaxed">{body}</p>
      </div>
    </div>
  )
}
