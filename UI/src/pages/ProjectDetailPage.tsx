import {
  AlertCircle, ArrowLeft, CheckCircle, Clock, Container, Copy, Download,
  ExternalLink, FileText, Image, Layers, LayoutGrid, Palette, Play, RefreshCw, Send, Square,
  Terminal, Trash2, Upload,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useProjectsCtx } from '../App'
import { Project } from '../types'
import PreviewFrame from '../components/PreviewFrame'
import ResizablePanels from '../components/ResizablePanels'
import StepProgress from '../components/StepProgress'
import InstructionsModal, { InstructionsBadge } from '../components/InstructionsModal'
import { api, DraftResult } from '../hooks/useApi'
import { draftToHtml } from '../utils/draftToHtml'
import { BuildLogRun, DockerStatus, GenerateResult, GenerateStep, HistoryEvent } from '../types'


// Format ISO timestamp to readable local time
function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

// Split "[HH:MM:SS +Xs] message" into prefix + body for styled rendering
function splitLogLine(line: string): { prefix: string; body: string } {
  const m = line.match(/^(\[\d{2}:\d{2}:\d{2} \+[\d.]+s\])\s*(.*)$/)
  return m ? { prefix: m[1], body: m[2] } : { prefix: '', body: line }
}

// Animated draft progress with elapsed timer and steps
const DRAFT_STEPS = ['Analyzing requirements', 'Designing page layouts', 'Creating wireframes', 'Finalizing draft']
function DraftProgress() {
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef(Date.now())
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 1000)
    return () => clearInterval(id)
  }, [])
  const activeStep = Math.min(Math.floor(elapsed / 8), DRAFT_STEPS.length - 1)
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 px-8">
      <div className="relative w-14 h-14">
        <svg className="w-14 h-14 animate-spin" viewBox="0 0 56 56">
          <circle cx="28" cy="28" r="24" fill="none" stroke="#e0e7ff" strokeWidth="4" />
          <circle cx="28" cy="28" r="24" fill="none" stroke="#4f46e5" strokeWidth="4"
            strokeDasharray="150.8" strokeDashoffset={150.8 * (1 - Math.min(elapsed / 45, 0.92))}
            strokeLinecap="round" className="transition-all duration-1000" />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-indigo-700">
          {elapsed}s
        </span>
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-indigo-700 mb-3">Generating draft wireframe…</p>
        <div className="flex flex-col gap-1.5 text-left">
          {DRAFT_STEPS.map((s, i) => (
            <div key={i} className={`flex items-center gap-2 text-xs transition-colors ${
              i < activeStep ? 'text-emerald-600' : i === activeStep ? 'text-indigo-600 font-medium' : 'text-slate-300'
            }`}>
              {i < activeStep
                ? <CheckCircle size={12} />
                : i === activeStep
                  ? <span className="w-3 h-3 rounded-full border-2 border-indigo-400 border-t-indigo-600 animate-spin" />
                  : <span className="w-3 h-3 rounded-full border border-slate-200" />}
              {s}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Internal step-control event names — never shown as log lines
const STEP_CONTROLS = /^(llm|write|install|start|ready|qa|figma_api|figma_api_done|screenshot_start|screenshot_done.*|llm_analysis.*|llm_codegen)$/

// Clean up persisted build log lines: filter control events, strip internal prefixes
function cleanLogLines(lines: string[]): string[] {
  return lines.flatMap(line => {
    const m = line.match(/^(\[\d{2}:\d{2}:\d{2} \+[\d.]+s\])\s*(.*)$/)
    const ts = m ? m[1] : ''
    const body = m ? m[2] : line
    if (STEP_CONTROLS.test(body.trim())) return []
    // Strip internal prefix like "llm_codegen:" → keep the human-readable part
    const clean = body.replace(/^[a-z_]+:/, '').trim()
    if (!clean) return []
    return [ts ? `${ts} ${clean}` : clean]
  })
}

export default function ProjectDetailPage() {
  const { name }    = useParams<{ name: string }>()
  const navigate    = useNavigate()

  // Shared context — same data source as sidebar
  const { projects, genMap, refresh: refreshProjects, setGenState } = useProjectsCtx()
  const project = projects.find((p: Project) => p.name === name) || null

  // Generation state lives in context so it persists across navigation
  const gen = genMap[name ?? ''] ?? { loading: false, step: null, log: [], error: '', result: null }
  const { loading, step, log, error, result } = gen
  const setLoading = (v: boolean)          => name && setGenState(name, { loading: v })
  const setStep    = (v: GenerateStep)     => name && setGenState(name, { step: v })
  const setLog     = (v: string[])         => name && setGenState(name, { log: v })
  const setError   = (v: string)           => name && setGenState(name, { error: v })
  const setResult  = (v: GenerateResult | null) => name && setGenState(name, { result: v })

  // Preview URL lives in context so sidebar Preview button updates this panel
  const { previewUrl, setPreviewUrl: setPreview } = useProjectsCtx()
  const onPreview = setPreview

  const [prompt,        setPrompt]    = useState('')
  const [figmaUrl,      setFigmaUrl]  = useState('')
  const [comment,       setComment]   = useState('')
  const [backendType,   setBackend]   = useState<'python' | 'java'>('python')
  const [instructions,  setInstructions] = useState('')
  const [showInstrModal, setShowInstrModal] = useState(false)
  const [viewInstructions, setViewInstructions] = useState<string | null>(null)
  const [sandboxCopied, setSandboxCopied] = useState(false)
  const [history,   setHistory]  = useState<HistoryEvent[]>([])
  const [showHistory,setShowHist]= useState(false)
  const [buildLog,  setBuildLog] = useState<BuildLogRun[]>([])
  const [rightTab,  setRightTab] = useState<'preview' | 'log' | 'history' | 'screenshots' | 'docker' | 'draft' | 'architecture'>('preview')
  const [screenshots, setScreenshots] = useState<{ filename: string; data: string; mimetype: string }[]>([])
  const [selectedShot, setSelectedShot] = useState<number>(0)
  const [docker,       setDocker]       = useState<DockerStatus | null>(null)
  const [dockerBusy,   setDockerBusy]   = useState<string | null>(null)  // 'build'|'run'|'stop'|'start'|'delete'|'download'
  const [dockerLog,    setDockerLog]    = useState<string[]>([])
  const [dockerError,  setDockerError]  = useState<string | null>(null)
  const [containerReady, setContainerReady] = useState(true)
  const dockerPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const healthPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [draft,        setDraft]        = useState<DraftResult | null>(null)
  const [draftLoading, setDraftLoading] = useState(false)
  const [architecture, setArchitecture] = useState<string>('')

  const loadArchitecture = async () => {
    if (!name) return
    try { const r = await api.getArchitecture(name); setArchitecture(r.markdown || '') } catch {}
  }

  const loadDockerStatus = async () => {
    if (!name) return
    try { setDocker(await api.getDockerStatus(name)) } catch {}
  }

  // Redirect to home if project doesn't exist (e.g., deleted then page refreshed)
  // Delay slightly to allow freshly-created projects to appear after refresh
  useEffect(() => {
    if (name && projects.length > 0 && !project) {
      const timer = setTimeout(() => {
        if (!projects.find((p: Project) => p.name === name)) {
          navigate('/', { replace: true })
        }
      }, 1500)
      return () => clearTimeout(timer)
    }
  }, [name, projects, project])

  // Auto-detect backend type from project metadata (locked once app is built)
  useEffect(() => {
    if (project?.backendType) {
      setBackend(project.backendType)
    }
  }, [project?.backendType, name])

  // Reset local state when switching projects
  useEffect(() => {
    if (dockerPollRef.current) { clearInterval(dockerPollRef.current); dockerPollRef.current = null }
    if (healthPollRef.current) { clearInterval(healthPollRef.current); healthPollRef.current = null }
    setContainerReady(true)
    setPrompt('')
    setFigmaUrl('')
    setComment('')
    setInstructions('')
    setHistory([])
    setShowHist(false)
    setScreenshots([])
    setSelectedShot(0)
    setDocker(null)
    setDockerLog([])
    setDockerBusy(null)
    setDockerError(null)
    setDraft(null)

    // Don't override rightTab if a build is already in progress (loading state from context)
    const currentGen = genMap[name ?? '']
    if (currentGen?.loading) {
      setRightTab('log')
    } else {
      setRightTab('preview')
      // Load saved draft from server for this project
      if (name) {
        api.getDraft(name).then(d => {
          if (d) { setDraft(d); setRightTab('draft') }
        }).catch(() => {})
      }
    }

    // Show preview if app is already running, otherwise clear
    const p = projects.find(x => x.name === name)
    if (p?.running && p.url) {
      setPreview(p.url)
    } else {
      setPreview(null)
    }
  }, [name])

  // Sync preview URL when project starts/stops (e.g. user clicks Start in sidebar)
  useEffect(() => {
    if (project?.running && project.url) {
      setPreview(project.url)
    } else if (project && !project.running) {
      setPreview(null)
    }
  }, [project?.running, project?.url])

  // Switch back to preview when build completes (only if still on log tab)
  useEffect(() => {
    if (!loading && step === 'ready' && rightTab === 'log') {
      setRightTab('preview')
    }
  }, [loading, step])


  // Load history
  const loadHistory = async () => {
    if (!name) return
    try { setHistory(await api.getHistory(name)) } catch {}
  }

  // Load persisted build log
  const loadBuildLog = async () => {
    if (!name) return
    try { const r = await api.getBuildLog(name); setBuildLog(r.runs || []) } catch {}
  }

  // Load screenshots
  const loadScreenshots = async () => {
    if (!name) return
    try {
      const r = await api.getScreenshots(name)
      setScreenshots(r.screenshots || [])
      if (r.screenshots?.length) setSelectedShot(0)
    } catch {}
  }

  useEffect(() => { loadHistory(); loadBuildLog(); loadScreenshots(); loadDockerStatus(); loadArchitecture() }, [name])

  const parseMessages = (msgs: string[]) => {
    const logLines: string[] = []
    let lastStep: GenerateStep = figmaUrl.trim() ? 'figma_api' : 'llm'
    for (const raw of msgs) {
      // Extract timestamp prefix and bare message body
      const tsMatch = raw.match(/^(\[\d{2}:\d{2}:\d{2} \+[\d.]+s\])\s*(.*)$/)
      const ts   = tsMatch ? tsMatch[1] : ''
      const body = tsMatch ? tsMatch[2] : raw
      if      (body === 'figma_api')                 { lastStep = 'figma_api' }
      else if (body === 'figma_api_done')            { lastStep = 'figma_api_done' }
      else if (body === 'screenshot_start')          { lastStep = 'screenshot_start' }
      else if (body.startsWith('screenshot_done'))   { lastStep = 'screenshot_done' }
      else if (body.startsWith('llm_analysis_done')) { lastStep = 'llm_analysis_done' }
      else if (body.startsWith('llm_analysis'))      { lastStep = 'llm_analysis' }
      else if (body.startsWith('llm_codegen:'))      {
        lastStep = 'llm_codegen'
        // Surface the human-readable part as a log line
        const msg = body.slice('llm_codegen:'.length).trim()
        if (msg) logLines.push(ts ? `${ts} ${msg}` : msg)
      }
      else if (body === 'llm')     { lastStep = 'llm' }
      else if (body === 'write')   { lastStep = 'write' }
      else if (body === 'install') { lastStep = 'install' }
      else if (body === 'start')   { lastStep = 'start' }
      else if (body === 'qa')      { lastStep = 'start' }
      else if (body === 'ready')   { lastStep = 'ready' }
      else if (body.startsWith('error:')) {
        lastStep = null
        const msg = body.slice('error:'.length).trim()
        if (msg) logLines.push(ts ? `${ts} ❌ ${msg}` : `❌ ${msg}`)
      }
      else {
        // Generic log line — strip any internal prefix
        const msg = body.replace(/^[a-z_]+:/, '').trim()
        if (msg) logLines.push(ts ? `${ts} ${msg}` : msg)
      }
    }
    return { lastStep, logLines }
  }

  // Poll progress using project-scoped endpoint (tab-safe) or request-id
  const pollUntilReady = (requestId?: string) => {
    let timer: ReturnType<typeof setInterval>
    let resolved = false
    const promise = new Promise<void>(resolve => {
      timer = setInterval(async () => {
        try {
          // Use request-specific endpoint if we have the requestId, else project-scoped
          const url = requestId
            ? `/api/generate/progress/${requestId}`
            : `/api/generate/progress/project/${name}`
          const r = await fetch(url)
          if (!r.ok) return
          const d = await r.json()
          const msgs: string[] = d.log || []
          if (!msgs.length) return
          const { lastStep, logLines } = parseMessages(msgs)
          setStep(lastStep); setLog(logLines)
          if ((lastStep as string) === 'ready' && !resolved) {
            resolved = true
            resolve()
          }
        } catch {}
      }, 800)
    })
    const stop = () => { clearInterval(timer) }
    return { promise, stop }
  }

  const runWithProgress = async (
    apiFn: () => Promise<GenerateResult>,
    hasFigma: boolean
  ) => {
    setLoading(true); setError(''); setResult(null); setLog([])
    setStep(hasFigma ? 'figma_api' : 'llm')
    setRightTab('log')  // Immediately switch to build log tab

    try {
      // API now returns immediately with { requestId, status }
      const initial = await apiFn() as any
      const requestId = initial.requestId as string

      // Start polling with the specific request ID (tab-safe)
      const { promise: readyPromise, stop } = pollUntilReady(requestId)

      // Poll job status until completed or failed
      const pollJob = async (): Promise<GenerateResult | null> => {
        while (true) {
          await new Promise(r => setTimeout(r, 2000))
          try {
            const job = await api.getJobStatus(requestId)
            if (job.status === 'completed') return job.result as GenerateResult
            if (job.status === 'failed') throw new Error(job.error || 'Generation failed')
          } catch (e: any) {
            if (e.message?.includes('not found')) continue
            throw e
          }
        }
      }

      // Race: either 'ready' from progress poll OR job completion
      const data = await Promise.race([
        readyPromise.then(() => null as GenerateResult | null),
        pollJob(),
      ])
      stop()

      setStep('ready')
      setLoading(false)
      setInstructions('')

      if (data?.url) {
        setResult(data)
        setPreview(data.url)
        onPreview(data.url)
      } else {
        const updated = await api.listProjects()
        const p = updated.find(x => x.name === name)
        if (p?.url) { setPreview(p.url); onPreview(p.url) }
      }
      refreshProjects(); loadHistory(); loadBuildLog(); loadScreenshots(); loadArchitecture()

    } catch (e: any) {
      setError(e.message); setStep(null); setLoading(false)
      setRightTab('log')  // Stay on log tab to show what happened
      loadBuildLog(); loadArchitecture()
    }
  }

  // Reconnect to a running/failed job, or clear stale loading state for completed jobs
  useEffect(() => {
    if (!name) return
    let cancelled = false
    const reconnect = async () => {
      try {
        const { id, log } = await api.getProgressByProject(name) as any
        if (cancelled || !id) {
          // No active job for this project — clear any stale loading state
          if (loading) { setLoading(false); setStep(null); setLog([]) }
          return
        }
        const job = await api.getJobStatus(id)
        if (cancelled) return

        // Job already completed — clear stale loading state, show preview
        if (job.status === 'completed') {
          setLoading(false); setStep(null); setLog([])
          // Ensure preview shows the running app
          const updated = await api.listProjects()
          const p = updated.find(x => x.name === name)
          if (p?.url) { setPreview(p.url); onPreview(p.url) }
          refreshProjects(); loadBuildLog(); loadArchitecture()
          return
        }

        // Job failed — show error
        if (job.status === 'failed') {
          setLoading(false); setStep(null)
          if (log?.length) {
            const { logLines } = parseMessages(log)
            setLog(logLines)
          }
          setError(job.error || 'Generation failed')
          setRightTab('log')
          loadBuildLog(); loadArchitecture()
          return
        }

        // Job is still running — reconnect to it
        if (job.status === 'running' && log?.length) {
          setLoading(true)
          setRightTab('log')
          const { lastStep, logLines } = parseMessages(log)
          setStep(lastStep); setLog(logLines)

          const { promise: readyPromise, stop } = pollUntilReady(id)
          const pollJob = async (): Promise<any> => {
            while (true) {
              await new Promise(r => setTimeout(r, 2000))
              if (cancelled) return null
              try {
                const j = await api.getJobStatus(id)
                if (j.status === 'completed') return j.result
                if (j.status === 'failed') throw new Error(j.error || 'Generation failed')
              } catch (e: any) {
                if (e.message?.includes('not found')) continue
                throw e
              }
            }
          }
          const data = await Promise.race([
            readyPromise.then(() => null),
            pollJob(),
          ])
          stop()
          if (cancelled) return
          setStep('ready')
          setLoading(false)
          if (data?.url) {
            setResult(data); setPreview(data.url); onPreview(data.url)
          } else {
            const updated = await api.listProjects()
            const p = updated.find(x => x.name === name)
            if (p?.url) { setPreview(p.url); onPreview(p.url) }
          }
          refreshProjects(); loadHistory(); loadBuildLog(); loadScreenshots(); loadArchitecture()
        }
      } catch (e: any) {
        if (!cancelled) {
          setLoading(false)
          if (e.message && !e.message.includes('not found')) setError(e.message)
        }
      }
    }
    reconnect()
    return () => { cancelled = true }
  }, [name])

  const canDraft = !!(prompt.trim() || instructions.trim() || project?.prompt)
  const previewDraft = async () => {
    if (!canDraft || draftLoading || loading) return
    const effectivePrompt = prompt.trim() || project?.prompt || 'Please create a draft using the instructions provided.'
    setDraftLoading(true); setError('')
    setRightTab('draft')
    try {
      const result = await api.draft(effectivePrompt, name, instructions.trim() || undefined)
      setDraft(result)
    } catch (e: any) { setError(e.message) }
    finally { setDraftLoading(false) }
  }

  const buildFromDraft = async () => {
    if (!draft || loading) return
    const arch = draft.architecture
    if (hasApp) {
      await runWithProgress(
        () => api.refine(name!, prompt.trim(), comment.trim() || undefined, instructions.trim() || undefined, arch, backendType),
        false
      )
    } else {
      await runWithProgress(
        () => api.generate(prompt.trim(), name, figmaUrl.trim() || undefined, instructions.trim() || undefined, arch, backendType),
        false
      )
    }
  }

  const generate = async () => {
    if ((!prompt.trim() && !figmaUrl.trim() && !instructions.trim()) || loading) return
    // If only instructions were provided (no prompt), use a generic prompt
    const effectivePrompt = prompt.trim() || (instructions.trim() ? 'Please create this web app using the instructions provided.' : '')
    await runWithProgress(
      () => api.generate(effectivePrompt, name, figmaUrl.trim() || undefined, instructions.trim() || undefined, undefined, backendType),
      !!figmaUrl.trim()
    )
  }

  const refine = async () => {
    if ((!prompt.trim() && !instructions.trim()) || !name || loading) return
    const effectivePrompt = prompt.trim() || 'Please refine this app using the instructions provided.'
    await runWithProgress(
      () => api.refine(name, effectivePrompt, comment.trim(), instructions.trim() || undefined, undefined, backendType),
      false
    )
  }

  const dockerBuildImage = async () => {
    if (!name) return
    setDockerBusy('build'); setDockerLog([]); setDockerError(null); setRightTab('docker')
    try {
      // Poll progress using project-scoped endpoint
      if (dockerPollRef.current) clearInterval(dockerPollRef.current)
      dockerPollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`/api/generate/progress/project/${name}`)
          if (!r.ok) return
          const d = await r.json()
          const lines: string[] = (d.log || [])
            .filter((l: string) => l.includes('docker_build:'))
            .map((l: string) => l.replace(/^.*docker_build:/, '').trim())
            .filter(Boolean)
          if (lines.length) setDockerLog(lines)
        } catch {}
      }, 800)
      const result = await api.buildDockerImage(name)
      if (dockerPollRef.current) { clearInterval(dockerPollRef.current); dockerPollRef.current = null }
      setDocker(result)
      loadDockerStatus()
    } catch (e: any) {
      const msg = e.message || 'Build failed'
      const lower = msg.toLowerCase()
      const isDockerIssue = ['docker not found', 'docker desktop', 'not fully running', 'grpc', 'eof', 'daemon', 'connection refused'].some(k => lower.includes(k))
      setDockerError(isDockerIssue
        ? 'Docker Desktop is not running or not fully ready. Please ensure Docker Desktop is started and the whale icon shows "running" in the system tray, then try again.'
        : `Build failed: ${msg}`)
      loadDockerStatus()
    } finally { setDockerBusy(null) }
  }

  const pollContainerHealth = (url: string) => {
    if (healthPollRef.current) clearInterval(healthPollRef.current)
    setContainerReady(false)
    let attempts = 0
    // Poll the /api/tables endpoint (guaranteed to exist) instead of root URL
    // Root URL may return HTML from nginx before the backend API is actually up
    const healthUrl = url.replace(/\/$/, '') + '/api/tables'
    healthPollRef.current = setInterval(async () => {
      attempts++
      try {
        const r = await fetch(healthUrl)
        if (r.ok) {
          setContainerReady(true)
          if (healthPollRef.current) { clearInterval(healthPollRef.current); healthPollRef.current = null }
        }
      } catch {
        // Not ready yet — connection refused or network error
      }
      if (attempts >= 45) {
        setContainerReady(true) // stop polling after 90s, let user try manually
        if (healthPollRef.current) { clearInterval(healthPollRef.current); healthPollRef.current = null }
      }
    }, 2000)
  }

  const dockerRunContainer = async () => {
    if (!name) return; setDockerBusy('run')
    try {
      const result = await api.runDockerContainer(name)
      setDocker(result)
      if (backendType === 'java' && result.containerUrl) pollContainerHealth(result.containerUrl)
    }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerStopContainer = async () => {
    if (!name) return; setDockerBusy('stop')
    if (healthPollRef.current) { clearInterval(healthPollRef.current); healthPollRef.current = null }
    setContainerReady(true)
    try { setDocker(await api.stopDockerContainer(name)) }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerStartContainer = async () => {
    if (!name) return; setDockerBusy('start')
    try {
      const result = await api.startDockerContainer(name)
      setDocker(result)
      if (backendType === 'java' && result.containerUrl) pollContainerHealth(result.containerUrl)
    }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerDeleteContainer = async () => {
    if (!name) return; setDockerBusy('delete')
    try { setDocker(await api.deleteDockerContainer(name)) }
    catch (e: any) { setDockerLog(prev => [...prev, `Error: ${e.message}`]) }
    finally { setDockerBusy(null) }
  }

  const dockerDownload = async () => {
    if (!name) return; setDockerBusy('download')
    try { api.downloadDockerImage(name) }
    finally { setTimeout(() => setDockerBusy(null), 1500) }
  }

  const canGenerate = (prompt.trim().length > 0 || figmaUrl.trim().length > 0 || instructions.trim().length > 0) && !loading
  const isRunning   = project?.running ?? false
  const hasApp      = project?.hasApp ?? false


  const _leftPanel = (
    <div className="border-r border-slate-200 flex flex-col h-full overflow-hidden">

        {/* Header */}
        <div className="p-4 border-b border-slate-200">
          <button onClick={() => navigate('/')} className="btn-ghost text-xs mb-3 -ml-1">
            <ArrowLeft size={13} /> Projects
          </button>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h2 className="font-bold text-slate-800 text-base truncate">{name}</h2>
              {isRunning
                ? <span className="badge-running mt-1 inline-flex">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />Running
                  </span>
                : hasApp
                  ? <span className="badge-stopped mt-1 inline-flex">Stopped</span>
                  : null
              }
            </div>
          </div>
        </div>

        {/* Prompt area */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">

          {/* Figma URL */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <Palette size={11} /> Figma URL
              <span className="text-slate-400 font-normal normal-case tracking-normal">(optional)</span>
            </label>
            <input className="input text-xs"
              placeholder="https://www.figma.com/design/..."
              value={figmaUrl} onChange={e => setFigmaUrl(e.target.value)}
              disabled={loading} />
          </div>

          {/* Prompt */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {figmaUrl ? 'Additional Instructions' : hasApp ? 'Refine or Rebuild' : 'Describe App'}
              </label>
              <InstructionsBadge
                hasInstructions={!!instructions.trim()}
                onClick={() => setShowInstrModal(true)}
                disabled={loading}
              />
            </div>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) hasApp && !figmaUrl.trim() ? refine() : generate() }}
              disabled={loading}
              placeholder={hasApp && !figmaUrl.trim()
                ? 'e.g. "add a login screen" or "make the sidebar collapsible"'
                : 'Describe the app to build…'}
              className="input resize-none h-28 leading-relaxed text-xs" />
          </div>

          {/* Optional comment — saved to history alongside the prompt */}
          {hasApp && (
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                Comment
                <span className="text-slate-400 font-normal normal-case tracking-normal">(optional — saved to history)</span>
              </label>
              <input
                className="input text-xs"
                placeholder='e.g. "Added login screen per design review feedback"'
                value={comment}
                onChange={e => setComment(e.target.value)}
                disabled={loading}
              />
            </div>
          )}

          {/* Backend type selector — locked once app is built */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 whitespace-nowrap">Backend:</span>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden flex-1">
              <button
                type="button"
                onClick={() => !hasApp && setBackend('python')}
                disabled={loading || hasApp}
                className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
                  backendType === 'python'
                    ? 'bg-indigo-600 text-white'
                    : hasApp ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-white text-slate-500 hover:text-slate-700'
                }`}
              >
                Python FastAPI
              </button>
              <button
                type="button"
                onClick={() => !hasApp && setBackend('java')}
                disabled={loading || hasApp}
                className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
                  backendType === 'java'
                    ? 'bg-indigo-600 text-white'
                    : hasApp ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'bg-white text-slate-500 hover:text-slate-700'
                }`}
              >
                Java Spring Boot
              </button>
            </div>
          </div>

          {/* Action buttons */}
          {hasApp && !figmaUrl.trim() ? (
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <button onClick={refine} disabled={loading || draftLoading || (!prompt.trim() && !instructions.trim())}
                  className="btn-primary flex-1 justify-center py-2.5">
                  {loading
                    ? <><span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />Updating…</>
                    : <><Send size={14} />Refine App</>}
                </button>
                <button onClick={generate} disabled={loading || draftLoading || !canGenerate}
                  className="btn-ghost px-3 py-2.5" title="Regenerate from scratch">
                  <RefreshCw size={14} />
                </button>
              </div>
              <button onClick={previewDraft} disabled={loading || draftLoading || !canDraft}
                className="flex items-center justify-center gap-2 w-full py-2 rounded-lg text-xs font-medium border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                {draftLoading
                  ? <><span className="w-3.5 h-3.5 rounded-full border-2 border-indigo-300 border-t-indigo-600 animate-spin" />Drafting…</>
                  : <><FileText size={13} />{hasApp ? 'Refine Draft' : 'Generate Draft'}</>}
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <button onClick={generate} disabled={!canGenerate || draftLoading}
                className="btn-primary w-full justify-center py-2.5">
                {loading
                  ? <><span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />Building…</>
                  : figmaUrl
                    ? <><Palette size={14} />{hasApp ? 'Rebuild from Figma' : 'Build from Figma'}</>
                    : <><Send size={14} />Generate App</>}
              </button>
              {!figmaUrl.trim() && (
                <button onClick={previewDraft} disabled={loading || draftLoading || !canDraft}
                  className="flex items-center justify-center gap-2 w-full py-2 rounded-lg text-xs font-medium border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  {draftLoading
                    ? <><span className="w-3.5 h-3.5 rounded-full border-2 border-indigo-300 border-t-indigo-600 animate-spin" />Drafting…</>
                    : <><FileText size={13} />{hasApp ? 'Refine Draft' : 'Generate Draft'}</>}
                </button>
              )}
            </div>
          )}
          <p className="text-xs text-slate-600 text-center -mt-2">
            {hasApp && !figmaUrl.trim() ? 'Refine updates · Generate draft first · ↺ rebuilds' : 'Generate draft before building · Ctrl+Enter to generate'}
          </p>

          {/* Error */}
          {error && (
            <div className="card p-3 border-red-200 bg-red-50 flex gap-2">
              <AlertCircle size={14} className="text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-600 leading-relaxed break-words">{error}</p>
            </div>
          )}

          {/* History / Quick Start */}
          {!loading && (
            <div>
              {hasApp ? (
                <div>
                  <button onClick={() => setShowHist(v => !v)}
                    className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 w-full hover:text-slate-600 transition-colors">
                    <Clock size={11} /> Project History
                    <span className="ml-auto">{showHistory ? '▾' : '▸'}</span>
                  </button>
                  {showHistory && (
                    <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                      {history.length === 0
                        ? <p className="text-xs text-slate-600 italic">No history yet.</p>
                        : history.map((h, i) => (
                          <div key={i} className="bg-slate-50 border border-slate-200 rounded-lg p-2.5">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-bold text-slate-700">{h.event}</span>
                              <span className="text-xs text-slate-600 ml-auto flex items-center gap-1">
                                <Clock size={9} />{fmtTime(h.timestamp)}
                              </span>
                            </div>
                            {h.figmaUrl && <a href={h.figmaUrl} target="_blank" rel="noreferrer"
                              className="text-xs text-indigo-600 hover:text-indigo-800 break-all block mb-1">{h.figmaUrl.slice(0,60)}…</a>}
                            {h.prompt && <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">{h.prompt}</p>}
                          </div>
                        ))
                      }
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Quick Start</div>
                  <div className="space-y-2">
                    {[
                      'IPL cricket dashboard. Pages: Dashboard (team scores, match results, top scorers KPIs), Analytics (win/loss charts, player stats), Players (cards grid with team filter). Dark sidebar, indigo accents.',
                      'SaaS project management. Pages: Dashboard (KPI cards, activity feed), Projects (cards with status/progress), Team (member table), Settings (profile form). Clean white, blue accents.',
                      'E-commerce admin. Pages: Dashboard (revenue chart, orders table), Products (grid with prices), Orders (filterable table), Customers (searchable list). Minimal white.',
                      'Finance tracker. Pages: Overview (net worth, income/expense chart), Transactions (filterable table), Budget (progress bars), Reports (monthly charts). Dark, green accents.',
                    ].map((p, i) => (
                      <button key={i} onClick={() => setPrompt(p)}
                        className="w-full text-left text-xs text-slate-500 hover:text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg px-3 py-2.5 leading-relaxed transition-colors">
                        {p.slice(0, 80)}…
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
  )

  const _rightPanel = (
      <div className="flex-1 min-w-0 min-h-0 flex flex-col bg-white">

        {/* Tab bar */}
        <div className="flex border-b border-slate-200 flex-shrink-0">
          {([
            { id: 'draft',        label: 'Draft',        icon: <FileText size={12} />, badge: draft ? 1 : undefined },
            { id: 'preview',      label: 'Preview',      icon: <ExternalLink size={12} /> },
            { id: 'architecture', label: 'Architecture', icon: <LayoutGrid size={12} />, badge: architecture ? 1 : undefined },
            { id: 'log',          label: 'Build Log',    icon: <Terminal size={12} />, badge: buildLog.length || undefined },
            { id: 'history',      label: 'History',      icon: <Clock size={12} />, badge: history.length || undefined },
            { id: 'screenshots',  label: 'Screenshots',  icon: <Image size={12} />, badge: screenshots.length || undefined },
            { id: 'docker',       label: 'Docker',       icon: <Container size={12} />, badge: docker?.imageExists ? 1 : undefined },
          ] as { id: 'preview'|'log'|'history'|'screenshots'|'docker'|'draft'|'architecture'; label: string; icon: React.ReactNode; badge?: number }[]).map(t => (
            <button key={t.id} onClick={() => setRightTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                rightTab === t.id
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-slate-500 hover:text-slate-600'
              }`}>
              {t.icon} {t.label}
              {t.badge ? <span className="ml-1 bg-slate-200 text-slate-600 text-xs px-1.5 py-0.5 rounded-full">{t.badge}</span> : null}
            </button>
          ))}
          {hasApp && !loading && (
            <div className="ml-auto flex items-center gap-2 px-4">
              {result && <><CheckCircle size={13} className="text-emerald-600" /><span className="text-xs text-emerald-700 font-medium">{result.title}</span></>}
              <button onClick={() => { navigator.clipboard.writeText(`${window.location.origin}/app/${name}/`).then(() => { setSandboxCopied(true); setTimeout(() => setSandboxCopied(false), 2000) }) }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-indigo-700 hover:bg-indigo-600 text-white transition-colors">
                {sandboxCopied ? <><CheckCircle size={11} /> Copied!</> : <><Copy size={11} /> Copy App Link</>}
              </button>
              <button onClick={() => window.open(`/app/${name}/`, '_blank')}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-600 transition-colors">
                <ExternalLink size={11} /> Open App
              </button>
              {docker?.containerStatus === 'running' && docker.containerUrl && (
                <button onClick={() => window.open(docker.containerUrl!, '_blank')}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 transition-colors">
                  <Layers size={11} /> Open Docker App
                </button>
              )}
            </div>
          )}
        </div>

        {/* Tab content */}
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">

          {/* Draft Preview */}
          {rightTab === 'draft' && (
            <div className="h-full min-h-0 overflow-hidden flex flex-col">
              {draft ? (
                <>
                  <div className="flex-1 min-h-0">
                    <iframe
                      srcDoc={draftToHtml(draft)}
                      className="w-full h-full border-0"
                      title="Draft Preview"
                    />
                  </div>
                  <div className="flex-shrink-0 bg-white border-t border-slate-200 py-3 flex gap-3 justify-center">
                    <button onClick={buildFromDraft}
                      className="px-6 py-2.5 rounded-lg text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors shadow-sm">
                      ✓ Looks Good — Build It
                    </button>
                    <button onClick={() => setRightTab('preview')}
                      className="px-6 py-2.5 rounded-lg text-sm font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors">
                      ✎ Revise
                    </button>
                  </div>
                </>
              ) : draftLoading ? (
                <DraftProgress />
              ) : (
                <div className="text-center text-slate-500 mt-20">
                  <FileText size={40} className="mx-auto mb-3 text-slate-300" />
                  <p className="text-sm">No draft yet.</p>
                  <p className="text-xs text-slate-400 mt-1">Click “Generate Draft” to see a wireframe before building.</p>
                </div>
              )}
            </div>
          )}

          {/* Preview */}
          {rightTab === 'preview' && <PreviewFrame url={previewUrl} loading={loading} step={step} hasApp={hasApp} />}

          {/* Architecture */}
          {rightTab === 'architecture' && (
            <div className="h-full min-h-0 overflow-hidden">
              {architecture ? (
                <iframe
                  src={api.getArchitectureHtmlUrl(name!)}
                  className="w-full h-full border-0"
                  title="Architecture"
                />
              ) : (
                <div className="p-6">
                  <p className="text-slate-600 italic text-xs">No architecture document yet — generate or refine the app to create one.</p>
                </div>
              )}
            </div>
          )}

          {/* Build Log — persisted runs oldest→newest, live run appended at bottom */}
          {rightTab === 'log' && (
            <div className="h-full min-h-0 flex flex-col">
              <div className="flex-1 min-h-0 overflow-y-scroll p-4 space-y-4">
                {buildLog.length === 0 && !loading && !step && (
                  <p className="text-slate-600 italic text-xs">No build log yet — run a generation to record the first entry.</p>
                )}
                {/* Persisted runs — oldest first */}
                {buildLog.map((run, ri) => (
                  <div key={ri} className="border border-slate-200 rounded-lg overflow-hidden">
                    <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 border-b border-slate-200">
                      <span className="text-xs font-semibold text-indigo-600">{run.event || 'Build'}</span>
                      <span className="text-xs text-slate-600">{fmtTime(run.timestamp)}</span>
                      {run.duration_s > 0 && (
                        <span className="text-xs text-slate-400 ml-auto flex items-center gap-1">
                          <Clock size={9} />{run.duration_s}s
                        </span>
                      )}
                    </div>
                    <div className="font-mono text-xs p-3 space-y-0.5">
                      {(() => {
                        const cleaned = cleanLogLines(run.lines)
                        if (cleaned.length === 0) return <span className="text-slate-400 italic">No log lines recorded.</span>
                        const isToken = (l: string) => /[━📊⏱️🔄│]|Token Usage|Input:|Output:|Total:.*\$/.test(l)
                        const mainLines: string[] = []
                        const tokenLines: string[] = []
                        let prevBody = ''
                        for (const line of cleaned) {
                          const { body } = splitLogLine(line)
                          if (isToken(body)) tokenLines.push(line)
                          else if (body !== prevBody) { mainLines.push(line); prevBody = body }
                        }
                        return (
                          <>
                            {mainLines.map((line, li) => {
                              const { prefix, body } = splitLogLine(line)
                              return (
                                <div key={li} className="text-slate-500 leading-relaxed">
                                  <span className="text-slate-400 mr-1">›</span>
                                  {prefix && <span className="text-slate-600 mr-1.5">{prefix}</span>}
                                  {body}
                                </div>
                              )
                            })}
                            {tokenLines.length > 0 && (
                              <div className="mt-2 pt-2 border-t border-slate-200">
                                {tokenLines.map((line, i) => (
                                  <div key={`t${i}`} className="text-emerald-600 leading-relaxed pl-4">
                                    {splitLogLine(line).body}
                                  </div>
                                ))}
                              </div>
                            )}
                          </>
                        )
                      })()}
                    </div>
                  </div>
                ))}
                {/* Live run in progress */}
                {(loading || (step && step !== 'ready')) && (
                  <div className="border border-violet-200 rounded-lg overflow-hidden">
                    <div className="flex items-center gap-3 px-3 py-2 bg-violet-50 border-b border-violet-200">
                      <span className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
                      <span className="text-xs font-semibold text-violet-700">In Progress…</span>
                    </div>
                    <div className="p-3">
                      <StepProgress current={step} log={[]} hasFigma={!!figmaUrl.trim()} />
                      {(() => {
                        const mainLines: string[] = []
                        const tokenLines: string[] = []
                        const isToken = (l: string) => /[━📊⏱️🔄│]|Token Usage|Input:|Output:|Total:.*\$/.test(l)
                        let prevBody = ''
                        for (const line of log) {
                          const { body } = splitLogLine(line)
                          if (isToken(body)) { tokenLines.push(line) }
                          else if (body !== prevBody) { mainLines.push(line); prevBody = body }
                        }
                        return (
                          <div className="font-mono text-xs mt-3 space-y-0.5">
                            {mainLines.map((line, i) => {
                              const { prefix, body } = splitLogLine(line)
                              return (
                                <div key={i} className="text-slate-500 leading-relaxed">
                                  <span className="text-slate-400 mr-1">›</span>
                                  {prefix && <span className="text-slate-600 mr-1.5">{prefix}</span>}
                                  {body}
                                </div>
                              )
                            })}
                            {tokenLines.length > 0 && (
                              <div className="mt-2 pt-2 border-t border-slate-200">
                                {tokenLines.map((line, i) => (
                                  <div key={`t${i}`} className="text-emerald-600 leading-relaxed pl-4">
                                    {splitLogLine(line).body}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* History tab */}
          {rightTab === 'history' && (
            <div className="h-full overflow-y-scroll p-4 space-y-3">
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
                      <span className="text-xs font-bold text-indigo-600">{h.event}</span>
                      <span className="ml-auto text-xs text-slate-600 flex items-center gap-1">
                        <Clock size={9} />{fmtTime(h.timestamp)}
                      </span>
                    </div>
                    {h.figmaUrl && (
                      <a href={h.figmaUrl} target="_blank" rel="noreferrer"
                        className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 break-all">
                        <ExternalLink size={10} className="flex-shrink-0" />{h.figmaUrl.slice(0, 70)}…
                      </a>
                    )}
                    {h.prompt && <p className="text-xs text-slate-500 leading-relaxed">{h.prompt}</p>}
                    {h.comment && <p className="text-xs text-slate-600 italic">"{h.comment}"</p>}
                    {h.instructions && (
                      <button
                        onClick={() => setViewInstructions(h.instructions!)}
                        className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800 transition-colors"
                      >
                        <FileText size={10} /> View instructions
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* Docker */}
          {rightTab === 'docker' && (
            <div className="h-full overflow-y-scroll p-6 space-y-6">

              {/* Docker not available */}
              {docker && !docker.dockerAvailable && (
                <div className="card p-4 border-amber-200 bg-amber-50 flex gap-3">
                  <AlertCircle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-amber-700">Docker not available</p>
                    <p className="text-xs text-amber-600 mt-1">Install Docker Desktop and make sure it is running, then refresh.</p>
                  </div>
                </div>
              )}

              {/* Build error */}
              {dockerError && (
                <div className="card p-4 border-red-200 bg-red-50 flex gap-3">
                  <AlertCircle size={16} className="text-red-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-red-700">Build Failed</p>
                    <p className="text-xs text-red-600 mt-1 break-words">{dockerError}</p>
                  </div>
                  <button onClick={() => setDockerError(null)} className="text-red-400 hover:text-red-600 flex-shrink-0">
                    <span className="text-lg leading-none">&times;</span>
                  </button>
                </div>
              )}

              {/* Image section */}
              <div className="card p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                      <Container size={14} className="text-indigo-600" /> Docker Image
                    </h3>
                    {docker?.imageExists
                      ? <div className="mt-1 space-y-0.5">
                          <p className="text-xs font-mono text-slate-500">{docker.imageTag}</p>
                          {docker.builtAt && <p className="text-xs text-slate-600">Built {fmtTime(docker.builtAt)}</p>}
                        </div>
                      : <p className="text-xs text-slate-600 mt-1">No image built yet</p>
                    }
                  </div>
                  {docker?.imageExists && (
                    <span className="badge-running text-xs"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />Ready</span>
                  )}
                </div>

                <div className="flex gap-2 flex-wrap">
                  {/* Build */}
                  <button
                    onClick={dockerBuildImage}
                    disabled={!!dockerBusy || !hasApp}
                    className="btn-primary text-xs px-3 py-2"
                  >
                    {dockerBusy === 'build'
                      ? <><span className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />Building…</>
                      : <><RefreshCw size={12} />{docker?.imageExists ? 'Rebuild Image' : 'Build Image'}</>}
                  </button>

                  {/* Run Container — only when image exists but no container */}
                  {docker?.imageExists && docker.containerStatus === 'none' && (
                    <button onClick={dockerRunContainer}
                      disabled={!!dockerBusy}
                      className="btn-success text-xs px-3 py-2">
                      {dockerBusy === 'run'
                        ? <><span className="w-3 h-3 rounded-full border border-emerald-400 border-t-transparent animate-spin" />Starting…</>
                        : <><Play size={12} />Run Container</>}
                    </button>
                  )}

                  {/* Download */}
                  <button
                    onClick={dockerDownload}
                    disabled={!!dockerBusy || !docker?.imageExists}
                    title={docker?.imageExists ? 'Download as .tar' : 'Build the image first'}
                    className="btn-ghost text-xs px-3 py-2"
                  >
                    {dockerBusy === 'download'
                      ? <><span className="w-3 h-3 rounded-full border border-slate-400 border-t-transparent animate-spin" />Saving…</>
                      : <><Download size={12} />Download .tar</>}
                  </button>

                  {/* Push to ECR — future release */}
                  <button
                    disabled
                    title="Push to ECR — coming in a future release"
                    className="btn-ghost text-xs px-3 py-2 opacity-40 cursor-not-allowed"
                  >
                    <Upload size={12} />Push to ECR
                  </button>
                </div>
              </div>

              {/* Container section — only when a container exists */}
              {docker?.imageExists && docker.containerStatus !== 'none' && (
                <div className="card p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                        <Layers size={14} className="text-violet-400" /> Container
                      </h3>
                      <p className="text-xs font-mono text-slate-500 mt-1">{docker.containerName}</p>
                    </div>
                    {docker.containerStatus === 'running' && (
                      <span className="badge-running text-xs"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />Running</span>
                    )}
                    {docker.containerStatus === 'exited' && (
                      <span className="badge-stopped text-xs"><span className="w-1.5 h-1.5 rounded-full bg-slate-600" />Stopped</span>
                    )}
                  </div>

                  {docker.containerUrl && docker.containerStatus === 'running' && (
                    containerReady ? (
                      <a href={docker.containerUrl} target="_blank" rel="noreferrer"
                        className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800">
                        <ExternalLink size={11} />{docker.containerUrl}
                      </a>
                    ) : (
                      <div className="flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-md">
                        <span className="w-3 h-3 rounded-full border-2 border-amber-400 border-t-transparent animate-spin" />
                        <span>Starting up — waiting for app to be ready...</span>
                      </div>
                    )
                  )}

                  <div className="flex gap-2 flex-wrap">
                    {docker.containerStatus === 'exited' ? (
                      <button onClick={dockerStartContainer}
                        disabled={!!dockerBusy}
                        className="btn-success text-xs px-3 py-2">
                        {dockerBusy === 'start'
                          ? <><span className="w-3 h-3 rounded-full border border-emerald-400 border-t-transparent animate-spin" />Starting…</>
                          : <><Play size={12} />Start Container</>}
                      </button>
                    ) : (
                      <button onClick={dockerStopContainer} disabled={!!dockerBusy}
                        className="btn-ghost text-xs px-3 py-2">
                        {dockerBusy === 'stop'
                          ? <><span className="w-3 h-3 rounded-full border border-slate-400 border-t-transparent animate-spin" />Stopping…</>
                          : <><Square size={12} />Stop Container</>}
                      </button>
                    )}

                    <button onClick={dockerDeleteContainer} disabled={!!dockerBusy}
                      className="btn-danger text-xs px-3 py-2">
                      {dockerBusy === 'delete'
                        ? <><span className="w-3 h-3 rounded-full border border-red-400 border-t-transparent animate-spin" />Removing…</>
                        : <><Trash2 size={12} />Remove Container</>}
                    </button>

                    {docker.hostPort && (
                      <span className="flex items-center text-xs text-slate-600 ml-auto">
                        host port {docker.hostPort}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Build log */}
              {dockerLog.length > 0 && (
                <div className="card overflow-hidden">
                  <div className="px-3 py-2 bg-slate-50 border-b border-slate-200">
                    <span className="text-xs font-semibold text-indigo-600">Build Output</span>
                  </div>
                  <div className="font-mono text-xs p-3 space-y-0.5 max-h-64 overflow-y-auto">
                    {dockerLog.map((line, i) => (
                      <div key={i} className="text-slate-500 leading-relaxed">
                        <span className="text-slate-400 mr-1">›</span>{line}
                      </div>
                    ))}
                    {dockerBusy === 'build' && (
                      <div className="text-slate-600 animate-pulse">Building…</div>
                    )}
                  </div>
                </div>
              )}

            </div>
          )}

          {/* Screenshots */}
          {rightTab === 'screenshots' && (
            <div className="h-full flex flex-col">
              {screenshots.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-8">
                  <Image size={40} className="text-slate-300" />
                  <p className="text-slate-600 text-sm font-semibold">No screenshots yet</p>
                  <p className="text-slate-400 text-xs leading-relaxed max-w-xs">
                    Screenshots are saved when a Figma URL is used to generate the app.
                  </p>
                </div>
              ) : (
                <div className="flex h-full min-h-0">
                  <div className="w-28 flex-shrink-0 border-r border-slate-200 overflow-y-auto p-2 space-y-2">
                    {screenshots.map((s, i) => (
                      <button key={i} onClick={() => setSelectedShot(i)}
                        className={`w-full rounded-lg overflow-hidden border-2 transition-colors ${selectedShot === i ? 'border-indigo-500' : 'border-slate-200 hover:border-slate-500'}`}>
                        <img src={`data:${s.mimetype};base64,${s.data}`} alt={s.filename} className="w-full object-cover" />
                        <p className="text-xs text-slate-500 truncate px-1 py-0.5 text-center">{i + 1}</p>
                      </button>
                    ))}
                  </div>
                  <div className="flex-1 min-w-0 flex flex-col items-center justify-center p-4 overflow-auto bg-slate-50">
                    {screenshots[selectedShot] && (
                      <>
                        <img src={`data:${screenshots[selectedShot].mimetype};base64,${screenshots[selectedShot].data}`}
                          alt={screenshots[selectedShot].filename}
                          className="max-w-full max-h-full object-contain rounded-lg shadow-2xl" />
                        <p className="text-xs text-slate-600 mt-2">{screenshots[selectedShot].filename}</p>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </div>
  )

  return (
    <>
      <ResizablePanels
        left={_leftPanel}
        right={_rightPanel}
        defaultLeftWidth={288}
      />
      {showInstrModal && (
        <InstructionsModal
          mode="edit"
          value={instructions}
          onChange={setInstructions}
          onClose={() => setShowInstrModal(false)}
        />
      )}
      {viewInstructions !== null && (
        <InstructionsModal
          mode="view"
          value={viewInstructions}
          title="Build Instructions"
          onClose={() => setViewInstructions(null)}
        />
      )}
    </>
  )
}
