import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { Route, Routes, useNavigate, useParams } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import FigmaSidebar from './components/FigmaSidebar'
import CollapsibleSidebar from './components/CollapsibleSidebar'
import Header, { Tab } from './components/Header'
import FigmaMockupPage from './pages/FigmaMockupPage'
import SandpackPreviewPage from './pages/SandpackPreviewPage'
import AgentChatPage from './pages/AgentChatPage'
import HomePage from './pages/HomePage'
import ProjectWorkspacePage from './pages/ProjectWorkspacePage'
import { api } from './hooks/useApi'
import { FigmaProject, GenerateResult, GenerateStep, Project } from './types'
import { Layers, Zap, Sparkles } from 'lucide-react'

// ── Per-project generation state ──────────────────────────────────────────────
export interface GenState {
  loading:    boolean
  step:       GenerateStep
  log:        string[]
  error:      string
  result:     GenerateResult | null
}

const defaultGenState = (): GenState => ({
  loading: false, step: null, log: [], error: '', result: null,
})

// ── UI App projects context ────────────────────────────────────────────────────
interface ProjectsCtx {
  projects:    Project[]
  busyMap:     Record<string, string>
  genMap:      Record<string, GenState>
  previewUrl:  string | null
  setPreviewUrl: (url: string | null) => void
  refresh:     () => Promise<void>
  setBusy:     (name: string, action: string | null) => void
  setGenState: (name: string, state: Partial<GenState>) => void
  clearGen:    (name: string) => void
}

export const ProjectsContext = createContext<ProjectsCtx>({
  projects: [], busyMap: {}, genMap: {}, previewUrl: null, setPreviewUrl: () => {},
  refresh: async () => {}, setBusy: () => {},
  setGenState: () => {}, clearGen: () => {},
})
export const useProjectsCtx = () => useContext(ProjectsContext)
export const useBusy = () => {
  const { busyMap } = useContext(ProjectsContext)
  const entries = Object.entries(busyMap)
  return {
    busyProject: entries.length > 0 ? entries[0][0] : null,
    busyAction:  entries.length > 0 ? entries[0][1] : null,
  }
}
export const BusyContext = ProjectsContext

// ── Figma mockup projects context ─────────────────────────────────────────────
interface FigmaProjectsCtx {
  figmaProjects:        FigmaProject[]
  activeFigmaProject:   string | null
  setActiveFigmaProject:(name: string | null) => void
  refreshFigmaProjects: () => Promise<void>
}

export const FigmaProjectsContext = createContext<FigmaProjectsCtx>({
  figmaProjects: [], activeFigmaProject: null,
  setActiveFigmaProject: () => {}, refreshFigmaProjects: async () => {},
})
export const useFigmaProjectsCtx = () => useContext(FigmaProjectsContext)

// Remount the conversational page per project so chat + preview state never leak
// across projects (useAgentStream keeps its own per-mount state).
function ChatRoute() {
  const { name } = useParams()
  return <AgentChatPage key={name ?? '__new__'} />
}

// ── Empty state for webapp tab ─────────────────────────────────────────────────
function WebAppEmptyState({ onSwitch }: { onSwitch: () => void }) {
  const navigate = useNavigate()
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-5 text-center px-8">
      <div className="w-16 h-16 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-center">
        <Zap size={28} className="text-slate-400" />
      </div>
      <div>
        <div className="text-slate-600 font-semibold text-lg mb-1">No project selected</div>
        <div className="text-slate-500 text-sm leading-relaxed max-w-xs">
          Create a project in the left panel, then generate your app from a prompt or Figma URL.
        </div>
      </div>
      <div className="flex gap-3 mt-2">
        <button onClick={() => navigate('/chat')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white text-xs font-medium hover:bg-violet-700 transition-colors shadow-sm">
          <Sparkles size={13} /> Chat to Build (SDK) · New
        </button>
        <button onClick={onSwitch}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-50 border border-violet-200 text-violet-700 text-xs font-medium hover:bg-violet-100 transition-colors">
          <Layers size={13} /> Build Figma Mockup
        </button>
      </div>
      <div className="flex flex-col gap-1.5 mt-2">
        {['React + TypeScript + Tailwind CSS', 'React Router multi-page navigation',
          'Recharts data visualisation', 'Figma URL → pixel-perfect app',
          'All data in src/data/*.json'].map(f => (
          <div key={f} className="flex items-center gap-2 text-xs text-slate-500">
            <span className="text-emerald-600">✓</span>{f}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── App ────────────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab,  setActiveTab]  = useState<Tab>('mockup')

  // UI app projects state
  const [projects,   setProjects]   = useState<Project[]>([])
  const [busyMap,    setBusyMap]    = useState<Record<string, string>>({})
  const [genMap,     setGenMap]     = useState<Record<string, GenState>>({})
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Figma mockup projects state
  const [figmaProjects,        setFigmaProjects]        = useState<FigmaProject[]>([])
  const [activeFigmaProject,   setActiveFigmaProject]   = useState<string | null>(
    () => localStorage.getItem('activeFigmaProject') || null
  )
  // Keep localStorage in sync whenever selection changes
  const _setActiveFigmaProject = (name: string | null) => {
    if (name) localStorage.setItem('activeFigmaProject', name)
    else localStorage.removeItem('activeFigmaProject')
    setActiveFigmaProject(name)
  }

  // ── UI App refresh ─────────────────────────────────────────────────────────
  const refresh = useCallback(async () => {
    try { setProjects(await api.listProjects()) } catch {}
  }, [])

  useEffect(() => {
    refresh()
    timerRef.current = setInterval(refresh, 3000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [refresh])

  // ── Figma projects refresh ─────────────────────────────────────────────────
  const refreshFigmaProjects = useCallback(async () => {
    try { setFigmaProjects(await api.listFigmaProjects()) } catch {}
  }, [])

  useEffect(() => { refreshFigmaProjects() }, [refreshFigmaProjects])

  // ── Busy map ───────────────────────────────────────────────────────────────
  const setBusy = useCallback((name: string, action: string | null) => {
    setBusyMap(prev => {
      const next = { ...prev }
      if (!action || !name) { delete next[name] } else { next[name] = action }
      return next
    })
    if (!action) { setTimeout(refresh, 300); setTimeout(refresh, 1200) }
  }, [refresh])

  const setGenState = useCallback((name: string, state: Partial<GenState>) => {
    setGenMap(prev => ({ ...prev, [name]: { ...(prev[name] ?? defaultGenState()), ...state } }))
  }, [])

  const clearGen = useCallback((name: string) => {
    setGenMap(prev => { const next = { ...prev }; delete next[name]; return next })
  }, [])

  const projectsCtx: ProjectsCtx = {
    projects, busyMap, genMap, previewUrl, setPreviewUrl,
    refresh, setBusy, setGenState, clearGen,
  }

  const figmaCtx: FigmaProjectsCtx = {
    figmaProjects, activeFigmaProject,
    setActiveFigmaProject: _setActiveFigmaProject,
    refreshFigmaProjects,
  }

  return (
    <ProjectsContext.Provider value={projectsCtx}>
      <FigmaProjectsContext.Provider value={figmaCtx}>
        <Routes>
          {/* Standalone sandbox preview — no header/sidebar, shareable URL */}
          <Route path="/sandbox/:name" element={<SandpackPreviewPage />} />

          {/* New unified workspace: homepage + per-project shell */}
          <Route path="/" element={<HomePage />} />
          <Route path="/p/:project" element={<ProjectWorkspacePage />} />

          {/* Legacy flat web-app workspace (pre-projects) — kept reachable at /legacy/* */}
          <Route path="*" element={
            <div className="flex flex-col h-screen overflow-hidden bg-white">

              {/* ── Global header with logo + tabs ── */}
              <Header activeTab={activeTab} onChange={setActiveTab} />

              {/* ── Body: sidebar + main ── */}
              <div className="flex flex-1 min-h-0 overflow-hidden">

                {/* Tab-aware sidebar */}
                <CollapsibleSidebar>
                  {activeTab === 'mockup'
                    ? <FigmaSidebar
                        activeProject={activeFigmaProject}
                        onSelect={_setActiveFigmaProject}
                      />
                    : <Sidebar />
                  }
                </CollapsibleSidebar>

                {/* Main content */}
                <main className="flex-1 min-w-0 min-h-0 overflow-hidden flex flex-col">
                  {activeTab === 'mockup'
                    ? <FigmaMockupPage />
                    : (
                      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
                        <Routes>
                          <Route path="/"             element={<WebAppEmptyState onSwitch={() => setActiveTab('mockup')} />} />
                          <Route path="/legacy"       element={<WebAppEmptyState onSwitch={() => setActiveTab('mockup')} />} />
                          {/* Legacy project route now opens the conversational builder too */}
                          <Route path="/project/:name" element={<ChatRoute />} />
                          <Route path="/chat"          element={<ChatRoute />} />
                          <Route path="/chat/:name"    element={<ChatRoute />} />
                        </Routes>
                      </div>
                    )
                  }
                </main>
              </div>
            </div>
          } />
        </Routes>
      </FigmaProjectsContext.Provider>
    </ProjectsContext.Provider>
  )
}
