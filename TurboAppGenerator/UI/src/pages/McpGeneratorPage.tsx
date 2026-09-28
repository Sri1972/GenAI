import { useState, useCallback, useEffect, useRef } from 'react'
import { Plug, Database, Globe, RefreshCw, AlertCircle, Sparkles, Terminal, FileJson, Wrench, Send, ChevronDown, ChevronRight, Bot, User, Pencil, Check, Trash2, ExternalLink, BookOpen, Clock, FileText } from 'lucide-react'
import { api } from '../hooks/useApi'
import { McpProjectEntry, McpMetadata, McpTable, McpEndpoint, McpTool, BuildLogRun, HistoryEvent } from '../types'
import ResizablePanels from '../components/ResizablePanels'
import InstructionsModal, { InstructionsBadge } from '../components/InstructionsModal'

interface ChatToolCall { name: string; args: Record<string, any>; result: string }
interface ChatMsg { role: 'user' | 'assistant'; content: string; toolCalls?: ChatToolCall[] }

function ToolCallChip({ tc }: { tc: ChatToolCall }) {
  const [open, setOpen] = useState(false)
  const argsStr = Object.keys(tc.args || {}).length ? JSON.stringify(tc.args) : '{}'
  return (
    <div className="border border-amber-200 bg-amber-50 rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-1.5 px-2 py-1 text-xs text-amber-800 hover:bg-amber-100 transition-colors"
      >
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        <Wrench size={10} className="flex-shrink-0" />
        <span className="font-mono truncate">{tc.name}({argsStr})</span>
      </button>
      {open && (
        <pre className="text-xs bg-white text-slate-600 p-2 border-t border-amber-200 overflow-x-auto max-h-40 overflow-y-auto">
          {tc.result}
        </pre>
      )}
    </div>
  )
}

interface Props {
  activeProject: string | null
  onSelect: (name: string | null) => void
}

export default function McpGeneratorPage({ activeProject, onSelect }: Props) {
  return activeProject
    // key={activeProject} forces a full remount on every project switch —
    // same fix, same reasoning as ApiGeneratorPage's own ApiProjectDetail:
    // without it, McpProjectDetail's local state (dbPath, baseUrl,
    // instructions, selections, ...) was reused across projects instead of
    // resetting, since only server-fetched state gets explicitly refreshed
    // on a name change. Reproduced directly: a new project showed the
    // previous project's Instructions text still populated.
    ? <McpProjectDetail key={activeProject} name={activeProject} onDeleted={() => onSelect(null)} />
    : <McpEmptyState />
}

function McpEmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-8">
      <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center">
        <Plug size={28} className="text-amber-400" />
      </div>
      <div>
        <div className="text-slate-600 font-semibold text-lg mb-1">No MCP server selected</div>
        <div className="text-slate-500 text-sm leading-relaxed max-w-sm">
          Type a name in the left panel and hit + to create one, then point it at a SQLite
          database or an existing API here.
        </div>
      </div>
      <div className="flex flex-col gap-1.5 mt-2">
        {[
          'Data Store: pick tables from a local SQLite file, get a read API + MCP tools',
          'API: auto-detects an OpenAPI spec and turns endpoints into MCP tools',
          'Runs over Streamable HTTP — start/stop it like any other generated project',
        ].map(f => (
          <div key={f} className="flex items-center gap-2 text-xs text-slate-500">
            <span className="text-amber-600">-</span>{f}
          </div>
        ))}
      </div>
    </div>
  )
}

type DetailTab = 'tools' | 'log' | 'metadata' | 'tryit' | 'history' | 'schema'

function fmtTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

function McpProjectDetail({ name, onDeleted }: { name: string; onDeleted: () => void }) {
  const [entry, setEntry] = useState<McpProjectEntry | null>(null)
  const [checked, setChecked] = useState(false)
  const [metadata, setMetadata] = useState<McpMetadata | null>(null)
  const [buildLog, setBuildLog] = useState<BuildLogRun[]>([])
  const [tab, setTab] = useState<DetailTab>('tools')

  // Both can be on at once — a single MCP server whose tools come from a
  // datastore AND an external API side by side (each source's own state
  // below is already independent, so combining them needs no new state,
  // just independent visibility instead of an exclusive either/or toggle).
  // At least one must always be on; the UI enforces that on click.
  const [useDatastore, setUseDatastore] = useState(true)
  const [useApiSource, setUseApiSource] = useState(false)

  // Data Store source
  const [dbPath, setDbPath] = useState('')
  const [tables, setTables] = useState<McpTable[]>([])
  const [selectedTables, setSelectedTables] = useState<Set<string>>(new Set())
  const [tableDescriptions, setTableDescriptions] = useState<Record<string, string>>({})
  // Keyed by "table::column" — column-level descriptions, editable only in
  // the Metadata tab (the left panel's pre-generation checklist stays table-
  // level only, to keep initial selection quick).
  const [columnDescriptions, setColumnDescriptions] = useState<Record<string, string>>({})

  // API source
  const [baseUrl, setBaseUrl] = useState('')
  const [apiUsername, setApiUsername] = useState('')
  const [apiPassword, setApiPassword] = useState('')
  const [endpoints, setEndpoints] = useState<McpEndpoint[]>([])
  const [selectedEndpoints, setSelectedEndpoints] = useState<Set<string>>(new Set())
  const [endpointDescriptions, setEndpointDescriptions] = useState<Record<string, string>>({})
  const [specNotFound, setSpecNotFound] = useState(false)
  const [pastedSpec, setPastedSpec] = useState('')

  const [introspecting, setIntrospecting] = useState(false)
  const [introspectError, setIntrospectError] = useState('')

  const [generating, setGenerating] = useState(false)
  const [progressLog, setProgressLog] = useState<string[]>([])
  const [genError, setGenError] = useState('')

  // Business-logic/join tools + instructions — datastore only. customTools
  // carries whatever's currently known (LLM-designed then possibly
  // user-edited/removed) straight through on every (re)generate; instructions
  // only gets re-processed by the backend when its text actually changed
  // since the last successful generate (see server.py's _run_mcp_generate).
  const [instructions, setInstructions] = useState('')
  const [showInstrModal, setShowInstrModal] = useState(false)
  const [customTools, setCustomTools] = useState<McpTool[]>([])

  // History — same shape/pattern as Web App/Web API's own History tab: a
  // semantic record of every generate/update's instructions/comment text,
  // distinct from the Build Log's raw progress lines.
  const [history, setHistory] = useState<HistoryEvent[]>([])
  const [comment, setComment] = useState('')
  const [viewInstructions, setViewInstructions] = useState<string | null>(null)
  const [seededFromMetadata, setSeededFromMetadata] = useState(false)
  const [metadataMode, setMetadataMode] = useState<'view' | 'edit'>('view')

  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [chatError, setChatError] = useState('')
  const [showRawExample, setShowRawExample] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  // Only one poll may ever be live per mounted instance — same fix, same
  // reasoning as ApiGeneratorPage's own pollRef: without it, this interval
  // (started via a plain setInterval, not inside a useEffect with its own
  // cleanup) survives a project switch and keeps calling this closure's
  // setState functions in the background, even after key={activeProject}
  // has unmounted this instance — a React key change only triggers effect
  // cleanups, it doesn't know about a bare setInterval this component never
  // registered for cleanup anywhere.
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refreshEntry = useCallback(() => {
    api.listMcpProjects()
      .then(list => setEntry(list.find(p => p.name === name) || null))
      .catch(() => setEntry(null))
      .finally(() => setChecked(true))
  }, [name])

  const refreshAfterGenerate = useCallback(() => {
    refreshEntry()
    // Also re-syncs customTools AND selection from the response — picks up
    // anything instructions just added (a new custom tool, or a whole extra
    // table/endpoint via additionalTables/additionalEndpoints in
    // mcp_orchestrator.design_custom_tools/select_additional_endpoints), not
    // just metadata for display. Without this, a table instructions just
    // added would silently drop out again on the NEXT Update, since
    // selectedTables wouldn't know about it and the SAME instructions text
    // (unchanged) never gets reprocessed a second time.
    api.getMcpMetadata(name).then(m => {
      setMetadata(m)
      setCustomTools(m.tools.filter(t => t.kind === 'custom'))
      // Independent, not else-if — a "both" project has both populated.
      if (m.datastore) {
        setSelectedTables(new Set(m.datastore.tables.map(t => t.name)))
        setTableDescriptions(prev => ({
          ...prev, ...Object.fromEntries(m.datastore!.tables.map(t => [t.name, t.description || ''])),
        }))
      }
      if (m.api) {
        setSelectedEndpoints(new Set(m.api.endpoints.map(e => `${e.method} ${e.path}`)))
        setEndpointDescriptions(prev => ({
          ...prev, ...Object.fromEntries(m.api!.endpoints.map(e => [`${e.method} ${e.path}`, e.description || ''])),
        }))
      }
    }).catch(() => {})
    api.getMcpBuildLog(name).then(setBuildLog).catch(() => {})
    api.getMcpHistory(name).then(setHistory).catch(() => {})
  }, [name, refreshEntry])

  const pollUntilDone = useCallback((requestId: string) => {
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
          setTab(t => t === 'log' ? 'tools' : t)
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

  useEffect(() => {
    let cancelled = false
    setChecked(false)
    setSeededFromMetadata(false)
    refreshEntry()
    api.getMcpMetadata(name).then(setMetadata).catch(() => setMetadata(null))
    api.getMcpBuildLog(name).then(setBuildLog).catch(() => setBuildLog([]))
    api.getMcpHistory(name).then(setHistory).catch(() => setHistory([]))

    // Reconnect to a generation already in progress for THIS project — same
    // mechanism as ApiGeneratorPage's own reconnect (the endpoint is
    // generator-agnostic, keyed purely on project name server-side). Without
    // this, starting two MCP generations in parallel (one per project) and
    // switching between their tabs would show the draft/idle config panel
    // for whichever one you're not currently viewing, even though it's still
    // genuinely running server-side — misleading, and inviting a duplicate
    // submit on the one that looks idle.
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
        }
      } catch {
        // no job for this project, or it's already finished — nothing to reconnect to
      }
    }).catch(() => {})

    return () => {
      cancelled = true
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [name, refreshEntry, pollUntilDone])

  // Seed the config-panel state from persisted metadata exactly ONCE per
  // project — bootstraps an already-generated project's descriptions/
  // selection/custom-tools/instructions without forcing a re-introspection,
  // but deliberately doesn't re-run on every post-generate metadata refresh:
  // metadata.datastore.tables only holds the previously-SELECTED tables (not
  // the full schema), so overwriting `tables` from it after every update
  // would silently lose whichever tables the user loaded but didn't select —
  // exactly the ones a custom/join tool might still need to reference.
  useEffect(() => {
    if (!metadata || seededFromMetadata) return
    setSeededFromMetadata(true)
    setInstructions(metadata.instructions || '')
    setCustomTools(metadata.tools.filter(t => t.kind === 'custom'))
    // Independent, not else-if — a "both" project has both populated.
    setUseDatastore(!!metadata.datastore)
    setUseApiSource(!!metadata.api)
    if (metadata.datastore) {
      setDbPath(metadata.datastore.dbPath)
      setTables(metadata.datastore.tables)
      setSelectedTables(new Set(metadata.datastore.tables.map(t => t.name)))
      setTableDescriptions(Object.fromEntries(metadata.datastore.tables.map(t => [t.name, t.description || ''])))
      setColumnDescriptions(Object.fromEntries(
        metadata.datastore.tables.flatMap(t => t.columns.map(c => [`${t.name}::${c.name}`, c.description || '']))
      ))
    }
    if (metadata.api) {
      setBaseUrl(metadata.api.baseUrl)
      setEndpoints(metadata.api.endpoints)
      setSelectedEndpoints(new Set(metadata.api.endpoints.map(e => `${e.method} ${e.path}`)))
      setEndpointDescriptions(Object.fromEntries(metadata.api.endpoints.map(e => [`${e.method} ${e.path}`, e.description || ''])))
    }
  }, [metadata, seededFromMetadata])

  const handleIntrospectSqlite = async () => {
    if (!dbPath.trim()) return
    setIntrospecting(true)
    setIntrospectError('')
    try {
      const { tables: found } = await api.introspectSqlite(dbPath.trim())
      setTables(found)
      setSelectedTables(new Set(found.map(t => t.name)))
    } catch (e: any) {
      setIntrospectError(e.message || 'Could not read that SQLite file')
    } finally {
      setIntrospecting(false)
    }
  }

  const handleIntrospectApi = async () => {
    if (!baseUrl.trim()) return
    setIntrospecting(true)
    setIntrospectError('')
    setSpecNotFound(false)
    try {
      const result = await api.introspectApi(baseUrl.trim(), apiUsername || undefined, apiPassword || undefined)
      if (!result.found) {
        setSpecNotFound(true)
        setEndpoints([])
      } else {
        const found = result.endpoints || []
        setEndpoints(found)
        setSelectedEndpoints(new Set(found.filter(e => e.method === 'GET').map(e => `${e.method} ${e.path}`)))
      }
    } catch (e: any) {
      setIntrospectError(e.message || 'Could not reach that API')
    } finally {
      setIntrospecting(false)
    }
  }

  const handleIntrospectFromSpec = async () => {
    if (!pastedSpec.trim() || !baseUrl.trim()) return
    setIntrospecting(true)
    setIntrospectError('')
    try {
      const spec = JSON.parse(pastedSpec)
      const result = await api.introspectApiFromSpec(baseUrl.trim(), spec)
      const found = result.endpoints || []
      setEndpoints(found)
      setSelectedEndpoints(new Set(found.filter(e => e.method === 'GET').map(e => `${e.method} ${e.path}`)))
      setSpecNotFound(false)
    } catch (e: any) {
      setIntrospectError(e.message || 'Could not parse that spec — paste valid OpenAPI JSON')
    } finally {
      setIntrospecting(false)
    }
  }

  // Shared by handleGenerate (what actually gets sent) and handleSaveMetadata
  // (a local preview of the same thing, so the JSON view reflects an edit
  // immediately instead of showing stale server data until the next Update).
  const withCurrentDescriptions = useCallback((t: McpTable) => ({
    ...t,
    description: tableDescriptions[t.name] || t.description || '',
    columns: t.columns.map(c => ({
      ...c,
      description: columnDescriptions[`${t.name}::${c.name}`] || c.description || '',
    })),
  }), [tableDescriptions, columnDescriptions])

  const handleGenerate = useCallback(async () => {
    setGenerating(true)
    setGenError('')
    setProgressLog([])
    setTab('log')
    try {
      let effUseDatastore = useDatastore
      let effUseApiSource = useApiSource
      let effDbPath = dbPath.trim()
      let effBaseUrl = baseUrl.trim()
      let effUsername = apiUsername
      let effPassword = apiPassword
      let effTables = tables
      let effSelectedTables = selectedTables
      let effEndpoints = endpoints
      let effSelectedEndpoints = selectedEndpoints

      // "Paste and go": if a toggled-on source still has no input, try to
      // pull one straight out of the pasted Instructions text — the exact
      // format every MCPGenerator/instructions doc already uses. Checked
      // independently per source, so a combined datastore+API project can
      // auto-fill either or both from one doc that mentions both.
      const isFreshDefault = !effUseApiSource && effUseDatastore && !effDbPath && effTables.length === 0
      if (instructions.trim()) {
        const dbMatch = instructions.match(/([A-Za-z]:\\[^\r\n`]*?\.(?:db|sqlite3?|sqlite))/i)
        const urlMatch = instructions.match(/https?:\/\/[^\s`)]+/)
        const credsMatch = instructions.match(/`([^`\s]+)`\s*\/\s*`([^`\s]+)`/)

        // Nothing customized yet (still on the initial default) and the
        // instructions only describe an API, not a database — flip to API,
        // same "paste and go" promise as before for the common single-
        // source case, now that Data Store is the default toggle.
        if (isFreshDefault && urlMatch && !dbMatch) {
          effUseDatastore = false
          effUseApiSource = true
          setUseDatastore(false)
          setUseApiSource(true)
        }

        if (effUseDatastore && (!effDbPath || effTables.length === 0) && dbMatch) {
          effDbPath = dbMatch[1]
          setDbPath(effDbPath)
          const { tables: found } = await api.introspectSqlite(effDbPath)
          effTables = found
          effSelectedTables = new Set(found.map(t => t.name))
          setTables(found)
          setSelectedTables(effSelectedTables)
        }
        if (effUseApiSource && (!effBaseUrl || effEndpoints.length === 0) && urlMatch) {
          effBaseUrl = urlMatch[0].replace(/[).,]+$/, '')
          effUsername = credsMatch?.[1] || effUsername
          effPassword = credsMatch?.[2] || effPassword
          setBaseUrl(effBaseUrl)
          if (effUsername) setApiUsername(effUsername)
          if (effPassword) setApiPassword(effPassword)
          const result = await api.introspectApi(effBaseUrl, effUsername || undefined, effPassword || undefined)
          if (!result.found) {
            throw new Error("Found an API URL in your instructions, but couldn't auto-detect its OpenAPI spec — enter it manually below and paste the spec if needed.")
          }
          effEndpoints = result.endpoints || []
          effSelectedEndpoints = new Set(effEndpoints.filter(e => e.method === 'GET').map(e => `${e.method} ${e.path}`))
          setEndpoints(effEndpoints)
          setSelectedEndpoints(effSelectedEndpoints)
        }
      }

      if (!effUseDatastore && !effUseApiSource) {
        throw new Error('Enable at least one source (Data Store and/or API) above.')
      }
      if (effUseDatastore && !effDbPath) {
        throw new Error('No database file entered, and none found in your Instructions text either.')
      }
      if (effUseApiSource && !effBaseUrl) {
        throw new Error('No API URL entered, and none found in your Instructions text either.')
      }

      // Both blocks can run — a combined project sends BOTH sets of keys in
      // one sourceConfig; the backend already treats them as independent
      // (see mcp_orchestrator.generate's has_datastore/has_api split).
      const sourceConfig: Record<string, any> = {}
      if (effUseDatastore) {
        sourceConfig.dbPath = effDbPath
        sourceConfig.tables = effTables.filter(t => effSelectedTables.has(t.name)).map(withCurrentDescriptions)
        // The FULL introspected schema, not just the selected subset above —
        // a join/custom tool should be able to use a table nobody wanted a
        // raw list_/get_ tool for. Also carries current column descriptions
        // through so the backend doesn't treat them as blank on every call.
        sourceConfig.allTables = effTables.map(withCurrentDescriptions)
        sourceConfig.customTools = customTools
      }
      if (effUseApiSource) {
        const withCurrentEndpointDescription = (e: McpEndpoint) => ({
          ...e, description: endpointDescriptions[`${e.method} ${e.path}`] || e.description || '',
        })
        sourceConfig.baseUrl = effBaseUrl
        sourceConfig.authType = effUsername ? 'basic' : 'none'
        sourceConfig.username = effUsername
        sourceConfig.password = effPassword
        sourceConfig.endpoints = effEndpoints
          .filter(e => effSelectedEndpoints.has(`${e.method} ${e.path}`))
          .map(withCurrentEndpointDescription)
        // Full discovered list, not just the selected subset — instructions
        // like "also add the vehicles endpoint" need to find it here.
        sourceConfig.allEndpoints = effEndpoints.map(withCurrentEndpointDescription)
      }
      const effSourceType = effUseDatastore && effUseApiSource ? 'both' : effUseDatastore ? 'datastore' : 'api'
      const { requestId } = await api.generateMcp(name, effSourceType, sourceConfig, instructions, comment)
      pollUntilDone(requestId)
    } catch (e: any) {
      setGenError(e.message || 'Generation failed')
      setGenerating(false)
    }
  }, [name, useDatastore, useApiSource, dbPath, tables, selectedTables, withCurrentDescriptions, customTools, instructions, comment,
      baseUrl, apiUsername, apiPassword, endpoints, selectedEndpoints, endpointDescriptions, pollUntilDone])

  // "Save" in the Metadata tab never talks to the server — the only thing
  // that actually regenerates and restarts anything is Generate/Update in
  // the left panel. This just rebuilds a local PREVIEW of what that next
  // Update would send, so the JSON view reflects your edit immediately
  // instead of showing whatever's still on the server from before.
  const handleSaveMetadata = useCallback(() => {
    setMetadata(prev => {
      if (!prev) return prev
      const previewTables = tables.filter(t => selectedTables.has(t.name)).map(withCurrentDescriptions)
      const previewEndpoints = endpoints
        .filter(e => selectedEndpoints.has(`${e.method} ${e.path}`))
        .map(e => ({ ...e, description: endpointDescriptions[`${e.method} ${e.path}`] || '' }))
      return {
        ...prev,
        instructions,
        tools: [
          ...prev.tools.filter(t => t.kind !== 'custom'),
          ...customTools,
        ],
        datastore: prev.datastore ? { ...prev.datastore, tables: previewTables } : prev.datastore,
        api: prev.api ? { ...prev.api, endpoints: previewEndpoints } : prev.api,
      }
    })
    setMetadataMode('view')
  }, [tables, selectedTables, withCurrentDescriptions, customTools, instructions,
      endpoints, selectedEndpoints, endpointDescriptions])

  const handleChatSend = useCallback(async () => {
    const text = chatInput.trim()
    if (!text || chatBusy) return
    const nextMessages: ChatMsg[] = [...chatMessages, { role: 'user', content: text }]
    setChatMessages(nextMessages)
    setChatInput('')
    setChatBusy(true)
    setChatError('')
    try {
      const result = await api.chatWithMcp(name, nextMessages.map(m => ({ role: m.role, content: m.content })))
      setChatMessages(prev => [...prev, { role: 'assistant', content: result.reply, toolCalls: result.toolCalls }])
    } catch (e: any) {
      setChatError(e.message || 'Chat failed')
    } finally {
      setChatBusy(false)
    }
  }, [name, chatInput, chatBusy, chatMessages])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, chatBusy])

  if (!checked) return <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">Loading...</div>

  // Non-empty Instructions alone is enough to enable Generate, even with no
  // source entered and nothing ticked yet — handleGenerate itself tries to
  // pull a database file path or API URL straight out of the instructions
  // text ("paste and go"), the same format every MCPGenerator/instructions
  // doc already uses. Falls back to the original requirement (a source
  // entered AND at least one table/endpoint ticked) when Instructions is
  // empty, so the existing manual flow is unchanged.
  const canGenerate = instructions.trim().length > 0 || (
    (useDatastore && selectedTables.size > 0 && dbPath.trim().length > 0) ||
    (useApiSource && selectedEndpoints.size > 0 && baseUrl.trim().length > 0)
  )

  const configPanel = (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-800 flex-1 truncate">{entry?.title || name}</h2>
        {/* Start/Stop lives ONLY in the left sidebar now — having it here too,
            as a second independent control with its own local `busy`/status
            state, meant the two could show different things until each
            happened to refetch (e.g. stop it from the sidebar, this panel
            still showed "Stop" until its own 5s refreshEntry tick caught up).
            One control, one source of truth. */}
        {entry?.status && (
          <span className={`text-xs px-2 py-0.5 rounded border ${
            entry.status === 'running' ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
            : entry.status === 'start_failed' ? 'bg-red-50 text-red-700 border-red-200'
            : 'bg-slate-100 text-slate-600 border-slate-200'
          }`}>
            {entry.status === 'running' ? 'Running' : entry.status === 'start_failed' ? 'Failed to start'
              : entry.status === 'draft' ? 'Draft' : 'Stopped'}
          </span>
        )}
      </div>

      {entry?.status === 'running' && entry.port && (
        <div className="flex items-center gap-1.5">
          <a href={`http://localhost:${entry.port}/mcp`} target="_blank" rel="noreferrer"
             className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-amber-50 hover:bg-amber-100
                        text-amber-700 border border-amber-200 transition-colors flex-1 justify-center">
            <ExternalLink size={11} /> MCP endpoint (:{entry.port})
          </a>
          <a href={`http://localhost:${entry.port}/docs`} target="_blank" rel="noreferrer"
             className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-indigo-50 hover:bg-indigo-100
                        text-indigo-700 border border-indigo-200 transition-colors flex-1 justify-center">
            <BookOpen size={11} /> Docs
          </a>
        </div>
      )}

      {metadata?.datastore?.backingApiBaseUrl && (
        <div className="flex items-center gap-2 text-xs bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5">
          <Database size={11} className="text-slate-400 flex-shrink-0" />
          <span className="text-slate-500">Backing API:</span>
          <span className="font-mono text-slate-700">{metadata.datastore.backingApiProject}</span>
          <a
            href={metadata.datastore.backingApiBaseUrl}
            target="_blank" rel="noreferrer"
            className="text-amber-700 underline ml-auto flex-shrink-0"
          >
            {metadata.datastore.backingApiBaseUrl}
          </a>
        </div>
      )}

      {/* Both can be active — a single MCP server combining a datastore AND
          an external API. Not a radio group: clicking one toggles it on/off
          independently, blocked only from turning the LAST active one off
          (at least one source is always required). */}
      <div className="flex gap-1.5 p-1 bg-slate-100 rounded-lg">
        <button
          onClick={() => setUseDatastore(v => !v)}
          disabled={useDatastore && !useApiSource}
          title={useDatastore && !useApiSource ? 'At least one source must stay enabled' : undefined}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-colors disabled:cursor-not-allowed ${
            useDatastore ? 'bg-white text-amber-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Database size={12} /> Data Store
        </button>
        <button
          onClick={() => setUseApiSource(v => !v)}
          disabled={useApiSource && !useDatastore}
          title={useApiSource && !useDatastore ? 'At least one source must stay enabled' : undefined}
          className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-colors disabled:cursor-not-allowed ${
            useApiSource ? 'bg-white text-amber-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Globe size={12} /> API
        </button>
      </div>

      {useDatastore && (
        <div className="space-y-2">
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">SQLite file path</label>
            <div className="flex gap-1.5">
              <input
                className="flex-1 bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800 min-w-0
                           focus:outline-none focus:border-amber-500"
                placeholder="C:/path/to/orders.db"
                value={dbPath}
                onChange={e => setDbPath(e.target.value)}
              />
              <button
                onClick={handleIntrospectSqlite}
                disabled={introspecting || !dbPath.trim()}
                className="flex-shrink-0 flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-amber-600 hover:bg-amber-500
                           text-white disabled:opacity-40"
              >
                {introspecting ? <RefreshCw size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                Load Tables
              </button>
            </div>
          </div>

          {introspectError && (
            <div className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={10} />{introspectError}</div>
          )}

          {/* Full table/column checklist lives in the Schema tab now — this
              panel is for input, not for browsing a potentially long list. */}
          {tables.length > 0 && (
            <button
              onClick={() => setTab('schema')}
              className="w-full flex items-center justify-between text-xs px-2.5 py-1.5 rounded-md bg-amber-50
                         border border-amber-200 text-amber-800 hover:bg-amber-100 transition-colors"
            >
              <span>{tables.length} table(s) found, {selectedTables.size} selected</span>
              <span className="underline">Choose in Schema tab →</span>
            </button>
          )}
        </div>
      )}

      {useApiSource && (
        <div className="space-y-2">
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">API base URL</label>
            <input
              className="w-full bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800
                         focus:outline-none focus:border-amber-500"
              placeholder="http://localhost:8400"
              value={baseUrl}
              onChange={e => setBaseUrl(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input
              className="bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-amber-500"
              placeholder="Username (optional)"
              value={apiUsername}
              onChange={e => setApiUsername(e.target.value)}
            />
            <input
              type="password"
              className="bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-amber-500"
              placeholder="Password"
              value={apiPassword}
              onChange={e => setApiPassword(e.target.value)}
            />
          </div>
          <button
            onClick={handleIntrospectApi}
            disabled={introspecting || !baseUrl.trim()}
            className="w-full flex items-center justify-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-amber-600 hover:bg-amber-500
                       text-white disabled:opacity-40"
          >
            {introspecting ? <RefreshCw size={11} className="animate-spin" /> : <RefreshCw size={11} />}
            Discover Endpoints
          </button>

          {introspectError && (
            <div className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={10} />{introspectError}</div>
          )}

          {specNotFound && (
            <div className="space-y-1.5 border border-amber-200 bg-amber-50 rounded-md p-2">
              <div className="text-xs text-amber-800">
                No OpenAPI spec found at the usual paths. Paste the spec's raw JSON below.
              </div>
              <textarea
                className="w-full h-24 bg-white border border-slate-300 rounded-md px-2 py-1.5 text-xs font-mono
                           focus:outline-none focus:border-amber-500"
                placeholder='{"paths": {...}}'
                value={pastedSpec}
                onChange={e => setPastedSpec(e.target.value)}
              />
              <button
                onClick={handleIntrospectFromSpec}
                disabled={introspecting || !pastedSpec.trim()}
                className="text-xs px-2.5 py-1 rounded-md bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-40"
              >
                Parse Spec
              </button>
            </div>
          )}

          {/* Full endpoint checklist lives in the Schema tab now — this
              panel is for input, not for browsing a potentially long list. */}
          {endpoints.length > 0 && (
            <button
              onClick={() => setTab('schema')}
              className="w-full flex items-center justify-between text-xs px-2.5 py-1.5 rounded-md bg-amber-50
                         border border-amber-200 text-amber-800 hover:bg-amber-100 transition-colors"
            >
              <span>{endpoints.filter(e => e.method === 'GET').length} GET endpoint(s) found, {selectedEndpoints.size} selected</span>
              <span className="underline">Choose in Schema tab →</span>
            </button>
          )}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs font-medium text-slate-600">
            {useDatastore && useApiSource
              ? 'Instructions — more tables/endpoints, joins/business logic (optional)'
              : useDatastore
              ? 'Instructions — more tables, joins/business logic (optional)'
              : 'Instructions — more endpoints, notes for descriptions (optional)'}
          </label>
          <InstructionsBadge
            hasInstructions={!!instructions.trim()}
            onClick={() => setShowInstrModal(true)}
            disabled={generating}
          />
        </div>
        {/* Edited exclusively in the modal above (same pattern as Web UI's/Web
            API's own Instructions field) -- a plain textarea mirroring the
            same state used to live here too, so importing a PRD/TRD from
            Product Forge inside the modal also silently overwrote this box. */}
        <p className="text-xs text-slate-400 italic">
          {instructions.trim()
            ? `${instructions.trim().length.toLocaleString()} chars — click "Instructions added" to view/edit.`
            : useDatastore
            ? 'e.g. "add a tool for total order value per customer" or "also expose the payments table"...'
            : 'e.g. "also include the /reports endpoints" or notes for how tools should be described...'}
        </p>
      </div>

      {metadata && (
        <div>
          <label className="text-xs font-medium text-slate-600 block mb-1">
            Comment <span className="text-slate-400 font-normal">(optional — saved to history)</span>
          </label>
          <input
            className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-lg focus:ring-2 focus:ring-amber-200 focus:border-amber-400 outline-none"
            placeholder='e.g. "Added revenue-per-customer tool per request"'
            value={comment}
            disabled={generating}
            onChange={e => setComment(e.target.value)}
          />
        </div>
      )}

      <button
        onClick={handleGenerate}
        disabled={generating || !canGenerate}
        className="w-full flex items-center justify-center gap-1.5 py-2 rounded-md bg-amber-600 hover:bg-amber-500
                   text-white text-sm font-medium disabled:opacity-40"
      >
        <Sparkles size={13} />
        {generating ? 'Generating...' : metadata ? 'Refine MCP Server' : 'Generate MCP Server'}
      </button>
      {genError && (
        <div className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={10} />{genError}</div>
      )}
    </div>
  )

  const tabsPanel = (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex border-b border-slate-200 flex-shrink-0">
        {([
          ['tools', 'Tools', Wrench],
          ['schema', 'Schema', Database],
          ['tryit', 'Try it', Terminal],
          ['log', 'Build Log', Terminal],
          ['history', 'History', Clock],
          ['metadata', 'Metadata', FileJson],
        ] as const).map(([key, label, Icon]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
              tab === key ? 'border-amber-600 text-amber-700' : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Icon size={12} /> {label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {tab === 'tools' && (
          metadata?.tools?.length ? (
            <div className="space-y-2">
              {metadata.tools.map(t => (
                <div key={t.name} className="border border-slate-200 rounded-md p-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-semibold text-amber-700">{t.name}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">{t.method} {t.path}</span>
                  </div>
                  <div className="text-xs text-slate-600 mt-1">{t.description}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-slate-400 text-center py-8">No tools yet — configure a source and generate.</div>
          )
        )}

        {tab === 'tryit' && (
          entry?.status === 'running' && entry.port ? (
            <div className="flex flex-col h-full -m-4">
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {chatMessages.length === 0 && (
                  <div className="text-xs text-slate-400 text-center py-8">
                    Ask a question in plain language — the LLM will call this server's tools to answer.
                  </div>
                )}
                {chatMessages.map((m, i) => (
                  <div key={i} className={`flex gap-2 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {m.role === 'assistant' && (
                      <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <Bot size={12} className="text-amber-700" />
                      </div>
                    )}
                    <div className={`max-w-[80%] space-y-1.5`}>
                      <div className={`rounded-lg px-3 py-2 text-xs whitespace-pre-wrap ${
                        m.role === 'user' ? 'bg-amber-600 text-white' : 'bg-slate-100 text-slate-800'
                      }`}>
                        {m.content}
                      </div>
                      {m.toolCalls && m.toolCalls.length > 0 && (
                        <div className="space-y-1">
                          {m.toolCalls.map((tc, j) => (
                            <ToolCallChip key={j} tc={tc} />
                          ))}
                        </div>
                      )}
                    </div>
                    {m.role === 'user' && (
                      <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <User size={12} className="text-slate-600" />
                      </div>
                    )}
                  </div>
                ))}
                {chatBusy && (
                  <div className="flex gap-2 justify-start">
                    <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                      <Bot size={12} className="text-amber-700" />
                    </div>
                    <div className="rounded-lg px-3 py-2 text-xs bg-slate-100 text-slate-400">Thinking...</div>
                  </div>
                )}
                {chatError && (
                  <div className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={10} />{chatError}</div>
                )}
                <div ref={chatEndRef} />
              </div>

              <div className="border-t border-slate-200 p-3 flex-shrink-0 space-y-2">
                <div className="flex gap-1.5">
                  <input
                    className="flex-1 bg-white border border-slate-300 rounded-md px-2.5 py-1.5 text-xs text-slate-800 min-w-0
                               focus:outline-none focus:border-amber-500"
                    placeholder="Ask a question about this server's data..."
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleChatSend()}
                    disabled={chatBusy}
                  />
                  <button
                    onClick={handleChatSend}
                    disabled={chatBusy || !chatInput.trim()}
                    className="flex-shrink-0 p-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 rounded-md transition-colors"
                  >
                    <Send size={14} className="text-white" />
                  </button>
                </div>
                <button
                  onClick={() => setShowRawExample(v => !v)}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600"
                >
                  {showRawExample ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                  Raw protocol example
                </button>
                {showRawExample && (
                  <pre className="bg-slate-900 text-slate-100 text-xs rounded-md p-2.5 overflow-x-auto">
{`curl -N -X POST http://localhost:${entry.port}/mcp/ \\
  -H "Content-Type: application/json" \\
  -H "Accept: application/json, text/event-stream" \\
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`}
                  </pre>
                )}
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-400 text-center py-8">Start the server to try it.</div>
          )
        )}

        {tab === 'log' && (
          <pre className="text-xs text-slate-600 font-mono whitespace-pre-wrap">
            {generating ? progressLog.join('\n') : (buildLog[buildLog.length - 1]?.lines || []).join('\n') || 'No build log yet.'}
          </pre>
        )}

        {tab === 'history' && (
          <div className="space-y-3">
            {history.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 text-center px-8 py-12">
                <Clock size={36} className="text-slate-300" />
                <p className="text-slate-600 text-sm font-semibold">No history yet</p>
                <p className="text-slate-500 text-xs leading-relaxed max-w-xs">Every generation and update is recorded here.</p>
              </div>
            ) : (
              [...history].reverse().map((h, i) => (
                <div key={i} className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-amber-700">{h.event}</span>
                    <span className="ml-auto text-xs text-slate-600 flex items-center gap-1">
                      <Clock size={9} />{fmtTime(h.timestamp)}
                    </span>
                  </div>
                  {h.prompt && <p className="text-xs text-slate-500 leading-relaxed">{h.prompt}</p>}
                  {h.comment && <p className="text-xs text-slate-600 italic">"{h.comment}"</p>}
                  {h.instructions && (
                    <button
                      onClick={() => setViewInstructions(h.instructions!)}
                      className="flex items-center gap-1 text-xs text-amber-700 hover:text-amber-800 transition-colors"
                    >
                      <FileText size={10} /> View instructions
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {tab === 'schema' && (
          <div className="space-y-5">
            {useDatastore && (
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  Tables {tables.length > 0 && `(${selectedTables.size}/${tables.length} selected)`}
                </div>
                {tables.length === 0 ? (
                  <p className="text-xs text-slate-400">No tables loaded yet — enter a SQLite file path in the left panel.</p>
                ) : (
                  tables.map(t => (
                    <div key={t.name} className="border border-slate-200 rounded-md p-2 space-y-1.5">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedTables.has(t.name)}
                          onChange={e => {
                            setSelectedTables(prev => {
                              const next = new Set(prev)
                              if (e.target.checked) next.add(t.name); else next.delete(t.name)
                              return next
                            })
                          }}
                        />
                        <span className="text-xs font-mono font-medium text-slate-700">{t.name}</span>
                        <span className="text-xs text-slate-400 ml-auto">{t.columns.length} cols</span>
                      </label>
                      {selectedTables.has(t.name) && (
                        <input
                          className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs text-slate-700
                                     focus:outline-none focus:border-amber-400"
                          placeholder={`What is "${t.name}" for an MCP client? (optional)`}
                          value={tableDescriptions[t.name] || ''}
                          onChange={e => setTableDescriptions(prev => ({ ...prev, [t.name]: e.target.value }))}
                        />
                      )}
                    </div>
                  ))
                )}
              </div>
            )}

            {useApiSource && (
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                  GET endpoints {endpoints.length > 0 && `(${selectedEndpoints.size}/${endpoints.filter(e => e.method === 'GET').length} selected)`} — v1 is read-only
                </div>
                {endpoints.length === 0 ? (
                  <p className="text-xs text-slate-400">No endpoints discovered yet — enter an API base URL in the left panel.</p>
                ) : (
                  endpoints.filter(e => e.method === 'GET').map(ep => {
                    const key = `${ep.method} ${ep.path}`
                    return (
                      <div key={key} className="border border-slate-200 rounded-md p-2 space-y-1.5">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={selectedEndpoints.has(key)}
                            onChange={e => {
                              setSelectedEndpoints(prev => {
                                const next = new Set(prev)
                                if (e.target.checked) next.add(key); else next.delete(key)
                                return next
                              })
                            }}
                          />
                          <span className="text-xs font-mono font-medium text-slate-700 truncate">{ep.path}</span>
                        </label>
                        {selectedEndpoints.has(key) && (
                          <input
                            className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs text-slate-700
                                       focus:outline-none focus:border-amber-400"
                            placeholder={ep.summary || 'What does this tool do? (optional)'}
                            value={endpointDescriptions[key] || ''}
                            onChange={e => setEndpointDescriptions(prev => ({ ...prev, [key]: e.target.value }))}
                          />
                        )}
                      </div>
                    )
                  })
                )}
              </div>
            )}
          </div>
        )}

        {tab === 'metadata' && (
          metadata ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">
                  {metadataMode === 'edit'
                    ? 'Editing a local preview — nothing is written to disk yet.'
                    : 'Descriptions and custom tools used by this MCP server.'}
                </span>
                <button
                  onClick={() => metadataMode === 'edit' ? handleSaveMetadata() : setMetadataMode('edit')}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-slate-300 bg-white
                             text-slate-600 hover:border-slate-400 hover:text-slate-800 transition-colors"
                >
                  {metadataMode === 'edit' ? <><Check size={11} /> Done editing</> : <><Pencil size={11} /> Edit</>}
                </button>
              </div>
              <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <span className="mt-0.5">⚠</span>
                <span>
                  This tab previews changes locally in your browser only. Nothing is saved to{' '}
                  <code className="px-1 py-0.5 rounded bg-amber-100">metadata.json</code> on disk, and the running
                  server is not affected, until you click <strong>"Refine MCP Server"</strong> in the left panel.
                </span>
              </div>

              {metadataMode === 'view' ? (
                <pre className="text-xs text-slate-600 font-mono whitespace-pre-wrap">
                  {JSON.stringify(metadata, null, 2)}
                </pre>
              ) : (
                <div className="space-y-4">
                {useDatastore && (
                <div className="space-y-3">
                  <div>
                    <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">Tables &amp; columns</div>
                    <div className="space-y-3">
                      {tables.filter(t => selectedTables.has(t.name)).map(t => (
                        <div key={t.name} className="border border-slate-200 rounded-md p-2 space-y-2">
                          <div>
                            <div className="text-xs font-mono font-semibold text-slate-700 mb-1">{t.name}</div>
                            <input
                              className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs text-slate-700
                                         focus:outline-none focus:border-amber-400"
                              placeholder="No description yet — type one, or click Refine to let the LLM fill it in"
                              value={tableDescriptions[t.name] || ''}
                              onChange={e => setTableDescriptions(prev => ({ ...prev, [t.name]: e.target.value }))}
                            />
                          </div>
                          <div className="pl-3 border-l-2 border-slate-100 space-y-1.5">
                            {t.columns.map(c => {
                              const key = `${t.name}::${c.name}`
                              return (
                                <div key={key} className="flex items-center gap-2">
                                  <span className="text-xs font-mono text-slate-500 flex-shrink-0 w-32 truncate" title={c.name}>
                                    {c.name}
                                    {c.primaryKey && <span className="text-amber-600" title="Primary key"> (pk)</span>}
                                  </span>
                                  <span className="text-xs text-slate-400 flex-shrink-0 w-16 truncate">{c.type}</span>
                                  <input
                                    className="flex-1 min-w-0 bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs text-slate-700
                                               focus:outline-none focus:border-amber-400"
                                    placeholder="No description yet"
                                    value={columnDescriptions[key] || ''}
                                    onChange={e => setColumnDescriptions(prev => ({ ...prev, [key]: e.target.value }))}
                                  />
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">
                      Custom tools (business logic / joins)
                    </div>
                    {customTools.length === 0 ? (
                      <div className="text-xs text-slate-400">
                        None yet — use the Instructions button in the left panel to ask for one.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {customTools.map((ct, i) => (
                          <div key={ct.name} className="border border-slate-200 rounded-md p-2 space-y-1.5">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono font-medium text-amber-700 flex-1 truncate">{ct.name}</span>
                              <button
                                onClick={() => setCustomTools(prev => prev.filter((_, j) => j !== i))}
                                className="text-slate-400 hover:text-red-500 transition-colors"
                                title="Remove this custom tool"
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>
                            <input
                              className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs text-slate-700
                                         focus:outline-none focus:border-amber-400"
                              value={ct.description}
                              onChange={e => setCustomTools(prev => prev.map((p, j) => j === i ? { ...p, description: e.target.value } : p))}
                            />
                            <textarea
                              className="w-full h-16 bg-slate-900 text-slate-100 rounded px-2 py-1.5 text-xs font-mono
                                         focus:outline-none resize-none"
                              value={ct.sql || ''}
                              onChange={e => setCustomTools(prev => prev.map((p, j) => j === i ? { ...p, sql: e.target.value } : p))}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                )}
                {useApiSource && (
                <div>
                  <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-1.5">Endpoints</div>
                  <div className="space-y-2">
                    {endpoints.filter(e => selectedEndpoints.has(`${e.method} ${e.path}`)).map(e => {
                      const key = `${e.method} ${e.path}`
                      return (
                        <div key={key} className="border border-slate-200 rounded-md p-2">
                          <div className="text-xs font-mono font-medium text-slate-700 mb-1">{key}</div>
                          <input
                            className="w-full bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs text-slate-700
                                       focus:outline-none focus:border-amber-400"
                            placeholder="No description yet — type one, or click Refine to let the LLM fill it in"
                            value={endpointDescriptions[key] || ''}
                            onChange={ev => setEndpointDescriptions(prev => ({ ...prev, [key]: ev.target.value }))}
                          />
                        </div>
                      )
                    })}
                  </div>
                </div>
                )}
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-400 text-center py-8">No metadata yet — generate first.</div>
          )
        )}
      </div>
    </div>
  )

  return (
    <>
      <ResizablePanels left={configPanel} right={tabsPanel} defaultLeftWidth={420} minLeft={320} maxLeft={560} />
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
          title="Instructions"
          onClose={() => setViewInstructions(null)}
        />
      )}
    </>
  )
}
