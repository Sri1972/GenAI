import { AlertCircle, CheckCircle, Send, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import PreviewFrame from '../components/PreviewFrame'
import ResizablePanels from '../components/ResizablePanels'
import StepProgress from '../components/StepProgress'
import { api } from '../hooks/useApi'
import { GenerateResult, GenerateStep } from '../types'

const QUICK_PROMPTS = [
  'IPL cricket dashboard with sidebar navigation. Pages: Dashboard (team scores, match results table, top scorers KPI cards), Analytics (win/loss charts by team, player stats charts), Players (player cards grid with team filter dropdown). Dark sidebar with indigo accent colors.',
  'SaaS project management app with sidebar. Pages: Dashboard (KPI cards for tasks/projects/team, activity feed), Projects (project cards with status badges and progress bars), Team (member table with roles), Settings (profile and notification forms). Clean white/light design with blue accents.',
  'E-commerce admin panel. Pages: Dashboard (revenue line chart, orders table, product stats KPIs), Products (product grid with images and prices), Orders (filterable orders table with status badges), Customers (searchable customer list with purchase history). Minimal clean design.',
  'Personal finance tracker. Pages: Overview (net worth KPI, income vs expense area chart, recent transactions list), Transactions (filterable/sortable table), Budget (category budget cards with progress bars), Reports (monthly bar charts). Modern dark theme with green accents.',
]

// Labels shown in the live log panel for known progress event prefixes
const STEP_LABELS: Record<string, string> = {
  llm:              '🤖 Asking Claude to generate app…',
  llm_codegen:      '🤖 Claude is writing code…',
  skill:            '⚡ Skill',
  tsc_heal:         '🔧 TypeScript',
  write:            '💾 Writing files to disk…',
  install:          '📦 Installing packages…',
  start:            '🚀 Starting dev server…',
  ready:            '✅ App is ready!',
  figma_api:        '🎨 Fetching Figma design data…',
  screenshot_start: '📸 Exporting Figma frames…',
}

// Keys whose detail text is already a self-contained message — don't prepend the label
const DETAIL_ONLY_KEYS = new Set(['skill', 'tsc_heal', 'llm_codegen'])

function labelForLogLine(raw: string): string {
  // raw format: "[HH:MM:SS +Xs] event" or "[HH:MM:SS +Xs] llm_codegen:detail message"
  const inner = raw.replace(/^\[\d{2}:\d{2}:\d{2} \+[\d.]+s\] /, '')
  const colonIdx = inner.indexOf(':')
  const key = colonIdx > 0 ? inner.slice(0, colonIdx) : inner
  const detail = colonIdx > 0 ? inner.slice(colonIdx + 1).trim() : ''
  if (detail && DETAIL_ONLY_KEYS.has(key)) return detail
  // Show detail-only for lines that are clearly self-describing (token usage, separators)
  if (detail && /^[━═─📊⏱️🔄\s│$]/.test(detail)) return detail
  const prefix = STEP_LABELS[key] ?? `⚙️ ${key}`
  return detail ? `${prefix} — ${detail}` : prefix
}

function isTokenLine(raw: string): boolean {
  const inner = raw.replace(/^\[\d{2}:\d{2}:\d{2} \+[\d.]+s\] /, '')
  return /[━📊⏱️🔄│]|Token Usage|Input:|Output:|Total:.*\$/.test(inner)
}

// Bare step keys (no colon) are only used by StepProgress — hide from log text
const STEP_ONLY_KEYS = new Set(['llm', 'write', 'install', 'start', 'ready', 'qa', 'figma_api', 'screenshot_start'])
function isStepOnly(raw: string): boolean {
  const inner = raw.replace(/^\[\d{2}:\d{2}:\d{2} \+[\d.]+s\] /, '')
  return STEP_ONLY_KEYS.has(inner.trim())
}

interface Props {
  onGenerated: (url: string) => void
  onRefreshProjects: () => void
}

export default function GeneratePage({ onGenerated, onRefreshProjects }: Props) {
  const [prompt, setPrompt]       = useState('')
  const [backendType, setBackend] = useState<'python' | 'java'>('python')
  const [step, setStep]           = useState<GenerateStep>(null)
  const [error, setError]         = useState('')
  const [result, setResult]       = useState<GenerateResult | null>(null)
  const [loading, setLoading]     = useState(false)
  const [previewUrl, setPreview]  = useState<string | null>(null)
  const [liveLog, setLiveLog]     = useState<string[]>([])
  const [elapsedSec, setElapsed]  = useState(0)
  const pollRef   = useRef<ReturnType<typeof setInterval> | null>(null)
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll log to bottom whenever it updates
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [liveLog])

  const stopPolling = () => {
    if (pollRef.current)  { clearInterval(pollRef.current);  pollRef.current  = null }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
  }

  const requestIdRef = useRef<string | null>(null)

  const startPolling = (requestId?: string) => {
    stopPolling()
    setElapsed(0)

    // Elapsed-time ticker
    timerRef.current = setInterval(() => setElapsed(s => s + 1), 1000)

    // Progress log poller — uses request-specific endpoint when available
    pollRef.current = setInterval(async () => {
      try {
        const rid = requestId || requestIdRef.current
        const url = rid
          ? `/api/generate/progress/${rid}`
          : '/api/generate/progress/latest'
        const data = await fetch(url).then(r => r.json()) as { log: string[] }
        if (data.log?.length) {
          setLiveLog(data.log)
          const last = data.log[data.log.length - 1] ?? ''
          if (last.includes('ready') || last.includes('Vite server ready')) setStep('ready')
          else if (last.includes('start') || last.includes('Vite')) setStep('start')
          else if (last.includes('install') || last.includes('npm')) setStep('install')
          else if (last.includes('Writing') || last.includes('write')) setStep('write')
          else if (last.includes('llm') || last.includes('Claude')) setStep('llm')
        }
      } catch {
        // network hiccup — ignore
      }
    }, 1500)
  }

  const generate = async () => {
    if (!prompt.trim() || loading) return
    setLoading(true)
    setError('')
    setResult(null)
    setPreview(null)
    setLiveLog([])
    setStep('llm')

    try {
      // Fire-and-forget: returns immediately with requestId
      const { requestId } = await api.generate(prompt.trim(), undefined, undefined, undefined, undefined, backendType) as any
      requestIdRef.current = requestId
      startPolling(requestId)

      // Poll job status until completed or failed
      const pollJob = async (): Promise<any> => {
        while (true) {
          await new Promise(r => setTimeout(r, 2000))
          try {
            const job = await api.getJobStatus(requestId)
            if (job.status === 'completed') return job.result
            if (job.status === 'failed') throw new Error(job.error || 'Generation failed')
          } catch (e: any) {
            if (e.message?.includes('not found')) continue
            throw e
          }
        }
      }

      const data = await pollJob()
      setStep('ready')
      setResult(data)
      setPreview(data.url)
      onGenerated(data.url)
      onRefreshProjects()
    } catch (e: any) {
      setError(e.message)
      setStep(null)
    } finally {
      setLoading(false)
      stopPolling()
      requestIdRef.current = null
    }
  }

  const fmtElapsed = (s: number) =>
    s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`

  const leftPanel = (
    <div className="border-r border-slate-800 flex flex-col h-full overflow-hidden">
      <div className="p-4 border-b border-slate-800">
        <h1 className="font-bold text-base text-slate-100 flex items-center gap-2">
          <Zap size={16} className="text-indigo-400" /> Generate App
        </h1>
        <p className="text-xs text-slate-500 mt-1">Describe your app and AI will build it</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) generate() }}
          disabled={loading}
          placeholder={"Describe your app…\n\nTip: mention pages, data, style (dark/light, accent color)"}
          className="input resize-none h-40 leading-relaxed"
        />

        {/* Backend type selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 whitespace-nowrap">Backend:</span>
          <div className="flex rounded-lg border border-slate-700 overflow-hidden flex-1">
            <button
              type="button"
              onClick={() => setBackend('python')}
              disabled={loading}
              className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
                backendType === 'python'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              Python FastAPI
            </button>
            <button
              type="button"
              onClick={() => setBackend('java')}
              disabled={loading}
              className={`flex-1 px-3 py-1.5 text-xs font-medium transition-colors ${
                backendType === 'java'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              Java Spring Boot
            </button>
          </div>
        </div>

        <button onClick={generate} disabled={loading || !prompt.trim()} className="btn-primary w-full justify-center py-2.5 text-sm font-semibold">
          {loading
            ? <><span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />Building…</>
            : <><Send size={14} />Generate App</>
          }
        </button>
        <p className="text-xs text-slate-600 text-center -mt-1">Ctrl+Enter to generate</p>

        {/* ── Live build progress ── */}
        {loading && (
          <div className="card p-3 flex flex-col gap-3">
            {/* Coarse step tracker */}
            <StepProgress current={step} />

            {/* Elapsed timer */}
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Build in progress…</span>
              <span className="font-mono text-indigo-400">{fmtElapsed(elapsedSec)}</span>
            </div>

            {/* Live log feed */}
            {liveLog.length > 0 && (() => {
              const mainLines: string[] = []
              const tokenLines: string[] = []
              for (const line of liveLog) {
                if (isTokenLine(line)) tokenLines.push(line)
                else if (!isStepOnly(line)) mainLines.push(line)
              }
              // Deduplicate consecutive identical labels
              const deduped: string[] = []
              let prev = ''
              for (const line of mainLines) {
                const label = labelForLogLine(line)
                if (label !== prev) { deduped.push(line); prev = label }
              }
              return (
                <div className="bg-slate-950 rounded-lg border border-slate-800 overflow-hidden">
                  <div className="px-2.5 py-1.5 border-b border-slate-800 flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Build Log</span>
                    <span className="text-xs text-slate-600">{deduped.length} steps</span>
                  </div>
                  <div className="max-h-52 overflow-y-auto p-2 space-y-0.5">
                    {deduped.map((line, i) => {
                      const isLast = i === deduped.length - 1 && tokenLines.length === 0
                      return (
                        <div key={i} className={`flex items-start gap-1.5 text-xs leading-relaxed ${
                          isLast ? 'text-indigo-300' : 'text-slate-500'
                        }`}>
                          <span className="text-slate-700 mt-px shrink-0">›</span>
                          <span className="font-mono">{labelForLogLine(line)}</span>
                        </div>
                      )
                    })}
                    {tokenLines.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-slate-800">
                        {tokenLines.map((line, i) => (
                          <div key={`t${i}`} className="text-xs leading-relaxed text-emerald-400 font-mono pl-4">
                            {labelForLogLine(line)}
                          </div>
                        ))}
                      </div>
                    )}
                    <div ref={logEndRef} />
                  </div>
                </div>
              )
            })()}
          </div>
        )}

        {error && (
          <div className="card p-3 border-red-900/50 bg-red-950/30 flex gap-2">
            <AlertCircle size={14} className="text-red-400 flex-shrink-0 mt-0.5" />
            <div className="flex flex-col gap-1">
              <p className="text-xs font-semibold text-red-300">Build failed</p>
              <p className="text-xs text-red-400/80 leading-relaxed font-mono whitespace-pre-wrap break-words">{error.slice(0, 600)}{error.length > 600 ? '…' : ''}</p>
            </div>
          </div>
        )}

        {result && !loading && (
          <div className="card p-3 border-emerald-900/50 bg-emerald-950/20 animate-fade-in">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle size={14} className="text-emerald-400" />
              <span className="text-sm font-semibold text-emerald-300">{result.title}</span>
            </div>
            <div className="text-xs text-slate-500 mb-3">{result.files.length} files · port {result.port}</div>
            <div className="flex gap-2">
              <button onClick={() => setPreview(result.url)} className="btn-success flex-1 justify-center text-xs">Preview</button>
              <button onClick={() => window.open(result.url, '_blank')} className="btn-ghost flex-1 justify-center text-xs">New tab</button>
            </div>
          </div>
        )}

        {!loading && !result && (
          <div>
            <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Quick Start</div>
            <div className="space-y-2">
              {QUICK_PROMPTS.map((p, i) => (
                <button key={i} onClick={() => setPrompt(p)}
                  className="w-full text-left text-xs text-slate-500 hover:text-slate-300 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg px-3 py-2.5 leading-relaxed transition-colors">
                  {p.slice(0, 80)}…
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <ResizablePanels
      left={leftPanel}
      right={<PreviewFrame url={previewUrl} loading={loading} />}
      defaultLeftWidth={288}
    />
  )
}
