import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { Route, Routes, useNavigate, useLocation } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import FigmaSidebar from './components/FigmaSidebar'
import ApiSidebar from './components/ApiSidebar'
import CollapsibleSidebar from './components/CollapsibleSidebar'
import Header, { Tab } from './components/Header'
import ProjectDetailPage from './pages/ProjectDetailPage'
import FigmaMockupPage from './pages/FigmaMockupPage'
import SandpackPreviewPage from './pages/SandpackPreviewPage'
import ApiGeneratorPage from './pages/ApiGeneratorPage'
import McpSidebar from './components/McpSidebar'
import McpGeneratorPage from './pages/McpGeneratorPage'
import ProductForgePage from './pages/ProductForgePage'
import WorkflowPage from './pages/WorkflowPage'
import WorkflowSidebar from './components/WorkflowSidebar'
import UtilityAgentsPage from './pages/UtilityAgentsPage'
import ContentAgentsSidebar from './components/ContentAgentsSidebar'
import LandDAgentPage from './pages/LandDAgentPage'
import LandDSidebar from './components/LandDSidebar'
import DataQualityPage from './pages/DataQualityPage'
import DataQualitySidebar from './components/DataQualitySidebar'
import { api } from './hooks/useApi'
import { Agent } from './hooks/contentAgentsApi'
import { FigmaProject, GenerateResult, GenerateStep, ModelsResponse, Project } from './types'
import { CrewStageInfo } from './components/StageProgress'
import { Layers, Zap, Server } from 'lucide-react'

// ── Per-project generation state ──────────────────────────────────────────────
export interface GenState {
  loading:    boolean
  step:       GenerateStep
  log:        string[]
  error:      string
  result:     GenerateResult | null
  /** Most recent "crew:Stage N/M" marker parsed from the live progress log — see StageProgress.tsx. */
  stageInfo:  CrewStageInfo | null
}

const defaultGenState = (): GenState => ({
  loading: false, step: null, log: [], error: '', result: null, stageInfo: null,
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

// ── Global model selection context (Header picker, all tabs) ──────────────────
interface ModelCtx {
  models:        ModelsResponse | null
  usingFallback: boolean
  selecting:     boolean
  selectError:   string | null
  selectModel:   (provider: string, model: string) => Promise<void>
  refresh:       () => Promise<void>
}

export const ModelContext = createContext<ModelCtx>({
  models: null, usingFallback: false, selecting: false, selectError: null,
  selectModel: async () => {}, refresh: async () => {},
})
export const useModelCtx = () => useContext(ModelContext)

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
        <button onClick={onSwitch}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-50 border border-violet-200 text-violet-700 text-xs font-medium hover:bg-violet-100 transition-colors">
          <Layers size={13} /> Build Figma Mockup
        </button>
        <button onClick={() => navigate('/webui')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium hover:bg-slate-100 transition-colors">
          <Zap size={13} /> Select a Project
        </button>
      </div>
      <div className="flex flex-col gap-1.5 mt-2">
        {['React + TypeScript + Tailwind CSS', 'React Router multi-page navigation',
          'Recharts data visualisation', 'Figma URL → pixel-perfect app',
          'SQLite + REST API backend (Python or Java)',
          'AI Concierge chat with your data'].map(f => (
          <div key={f} className="flex items-center gap-2 text-xs text-slate-500">
            <span className="text-emerald-600">-</span>{f}
          </div>
        ))}
      </div>
    </div>
  )
}

// Each tab's top-level path — matches its label (webui, figmamockup, webapi,
// mcp, productforge). "webapp" still needs the special-case below (Web UI
// has real sub-routes /webui, /webui/project/:name instead of one fixed
// path), so its entry here is just the default landing path, not literally
// read by setActiveTab(). Product Forge's tab path is "/productforge", NOT
// "/forge" — server.py already registers "/forge" and "/forge/" as real
// backend routes that serve Product Forge's own inner page directly for the
// iframe (plus "/forge/api/*" as its whole API mount) — reusing that exact
// path for this outer tab would mean a hard refresh here returned Product
// Forge's bare page with no Header/tab bar around it, instead of this shell.
const TAB_PATHS: Record<Tab, string> = {
  forge: '/productforge', mockup: '/figmamockup', api: '/webapi', mcp: '/mcp', webapp: '/webui',
  workflow: '/workflow', utility_agents: '/utilityagents', data_quality: '/dataquality', land_d: '/techld',
}

// ── App ────────────────────────────────────────────────────────────────────────
export default function App() {
  const navigate = useNavigate()
  const location = useLocation()

  // The active tab is derived from the URL itself, not separate state —
  // tab-switching used to only flip local state and never navigate, so the
  // address bar kept showing whatever URL was last visited (e.g. a Web UI
  // project) no matter which tab you'd since clicked into.
  const activeTab: Tab =
    location.pathname.startsWith('/figmamockup')   ? 'mockup'         :
    location.pathname.startsWith('/webapi')        ? 'api'            :
    location.pathname.startsWith('/mcp')           ? 'mcp'            :
    location.pathname.startsWith('/workflow')      ? 'workflow'       :
    location.pathname.startsWith('/utilityagents') ? 'utility_agents' :
    location.pathname.startsWith('/dataquality')   ? 'data_quality'   :
    location.pathname.startsWith('/techld')        ? 'land_d'         :
    location.pathname.startsWith('/productforge')  ? 'forge'          : 'webapp'

  // Web UI has real sub-routes (/webui, /webui/project/:name) instead of one
  // fixed path — remember whichever one you were last on so switching to
  // another tab and back returns you to the same project instead of
  // resetting to the empty state.
  const lastWebappPath = useRef('/webui')
  useEffect(() => {
    if (activeTab === 'webapp') lastWebappPath.current = location.pathname
  }, [activeTab, location.pathname])

  const setActiveTab = useCallback((t: Tab) => {
    navigate(t === 'webapp' ? lastWebappPath.current : TAB_PATHS[t])
  }, [navigate])

  // On initial load only (empty deps — an in-app navigation never remounts
  // App, so neither of these can fire on a click, only on an actual page
  // load): bare "/" has no tab of its own now that activeTab is derived
  // from the URL, so without this it would fall through to the Web UI
  // fallback case instead of landing on Workflow (now the first tab) as
  // intended. And a hard refresh (or pasting/bookmarking) on
  // /webui/project/:name — never meant to be a durable bookmark the way
  // /sandbox/:name explicitly is (see that route's own comment) —
  // normalizes back to "/webui".
  useEffect(() => {
    if (location.pathname === '/') {
      navigate('/workflow', { replace: true })
    } else if (location.pathname.startsWith('/webui/project/')) {
      navigate('/webui', { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // UI app projects state
  const [projects,   setProjects]   = useState<Project[]>([])
  const [busyMap,    setBusyMap]    = useState<Record<string, string>>({})
  const [genMap,     setGenMap]     = useState<Record<string, GenState>>({})
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // API projects state (which project is shown in the detail panel)
  const [activeApiProject, setActiveApiProject] = useState<string | null>(null)

  // MCP projects state (which project is shown in the detail panel)
  const [activeMcpProject, setActiveMcpProject] = useState<string | null>(null)

  // Workflow tab state (which saved workflow is loaded on the canvas —
  // null means "new, unsaved workflow"). WorkflowPage is remounted via
  // `key` whenever this changes, so it always starts from a clean slate.
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null)
  // Auto Mode lives here, not as local state inside WorkflowPage -- saving a
  // brand-new workflow changes activeWorkflowId (null -> a real id), which
  // remounts WorkflowPage via its `key` below; local state there would
  // silently reset back to the default right after the user set it.
  const [workflowAutoMode, setWorkflowAutoMode] = useState(true)

  // Utility Agents tab state (which of the 8 agents is selected)
  const [activeUtilityAgent, setActiveUtilityAgent] = useState<Agent>('excel_parser')

  // Tech L&D tab state (which saved item is shown, null = "new" create form)
  const [activeLandDItem, setActiveLandDItem] = useState<string | null>(null)
  // Bumped whenever a generate/regenerate/delete completes, so LandDSidebar's
  // list refreshes immediately instead of waiting for its own 5s poll.
  const [landDRefreshKey, setLandDRefreshKey] = useState(0)

  // Data Quality tab state -- same shape as Tech L&D just above.
  const [activeDataQualityItem, setActiveDataQualityItem] = useState<string | null>(null)
  const [dataQualityRefreshKey, setDataQualityRefreshKey] = useState(0)

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

  // ── Global model selection ──────────────────────────────────────────────────
  // Source of truth is the server's .model_selection.json (it already
  // survives restarts on its own), so this just mirrors whatever /api/models
  // reports — no separate localStorage layer needed.
  const [models,        setModels]        = useState<ModelsResponse | null>(null)
  const [selecting,     setSelecting]     = useState(false)
  const [selectError,   setSelectError]   = useState<string | null>(null)

  const refreshModels = useCallback(async () => {
    try { setModels(await api.getModels()) } catch {}
  }, [])

  useEffect(() => {
    refreshModels()
    const t = setInterval(refreshModels, 15000)  // pick up fallback status without user action
    return () => clearInterval(t)
  }, [refreshModels])

  const selectModel = useCallback(async (provider: string, model: string) => {
    setSelecting(true)
    setSelectError(null)
    try {
      const res = await api.selectModel(provider, model)
      if (!res.ok) setSelectError(res.error || 'Model is not reachable')
    } catch (e: any) {
      setSelectError(e?.message || 'Could not reach the server')
    } finally {
      setSelecting(false)
      refreshModels()
    }
  }, [refreshModels])

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

  const modelCtx: ModelCtx = {
    models, usingFallback: models?.using_fallback ?? false,
    selecting, selectError, selectModel, refresh: refreshModels,
  }

  return (
    <ProjectsContext.Provider value={projectsCtx}>
      <FigmaProjectsContext.Provider value={figmaCtx}>
      <ModelContext.Provider value={modelCtx}>
        <Routes>
          {/* Standalone sandbox preview — no header/sidebar, shareable URL */}
          <Route path="/sandbox/:name" element={<SandpackPreviewPage />} />

          {/* Main app shell */}
          <Route path="*" element={
            <div className="flex flex-col h-screen overflow-hidden bg-white">

              {/* ── Global header with logo + tabs ── */}
              <Header activeTab={activeTab} onChange={setActiveTab} />

              {/* ── Body: sidebar + main ── */}
              <div className="flex flex-1 min-h-0 overflow-hidden">

                {/* Tab-aware sidebar — Product Forge is a single embedded
                    app, not a multi-project generator, so it has none. */}
                {activeTab !== 'forge' && (
                  <CollapsibleSidebar>
                    {activeTab === 'mockup'
                      ? <FigmaSidebar
                          activeProject={activeFigmaProject}
                          onSelect={_setActiveFigmaProject}
                        />
                      : activeTab === 'api'
                      ? <ApiSidebar
                          activeProject={activeApiProject}
                          onSelect={setActiveApiProject}
                        />
                      : activeTab === 'mcp'
                      ? <McpSidebar
                          activeProject={activeMcpProject}
                          onSelect={setActiveMcpProject}
                        />
                      : activeTab === 'workflow'
                      ? <WorkflowSidebar
                          activeWorkflowId={activeWorkflowId}
                          onSelect={setActiveWorkflowId}
                          onNew={() => setActiveWorkflowId(null)}
                        />
                      : activeTab === 'utility_agents'
                      ? <ContentAgentsSidebar
                          selected={activeUtilityAgent}
                          onSelect={setActiveUtilityAgent}
                        />
                      : activeTab === 'data_quality'
                      ? <DataQualitySidebar
                          activeItemId={activeDataQualityItem}
                          onSelect={setActiveDataQualityItem}
                          refreshKey={dataQualityRefreshKey}
                        />
                      : activeTab === 'land_d'
                      ? <LandDSidebar
                          activeItemId={activeLandDItem}
                          onSelect={setActiveLandDItem}
                          refreshKey={landDRefreshKey}
                        />
                      : <Sidebar />
                    }
                  </CollapsibleSidebar>
                )}

                {/* Main content */}
                <main className="flex-1 min-w-0 min-h-0 overflow-hidden flex flex-col">
                  {/* Product Forge stays mounted even when another tab is
                      active (hidden with CSS, not unmounted) — its iframe
                      holds a live SSE connection to the running session, and
                      tearing that down on every tab switch forced a full
                      reload + "catch up" fetch each time you came back,
                      which is what looked like slow loads and content
                      "suddenly" appearing all at once. */}
                  <div
                    className="flex-1 min-h-0 flex flex-col overflow-hidden"
                    style={{ display: activeTab === 'forge' ? 'flex' : 'none' }}
                  >
                    <ProductForgePage />
                  </div>
                  {/* Same reasoning as Product Forge above — an unsaved
                      Workflow canvas (dragged-but-not-saved nodes, a typed
                      name) or an in-progress Utility Agents upload/chat
                      would otherwise silently reset every time you glanced
                      at another tab, since a plain ternary swap here
                      unmounts whichever page isn't "active". */}
                  <div
                    className="flex-1 min-h-0 flex flex-col overflow-hidden"
                    style={{ display: activeTab === 'workflow' ? 'flex' : 'none' }}
                  >
                    <WorkflowPage
                      key={activeWorkflowId ?? 'new'}
                      workflowId={activeWorkflowId}
                      onNew={() => setActiveWorkflowId(null)}
                      onSaved={setActiveWorkflowId}
                      autoMode={workflowAutoMode}
                      onAutoModeChange={setWorkflowAutoMode}
                    />
                  </div>
                  <div
                    className="flex-1 min-h-0 flex flex-col overflow-hidden"
                    style={{ display: activeTab === 'utility_agents' ? 'flex' : 'none' }}
                  >
                    <UtilityAgentsPage agent={activeUtilityAgent} />
                  </div>
                  {/* Same reasoning as Utility Agents just above -- a
                      half-typed topic/instructions edit shouldn't reset if
                      you glance at another tab. */}
                  <div
                    className="flex-1 min-h-0 flex flex-col overflow-hidden"
                    style={{ display: activeTab === 'land_d' ? 'flex' : 'none' }}
                  >
                    <LandDAgentPage
                      activeItemId={activeLandDItem}
                      onSelect={setActiveLandDItem}
                      onChanged={() => setLandDRefreshKey(k => k + 1)}
                    />
                  </div>
                  {/* Same reasoning as Tech L&D just above. */}
                  <div
                    className="flex-1 min-h-0 flex flex-col overflow-hidden"
                    style={{ display: activeTab === 'data_quality' ? 'flex' : 'none' }}
                  >
                    <DataQualityPage
                      activeItemId={activeDataQualityItem}
                      onSelect={setActiveDataQualityItem}
                      onChanged={() => setDataQualityRefreshKey(k => k + 1)}
                    />
                  </div>
                  {activeTab === 'mockup'
                    ? <FigmaMockupPage />
                    : activeTab === 'api'
                    ? <ApiGeneratorPage
                        activeProject={activeApiProject}
                        onSelect={setActiveApiProject}
                      />
                    : activeTab === 'mcp'
                    ? <McpGeneratorPage
                        activeProject={activeMcpProject}
                        onSelect={setActiveMcpProject}
                      />
                    : activeTab === 'forge'
                    ? null
                    : activeTab === 'workflow'
                    ? null
                    : activeTab === 'utility_agents'
                    ? null
                    : activeTab === 'land_d'
                    ? null
                    : activeTab === 'data_quality'
                    ? null
                    : (
                      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
                        <Routes>
                          <Route path="/webui"              element={<WebAppEmptyState onSwitch={() => setActiveTab('mockup')} />} />
                          <Route path="/webui/project/:name" element={<ProjectDetailPage />} />
                        </Routes>
                      </div>
                    )
                  }
                </main>
              </div>
            </div>
          } />
        </Routes>
      </ModelContext.Provider>
      </FigmaProjectsContext.Provider>
    </ProjectsContext.Provider>
  )
}
