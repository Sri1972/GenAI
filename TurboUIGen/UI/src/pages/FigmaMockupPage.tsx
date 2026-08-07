import {
  AlertCircle, CheckCircle, Clock, Copy, ExternalLink, FileText, FolderOpen,
  Globe, Info, Layers, RefreshCw, Send, Settings2, Wifi, WifiOff,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useFigmaProjectsCtx } from '../App'
import InstructionsModal, { InstructionsBadge } from '../components/InstructionsModal'
import ResizablePanels from '../components/ResizablePanels'
import { api } from '../hooks/useApi'
import { McpStatus, WireframeMode } from '../types'

// ── Quick-start prompts ───────────────────────────────────────────────────────
const QUICK_PROMPTS = [
  'Build a simple 2-screen desktop web app to test prototype wiring. Screen 1 called Home: has a heading "Welcome", a search bar button labeled "Search...", and a button labeled "View Items". Screen 2 called Items: has a heading "Item List", a back button labeled "← Back to Home", and 3 item rows. The search bar on Home opens a small search popup overlay (400×300) with a text input and a Close button. The View Items button navigates to the Items screen. The Back button navigates to Home. Dark theme, blue accents, desktop 1440×900.',
  'Create a 3-screen desktop automotive analytics dashboard for OEM vehicle sales. Screens: Sales Overview (bar chart placeholder, top 5 OEMs table, YTD revenue stat cards), Vehicle Inventory (make/model/year table with status badges, search bar), Forecast (line chart placeholder, forecast summary cards). Light theme, navy and white with orange accents. Desktop layout 1440x900.',
  'Create a 3-screen desktop sports analytics web app. Screens: Dashboard (live scores table, top stats KPI cards, league standings), Players (searchable data table with avatar, name, position, stats columns), Match Detail (score header, match stats bar chart placeholder, key events timeline). Dark theme, blue accents. Desktop 1440x900.',
  'Create a 4-screen desktop SaaS project management web app. Screens: Dashboard (KPI cards for tasks/projects/team, activity feed), Projects (project cards with progress bars and status badges), Team (member table with roles and avatar), Settings (profile form, notification toggles). Clean white theme, indigo accents. Desktop 1440x900.',
]

// ── Mode descriptions ─────────────────────────────────────────────────────────
const MODES: { value: WireframeMode; label: string; desc: string; hint: string; safe: boolean }[] = [
  {
    value: 'new',
    label: 'New Wireframe',
    desc:  'Build all screens from scratch on a clean canvas. Tracks expected screens and resumes if the build stops early.',
    hint:  'Will warn if existing screens are found — clears the canvas first',
    safe:  false,
  },
  {
    value: 'edit',
    label: 'Edit Wireframe',
    desc:  'Edit existing screens (surgical changes) or add new screens alongside them. Nothing is deleted.',
    hint:  'Safest choice — existing screens are never removed',
    safe:  true,
  },
  {
    value: 'replace',
    label: 'Replace Wireframe',
    desc:  'Pre-delete screens matching your prompt, then rebuild them fresh. Other screens are untouched.',
    hint:  'Only deletes screens whose names match — others are preserved',
    safe:  false,
  },
]

// ── MCP status badge ──────────────────────────────────────────────────────────
function McpStatusBadge({ status, checking }: { status: McpStatus | null; checking: boolean }) {
  if (checking) return (
    <div className="flex items-center gap-1.5 text-xs text-slate-500">
      <span className="w-2 h-2 rounded-full border border-slate-500 border-t-transparent animate-spin" />
      Checking…
    </div>
  )
  if (!status) return (
    <div className="flex items-center gap-1.5 text-xs text-red-600">
      <WifiOff size={12} /> API backend offline — run start.bat
    </div>
  )
  if (!status.mcp_server) return (
    <div className="flex items-center gap-1.5 text-xs text-red-600">
      <WifiOff size={12} /> Figma MCP server offline
    </div>
  )
  if (!status.relay_connected) return (
    <div className="flex items-center gap-1.5 text-xs text-amber-600">
      <Wifi size={12} /> Server up · relay not connected
    </div>
  )
  return (
    <div className="flex items-center gap-1.5 text-xs text-emerald-700">
      <Wifi size={12} /> Ready · {status.tools} tools
    </div>
  )
}

// ── Log → user-friendly milestones ───────────────────────────────────────────
interface Milestone { icon: string; text: string; type: 'done' | 'active' | 'qa' | 'info' | 'error' | 'warn' }

function toMilestones(msgs: string[]): Milestone[] {
  const milestones: Milestone[] = []
  const seen = new Set<string>()

  const add = (icon: string, text: string, type: Milestone['type'] = 'done') => {
    if (!seen.has(text)) { seen.add(text); milestones.push({ icon, text, type }) }
  }
  const addAlways = (icon: string, text: string, type: Milestone['type'] = 'done') => {
    milestones.push({ icon, text, type })
  }

  const framesCreated = new Set<string>()
  let qaStarted    = false
  let qaIssuesFixed = 0
  let wiringErrors  = 0

  // Strip the timestamp prefix "[HH:MM:SS +N.Ns] " before matching
  const strip = (m: string) => m.replace(/^\[\d{2}:\d{2}:\d{2} \+[\d.]+s\]\s*/, '')

  for (const raw of msgs) {
    const m = strip(raw)

    // ── Skip decorative separators ─────────────────────────────────────────
    if (/^[═]{4,}/.test(m)) continue
    if (/^[━]{4,}/.test(m)) continue

    // ── Token usage summary ────────────────────────────────────────────────
    if (m.includes('📊 Token Usage')) {
      addAlways('📊', m.replace(/.*📊\s*/, ''), 'done')
      continue
    }
    if (/^\s+(Input|Output|Total):/.test(m)) {
      addAlways('💰', m.trim(), 'info')
      continue
    }

    // ══════════════════════════════════════════════════════════════════
    // DISCOVER PHASE (webapp → figma)
    // ══════════════════════════════════════════════════════════════════

    if (m.startsWith('[BROWSER]')) {
      const url = m.replace('[BROWSER]', '').trim()
      add('🌐', `Opening app: ${url}`, 'active')
      continue
    }

    if (m.startsWith('[LOGIN]')) {
      const msg = m.replace('[LOGIN]', '').trim()
      if (msg.includes('No login form'))
        add('🔓', 'No login required', 'info')
      else if (msg.includes('Signing in'))
        add('🔑', msg, 'active')
      else
        add('✅', msg)
      continue
    }

    if (m.startsWith('[DISCOVER]')) {
      const msg = m.replace('[DISCOVER]', '').trim()
      add('🔎', msg, 'active')
      continue
    }

    if (m.startsWith('[NAV]')) {
      const label = m.replace('[NAV]', '').replace('Navigating to:', '').trim()
      addAlways('↗', `Navigating: ${label}`, 'info')
      continue
    }

    if (m.startsWith('[SCREENSHOT]')) {
      const inner = m.replace('[SCREENSHOT]', '').trim()
      const numMatch = inner.match(/^\[(\d+)\]\s+(.+?)\s+—\s+(.+)$/)
      if (numMatch) {
        addAlways('📸', `Screenshot ${numMatch[1]}: ${numMatch[2]}`, 'done')
      } else {
        addAlways('📸', inner, 'done')
      }
      continue
    }

    if (m.startsWith('[SCREENSHOTS_DONE]')) {
      const msg = m.replace('[SCREENSHOTS_DONE]', '').trim()
      add('✅', msg)
      continue
    }

    // ══════════════════════════════════════════════════════════════════
    // VISION ANALYSIS PHASE
    // ══════════════════════════════════════════════════════════════════

    if (m.startsWith('[PHASE]')) {
      const msg = m.replace('[PHASE]', '').trim()
      if (msg.includes('Vision'))
        add('👁', msg, 'active')
      else if (msg.includes('Figma build'))
        add('🚀', 'Launching Figma build agent…', 'active')
      else if (msg.includes('Screenshot'))
        add('📷', msg, 'active')
      else
        add('⚙️', msg, 'active')
      continue
    }

    if (m.startsWith('[VISION]')) {
      const inner = m.replace('[VISION]', '').trim()
      const match = inner.match(/^\[(\d+)\/(\d+)\]\s+Analysing:\s+(.+)$/)
      if (match)
        addAlways('🔬', `Analysing page ${match[1]}/${match[2]}: ${match[3]}`, 'active')
      continue
    }

    if (m.startsWith('[VISION_DONE]')) {
      const inner = m.replace('[VISION_DONE]', '').trim()
      addAlways('✅', `Analysed: ${inner}`, 'done')
      continue
    }

    // ══════════════════════════════════════════════════════════════════
    // FIGMA BUILD PHASE — Phase headers (separator lines)
    // ══════════════════════════════════════════════════════════════════

    // Phase separator lines with content
    if (/^[─]{4,}/.test(m)) continue

    // Connection & setup
    if (m.includes('Loaded') && m.includes('tools'))
      add('🔌', 'Connected to Figma MCP — ready to build')
    if (m.includes('Figma connected'))
      add('🔌', m.replace(/^\s*/, '').trim())
    if (m.includes('Mobility Global Brand') || m.includes('BRANDING OVERRIDE'))
      add('🎨', 'Applying Mobility Global brand colors', 'info')

    // Pre-delete
    if (m.includes('Clearing') && m.includes('existing frame'))
      add('🗑', m.replace(/^\s*/, '').trim(), 'active')

    // ── Screen creation (new format: "🖼️  Screen N/M: Name") ──────────────
    const screenNewMatch = m.match(/🖼️\s+Screen\s+(\d+)\/(\d+|\?):\s+(.+)/)
    if (screenNewMatch) {
      const [, n, total, name] = screenNewMatch
      if (!framesCreated.has(name)) {
        framesCreated.add(name)
        addAlways('🖼️', `Building screen ${n}/${total}: ${name}`, 'active')
      }
      continue
    }

    // Legacy format: "🖼️  Creating screen: Name (N/M)"
    const screenOldMatch = m.match(/🖼️\s+Creating screen:\s+(.+?)\s+\((\d+)\/(\d+)\)/)
    if (screenOldMatch) {
      const [, name, n, total] = screenOldMatch
      if (!framesCreated.has(name)) {
        framesCreated.add(name)
        addAlways('🖼️', `Building screen ${n}/${total}: ${name}`, 'active')
      }
      continue
    }

    // Fallback: "🖼️  Creating frame: Name"
    const frameMatch = m.match(/🖼️\s+Creating frame:\s+(.+)/)
    if (frameMatch) {
      const name = frameMatch[1].trim()
      if (!framesCreated.has(name)) {
        framesCreated.add(name)
        addAlways('🖼️', `Building: ${name}`, 'active')
      }
      continue
    }

    // ── Per-screen components ──────────────────────────────────────────────
    if (m.includes('📋 Sidebar nav'))
      addAlways('📋', 'Sidebar nav', 'info')
    if (m.includes('🏷️') && m.includes('Logo'))
      addAlways('🏷️', 'Brand logo', 'info')

    // Tables
    const tableMatch = m.match(/📊\s+Table:\s+(.+)/)
    if (tableMatch) {
      addAlways('📊', `Table: ${tableMatch[1].trim()}`, 'info')
      continue
    }

    // Charts
    const chartMatch = m.match(/📈\s+Chart:\s+(.+)/)
    if (chartMatch) {
      addAlways('📈', `Chart: ${chartMatch[1].trim()}`, 'info')
      continue
    }

    // Maps
    const mapMatch = m.match(/🗺️\s+Map:\s+(.+)/)
    if (mapMatch) {
      addAlways('🗺️', `Map: ${mapMatch[1].trim()}`, 'info')
      continue
    }

    // Interactive buttons (only major ones)
    const btnMatch = m.match(/🔘\s+Interactive:\s+(.+)/)
    if (btnMatch) {
      addAlways('🔘', `Button: ${btnMatch[1].trim()}`, 'info')
      continue
    }

    // Screen completion summary
    const summaryMatch = m.match(/✓\s+(.+?)\s+complete:\s+(.+)/)
    if (summaryMatch) {
      addAlways('✅', `${summaryMatch[1]}: ${summaryMatch[2]}`, 'done')
      continue
    }

    // ── Phase 2: Overlays ──────────────────────────────────────────────────
    if (m.includes('Phase 2:') && m.includes('overlay'))
      add('📦', 'Building overlays & modals', 'active')

    const modalMatch = m.match(/📋\s+Modal:\s+(.+)/)
    if (modalMatch) {
      addAlways('💬', `Modal: ${modalMatch[1].trim()}`, 'info')
      continue
    }

    // ── Phase 3: Wiring ────────────────────────────────────────────────────
    if (m.includes('Phase 3:') && m.includes('Wiring'))
      add('🔗', 'Wiring prototype interactions', 'active')

    const wiringMatch = m.match(/🔗\s+Wiring\s+(\d+)\s+links/)
    if (wiringMatch) {
      addAlways('🔗', `Wiring ${wiringMatch[1]} links…`, 'active')
      continue
    }

    const wiredResult = m.match(/✓\s+Wired\s+(\d+)\s+links\s+\((\d+)\s+nav,\s+(\d+)\s+overlay\)/)
    if (wiredResult) {
      add('✅', `Wired: ${wiredResult[1]} links (${wiredResult[2]} nav, ${wiredResult[3]} overlay)`)
      continue
    }

    // Legacy wired format
    const wiredLegacy = m.match(/✓\s+Wired\s+(\d+)\s+links/)
    if (wiredLegacy && !wiredResult) {
      add('✅', `Wired ${wiredLegacy[1]} interaction links`)
      continue
    }

    if (m.includes('✗') && m.includes('Failed:')) {
      wiringErrors++
      const clean = m.replace(/.*Failed:\s*/, '').trim()
      addAlways('⚠️', `Wire failed: ${clean}`, 'warn')
      continue
    }

    // ── Phase 4: Final setup ───────────────────────────────────────────────
    if (m.includes('Phase 4:') && m.includes('Final'))
      add('✅', 'Final setup', 'active')

    if (m.includes('▶️') && m.includes('Prototype start'))
      add('▶️', m.replace(/.*▶️\s*/, '').trim())

    if (m.includes('📜') && m.includes('Scrollable'))
      addAlways('📜', m.replace(/.*📜\s*/, '').trim(), 'info')

    // Verify
    if (m.includes('🔍') && m.includes('Verifying'))
      addAlways('🔍', m.replace(/.*🔍\s*/, '').trim(), 'info')

    if (m.includes('✓') && m.includes('all interactive nodes wired'))
      addAlways('✅', m.replace(/.*✓\s*/, '').trim(), 'qa')

    if (m.includes('⚠') && m.includes('unwired node')) {
      wiringErrors++
      addAlways('⚠️', m.replace(/.*⚠\s*/, '').trim(), 'warn')
    }

    // ── Build complete summary ─────────────────────────────────────────────
    const completeMatch = m.match(/✅\s+Build complete:\s+(.+)/)
    if (completeMatch) {
      add('✅', `Build complete: ${completeMatch[1]}`)
      continue
    }

    // ── Completeness nudges ────────────────────────────────────────────────
    if (m.includes('Completeness check failed') || m.includes('Nudging builder'))
      add('🔄', 'Completing missing content…', 'active')

    if (m.includes('Output limit reached'))
      add('🔄', 'Continuing build (output limit)…', 'active')

    // ── QA pass ────────────────────────────────────────────────────────────
    if (m.includes('Quality check') || m.includes('auditing all frames')) {
      if (!qaStarted) { qaStarted = true; add('🔍', 'Running quality check…', 'qa') }
    }

    if (m.includes('[QA]') && m.includes('figma_wire_all')) qaIssuesFixed++
    if (m.includes('[QA]') && m.includes('figma_create_frame') && m.includes('modal'))
      add('💬', 'QA: Creating missing modals', 'qa')

    // QA audit results
    if (m.includes('— no issues'))
      addAlways('✅', m.replace(/.*[✓]\s*/, '').replace(/^\s*/, '').trim(), 'qa')

    // Errors
    if (m.includes('✗') && !m.includes('Failed:') && (m.includes('not found') || m.includes('error'))) {
      wiringErrors++
      const clean = m.replace(/^\s*[✗→\[\]\s]+/, '').trim()
      if (clean.length > 0 && clean.length < 150)
        addAlways('⚠️', clean, 'warn')
    }

    // Claude commentary
    if (m.startsWith('[Claude]')) {
      const text = m.replace('[Claude]', '').trim()
      if (/resuming|missing.*screen/i.test(text))
        add('🔄', text.slice(0, 120), 'warn')
    }
  }

  // QA summary
  if (qaStarted) {
    if (wiringErrors > 0 && qaIssuesFixed === 0)
      add('⚠️', `${wiringErrors} wiring issue${wiringErrors > 1 ? 's' : ''} — some links may not work`, 'warn')
    else if (qaIssuesFixed > 0)
      add('✅', `Quality check fixed ${qaIssuesFixed} link${qaIssuesFixed > 1 ? 's' : ''}`, 'qa')
    else
      add('✅', 'Quality check passed — all links verified', 'qa')
  } else if (wiringErrors > 0) {
    add('⚠️', `${wiringErrors} wiring issue${wiringErrors > 1 ? 's' : ''} — some nav links may not work`, 'warn')
  }

  return milestones
}

// ── Expandable quick-start prompt card ────────────────────────────────────────
function ExpandablePrompt({ prompt, onSelect, disabled }: {
  prompt: string; onSelect: () => void; disabled: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  // First sentence or first 70 chars as the card title
  const title = prompt.split('.')[0].trim()
  const preview = title.length > 70 ? title.slice(0, 70) + '…' : title

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden
                    hover:border-violet-200 transition-colors group">
      {/* Header row — always visible */}
      <div className="flex items-start gap-2 px-3 py-2.5">
        <p className="flex-1 text-xs text-slate-600 group-hover:text-slate-800 leading-relaxed transition-colors">
          {preview}
        </p>
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex-shrink-0 text-xs text-slate-600 hover:text-violet-600 transition-colors pt-0.5"
          title={expanded ? 'Collapse' : 'Show full prompt'}>
          {expanded ? '▲' : '▼'}
        </button>
      </div>

      {/* Expanded full prompt */}
      {expanded && (
        <div className="px-3 pb-2.5 border-t border-slate-200">
          <p className="text-xs text-slate-600 leading-relaxed mt-2 whitespace-pre-wrap">
            {prompt}
          </p>
        </div>
      )}

      {/* Action row */}
      <div className="flex border-t border-slate-200">
        <button
          onClick={onSelect}
          disabled={disabled}
          className="flex-1 text-xs text-violet-600 hover:text-violet-700 hover:bg-violet-50/30
                     py-1.5 transition-colors disabled:opacity-40 font-medium">
          Use this prompt
        </button>
        {!expanded && (
          <button
            onClick={() => setExpanded(true)}
            className="text-xs text-slate-500 hover:text-slate-700 px-3 py-1.5
                       border-l border-slate-200 transition-colors">
            See full
          </button>
        )}
      </div>
    </div>
  )
}

export default function FigmaMockupPage() {
  const { figmaProjects, activeFigmaProject, refreshFigmaProjects } = useFigmaProjectsCtx()
  const activeProject = figmaProjects.find(p => p.name === activeFigmaProject) ?? null

  const [prompt,         setPrompt]         = useState('')
  const [instructions,   setInstructions]   = useState('')
  const [showInstrModal, setShowInstrModal] = useState(false)
  const [viewInstructions, setViewInstructions] = useState<string | null>(null)
  const [mode,     setMode]     = useState<WireframeMode>('new')
  const [loading,  setLoading]  = useState(false)
  const [log,      setLog]      = useState<Milestone[]>([])
  const [error,    setError]    = useState('')
  const [done,     setDone]     = useState(false)
  const [summary,  setSummary]  = useState('')
  const [figmaResultUrl, setFigmaResultUrl] = useState('')
  const [status,   setStatus]   = useState<McpStatus | null>(null)
  const [checking,        setChecking]        = useState(false)
  const [applyBrand,      setApplyBrand]      = useState(false)
  const [rightPanelTab,   setRightPanelTab]   = useState<'details' | 'log' | 'history' | 'screenshots'>('details')
  const [sourceTab,       setSourceTab]       = useState<'prompt' | 'webapp'>('prompt')

  // Web App → Figma state
  const [webAppUrl,        setWebAppUrl]        = useState('')
  const [webMaxPages,      setWebMaxPages]      = useState<number | ''>('')
  const [webNavDepth,      setWebNavDepth]      = useState<number | ''>('')
  const [webInstructions,  setWebInstructions]  = useState('')
  const [discovering,      setDiscovering]      = useState(false)
  const [discoveredPages,  setDiscoveredPages]  = useState<{title: string; url: string; nav_label: string}[] | null>(null)
  const [discoverError,    setDiscoverError]    = useState('')
  const [webUsername,      setWebUsername]      = useState('')
  const [webPassword,      setWebPassword]      = useState('')
  const [webScreenshots,   setWebScreenshots]   = useState<{filename: string; data: string; mimetype: string}[]>([])
  const [discoverLog,      setDiscoverLog]      = useState<Milestone[]>([])

  const logEndRef       = useRef<HTMLDivElement>(null)
  const logContainerRef = useRef<HTMLDivElement>(null)
  const pollRef         = useRef<ReturnType<typeof setInterval> | null>(null)
  const buildActiveRef  = useRef(false)   // true while a build is running; guards loadLog from overwriting live log

  // Auto-scroll log — only when user is already near the bottom
  useEffect(() => {
    const container = logContainerRef.current
    if (!container) return
    const { scrollTop, scrollHeight, clientHeight } = container
    if (scrollHeight - scrollTop - clientHeight < 140)
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [log])

  // Check MCP status on mount and every 10s
  const checkStatus = async () => {
    setChecking(true)
    try { setStatus(await api.getMcpStatus()) } catch {}
    finally { setChecking(false) }
  }
  useEffect(() => {
    checkStatus()
    const t = setInterval(checkStatus, 10000)
    return () => clearInterval(t)
  }, [])

  const [confirmState, setConfirmState] = useState<{
    visible: boolean
    frameCount: number
    frameNames: string
    message: string
  } | null>(null)

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  // Load persisted log when active project changes (skip while a build is running)
  useEffect(() => {
    if (!activeFigmaProject || buildActiveRef.current) return
    api.getFigmaBuildLog(activeFigmaProject).then(r => {
      if (r.log.length > 0) setLog(toMilestones(r.log))
    }).catch(() => {})
  }, [activeFigmaProject])

  const runGenerate = async (overrideMode?: WireframeMode, confirmed = false) => {
    const effectiveMode = overrideMode ?? mode
    buildActiveRef.current = true
    setLoading(true); setError(''); setLog([]); setDone(false); setSummary(''); setRightPanelTab('log')
    setConfirmState(null)

    let lastLogLen = 0
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch('/api/generate/progress/latest')
        if (!r.ok) return
        const d = await r.json()
        const msgs: string[] = d.log || []
        if (msgs.length > lastLogLen) {
          lastLogLen = msgs.length
          setLog(toMilestones(msgs))
        }
      } catch {}
    }, 1000)

    try {
      const r = await api.generateWireframe(prompt.trim(), effectiveMode, applyBrand, activeFigmaProject ?? undefined, instructions.trim() || undefined, confirmed)

      // ── Handle error codes ────────────────────────────────────────────────
      if (r.error_code === 'NO_MCP_SERVER' || r.error_code === 'NO_TOOLS') {
        stopPolling(); setLoading(false); setDone(false)
        setError(r.error || 'MCP server not running. Start FigmaMockupGenerator\\figma\\mcp\\start.bat')
        return
      }
      if (r.error_code === 'NO_FIGMA_FILE') {
        stopPolling(); setLoading(false); setDone(false)
        setError(r.error || 'No Figma file is open. Open a file in Figma Desktop, run the Desktop Bridge plugin, and wait for "Local Ready".')
        return
      }
      if (r.error_code === 'BRIDGE_NOT_CONNECTED') {
        stopPolling(); setLoading(false); setDone(false)
        setError(r.error || 'Figma Desktop Bridge is not running. Go to Plugins → Development → Figma Desktop Bridge → Run.')
        return
      }

      // ── Handle existing frames confirmation ───────────────────────────────
      if (r.needs_confirm && r.error_code === 'EXISTING_FRAMES') {
        stopPolling(); setLoading(false); setDone(false)
        setConfirmState({
          visible:    true,
          frameCount: r.frame_count ?? 0,
          frameNames: r.frame_names ?? '',
          message:    r.message ?? '',
        })
        return
      }

      setSummary(r.result)
      if (r.figma_url) setFigmaResultUrl(r.figma_url)

      // Update project with figma_url returned by the agent
      if (activeFigmaProject) {
        try {
          await api.updateFigmaProject(activeFigmaProject, prompt.trim(), effectiveMode, undefined, r.figma_url || '')
          await refreshFigmaProjects()
        } catch {}
      }
    } catch (e: any) {
      setError(e.message)
    }

    stopPolling()
    buildActiveRef.current = false
    setLoading(false)
    setDone(true)
    checkStatus()

    await refreshFigmaProjects()
  }

  const generate = () => runGenerate()

  const discoverWebApp = async () => {
    if (!webAppUrl.trim()) return
    setDiscovering(true); setDiscoveredPages(null); setDiscoverError('')
    setLog([]); setRightPanelTab('log')

    let lastLogLen = 0
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch('/api/generate/progress/latest')
        if (!r.ok) return
        const d = await r.json()
        const msgs: string[] = d.log || []
        if (msgs.length > lastLogLen) {
          lastLogLen = msgs.length
          setLog(toMilestones(msgs))
        }
      } catch {}
    }, 800)

    try {
      const r = await api.webappDiscover(webAppUrl.trim(), webUsername, webPassword, activeFigmaProject ?? '')
      setDiscoveredPages(r.pages)
      setWebMaxPages(r.count)
      setWebNavDepth(r.max_depth)
      // Use the log returned by the server — authoritative, not the polled snapshot
      const serverLog: string[] = (r as any).log || []
      const discoverMilestones = serverLog.length > 0 ? toMilestones(serverLog) : log
      setDiscoverLog(discoverMilestones)
      setLog(discoverMilestones)
    } catch (e: any) {
      setDiscoverError(e.message || 'Discovery failed')
    } finally {
      stopPolling()
      setDiscovering(false)
    }
  }

  const runWebAppToFigma = async () => {
    if (!webAppUrl.trim()) return
    const projectAtStart = activeFigmaProject  // capture before any async re-renders
    let resolvedProject = projectAtStart        // may be updated from API response
    buildActiveRef.current = true
    const separator: Milestone = { icon: '──', text: 'Building Figma mockup…', type: 'active' }
    setLoading(true); setError(''); setLog([...discoverLog, separator]); setDone(false); setSummary(''); setRightPanelTab('log')

    let lastLogLen = 0
    const baseLog = [...discoverLog, separator]
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch('/api/generate/progress/latest')
        if (!r.ok) return
        const d = await r.json()
        const msgs: string[] = d.log || []
        if (msgs.length > lastLogLen) {
          lastLogLen = msgs.length
          setLog([...baseLog, ...toMilestones(msgs)])
        }
      } catch {}
    }, 1000)

    try {
      const r = await api.webappToFigma(
        webAppUrl.trim(),
        activeFigmaProject ?? '',
        webMaxPages === '' ? 20 : webMaxPages,
        webNavDepth === '' ? 2  : webNavDepth,
        webInstructions.trim(),
        webUsername,
        webPassword,
      )
      if (r.error_code) {
        stopPolling(); setLoading(false); setDone(false)
        setError(r.error || r.error_code)
        return
      }
      setSummary(r.result)
      if (r.figma_url) setFigmaResultUrl(r.figma_url)
      if (r.project_name) resolvedProject = r.project_name

      // Load screenshots (server already persisted history + figma_url)
      try {
        const targetProject = resolvedProject ?? ''
        if (targetProject) {
          const shots = await api.getWebappScreenshots(targetProject)
          if (shots.screenshots.length > 0) {
            setWebScreenshots(shots.screenshots)
          }
        }
      } catch {}
    } catch (e: any) {
      setError(e.message)
    }

    stopPolling()
    buildActiveRef.current = false
    setLoading(false)
    setDone(true)
    checkStatus()
    await refreshFigmaProjects()
  }

  const reset = () => {
    stopPolling()
    setLoading(false); setLog([]); setError('')
    setDone(false); setSummary(''); setFigmaResultUrl(''); setConfirmState(null)
  }

  // edit mode only needs MCP server (no relay/Figma connection required for inspect+patch)
  const canGenerate = prompt.trim().length > 0 && !loading &&
    (status?.mcp_server === true) &&
    (status?.relay_connected === true)

  const disabledReason = loading ? '' :
    !status                   ? 'API backend not reachable — run start.bat in the TurboUIGen folder' :
    !status.mcp_server        ? 'Figma MCP server is not running — start FigmaMockupGenerator\\figma\\mcp\\start.bat' :
    !status.relay_connected   ? 'Relay not connected — start relay.py and the Desktop Bridge plugin' :
    prompt.trim().length === 0 ? 'Enter a prompt first' :
    ''

  // ── Prompt builder ──────────────────────────────────────────────────────────
  const [showBuilder, setShowBuilder] = useState(false)
  const [pb, setPb] = useState({
    layout:    'Desktop (1440×900)',
    appName:   '',
    domain:    '',
    screens:   '',
    theme:     'Dark (navy/indigo)',
    accent:    '#6366f1',
    extras:    '',
  })

  const buildPrompt = () => {
    const screens = pb.screens.split(',').map(s => s.trim()).filter(Boolean)
    const screenList = screens.length
      ? screens.map((s, i) => `Screen ${i + 1}: ${s}`).join(', ')
      : 'Dashboard, Details, Settings'
    const parts = [
      `Create a ${screens.length || 3}-screen ${pb.layout.toLowerCase()} web app`,
      pb.appName ? `called "${pb.appName}"` : '',
      pb.domain  ? `for ${pb.domain}`       : '',
      '.',
      `Screens: ${screenList}.`,
      `Theme: ${pb.theme}`,
      pb.accent !== '#6366f1' ? `, accent color ${pb.accent}` : '',
      '.',
      pb.extras ? pb.extras : '',
    ]
    const built = parts.filter(Boolean).join(' ').replace(/\s+\./g, '.').replace(/\.\s+\./g, '.').trim()
    setPrompt(built)
    setShowBuilder(false)
  }

  const _leftPanel = (
    <div className="border-r border-slate-200 flex flex-col h-full overflow-hidden">

        {/* Header */}
        <div className="p-4 border-b border-slate-200 flex-shrink-0">
          {/* Active project — compact badge only; full details shown in right panel */}
          {activeProject ? (
            <div className="mb-3 px-3 py-2 rounded-lg bg-violet-50 border border-violet-200 flex items-center gap-2 min-w-0">
              <FolderOpen size={13} className="text-violet-600 flex-shrink-0" />
              <span className="text-xs font-semibold text-violet-700 truncate flex-1">{activeProject.title}</span>
              {activeProject.figma_url && (
                <a href={activeProject.figma_url} target="_blank" rel="noreferrer"
                  className="flex-shrink-0 text-violet-500 hover:text-violet-700 transition-colors">
                  <ExternalLink size={11} />
                </a>
              )}
              <span className="flex-shrink-0 text-xs text-slate-600">
                {activeProject.history.length} build{activeProject.history.length !== 1 ? 's' : ''}
              </span>
            </div>
          ) : (
            <div className="mb-3 p-2.5 rounded-lg bg-slate-50 border border-slate-300 border-dashed">
              <p className="text-xs text-slate-600 text-center">
                No project selected — click a project in the sidebar
              </p>
            </div>
          )}

          <h1 className="font-bold text-base text-slate-900 flex items-center gap-2">
            <Layers size={16} className="text-violet-600" />
            {mode === 'replace' ? 'Replace Wireframe' : mode === 'edit' ? 'Edit Wireframe' : 'New Wireframe'}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            {mode === 'replace'
              ? 'Describe the screens to rebuild from scratch'
              : mode === 'edit'
              ? 'Describe edits to existing screens or new screens to add'
              : 'Describe all screens to build on a blank Figma canvas'}
          </p>
          <div className="mt-2">
            <McpStatusBadge status={status} checking={checking} />
          </div>
        </div>

        {/* Source tab switcher */}
        <div className="flex border-b border-slate-200 flex-shrink-0">
          <button
            onClick={() => setSourceTab('prompt')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium border-b-2 transition-colors ${
              sourceTab === 'prompt' ? 'border-violet-500 text-violet-700' : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}>
            <Send size={11} /> From Prompt
          </button>
          <button
            onClick={() => setSourceTab('webapp')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium border-b-2 transition-colors ${
              sourceTab === 'webapp' ? 'border-violet-500 text-violet-700' : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}>
            <Globe size={11} /> From Web App
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-scroll p-4 flex flex-col gap-4">

          {/* ── Web App → Figma form ── */}
          {sourceTab === 'webapp' && (<>

            {/* MCP warning */}
            {(!status || !status.mcp_server || !status.relay_connected) && !checking && (
              <div className="card p-3 border-amber-200 bg-amber-50 flex gap-2">
                <Info size={13} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-amber-700 leading-relaxed">
                  {!status
                    ? <><strong>API backend is not running.</strong><br /><code className="text-amber-700">TurboUIGen\start.bat</code></>
                    : !status.mcp_server
                    ? <><strong>Figma MCP server is not running.</strong><br /><code className="text-amber-700">FigmaMockupGenerator\figma\mcp\start.bat</code></>
                    : <><strong>Relay not connected.</strong> Start relay.py and the Desktop Bridge plugin.</>
                  }
                </div>
              </div>
            )}

            {/* 1. Web App URL */}
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">
                Web App URL
              </label>
              <input
                className="input text-xs w-full"
                placeholder="http://localhost:3000/sandbox/my-app"
                value={webAppUrl}
                onChange={e => { setWebAppUrl(e.target.value); setDiscoveredPages(null); setDiscoverError('') }}
                disabled={loading || discovering}
              />
            </div>

            {/* 2. Login credentials (optional) */}
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">
                Login Credentials <span className="text-slate-700 normal-case font-normal">(optional — if the app has a login page)</span>
              </label>
              <div className="flex gap-2">
                <input
                  className="input text-xs flex-1"
                  placeholder="Username / email"
                  value={webUsername}
                  onChange={e => setWebUsername(e.target.value)}
                  disabled={loading || discovering}
                  autoComplete="off"
                />
                <input
                  className="input text-xs flex-1"
                  type="password"
                  placeholder="Password"
                  value={webPassword}
                  onChange={e => setWebPassword(e.target.value)}
                  disabled={loading || discovering}
                  autoComplete="off"
                />
              </div>
            </div>

            {/* 3. Discover button */}
            <button
              onClick={discoverWebApp}
              disabled={!webAppUrl.trim() || loading || discovering}
              className="btn-ghost w-full justify-center py-2 border border-slate-300 text-xs flex items-center gap-2">
              {discovering
                ? <><span className="w-3 h-3 rounded-full border-2 border-slate-400 border-t-transparent animate-spin" /> Scanning pages…</>
                : <><Globe size={12} /> Discover Pages</>}
            </button>
            {!discoveredPages && !discovering && (
              <p className="text-xs text-slate-600 -mt-2 text-center">
                Scans the app and fills in page count automatically — or set manually below
              </p>
            )}

            {/* Discover error */}
            {discoverError && (
              <div className="flex gap-2 p-2.5 rounded-lg bg-red-50 border border-red-200">
                <AlertCircle size={12} className="text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-red-600">{discoverError}</p>
              </div>
            )}

            {/* 4. Discovered pages list */}
            {discoveredPages && (
              <div className="rounded-lg border border-emerald-200 overflow-hidden">
                <div className="flex items-center justify-between px-3 py-2 bg-emerald-50 border-b border-emerald-200">
                  <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1.5">
                    <CheckCircle size={11} /> Found {discoveredPages.length} page{discoveredPages.length !== 1 ? 's' : ''}
                  </span>
                  <button onClick={() => setDiscoveredPages(null)}
                    className="text-xs text-slate-600 hover:text-slate-800 transition-colors">clear</button>
                </div>
                <div className="divide-y divide-slate-800 max-h-36 overflow-y-scroll">
                  {discoveredPages.map((p, i) => (
                    <div key={i} className="flex items-center gap-2 px-3 py-1.5">
                      <span className="text-xs text-slate-600 w-4 flex-shrink-0">{i + 1}</span>
                      <span className="text-xs font-medium text-slate-700 flex-1 truncate">{p.title || p.nav_label}</span>
                      <span className="text-xs text-slate-600 truncate max-w-[130px]">{p.url.replace(/^https?:\/\/[^/]+/, '')}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 5. Max Pages + Nav Depth — auto-filled by Discover, user-editable */}
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">
                  Max Pages {discoveredPages && <span className="text-emerald-500 normal-case font-normal">(auto-filled)</span>}
                </label>
                <input
                  type="number" min={1} max={50}
                  className="input text-xs w-full"
                  value={webMaxPages}
                  onChange={e => setWebMaxPages(e.target.value === '' ? '' : Math.max(1, Math.min(50, +e.target.value)))}
                  disabled={loading}
                />
              </div>
              <div className="flex-1">
                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">
                  Nav Depth {discoveredPages && <span className="text-emerald-500 normal-case font-normal">(auto-filled)</span>}
                </label>
                <input
                  type="number" min={1} max={5}
                  className="input text-xs w-full"
                  value={webNavDepth}
                  onChange={e => setWebNavDepth(e.target.value === '' ? '' : Math.max(1, Math.min(5, +e.target.value)))}
                  disabled={loading}
                />
              </div>
            </div>
            <div className="flex gap-3 -mt-2 text-xs text-slate-600">
              <span className="flex-1">Screenshots to capture</span>
              <span className="flex-1">Drilldown levels for Figma wiring</span>
            </div>

            {/* Extra instructions */}
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 block">
                Extra Instructions <span className="text-slate-700 normal-case font-normal">(optional)</span>
              </label>
              <textarea
                className="input resize-none h-16 text-xs leading-relaxed w-full"
                placeholder="e.g. Use dark theme, keep the KPI card layout, ignore the footer"
                value={webInstructions}
                onChange={e => setWebInstructions(e.target.value)}
                disabled={loading}
              />
            </div>

            {/* Submit */}
            <button
              onClick={runWebAppToFigma}
              disabled={!webAppUrl.trim() || loading || discovering || !discoveredPages || !status?.mcp_server || !status?.relay_connected}
              className="btn-primary w-full justify-center py-2.5 text-sm font-semibold">
              {loading
                ? <><span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" /> Screenshotting &amp; Building…</>
                : <><Globe size={14} /> Generate Figma from Web App</>
              }
            </button>
            {!discoveredPages && !loading && !discovering && (
              <p className="text-xs text-slate-600 text-center -mt-2">Run Discover first to enable generation</p>
            )}
            {(!status?.mcp_server || !status?.relay_connected) && !loading && (
              <p className="text-xs text-amber-500/80 text-center -mt-2">MCP server + relay must be running</p>
            )}

            {/* Error */}
            {error && (
              <div className="card p-3 border-red-200 bg-red-50">
                <div className="flex gap-2">
                  <AlertCircle size={13} className="text-red-600 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-600 leading-relaxed break-words">{error}</p>
                </div>
                <button onClick={reset} className="text-xs text-red-600 hover:text-red-700 mt-2 underline block">Dismiss</button>
              </div>
            )}

            {/* Done */}
            {done && !error && (
              <div className="card p-3 border-emerald-200 bg-emerald-50">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle size={13} className="text-emerald-700" />
                  <span className="text-xs font-semibold text-emerald-600">Figma wireframe created!</span>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Check Figma Desktop — screens have been built from your web app.
                </p>
                {figmaResultUrl && (
                  <a href={figmaResultUrl} target="_blank" rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-violet-700 hover:text-violet-700 mt-2 truncate">
                    <ExternalLink size={11} /><span className="truncate">{figmaResultUrl}</span>
                  </a>
                )}
                <button onClick={reset} className="btn-ghost text-xs mt-2 w-full justify-center">
                  <RefreshCw size={11} /> Convert another
                </button>
              </div>
            )}
          </>)}

          {/* ── Prompt-based form ── */}
          {sourceTab === 'prompt' && (<>

          {/* MCP not ready warning */}
          {(!status || !status.mcp_server || (mode !== 'edit' && !status.relay_connected)) && !checking && (
            <div className="card p-3 border-amber-200 bg-amber-50 flex gap-2">
              <Info size={13} className="text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-amber-700 leading-relaxed">
                {!status
                  ? <><strong>API backend is not running.</strong> Double-click:<br />
                      <code className="text-amber-700">TurboUIGen\start.bat</code></>
                  : !status.mcp_server
                  ? <><strong>Figma MCP server is not running.</strong> Double-click:<br />
                      <code className="text-amber-700">FigmaMockupGenerator\figma\mcp\start.bat</code></>
                  : <><strong>Relay not connected.</strong> Start it with:<br />
                      <code className="text-amber-700">python figma\mcp\relay.py</code>
                      <br />Then open the <strong>Desktop Bridge</strong> plugin in Figma Desktop.</>
                }
              </div>
            </div>
          )}

          {/* Mode selector */}
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 block">
              Mode
            </label>
            <div className="flex flex-col gap-1.5">
              {MODES.map(m => (
                <button key={m.value}
                  onClick={() => setMode(m.value)}
                  disabled={loading}
                  className={`text-left rounded-lg px-3 py-2.5 border transition-colors ${
                    mode === m.value
                      ? 'border-violet-600 bg-violet-50 text-violet-700'
                      : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 hover:text-slate-700'
                  }`}>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold flex-1">{m.label}</span>
                    {m.safe
                      ? <span className="text-xs text-emerald-500 font-medium flex-shrink-0">✓ safe</span>
                      : <span className="text-xs text-amber-500 font-medium flex-shrink-0">⚠ modifies</span>
                    }
                  </div>
                  <div className="text-xs opacity-70 mt-0.5 leading-relaxed">{m.desc}</div>
                  {mode === m.value && (
                    <div className={`text-xs mt-1 italic ${m.safe ? 'text-emerald-700/70' : 'text-amber-600/70'}`}>
                      {m.hint}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Prompt */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Prompt
              </label>
              <div className="flex items-center gap-2">
                <InstructionsBadge
                  hasInstructions={!!instructions.trim()}
                  onClick={() => setShowInstrModal(true)}
                  disabled={loading}
                />
                <button
                  onClick={() => setShowBuilder(v => !v)}
                  disabled={loading}
                  className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-700 transition-colors">
                  <Settings2 size={11} />
                  {showBuilder ? 'Hide builder' : 'Prompt builder'}
                </button>
              </div>
            </div>

            {/* Structured prompt builder */}
            {showBuilder && (
              <div className="mb-2 p-3 bg-slate-50 border border-slate-300 rounded-lg space-y-2.5">
                <div className="text-xs font-semibold text-slate-600 mb-1">Build your prompt</div>

                {/* Layout */}
                <div>
                  <div className="text-xs text-slate-600 mb-1">Layout</div>
                  <div className="flex gap-1.5">
                    {['Desktop (1440×900)', 'Mobile (390×844)'].map(l => (
                      <button key={l} onClick={() => setPb(p => ({ ...p, layout: l }))}
                        className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                          pb.layout === l
                            ? 'border-violet-600 bg-violet-50 text-violet-700'
                            : 'border-slate-300 text-slate-500 hover:text-slate-700'
                        }`}>{l}</button>
                    ))}
                  </div>
                </div>

                {/* App name + domain */}
                <div className="flex gap-2">
                  <div className="flex-1">
                    <div className="text-xs text-slate-600 mb-1">App name</div>
                    <input className="input text-xs py-1 w-full"
                      placeholder="e.g. SportsHub"
                      value={pb.appName}
                      onChange={e => setPb(p => ({ ...p, appName: e.target.value }))} />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs text-slate-600 mb-1">Domain / industry</div>
                    <input className="input text-xs py-1 w-full"
                      placeholder="e.g. automotive sales"
                      value={pb.domain}
                      onChange={e => setPb(p => ({ ...p, domain: e.target.value }))} />
                  </div>
                </div>

                {/* Screens */}
                <div>
                  <div className="text-xs text-slate-600 mb-1">Screens (comma-separated)</div>
                  <input className="input text-xs py-1 w-full"
                    placeholder="e.g. Dashboard, Players, Match Detail"
                    value={pb.screens}
                    onChange={e => setPb(p => ({ ...p, screens: e.target.value }))} />
                </div>

                {/* Theme */}
                <div>
                  <div className="text-xs text-slate-600 mb-1">Theme</div>
                  <div className="flex gap-1.5 flex-wrap">
                    {['Dark (navy/indigo)', 'Dark (slate/violet)', 'Light (white/blue)', 'Light (white/green)'].map(t => (
                      <button key={t} onClick={() => setPb(p => ({ ...p, theme: t }))}
                        className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                          pb.theme === t
                            ? 'border-violet-600 bg-violet-50 text-violet-700'
                            : 'border-slate-300 text-slate-500 hover:text-slate-700'
                        }`}>{t}</button>
                    ))}
                  </div>
                </div>

                {/* Extra instructions */}
                <div>
                  <div className="text-xs text-slate-600 mb-1">Extra details (optional)</div>
                  <input className="input text-xs py-1 w-full"
                    placeholder="e.g. include a filter modal on the Players screen"
                    value={pb.extras}
                    onChange={e => setPb(p => ({ ...p, extras: e.target.value }))} />
                </div>

                <button onClick={buildPrompt}
                  className="btn-primary w-full justify-center py-1.5 text-xs">
                  Generate prompt →
                </button>
              </div>
            )}

            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) generate() }}
              disabled={loading}
              placeholder={mode === 'edit'
                ? "Describe what to change…\n\ne.g. On the Dashboard screen, change the sidebar background to white and make the heading font size 24px"
                : "Describe the screens to create…\n\nTip: use 'Prompt builder' above for best results"}
              className="input resize-none h-28 leading-relaxed text-xs"
            />
          </div>

          {/* Corporate branding checkbox */}
          <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
            applyBrand
              ? 'border-blue-600 bg-blue-50'
              : 'border-slate-300 bg-slate-50 hover:border-slate-300'
          }`}>
            <div className="flex-shrink-0 mt-0.5">
              <input
                type="checkbox"
                checked={applyBrand}
                onChange={e => setApplyBrand(e.target.checked)}
                disabled={loading}
                className="w-4 h-4 accent-blue-500 cursor-pointer"
              />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-800">
                  Corporate / Mobility Global Branding
                </span>
                {applyBrand && (
                  <span className="text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded font-medium">ON</span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
                Apply Vital Blue, Forward Blue and Morning Mist brand colors.
                Auto-detected from prompt keywords when unchecked.
              </p>
            </div>
          </label>

          {/* Generate button */}
          <button onClick={generate} disabled={!canGenerate}
            className="btn-primary w-full justify-center py-2.5 text-sm font-semibold">
            {loading
              ? <><span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />{'Building in Figma…'}</>
              : <><Send size={14} />{mode === 'replace' ? 'Replace Wireframe' : mode === 'edit' ? 'Edit Wireframe' : 'New Wireframe'}</>
            }
          </button>
          {disabledReason
            ? <p className="text-xs text-amber-500/80 text-center -mt-2">{disabledReason}</p>
            : <p className="text-xs text-slate-600 text-center -mt-2">Ctrl+Enter to generate</p>
          }

          {/* Error — with specific guidance per error type */}
          {error && (
            <div className="card p-3 border-red-200 bg-red-50">
              <div className="flex gap-2 mb-2">
                <AlertCircle size={13} className="text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-red-600 leading-relaxed break-words">{error}</p>
              </div>
              {error.includes('No Figma file') && (
                <div className="mt-2 bg-red-50 rounded p-2 text-xs text-red-600 space-y-1">
                  <p className="font-semibold">Steps to fix:</p>
                  <p>1. Open Figma Desktop and open or create a file</p>
                  <p>2. Go to Plugins → Development → Figma Desktop Bridge → Run</p>
                  <p>3. Wait for "Local Ready" in the plugin panel</p>
                  <p>4. Try again</p>
                </div>
              )}
              {error.includes('Desktop Bridge') && (
                <div className="mt-2 bg-red-50 rounded p-2 text-xs text-red-600 space-y-1">
                  <p className="font-semibold">Steps to fix:</p>
                  <p>1. In Figma Desktop: Plugins → Development → Figma Desktop Bridge → Run</p>
                  <p>2. Wait for "Local Ready" in the plugin panel</p>
                  <p>3. Try again</p>
                </div>
              )}
              {error.includes('MCP server') && (
                <div className="mt-2 bg-red-50 rounded p-2 text-xs text-red-600 space-y-1">
                  <p className="font-semibold">Steps to fix:</p>
                  <p>1. Run: <code className="bg-red-100 px-1 rounded">FigmaMockupGenerator\figma\mcp\start.bat</code></p>
                  <p>2. Wait for both windows to show ready</p>
                  <p>3. Try again</p>
                </div>
              )}
              <button onClick={reset} className="text-xs text-red-600 hover:text-red-700 mt-2 underline block">
                Dismiss
              </button>
            </div>
          )}

          {/* Existing frames warning — shown when New Wireframe is used on a canvas that already has screens */}
          {confirmState && (
            <div className="card p-4 border-amber-200 bg-amber-50">
              <div className="flex gap-2 mb-3">
                <Info size={14} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-amber-700 mb-1">
                    Canvas already has {confirmState.frameCount} screen{confirmState.frameCount !== 1 ? 's' : ''}
                  </p>
                  <p className="text-xs text-amber-600 leading-relaxed">
                    Found: <span className="text-amber-700">{confirmState.frameNames}</span>
                  </p>
                  <p className="text-xs text-amber-700 mt-2 leading-relaxed">
                    <strong className="text-amber-700">New Wireframe</strong> is designed for a blank canvas and may conflict with existing screens.
                    Choose a mode that matches your intent:
                  </p>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => runGenerate('edit')}
                  className="text-left text-xs px-3 py-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100 transition-colors">
                  <div className="font-semibold text-emerald-600">Switch to Edit Wireframe ✓ recommended</div>
                  <div className="text-emerald-600/60 mt-0.5">Edit existing screens or add new ones alongside them — nothing is deleted</div>
                </button>
                <button
                  onClick={() => runGenerate('replace')}
                  className="text-left text-xs px-3 py-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 hover:bg-amber-100 transition-colors">
                  <div className="font-semibold text-amber-700">Switch to Replace Wireframe</div>
                  <div className="text-amber-700/60 mt-0.5">Delete screens with matching names and rebuild them from scratch</div>
                </button>
                <button
                  onClick={() => runGenerate('new', true)}
                  className="text-left text-xs px-3 py-2.5 rounded-lg bg-slate-50 border border-slate-300 text-slate-600 hover:border-slate-300 hover:text-slate-700 transition-colors">
                  <div className="font-semibold">Continue with New Wireframe anyway</div>
                  <div className="text-slate-500 mt-0.5">Clears ALL existing frames first, then builds everything fresh</div>
                </button>
                <button
                  onClick={() => setConfirmState(null)}
                  className="text-xs text-slate-600 hover:text-slate-800 transition-colors text-center py-1">
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Done */}
          {done && !error && (
            <div className="card p-3 border-emerald-200 bg-emerald-50">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle size={13} className="text-emerald-700" />
                <span className="text-xs font-semibold text-emerald-600">
                  {mode === 'replace' ? 'Screens replaced!' : mode === 'edit' ? 'Wireframe updated!' : 'Wireframe built!'}
                </span>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                {mode === 'replace'
                  ? 'Check Figma Desktop — the screens have been rebuilt.'
                  : mode === 'edit'
                  ? 'Check Figma Desktop — changes have been applied.'
                  : 'Check Figma Desktop — your wireframe is ready.'}
              </p>
              <button onClick={reset}
                className="btn-ghost text-xs mt-2 w-full justify-center">
                <RefreshCw size={11} /> Build another
              </button>
            </div>
          )}


          {/* Quick prompts */}
          {!loading && !done && (
            <div>
              <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Quick Start</div>
              <div className="space-y-2">
                {QUICK_PROMPTS.map((p, i) => (
                  <ExpandablePrompt key={i} prompt={p} onSelect={() => setPrompt(p)} disabled={loading} />
                ))}
              </div>
            </div>
          )}

          </>)}

        </div>
      </div>
  )

  const _rightPanel = (
      <div className="flex-1 min-w-0 min-h-0 flex flex-col bg-white overflow-hidden">

        {/* Header */}
        <div className="p-4 border-b border-slate-200 flex items-center justify-between flex-shrink-0">
          <div>
            <h2 className="text-sm font-semibold text-slate-700">
              {loading ? 'Build Log' : activeProject ? 'Project Details' : 'Build Log'}
            </h2>
            <p className="text-xs text-slate-600 mt-0.5">
              {loading
                ? 'Figma uses its own renderer — shadows, gradients, rounded corners and blur are applied natively'
                : activeProject
                ? 'Figma URL, screens and full build history for the active project'
                : 'Select a project in the sidebar, or enter a prompt and build'
              }
            </p>
          </div>
          {loading && (
            <div className="flex items-center gap-2 text-xs text-violet-600">
              <span className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
              Building…
            </div>
          )}
        </div>

        {/* ── Right panel tab bar ── */}
        {(() => {
          const tabs = [
            { id: 'details',     label: activeProject ? 'Project' : 'Details', icon: <Layers size={12} /> },
            { id: 'log',         label: 'Build Log',   icon: <Clock size={12} /> },
            { id: 'screenshots', label: 'Screenshots',  icon: <FileText size={12} />,
              badge: webScreenshots.length > 0 ? webScreenshots.length : undefined },
            { id: 'history',     label: 'History',     icon: <Clock size={12} />,
              badge: activeProject ? activeProject.history.length : undefined },
          ] as { id: string; label: string; icon: React.ReactNode; badge?: number }[]

          const [rpTab, setRpTab] = [rightPanelTab, setRightPanelTab]

          return (
            <div className="flex border-b border-slate-200 flex-shrink-0">
              {tabs.map(t => (
                <button key={t.id} onClick={() => setRpTab(t.id as typeof rightPanelTab)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                    rpTab === t.id ? 'border-violet-500 text-violet-700' : 'border-transparent text-slate-500 hover:text-slate-700'
                  }`}>
                  {t.icon} {t.label}
                  {t.badge ? <span className="ml-1 bg-slate-200 text-slate-600 text-xs px-1.5 py-0.5 rounded-full">{t.badge}</span> : null}
                </button>
              ))}
            </div>
          )
        })()}

        {/* ── Tab content — single bounded flex box so overflow-y-auto always works ── */}
        <div className="flex-1 min-h-0 overflow-hidden relative">

        {/* ── Build log tab ── */}
        {rightPanelTab === 'log' && (
          <div ref={logContainerRef} className="absolute inset-0 overflow-y-auto p-4 font-mono text-xs text-slate-600 space-y-1">
            {log.length === 0 && loading && (
              <div className="flex flex-col items-center justify-center h-full gap-3">
                <span className="w-8 h-8 rounded-full border-2 border-violet-700 border-t-violet-400 animate-spin" />
                <p className="text-slate-500 text-xs">Connecting to Figma agent…</p>
              </div>
            )}
            {log.length === 0 && !loading && (
              <p className="text-slate-700 italic">No build log yet — run a build to see progress here.</p>
            )}
            {log.map((m, i) => (
              <div key={i} className={`flex items-start gap-3 py-2 px-3 rounded-lg ${
                m.type === 'qa'     ? 'bg-blue-50 border border-blue-200'    :
                m.type === 'active' ? 'bg-violet-50 border border-violet-200':
                m.type === 'warn'   ? 'bg-amber-50 border border-amber-200'  :
                m.type === 'error'  ? 'bg-red-50 border border-red-200'      : ''
              }`}>
                <span className="text-base flex-shrink-0 mt-0.5">{m.icon}</span>
                <span className={`text-sm leading-relaxed ${
                  m.type === 'qa'     ? 'text-blue-700'   : m.type === 'active' ? 'text-violet-700' :
                  m.type === 'warn'   ? 'text-amber-700'  : m.type === 'error'  ? 'text-red-600'    :
                  m.type === 'done'   ? 'text-slate-800'  : 'text-slate-600'
                }`}>{m.text}</span>
              </div>
            ))}
            {loading && log.length > 0 && (
              <div className="flex items-center gap-3 px-3 py-1.5">
                <span className="w-4 h-4 rounded-full border-2 border-violet-600 border-t-violet-300 animate-spin flex-shrink-0" />
                <span className="text-sm text-slate-500 italic">Working…</span>
              </div>
            )}
            {summary && (
              <div className="mt-2 p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                <div className="text-sm font-semibold text-emerald-600 mb-1">✅ Done</div>
                <div className="text-xs text-slate-600 leading-relaxed">
                  Check Figma Desktop — your wireframe is ready. Hit ▶ Play to test the prototype.
                </div>
                {figmaResultUrl && (
                  <div className="mt-2 pt-2 border-t border-emerald-200 flex items-center gap-2">
                    <a href={figmaResultUrl} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1 text-xs text-violet-700 hover:text-violet-700 truncate flex-1 min-w-0">
                      <ExternalLink size={11} className="flex-shrink-0" />
                      <span className="truncate">{figmaResultUrl}</span>
                    </a>
                    <button onClick={() => navigator.clipboard.writeText(figmaResultUrl)}
                      className="flex-shrink-0 p-1 rounded text-slate-500 hover:text-slate-700 transition-colors" title="Copy Figma link">
                      <Copy size={11} />
                    </button>
                  </div>
                )}
              </div>
            )}
            <div ref={logEndRef} />
          </div>
        )}

        {/* ── Screenshots tab ── */}
        {rightPanelTab === 'screenshots' && (
          <div className="absolute inset-0 overflow-y-auto p-3">
            {webScreenshots.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                <FileText size={36} className="text-slate-300" />
                <p className="text-slate-600 text-sm font-semibold">No screenshots yet</p>
                <p className="text-slate-700 text-xs leading-relaxed max-w-xs">Screenshots captured from the web app will appear here after generation.</p>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs text-slate-600">{webScreenshots.length} screenshot{webScreenshots.length !== 1 ? 's' : ''} captured from the web app</p>
                {webScreenshots.map((s, i) => (
                  <div key={i} className="rounded-lg overflow-hidden border border-slate-200">
                    <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200 flex items-center gap-2">
                      <span className="text-xs text-slate-500 w-5">{i + 1}</span>
                      <span className="text-xs text-slate-600 truncate flex-1">{s.filename.replace(/^\d+_/, '').replace(/-/g, ' ').replace(/\.png$/i, '')}</span>
                      <span className="text-xs text-slate-700">{s.filename}</span>
                    </div>
                    <img
                      src={`data:${s.mimetype};base64,${s.data}`}
                      alt={s.filename}
                      className="w-full block"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── History tab ── */}
        {rightPanelTab === 'history' && (
          <div className="absolute inset-0 overflow-y-auto p-4 space-y-3">
            {!activeProject ? (
              <p className="text-slate-700 italic text-xs">Select a project to see its build history.</p>
            ) : activeProject.history.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
                <Clock size={36} className="text-slate-300" />
                <p className="text-slate-600 text-sm font-semibold">No builds yet</p>
                <p className="text-slate-700 text-xs leading-relaxed max-w-xs">Every build and edit will be recorded here with its prompt and timestamp.</p>
              </div>
            ) : (
              [...activeProject.history].reverse().map((h: any, i: number) => (
                <button key={i} onClick={() => h.prompt && setPrompt(h.prompt)}
                  className="w-full text-left bg-slate-50 border border-slate-200 hover:border-violet-300 rounded-lg px-4 py-3 transition-colors group"
                  title={h.prompt ? 'Click to reload this prompt' : undefined}>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="text-xs font-semibold text-violet-600 uppercase">{h.event || h.mode || 'Build'}</span>
                    <span className="text-xs text-slate-600 flex items-center gap-1">
                      <Clock size={9} />
                      {new Date(h.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {h.source_url && (
                    <p className="text-xs text-slate-500 mb-1 truncate">🌐 {h.source_url}</p>
                  )}
                  {h.prompt && (
                    <p className="text-xs text-slate-600 group-hover:text-slate-800 leading-relaxed transition-colors line-clamp-3">{h.prompt}</p>
                  )}
                  {h.instructions && (
                    <button
                      onClick={e => { e.stopPropagation(); setViewInstructions(h.instructions!) }}
                      className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-700 transition-colors mt-1"
                    >
                      <FileText size={10} /> View instructions
                    </button>
                  )}
                </button>
              ))
            )}
          </div>
        )}

        {/* ── Project details tab (default when idle) ── */}
        {rightPanelTab === 'details' && (
          <div className="absolute inset-0 overflow-y-auto p-5 space-y-5">
            {activeProject ? (
              <>
                <div>
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Figma File</div>
                  {(activeProject.figma_url || figmaResultUrl) ? (
                    <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-violet-50 border border-violet-200">
                      <a href={activeProject.figma_url || figmaResultUrl} target="_blank" rel="noreferrer"
                        className="flex items-center gap-2 text-sm text-violet-700 hover:text-violet-900 transition-colors break-all flex-1 min-w-0">
                        <ExternalLink size={14} className="flex-shrink-0" />
                        <span className="truncate">{activeProject.figma_url || figmaResultUrl}</span>
                      </a>
                      <button onClick={() => navigator.clipboard.writeText(activeProject.figma_url || figmaResultUrl)}
                        className="flex-shrink-0 p-1 rounded text-slate-500 hover:text-slate-700 transition-colors" title="Copy link">
                        <Copy size={13} />
                      </button>
                    </div>
                  ) : (
                    <div className="px-3 py-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-600 italic">
                      No Figma link yet — run a build to generate one
                    </div>
                  )}
                </div>
                {activeProject.screens.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                      Screens ({activeProject.screens.length})
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {activeProject.screens.map((s: string) => (
                        <span key={s} className="text-xs bg-violet-50 border border-violet-200 text-violet-700 px-2 py-1 rounded-md">{s}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="text-xs text-slate-600 space-y-1">
                  <div>Created: {new Date(activeProject.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
                  <div>Last updated: {new Date(activeProject.updated_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
                  <div>{activeProject.history.length} build{activeProject.history.length !== 1 ? 's' : ''} — see History tab for details</div>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
                <Layers size={40} className="text-slate-300" />
                <div>
                  <p className="text-slate-500 font-semibold text-sm">Select a project to get started</p>
                  <p className="text-slate-700 text-xs mt-1 max-w-xs leading-relaxed">Click a project in the sidebar to see its Figma link and build history, or create a new one.</p>
                </div>
                <div className="text-left space-y-2 mt-1">
                  {[
                    { label: 'MCP server on port 7771', ok: status?.mcp_server },
                    { label: 'relay.py + Desktop Bridge connected', ok: status?.relay_connected },
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-slate-600">
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0 ${item.ok ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{item.ok ? '✓' : '·'}</span>
                      {item.label}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        </div>{/* end tab content wrapper */}
      </div>
  )

  return (
    <>
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      <ResizablePanels
        left={_leftPanel}
        right={_rightPanel}
        defaultLeftWidth={320}
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
