import { useState, useCallback, useEffect, useRef } from 'react'
import { Server, Play, Square, FileCode, Plus, Trash2, ExternalLink, RefreshCw, LayoutGrid, Terminal, Clock, Lock, LogIn, LogOut, Copy, Check, Beaker, X, Container, Download, Upload, Layers, AlertCircle, RotateCcw, Sparkles, FileText } from 'lucide-react'
import { api } from '../hooks/useApi'
import { ApiArchitecture, ApiExample, ApiProjectEntry, ApiUsageSummary, BuildLogRun, DockerStatus, HistoryEvent } from '../types'
import PreviewFrame from '../components/PreviewFrame'
import ResizablePanels from '../components/ResizablePanels'
import InstructionsModal, { InstructionsBadge } from '../components/InstructionsModal'
import StageProgress, { CrewStageInfo, parseCrewStage } from '../components/StageProgress'

// Mirrors WebAPIGenerator/api_agents/api_orchestrator.py's API_STAGES `name`
// field exactly, in order — kept here since the frontend has no endpoint
// that returns that list, and it changes about as often as the pipeline's
// own stage count does.
const API_STAGE_NAMES = [
  'API Architecture', 'Data Modeling', 'API Implementation',
  'Security & Middleware', 'Testing & Documentation', 'Packaging & Deploy',
]

// Scans raw (unstripped) progress lines for the most recent "crew:Stage N/M"
// marker — later lines override earlier ones, so this always reflects
// wherever the pipeline currently is.
function latestCrewStage(lines: string[]): CrewStageInfo | null {
  let found: CrewStageInfo | null = null
  for (const line of lines) {
    const parsed = parseCrewStage(line)
    if (parsed) found = parsed
  }
  return found
}

// Routes the docs iframe through the same-origin docs-proxy (API/server.py) instead
// of the generated API's own port. Needed because Chrome outright blocks iframe src
// URLs with embedded `user:pass@host` credentials (the technique this replaced), and
// a bare cross-origin iframe would otherwise hit the native Basic Auth popup the
// custom login form exists to avoid. For Java, skip springdoc's /swagger-ui.html
// redirect entirely and go straight to swagger-ui/index.html — the proxy rewrites
// its swagger-initializer.js to point at this same proxy's /v3/api-docs, since
// springdoc's own query-param-based configUrl mechanism doesn't reliably fire.
const docsProxyUrl = (name: string, language: string | null) => {
  const base = `/api/webapi/projects/${name}/docs-proxy`
  if (language === 'java') {
    return `${base}/swagger-ui/index.html`
  }
  return `${base}/docs`
}

interface ApiEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  path: string
  description: string
}

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-emerald-100 text-emerald-700',
  POST: 'bg-blue-100 text-blue-700',
  PUT: 'bg-amber-100 text-amber-700',
  DELETE: 'bg-red-100 text-red-700',
  PATCH: 'bg-purple-100 text-purple-700',
}

interface Props {
  activeProject: string | null
  onSelect: (name: string | null) => void
}

export default function ApiGeneratorPage({ activeProject, onSelect }: Props) {
  return activeProject
    // key={activeProject} forces a full remount on every project switch —
    // without it, ApiProjectDetail's OWN local state (requirements,
    // instructions, opts, refinePrompt, table/endpoint selections, ...) was
    // simply reused across projects, since only server-fetched state
    // (entry/metadata/buildLog) gets explicitly refreshed on a name change.
    // Reproduced directly: creating a brand-new project showed whatever
    // Requirements/Instructions text was last typed for a PREVIOUS project.
    // The pollUntilDone interval cleanup this component already does on
    // unmount (see its own effect) still runs correctly under a remount —
    // this is additive, not a replacement for that fix.
    ? <ApiProjectDetail key={activeProject} name={activeProject} onDeleted={() => onSelect(null)} />
    : <ApiEmptyState />
}

// ── Empty state (mirrors WebAppEmptyState in App.tsx) ────────────────────────────

function ApiEmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-8">
      <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center">
        <Server size={28} className="text-emerald-400" />
      </div>
      <div>
        <div className="text-slate-600 font-semibold text-lg mb-1">No API project selected</div>
        <div className="text-slate-500 text-sm leading-relaxed max-w-sm">
          Type a name in the left panel and hit + to create one, then configure and generate it here.
        </div>
      </div>
      <div className="flex flex-col gap-1.5 mt-2">
        {[
          'Auto-generates OpenAPI / Swagger spec — try it out live, like Postman',
          'Deterministic throttling + usage metering, every generation',
          'Basic auth (or none) out of the box — OKTA/SSO can come later',
          'Python (FastAPI) or Java (Spring Boot)',
        ].map(f => (
          <div key={f} className="flex items-center gap-2 text-xs text-slate-500">
            <span className="text-emerald-600">-</span>{f}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Generate form config shape (rendered inline in ApiProjectDetail's left panel) ─

interface NewApiOptions {
  description: string
  language: 'python' | 'java'
  authType: 'none' | 'basic'
  rateLimit: number
  endpoints: ApiEndpoint[]
}

// ── Basic Auth login gate (replaces the native browser popup for the Preview
// tab) — verifies credentials same-origin via the usage proxy, then the caller
// embeds them into the iframe URL so the browser never has to prompt at all.

function BasicAuthForm({ name, onAuthenticated }: { name: string; onAuthenticated: (username: string, password: string) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password || checking) return
    setChecking(true)
    setError('')
    try {
      const { ok, status } = await api.verifyApiAuth(name, username, password)
      if (ok) {
        onAuthenticated(username, password)
      } else if (status === 401) {
        setError('Invalid username or password')
      } else {
        setError(`Unexpected response (HTTP ${status})`)
      }
    } catch {
      setError('Could not reach the API — is it running?')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex-1 flex items-center justify-center bg-slate-50">
      <form onSubmit={handleSubmit} className="w-80 bg-white border border-slate-200 rounded-xl shadow-sm p-6 space-y-4">
        <div className="text-center">
          <div className="w-10 h-10 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center mx-auto mb-2">
            <Lock size={16} className="text-emerald-500" />
          </div>
          <div className="text-sm font-semibold text-slate-700">Sign in to preview</div>
          <p className="text-xs text-slate-500 mt-1">This API requires Basic Auth — credentials are in the generated .env file.</p>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600 block mb-1">Username</label>
          <input
            autoFocus
            value={username}
            onChange={e => setUsername(e.target.value)}
            disabled={checking}
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600 block mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            disabled={checking}
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none"
          />
        </div>
        {error && <div className="text-xs text-red-600">{error}</div>}
        <button
          type="submit"
          disabled={checking || !username || !password}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {checking
            ? <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
            : <LogIn size={14} />}
          Sign In
        </button>
      </form>
    </div>
  )
}

// ── Project detail ──────────────────────────────────────────────────────────────

type DetailTab = 'preview' | 'usage' | 'examples' | 'architecture' | 'log' | 'history' | 'docker'

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

// Strip internal "event:" prefixes (llm_codegen:, skill:, crew:) → human-readable text
function cleanLogLines(lines: string[]): string[] {
  return lines.map(l => l.replace(/^[a-z_]+:/, '').trim()).filter(Boolean)
}

function ApiProjectDetail({ name, onDeleted }: { name: string; onDeleted: () => void }) {
  const [entry, setEntry] = useState<ApiProjectEntry | null>(null)
  const [checked, setChecked] = useState(false)  // has the first fetch attempt resolved?
  const [usage, setUsage] = useState<ApiUsageSummary | null>(null)
  const [architecture, setArchitecture] = useState<ApiArchitecture | null>(null)
  const [buildLog, setBuildLog] = useState<BuildLogRun[]>([])
  const [busy, setBusy] = useState<'starting' | 'stopping' | 'deleting' | null>(null)
  const [tab, setTab] = useState<DetailTab>('preview')
  const [creds, setCreds] = useState<{ username: string; password: string } | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // Generation config + progress — merged in here (rather than a separate
  // component shown only for draft projects) so the tab bar and Build Log are
  // visible from the moment a project is created, matching how the web-app
  // builder always shows its tabs instead of swapping to a different screen.
  const [opts, setOpts] = useState<NewApiOptions>({
    description: '', language: 'python', authType: 'basic', rateLimit: 100, endpoints: [],
  })
  const [requirements, setRequirements] = useState('')
  const [instructions, setInstructions] = useState('')
  const [showInstrModal, setShowInstrModal] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [progressLog, setProgressLog] = useState<string[]>([])
  const [genError, setGenError] = useState('')

  // History — same shape/pattern as the Web App tab's own History tab
  // (server.py's .history.json): a semantic record of every generate/
  // refine's prompt/comment/instructions, distinct from the Build Log's
  // raw progress lines.
  const [history, setHistory] = useState<HistoryEvent[]>([])
  const [comment, setComment] = useState('')
  const [viewInstructions, setViewInstructions] = useState<string | null>(null)

  // Docker — opt-in, separate from generation (mirrors ProjectDetailPage's Docker tab)
  const [docker, setDocker] = useState<DockerStatus | null>(null)
  const [dockerBusy, setDockerBusy] = useState<string | null>(null)  // 'build'|'run'|'stop'|'start'|'delete'|'download'
  const [dockerLog, setDockerLog] = useState<string[]>([])
  const [dockerError, setDockerError] = useState<string | null>(null)
  const dockerPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refreshEntry = useCallback(() => {
    api.listApiProjects()
      .then(list => setEntry(list.find(p => p.name === name) || null))
      .catch(() => setEntry(null))
      .finally(() => setChecked(true))
  }, [name])

  // Architecture/build-log are otherwise only fetched once on mount — without
  // this, finishing a fresh generation would leave those two tabs showing
  // stale (empty) data even though the server just wrote real ones.
  const refreshAfterGenerate = useCallback(() => {
    refreshEntry()
    api.getApiArchitecture(name).then(r => setArchitecture(r.architecture)).catch(() => {})
    api.getApiBuildLog(name).then(r => setBuildLog(r.runs)).catch(() => {})
    api.getApiHistory(name).then(setHistory).catch(() => {})
  }, [name, refreshEntry])

  // Poll by request ID, not by project name: /api/generate/progress/{id} and
  // /api/jobs/{id} both key off the id we already have from the initial
  // response, unlike /api/generate/progress/project/{name} — that one only
  // starts returning data once the (multi-minute) orchestrator call finishes
  // server-side, which used to leave the Build Log tab looking empty for the
  // entire generation. Matches ProjectDetailPage's proven pollUntilReady/pollJob
  // pattern for the same reason.
  const pollUntilDone = useCallback((requestId: string) => {
    // Only one poll may ever be live per mounted instance — without this,
    // switching projects (ApiGeneratorPage renders ApiProjectDetail without a
    // `key`, so this component instance is REUSED across projects, not
    // remounted) left an old project's poll still running on its own 3s
    // cadence, calling these same setState functions with the OLD project's
    // requestId/closures — visible as the Build Log tab flickering between
    // two different projects' content. Clearing any prior poll before
    // starting a new one, and on unmount/project-change (see the effect
    // below), makes at most one poll active at a time.
    if (pollRef.current) clearInterval(pollRef.current)
    const iv = setInterval(async () => {
      try {
        const { log } = await api.getProgress(requestId)
        if (log) setProgressLog(log)
        const job = await api.getJobStatus(requestId)
        if (job.status === 'completed') {
          clearInterval(iv)
          pollRef.current = null
          setGenerating(false)
          refreshAfterGenerate()
          // Matches the web-app builder: only hop back to Preview if the user
          // hadn't already navigated elsewhere while it was running.
          setTab(t => t === 'log' ? 'preview' : t)
        } else if (job.status === 'failed') {
          clearInterval(iv)
          pollRef.current = null
          setGenerating(false)
          setGenError(job.error || 'Generation failed')
        }
      } catch {
        // transient — keep polling
      }
    }, 3000)
    pollRef.current = iv
    return iv
  }, [refreshAfterGenerate])

  const handleGenerate = useCallback(async () => {
    if (!(requirements.trim() || instructions.trim())) return
    setGenerating(true)
    setGenError('')
    setProgressLog([])
    setTab('log')  // Immediately switch to the Build Log tab, like the web-app builder
    try {
      const { requestId } = await api.generateApi(requirements, name, {
        language: opts.language,
        auth_type: opts.authType,
        rate_limit: opts.rateLimit,
        database: 'sqlite',
        // Docker support is a separate, deliberate future enhancement (its own
        // tab, mirroring Web UI's) — not a default side effect of generation.
        // The runner already starts the API directly (uvicorn / spring-boot:run),
        // so a Dockerfile generated here would just go unused.
        include_docker: false,
        include_tests: true,
        endpoints: opts.endpoints.length > 0 ? opts.endpoints : undefined,
      }, instructions)
      pollUntilDone(requestId)
    } catch (e: any) {
      setGenError(e.message || 'Generation failed')
      setGenerating(false)
    }
  }, [name, opts, requirements, instructions, pollUntilDone])

  // Refine reuses the exact same progress machinery as a fresh generate —
  // the endpoint returns the identical {requestId, status, projectName}
  // shape and reports progress through the same job/log polling, so there's
  // no separate state machine needed, just a different kick-off call.
  const [refinePrompt, setRefinePrompt] = useState('')
  const handleRefine = useCallback(async () => {
    if (!refinePrompt.trim() || generating) return
    setGenerating(true)
    setGenError('')
    setProgressLog([])
    setTab('log')
    try {
      const { requestId } = await api.refineApiProject(name, refinePrompt, instructions, comment)
      pollUntilDone(requestId)
    } catch (e: any) {
      setGenError(e.message || 'Refine failed')
      setGenerating(false)
    }
  }, [name, refinePrompt, instructions, comment, generating, pollUntilDone])

  const addEndpoint = () => {
    setOpts(p => ({ ...p, endpoints: [...p.endpoints, { method: 'GET', path: '/api/', description: '' }] }))
  }
  const removeEndpoint = (idx: number) => {
    setOpts(p => ({ ...p, endpoints: p.endpoints.filter((_, i) => i !== idx) }))
  }
  const updateEndpoint = (idx: number, field: keyof ApiEndpoint, value: string) => {
    setOpts(p => ({ ...p, endpoints: p.endpoints.map((ep, i) => i === idx ? { ...ep, [field]: value } : ep) }))
  }

  useEffect(() => {
    let cancelled = false
    setEntry(null)
    setChecked(false)
    setCreds(null)
    setDeleteError(null)
    refreshEntry()
    setUsage(null)
    setExamples(null)
    setTab('preview')
    setGenerating(false)
    setProgressLog([])
    setGenError('')
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    if (dockerPollRef.current) { clearInterval(dockerPollRef.current); dockerPollRef.current = null }
    setDocker(null)
    setDockerLog([])
    setDockerBusy(null)
    setDockerError(null)
    api.getApiArchitecture(name).then(r => setArchitecture(r.architecture)).catch(() => setArchitecture(null))
    api.getApiBuildLog(name).then(r => setBuildLog(r.runs)).catch(() => setBuildLog([]))
    api.getApiHistory(name).then(setHistory).catch(() => setHistory([]))
    api.getApiDockerStatus(name).then(setDocker).catch(() => {})
    const interval = setInterval(refreshEntry, 5000)

    // Reconnect to a generation already in progress — e.g. the browser was
    // closed or navigated away mid-generation and came back. The job itself
    // is a background task on the server and keeps running regardless; without
    // this, this component's local `generating` state would come back false
    // and show the draft config form again, hiding the fact that a generation
    // is already under way (and inviting a duplicate submit).
    api.getProgressByProject(name).then(async ({ id, log }) => {
      if (cancelled || !id) return
      try {
        const job = await api.getJobStatus(id)
        if (cancelled) return
        if (job.status === 'running') {
          setGenerating(true)
          setProgressLog(log || [])
          setTab('log')
          pollUntilDone(id)
        } else if (job.status === 'failed') {
          setGenError(job.error || 'Generation failed')
          setProgressLog(log || [])
        }
      } catch {
        // transient — the regular tab content will just show as not-yet-generated
      }
    }).catch(() => {})

    return () => {
      cancelled = true
      clearInterval(interval)
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [name, refreshEntry, pollUntilDone])

  const loadUsage = useCallback(() => {
    api.getApiUsage(name).then(setUsage).catch(() => setUsage(null))
  }, [name])

  useEffect(() => { if (tab === 'usage') loadUsage() }, [tab, loadUsage])

  const [resettingUsage, setResettingUsage] = useState(false)
  const resetUsage = useCallback(async () => {
    setResettingUsage(true)
    try {
      await api.resetApiUsage(name)
      loadUsage()
    } catch {
      // surfaced implicitly — loadUsage() below just won't reflect a reset
    } finally {
      setResettingUsage(false)
    }
  }, [name, loadUsage])

  const [examples, setExamples] = useState<ApiExample[] | null>(null)
  const [examplesLoading, setExamplesLoading] = useState(false)
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null)
  const loadExamples = useCallback(() => {
    setExamplesLoading(true)
    api.getApiExamples(name)
      .then(r => setExamples(r.examples))
      .catch(() => setExamples([]))
      .finally(() => setExamplesLoading(false))
  }, [name])

  useEffect(() => { if (tab === 'examples' && examples === null) loadExamples() }, [tab, examples, loadExamples])

  const copyCurl = (curl: string, idx: number) => {
    navigator.clipboard.writeText(curl).then(() => {
      setCopiedIdx(idx)
      setTimeout(() => setCopiedIdx(null), 1500)
    })
  }

  const start = async () => { setBusy('starting'); try { await api.startApiProject(name) } finally { setBusy(null); refreshEntry() } }
  const stop = async () => { setBusy('stopping'); try { await api.stopApiProject(name) } finally { setBusy(null); refreshEntry() } }
  const del = async () => {
    setBusy('deleting'); setDeleteError(null)
    try {
      await api.deleteApiProject(name)
      onDeleted()
    } catch (e: any) {
      // Don't call onDeleted() here — the project (and its folder) are still
      // there on a partial-delete failure; navigating away would hide the
      // only place the user can see this and retry.
      setDeleteError(e?.message || 'Delete failed.')
    } finally {
      setBusy(null)
    }
  }

  const loadDockerStatus = useCallback(() => {
    api.getApiDockerStatus(name).then(setDocker).catch(() => {})
  }, [name])

  const dockerBuildImage = async () => {
    setDockerBusy('build'); setDockerLog([]); setDockerError(null); setTab('docker')
    try {
      // Poll progress the same way generation does — the build endpoint
      // registers this project's request id synchronously before dispatching
      // to the executor, so /api/generate/progress/project/{name} has live
      // "docker_build:" lines from the very first poll.
      if (dockerPollRef.current) clearInterval(dockerPollRef.current)
      dockerPollRef.current = setInterval(async () => {
        try {
          const { log } = await api.getProgressByProject(name)
          const lines = (log || [])
            .filter(l => l.includes('docker_build:'))
            .map(l => l.replace(/^.*docker_build:/, '').trim())
            .filter(Boolean)
          if (lines.length) setDockerLog(lines)
        } catch {}
      }, 800)
      const result = await api.buildApiDockerImage(name)
      if (dockerPollRef.current) { clearInterval(dockerPollRef.current); dockerPollRef.current = null }
      setDocker(result)
    } catch (e: any) {
      const msg = e.message || 'Build failed'
      const lower = msg.toLowerCase()
      const isDockerIssue = ['docker not found', 'docker desktop', 'not fully running', 'grpc', 'eof', 'daemon', 'connection refused'].some(k => lower.includes(k))
      setDockerError(isDockerIssue
        ? 'Docker Desktop is not running or not fully ready. Please ensure Docker Desktop is started and the whale icon shows "running" in the system tray, then try again.'
        : `Build failed: ${msg}`)
      loadDockerStatus()
    } finally {
      if (dockerPollRef.current) { clearInterval(dockerPollRef.current); dockerPollRef.current = null }
      setDockerBusy(null)
    }
  }

  const dockerRunContainer = async () => {
    setDockerBusy('run')
    try { setDocker(await api.runApiDockerContainer(name)) }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerStopContainer = async () => {
    setDockerBusy('stop')
    try { setDocker(await api.stopApiDockerContainer(name)) }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerStartContainer = async () => {
    setDockerBusy('start')
    try { setDocker(await api.startApiDockerContainer(name)) }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerDeleteContainer = async () => {
    setDockerBusy('delete')
    try { setDocker(await api.deleteApiDockerContainer(name)) }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerDownload = () => {
    setDockerBusy('download')
    try { api.downloadApiDockerImage(name) }
    finally { setTimeout(() => setDockerBusy(null), 1500) }
  }

  if (!entry) {
    if (!checked) {
      return <div className="flex-1 flex items-center justify-center text-sm text-slate-400">Loading...</div>
    }
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
        <div className="text-slate-600 font-semibold">Project not found</div>
        <p className="text-slate-500 text-sm max-w-xs">
          "{name}" doesn't exist in the registry — it may have been deleted.
        </p>
        <button onClick={onDeleted}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium hover:bg-emerald-100 transition-colors">
          <Plus size={13} /> Back
        </button>
      </div>
    )
  }

  const isDraft = entry.status === 'draft'
  const liveUrl = entry.status === 'running' && entry.port ? `http://localhost:${entry.port}` : null
  const docsUrl = liveUrl ? docsProxyUrl(name, entry.language) : null
  const needsAuth = entry.authType === 'basic'
  const canGenerate = !!(requirements.trim() || instructions.trim())

  const configPanel = isDraft && generating ? (
    // Read from the entry (persisted server-side the moment generation was
    // submitted), not the local `opts` form state — that state resets to its
    // defaults on any remount (e.g. reconnecting to this job after
    // navigating away and back), which was showing the wrong language/auth/
    // rate-limit while a generation the user already submitted was still
    // running under completely different settings.
    <div className="flex-1 overflow-y-auto p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <Server size={16} className="text-emerald-600" />{name}
        </h2>
        <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full border-2 border-slate-200 border-t-emerald-500 animate-spin" />
          Generating…
        </p>
      </div>
      <div className="space-y-2 text-xs">
        <div className="flex justify-between"><span className="text-slate-400">Language</span><span className="font-medium text-slate-700">{entry.language === 'java' ? 'Java (Spring Boot)' : 'Python (FastAPI)'}</span></div>
        <div className="flex justify-between"><span className="text-slate-400">Auth</span><span className="font-medium text-slate-700">{entry.authType === 'basic' ? 'Basic Auth' : 'None'}</span></div>
        {entry.rateLimit != null && <div className="flex justify-between"><span className="text-slate-400">Rate limit</span><span className="font-medium text-slate-700">{entry.rateLimit} req/min</span></div>}
      </div>
    </div>
  ) : isDraft ? (
    <div className="flex-1 overflow-y-auto p-5 space-y-5">
      <div>
        <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <Server size={16} className="text-emerald-600" />{name}
        </h2>
        <p className="text-xs text-slate-500 mt-1">Configure and generate — usually takes a few minutes</p>
      </div>

      <div className="space-y-3">
        <div>
          <label className="text-xs font-medium text-slate-600 block mb-1">Language / Framework</label>
          <select
            value={opts.language}
            disabled={generating}
            onChange={e => setOpts(p => ({ ...p, language: e.target.value as NewApiOptions['language'] }))}
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none"
          >
            <option value="python">Python (FastAPI)</option>
            <option value="java">Java (Spring Boot)</option>
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">Authentication</label>
            <select
              value={opts.authType}
              disabled={generating}
              onChange={e => setOpts(p => ({ ...p, authType: e.target.value as NewApiOptions['authType'] }))}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none"
            >
              <option value="basic">Basic Auth</option>
              <option value="none">None</option>
            </select>
            <p className="text-[10px] text-slate-400 mt-1">OKTA/SSO can come later — start simple.</p>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">Rate limit (req/min)</label>
            <input
              type="number"
              min={0}
              disabled={generating}
              value={opts.rateLimit}
              onChange={e => setOpts(p => ({ ...p, rateLimit: Number(e.target.value) || 0 }))}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none"
            />
          </div>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600 block mb-1">Description</label>
          <textarea
            value={opts.description}
            disabled={generating}
            onChange={e => setOpts(p => ({ ...p, description: e.target.value }))}
            placeholder="Brief description of what this API does..."
            rows={2}
            className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none resize-none"
          />
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs font-medium text-slate-600">
            Requirements (or paste a PRD / specs document)
          </label>
          <InstructionsBadge
            hasInstructions={!!instructions.trim()}
            onClick={() => setShowInstrModal(true)}
            disabled={generating}
          />
        </div>
        <textarea
          value={requirements}
          disabled={generating}
          onChange={e => setRequirements(e.target.value)}
          placeholder={"Describe what the API should do, what data it manages, key business rules...\n\nOr paste a Product Requirements Document here."}
          rows={6}
          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none resize-none"
        />
      </div>

      {showInstrModal && (
        <InstructionsModal
          mode="edit"
          value={instructions}
          onChange={setInstructions}
          onClose={() => setShowInstrModal(false)}
        />
      )}

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs font-medium text-slate-600">Endpoints (optional — AI will infer if blank)</label>
          <button onClick={addEndpoint} disabled={generating} className="flex items-center gap-1 text-xs text-emerald-600 hover:text-emerald-700 font-medium disabled:opacity-40">
            <Plus size={12} /> Add
          </button>
        </div>
        <div className="space-y-2">
          {opts.endpoints.map((ep, idx) => (
            <div key={idx} className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg border border-slate-100">
              <select
                value={ep.method}
                disabled={generating}
                onChange={e => updateEndpoint(idx, 'method', e.target.value)}
                className={`text-xs font-bold px-2 py-1 rounded ${METHOD_COLORS[ep.method]} border-0 outline-none`}
              >
                {['GET', 'POST', 'PUT', 'DELETE', 'PATCH'].map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <input
                value={ep.path}
                disabled={generating}
                onChange={e => updateEndpoint(idx, 'path', e.target.value)}
                placeholder="/api/..."
                className="flex-1 px-2 py-1 text-xs font-mono border border-slate-200 rounded outline-none"
              />
              <button onClick={() => removeEndpoint(idx)} disabled={generating} className="text-slate-400 hover:text-red-500 disabled:opacity-40">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          {opts.endpoints.length === 0 && (
            <p className="text-xs text-slate-400 italic">No endpoints defined — AI will generate based on requirements</p>
          )}
        </div>
      </div>

      {genError && <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">{genError}</div>}

      <button
        onClick={handleGenerate}
        disabled={generating || !canGenerate}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-medium text-sm rounded-lg transition-colors"
      >
        {generating
          ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Generating...</>
          : <><Play size={14} /> Generate API</>}
      </button>
    </div>
  ) : (
    <div className="flex-1 overflow-y-auto p-5 space-y-4">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Configuration</div>
      <div className="space-y-2 text-xs">
        <div className="flex justify-between"><span className="text-slate-400">Language</span><span className="font-medium text-slate-700">{entry.language === 'java' ? 'Java (Spring Boot)' : 'Python (FastAPI)'}</span></div>
        <div className="flex justify-between"><span className="text-slate-400">Auth</span><span className="font-medium text-slate-700">{entry.authType === 'basic' ? 'Basic Auth' : 'None'}</span></div>
        {entry.createdAt && <div className="flex justify-between"><span className="text-slate-400">Created</span><span className="font-medium text-slate-700">{fmtTime(entry.createdAt)}</span></div>}
        {liveUrl && <div className="flex justify-between items-start gap-2"><span className="text-slate-400 flex-shrink-0">URL</span><span className="font-medium text-slate-700 font-mono text-[11px] break-all text-right">{liveUrl}</span></div>}
      </div>

      <div className="pt-3 border-t border-slate-200 space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Refine API</div>
          <InstructionsBadge
            hasInstructions={!!instructions.trim()}
            onClick={() => setShowInstrModal(true)}
            disabled={generating}
          />
        </div>
        <p className="text-[11px] text-slate-400">
          Add new fields, endpoints, or entities to the existing API — e.g. "add a
          warrantyExpiry date field to Vehicles and return it in GET /vehicles" or
          "add a GET /technicians/{'{id}'}/workload endpoint". Renaming or removing
          existing fields/tables isn't supported here yet.
        </p>
        <textarea
          value={refinePrompt}
          disabled={generating}
          onChange={e => setRefinePrompt(e.target.value)}
          placeholder="Describe what to add or change..."
          rows={4}
          className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none resize-none"
        />
        <div>
          <label className="text-[11px] font-medium text-slate-500 block mb-1">
            Comment <span className="text-slate-400 font-normal">(optional — saved to history)</span>
          </label>
          <input
            className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-emerald-200 focus:border-emerald-400 outline-none"
            placeholder='e.g. "Added warranty field per support request"'
            value={comment}
            disabled={generating}
            onChange={e => setComment(e.target.value)}
          />
        </div>
        <button
          onClick={handleRefine}
          disabled={generating || !refinePrompt.trim()}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-medium text-sm rounded-lg transition-colors"
        >
          {generating
            ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Refining...</>
            : <><Sparkles size={14} /> Refine API</>}
        </button>
        {genError && <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">{genError}</div>}
      </div>
      {showInstrModal && (
        <InstructionsModal
          mode="edit"
          value={instructions}
          onChange={setInstructions}
          onClose={() => setShowInstrModal(false)}
        />
      )}
    </div>
  )

  const tabsPanel = (
    <>
    <div className="flex-1 min-w-0 min-h-0 flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 flex-shrink-0">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">{entry.title || entry.name}</h3>
          <p className="text-xs text-slate-500">{entry.description}</p>
        </div>
        <div className="flex items-center gap-2">
          {entry.language && <span className="px-2 py-1 rounded bg-slate-100 text-slate-600 border border-slate-200 text-xs">{entry.language}</span>}
          {entry.authType && <span className="px-2 py-1 rounded bg-slate-100 text-slate-600 border border-slate-200 text-xs">{entry.authType} auth</span>}
          <span className={`px-2 py-1 rounded border text-xs ${entry.status === 'running' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : entry.status === 'start_failed' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-slate-100 text-slate-600 border-slate-200'}`}>
            {entry.status}
          </span>
          {!isDraft && (entry.status === 'running'
            ? <button onClick={stop} disabled={!!busy} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-slate-100 hover:bg-slate-200 rounded-md transition-colors disabled:opacity-40">
                {busy === 'stopping' ? <span className="w-3 h-3 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" /> : <Square size={11} />}
                Stop
              </button>
            : <button onClick={start} disabled={!!busy} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-md transition-colors disabled:opacity-40">
                {busy === 'starting' ? <span className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" /> : <Play size={11} />}
                Start
              </button>
          )}
          <button onClick={del} disabled={!!busy} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-red-50 hover:bg-red-100 text-red-600 rounded-md transition-colors disabled:opacity-40">
            {busy === 'deleting' ? <span className="w-3 h-3 rounded-full border-2 border-red-400 border-t-transparent animate-spin" /> : <Trash2 size={12} />}
          </button>
        </div>
      </div>

      {entry.status === 'start_failed' && (
        <div className="m-4 mb-0 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex-shrink-0">
          The dev server didn't come up — check <span className="font-mono">api_server.log</span> in the project folder, then try Start again.
        </div>
      )}

      {deleteError && (
        <div className="m-4 mb-0 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 flex-shrink-0 flex items-start justify-between gap-3">
          <span>{deleteError}</span>
          <button onClick={() => setDeleteError(null)} className="text-red-400 hover:text-red-600 flex-shrink-0">
            <X size={12} />
          </button>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex border-b border-slate-200 flex-shrink-0">
        {([
          { id: 'preview',      label: 'Preview',      icon: <ExternalLink size={12} /> },
          { id: 'usage',        label: 'Usage',         icon: <RefreshCw size={12} /> },
          { id: 'examples',     label: 'Examples',      icon: <Beaker size={12} />, badge: examples?.length || undefined },
          { id: 'architecture', label: 'Architecture', icon: <LayoutGrid size={12} />, badge: architecture ? 1 : undefined },
          { id: 'log',          label: 'Build Log',    icon: <Terminal size={12} />, badge: buildLog.length || undefined },
          { id: 'history',      label: 'History',      icon: <Clock size={12} />, badge: history.length || undefined },
          { id: 'docker',       label: 'Docker',       icon: <Container size={12} />, badge: docker?.imageExists ? 1 : undefined },
        ] as { id: DetailTab; label: string; icon: React.ReactNode; badge?: number }[]).map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
              tab === t.id ? 'border-emerald-500 text-emerald-600' : 'border-transparent text-slate-500 hover:text-slate-600'
            }`}>
            {t.icon} {t.label}
            {t.badge ? <span className="ml-1 bg-slate-200 text-slate-600 text-xs px-1.5 py-0.5 rounded-full">{t.badge}</span> : null}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">

        {tab === 'preview' && (
          generating ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
              <div className="w-10 h-10 rounded-full border-2 border-slate-200 border-t-emerald-500 animate-spin" />
              <div className="text-slate-600 text-sm font-medium">
                Running the pipeline (architecture → data model → implementation → security → tests → packaging)…
              </div>
              <p className="text-slate-400 text-xs max-w-xs">Check the Build Log tab for detailed progress</p>
            </div>
          ) : isDraft ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-8">
              <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                <Server size={28} className="text-emerald-400" />
              </div>
              <div>
                <div className="text-slate-600 font-semibold mb-1">Not generated yet</div>
                <div className="text-slate-500 text-sm leading-relaxed max-w-sm">
                  Configure the language, auth, and requirements on the left, then click <span className="text-emerald-600 font-medium">Generate API</span>.
                </div>
              </div>
              <div className="flex flex-col gap-1.5 mt-2">
                {[
                  'Auto-generates OpenAPI / Swagger spec — try it out live, like Postman',
                  'Request & response validation',
                  'Database models + migrations',
                  'Deterministic throttling + usage metering, every generation',
                  'Basic auth (or none) out of the box — OKTA/SSO can come later',
                  'Test harness with example requests',
                  'Docker-ready with health checks',
                  'Python (FastAPI) or Java (Spring Boot)',
                ].map(f => (
                  <div key={f} className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="text-emerald-600">-</span>{f}
                  </div>
                ))}
              </div>
            </div>
          ) : busy === 'starting' ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center px-8">
              <div className="w-10 h-10 rounded-full border-2 border-slate-200 border-t-emerald-500 animate-spin" />
              <div className="text-slate-600 text-sm font-medium">Starting the {entry.language === 'java' ? 'Spring Boot' : 'FastAPI'} server…</div>
              <p className="text-slate-400 text-xs max-w-xs">
                {entry.language === 'java'
                  ? 'Java/Spring Boot startup (JPA, embedded Tomcat) typically takes 15-30 seconds — longer on the very first run if dependencies still need downloading.'
                  : 'This is usually quick — a few seconds.'}
              </p>
            </div>
          ) : needsAuth && !creds ? (
            <BasicAuthForm name={name} onAuthenticated={(username, password) => setCreds({ username, password })} />
          ) : (
            <div className="relative flex-1 min-h-0 flex flex-col">
              {needsAuth && (
                <button onClick={() => setCreds(null)}
                  className="absolute top-2 right-2 z-10 flex items-center gap-1 px-2 py-1 text-xs font-medium
                             bg-white border border-slate-200 rounded-md shadow-sm text-slate-500 hover:text-slate-700 hover:border-slate-300 transition-colors">
                  <LogOut size={11} /> Sign out
                </button>
              )}
              <PreviewFrame url={docsUrl} hasApp loading={false} />
            </div>
          )
        )}

        {tab === 'usage' && (
          <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-4">
            <div className="flex items-center justify-end gap-2">
              <button onClick={resetUsage} disabled={resettingUsage} title="Wipes the usage log — both the rate-limit counter and Total Requests/Recent Activity history. A dev/test convenience; can't be undone."
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-red-50 hover:bg-red-100 text-red-600 rounded-md transition-colors disabled:opacity-40">
                {resettingUsage
                  ? <span className="w-3 h-3 rounded-full border-2 border-red-300 border-t-red-600 animate-spin" />
                  : <RotateCcw size={11} />}
                Reset
              </button>
              <button onClick={loadUsage} className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-slate-100 hover:bg-slate-200 rounded-md transition-colors">
                <RefreshCw size={11} /> Refresh
              </button>
            </div>
            {liveUrl && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 font-mono">
                {liveUrl} — try <span className="font-semibold">{liveUrl}/health</span>
                {entry.authType === 'basic' && <> (credentials are in the generated .env file)</>}
              </div>
            )}
            {usage?.rate_limit && usage.rate_limit.limit > 0 && (() => {
              const { used, limit, windowSeconds } = usage.rate_limit
              const pct = Math.min(100, (used / limit) * 100)
              const level = pct >= 100 ? 'red' : pct >= 70 ? 'amber' : 'emerald'
              const c = {
                emerald: { bar: 'bg-emerald-500', text: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-300' },
                amber:   { bar: 'bg-amber-500',   text: 'text-amber-700',   bg: 'bg-amber-50',   border: 'border-amber-300' },
                red:     { bar: 'bg-red-500',     text: 'text-red-700',     bg: 'bg-red-50',     border: 'border-red-300' },
              }[level]
              return (
                <div className={`p-4 rounded-xl border-2 ${c.border} ${c.bg}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold text-slate-700">Rate Limit</span>
                    <span className={`text-2xl font-bold ${c.text}`}>{used} / {limit}</span>
                  </div>
                  <div className="h-3 bg-white/70 rounded-full overflow-hidden border border-slate-200">
                    <div className={`h-full rounded-full transition-all ${c.bar}`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1.5">
                    requests in the last {windowSeconds}s
                    {used >= limit && <span className="font-semibold text-red-600"> — limit reached, further requests return 429</span>}
                  </div>
                </div>
              )
            })()}
            {usage ? (
              <div className="bg-white border border-slate-200 rounded-lg p-4">
                <div className="grid grid-cols-4 gap-3 text-center">
                  <div><div className="text-lg font-bold text-slate-800">{usage.total_requests}</div><div className="text-[10px] text-slate-400">Total requests</div></div>
                  <div><div className="text-lg font-bold text-slate-800">{usage.requests_last_24h}</div><div className="text-[10px] text-slate-400">Last 24h</div></div>
                  <div><div className="text-lg font-bold text-slate-800">{usage.error_count}</div><div className="text-[10px] text-slate-400">Errors</div></div>
                  <div><div className="text-lg font-bold text-slate-800">{(usage.error_rate * 100).toFixed(1)}%</div><div className="text-[10px] text-slate-400">Error rate</div></div>
                </div>
                {usage.recent.length > 0 && (
                  <div className="mt-4">
                    <div className="text-xs font-semibold text-slate-600 mb-1.5">Recent Activity</div>
                    <div className="text-[11px] font-mono border border-slate-100 rounded-md">
                      {usage.recent.map((r, i) => (
                        <div key={i} className="flex items-center gap-2 px-2 py-1 border-b border-slate-50 last:border-0">
                          <span className="text-slate-400 w-16 shrink-0">{new Date(r.ts * 1000).toLocaleTimeString()}</span>
                          <span className="font-bold w-14 shrink-0 text-slate-600">{r.method}</span>
                          <span className="text-slate-700 truncate flex-1">{r.path}</span>
                          <span className={`w-8 shrink-0 text-right font-bold ${r.status_code >= 400 ? 'text-red-600' : 'text-emerald-600'}`}>{r.status_code}</span>
                          <span className="text-slate-400 w-14 shrink-0 text-right">{r.duration_ms}ms</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-slate-400 italic flex items-center gap-2">
                <FileCode size={12} /> {liveUrl ? 'Loading usage stats...' : 'Start the server to view usage stats.'}
              </div>
            )}
          </div>
        )}

        {tab === 'examples' && (
          <div className="flex-1 min-h-0 overflow-y-auto p-5 space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-500">Ready-to-run requests, built from real data currently in the database.</p>
              <button onClick={loadExamples} className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-slate-100 hover:bg-slate-200 rounded-md transition-colors">
                <RefreshCw size={11} /> Refresh
              </button>
            </div>

            {examplesLoading ? (
              <div className="text-xs text-slate-400 italic flex items-center gap-2">
                <Beaker size={12} /> Fetching live sample data…
              </div>
            ) : !examples || examples.length === 0 ? (
              <p className="text-slate-600 italic text-xs">
                {!liveUrl
                  ? 'Start the server to generate examples.'
                  : !architecture
                  ? 'No architecture recorded for this project (it was generated before this feature existed) — regenerate to get examples.'
                  : 'No examples available yet — try Refresh once the database has some data in it.'}
              </p>
            ) : (
              <div className="space-y-3">
                {examples.map((ex, i) => (
                  <div key={i} className="border border-slate-200 rounded-lg overflow-hidden">
                    <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 border-b border-slate-200">
                      <span className={`px-2 py-0.5 rounded font-bold text-xs ${METHOD_COLORS[ex.method] || 'bg-slate-100 text-slate-600'}`}>{ex.method}</span>
                      <span className="font-mono text-xs text-slate-700 truncate">{ex.path}</span>
                      {ex.entity && <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">{ex.entity}</span>}
                    </div>
                    {ex.description && <p className="text-xs text-slate-500 px-3 pt-2">{ex.description}</p>}
                    <div className="flex items-start gap-2 p-3">
                      <pre className="flex-1 min-w-0 text-[11px] font-mono text-slate-600 bg-slate-50 rounded-md p-2.5 overflow-x-auto whitespace-pre-wrap break-all">{ex.curl}</pre>
                      <button onClick={() => copyCurl(ex.curl, i)}
                        className="flex-shrink-0 flex items-center gap-1 px-2 py-1.5 text-xs font-medium bg-slate-100 hover:bg-slate-200 rounded-md transition-colors">
                        {copiedIdx === i ? <><Check size={11} className="text-emerald-600" /> Copied</> : <><Copy size={11} /> Copy</>}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'architecture' && (
          <div className="h-full min-h-0 overflow-hidden">
            {architecture ? (
              <iframe
                src={api.getApiArchitectureHtmlUrl(name)}
                className="w-full h-full border-0"
                title="Architecture"
              />
            ) : (
              <div className="p-6">
                <p className="text-slate-600 italic text-xs">
                  {isDraft ? 'No architecture document yet — generate the API to create one.' : 'No architecture recorded for this project (it was generated before this feature existed).'}
                </p>
              </div>
            )}
          </div>
        )}

        {tab === 'log' && (
          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
            {buildLog.length === 0 && !generating && (
              <p className="text-slate-600 italic text-xs">No build log yet — generate the API to record the first entry.</p>
            )}
            {buildLog.map((run, ri) => (
              <div key={ri} className="border border-slate-200 rounded-lg overflow-hidden">
                <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 border-b border-slate-200">
                  <span className="text-xs font-semibold text-emerald-600">{run.event || 'Build'}</span>
                  <span className="text-xs text-slate-600">{fmtTime(run.timestamp)}</span>
                  {run.duration_s > 0 && (
                    <span className="text-xs text-slate-400 ml-auto flex items-center gap-1"><Clock size={9} />{run.duration_s}s</span>
                  )}
                </div>
                <div className="font-mono text-xs p-3 space-y-0.5">
                  {cleanLogLines(run.lines).map((line, li) => (
                    <div key={li} className="text-slate-600">{line}</div>
                  ))}
                </div>
              </div>
            ))}
            {/* Live run in progress — same shape as the persisted cards above,
                just still streaming. No inner max-height/scroll on either card:
                the outer tab container above is already the full-height,
                scrollable region — a second nested scrollbar here just makes
                the log feel cramped into a small box. */}
            {generating && (
              <div className="border border-violet-200 rounded-lg overflow-hidden">
                <div className="flex items-center gap-3 px-3 py-2 bg-violet-50 border-b border-violet-200">
                  <span className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
                  <span className="text-xs font-semibold text-violet-700">In Progress…</span>
                </div>
                <div className="p-3">
                  <StageProgress names={API_STAGE_NAMES} stageInfo={latestCrewStage(progressLog)} />
                </div>
                <details className="border-t border-violet-100">
                  <summary className="px-3 py-1.5 text-xs text-slate-500 cursor-pointer select-none hover:bg-slate-50">
                    Build log details
                  </summary>
                  <div className="font-mono text-xs p-3 pt-0 space-y-0.5">
                  {cleanLogLines(progressLog).length === 0
                    ? <span className="text-slate-400 italic">Starting the pipeline…</span>
                    : cleanLogLines(progressLog).map((line, li) => (
                        <div key={li} className="text-slate-600">{line}</div>
                      ))}
                  </div>
                </details>
              </div>
            )}
          </div>
        )}

        {tab === 'history' && (
          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
            {history.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
                <Clock size={36} className="text-slate-300" />
                <p className="text-slate-600 text-sm font-semibold">No history yet</p>
                <p className="text-slate-500 text-xs leading-relaxed max-w-xs">Every generation and refinement is recorded here.</p>
              </div>
            ) : (
              [...history].reverse().map((h, i) => (
                <div key={i} className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-emerald-600">{h.event}</span>
                    <span className="ml-auto text-xs text-slate-600 flex items-center gap-1">
                      <Clock size={9} />{fmtTime(h.timestamp)}
                    </span>
                  </div>
                  {h.prompt && <p className="text-xs text-slate-500 leading-relaxed">{h.prompt}</p>}
                  {h.comment && <p className="text-xs text-slate-600 italic">"{h.comment}"</p>}
                  {h.instructions && (
                    <button
                      onClick={() => setViewInstructions(h.instructions!)}
                      className="flex items-center gap-1 text-xs text-emerald-600 hover:text-emerald-800 transition-colors"
                    >
                      <FileText size={10} /> View instructions
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {tab === 'docker' && (
          <div className="h-full overflow-y-scroll p-6 space-y-6">

            {isDraft && (
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-500">
                Generate the API first — Docker packages the files it produces.
              </div>
            )}

            {docker && !docker.dockerAvailable && (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg flex gap-3">
                <AlertCircle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-amber-700">Docker not available</p>
                  <p className="text-xs text-amber-600 mt-1">Install Docker Desktop and make sure it is running, then refresh.</p>
                </div>
              </div>
            )}

            {dockerError && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex gap-3">
                <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-red-700">Build Failed</p>
                  <p className="text-xs text-red-600 mt-1 break-words">{dockerError}</p>
                </div>
                <button onClick={() => setDockerError(null)} className="text-red-400 hover:text-red-600 flex-shrink-0">
                  <X size={16} />
                </button>
              </div>
            )}

            {/* Image */}
            <div className="border border-slate-200 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                    <Container size={14} className="text-emerald-600" /> Docker Image
                  </h3>
                  {docker?.imageExists
                    ? <div className="mt-1 space-y-0.5">
                        <p className="text-xs font-mono text-slate-500">{docker.imageTag}</p>
                        {docker.builtAt && <p className="text-xs text-slate-500">Built {fmtTime(docker.builtAt)}</p>}
                      </div>
                    : <p className="text-xs text-slate-500 mt-1">No image built yet</p>
                  }
                </div>
                {docker?.imageExists && (
                  <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />Ready
                  </span>
                )}
              </div>

              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={dockerBuildImage}
                  disabled={!!dockerBusy || isDraft}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white rounded-md transition-colors"
                >
                  {dockerBusy === 'build'
                    ? <><span className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />Building…</>
                    : <><RefreshCw size={12} />{docker?.imageExists ? 'Rebuild Image' : 'Build Image'}</>}
                </button>

                {docker?.imageExists && docker.containerStatus === 'none' && (
                  <button onClick={dockerRunContainer} disabled={!!dockerBusy}
                    className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-emerald-50 hover:bg-emerald-100 disabled:opacity-40 border border-emerald-200 text-emerald-700 rounded-md transition-colors">
                    {dockerBusy === 'run'
                      ? <><span className="w-3 h-3 rounded-full border border-emerald-400 border-t-transparent animate-spin" />Starting…</>
                      : <><Play size={12} />Run Container</>}
                  </button>
                )}

                <button
                  onClick={dockerDownload}
                  disabled={!!dockerBusy || !docker?.imageExists}
                  title={docker?.imageExists ? 'Download as .tar' : 'Build the image first'}
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-slate-100 hover:bg-slate-200 disabled:opacity-40 rounded-md transition-colors"
                >
                  {dockerBusy === 'download'
                    ? <><span className="w-3 h-3 rounded-full border border-slate-400 border-t-transparent animate-spin" />Saving…</>
                    : <><Download size={12} />Download .tar</>}
                </button>

                <button disabled title="Push to ECR — coming in a future release"
                  className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-slate-100 text-slate-400 rounded-md opacity-40 cursor-not-allowed">
                  <Upload size={12} />Push to ECR
                </button>
              </div>
            </div>

            {/* Container — only once one exists */}
            {docker?.imageExists && docker.containerStatus !== 'none' && (
              <div className="border border-slate-200 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                      <Layers size={14} className="text-violet-500" /> Container
                    </h3>
                    <p className="text-xs font-mono text-slate-500 mt-1">{docker.containerName}</p>
                  </div>
                  {docker.containerStatus === 'running' && (
                    <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />Running
                    </span>
                  )}
                  {docker.containerStatus === 'exited' && (
                    <span className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-100 border border-slate-200 text-slate-600 text-xs">
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />Stopped
                    </span>
                  )}
                </div>

                {docker.containerUrl && docker.containerStatus === 'running' && (
                  <a href={docker.containerUrl} target="_blank" rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-emerald-700 hover:text-emerald-800">
                    <ExternalLink size={11} />{docker.containerUrl}
                  </a>
                )}

                <div className="flex gap-2 flex-wrap items-center">
                  {docker.containerStatus === 'exited' ? (
                    <button onClick={dockerStartContainer} disabled={!!dockerBusy}
                      className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-emerald-50 hover:bg-emerald-100 disabled:opacity-40 border border-emerald-200 text-emerald-700 rounded-md transition-colors">
                      {dockerBusy === 'start'
                        ? <><span className="w-3 h-3 rounded-full border border-emerald-400 border-t-transparent animate-spin" />Starting…</>
                        : <><Play size={12} />Start Container</>}
                    </button>
                  ) : (
                    <button onClick={dockerStopContainer} disabled={!!dockerBusy}
                      className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-slate-100 hover:bg-slate-200 disabled:opacity-40 rounded-md transition-colors">
                      {dockerBusy === 'stop'
                        ? <><span className="w-3 h-3 rounded-full border border-slate-400 border-t-transparent animate-spin" />Stopping…</>
                        : <><Square size={12} />Stop Container</>}
                    </button>
                  )}

                  <button onClick={dockerDeleteContainer} disabled={!!dockerBusy}
                    className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium bg-red-50 hover:bg-red-100 disabled:opacity-40 border border-red-200 text-red-600 rounded-md transition-colors">
                    {dockerBusy === 'delete'
                      ? <><span className="w-3 h-3 rounded-full border border-red-400 border-t-transparent animate-spin" />Removing…</>
                      : <><Trash2 size={12} />Remove Container</>}
                  </button>

                  {docker.hostPort && (
                    <span className="text-xs text-slate-500 ml-auto">host port {docker.hostPort}</span>
                  )}
                </div>
              </div>
            )}

            {/* Build log */}
            {dockerLog.length > 0 && (
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <div className="px-3 py-2 bg-slate-50 border-b border-slate-200">
                  <span className="text-xs font-semibold text-emerald-600">Build Output</span>
                </div>
                <div className="font-mono text-xs p-3 space-y-0.5">
                  {dockerLog.map((line, i) => (
                    <div key={i} className="text-slate-600">{line}</div>
                  ))}
                  {dockerBusy === 'build' && <div className="text-slate-500 animate-pulse">Building…</div>}
                </div>
              </div>
            )}

          </div>
        )}
      </div>
    </div>
    {viewInstructions !== null && (
      <InstructionsModal
        mode="view"
        value={viewInstructions}
        title="Instructions"
        onClose={() => setViewInstructions(null)}
      />
    )}
    </>
  )

  return <ResizablePanels left={configPanel} right={tabsPanel} defaultLeftWidth={380} minLeft={280} maxLeft={520} />
}
