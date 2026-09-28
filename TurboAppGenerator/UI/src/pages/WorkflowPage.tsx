import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap,
  useNodesState, useEdgesState, addEdge, useReactFlow,
  type Connection, type Node, type Edge, type NodeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Play, Save, Plus, X, Zap } from 'lucide-react'
import { Agent } from '../hooks/contentAgentsApi'
import {
  PipelineAgent, WorkflowRunStatus,
  getWorkflow, saveWorkflow, startWorkflowRun, getWorkflowRunStatus, getLatestWorkflowRun, continueWorkflowNode,
} from '../hooks/workflowApi'
import { AGENT_META } from '../components/ContentAgentsSidebar'
import { Artifact } from '../components/ArtifactPreview'
import ContentModelPicker from '../components/ContentModelPicker'
import RightPreviewPanel from '../components/RightPreviewPanel'
import AgentNode, { AgentNodeData } from '../workflows/nodes/AgentNode'
import ForgeNode, { ForgeNodeData, DEFAULT_ARTIFACT_STAGES } from '../workflows/nodes/ForgeNode'
import WebUiGeneratorNode, { WebUiGeneratorNodeData } from '../workflows/nodes/WebUiGeneratorNode'
import WebApiGeneratorNode, { WebApiGeneratorNodeData } from '../workflows/nodes/WebApiGeneratorNode'
import McpGeneratorNode, { McpGeneratorNodeData } from '../workflows/nodes/McpGeneratorNode'

const nodeTypes: NodeTypes = {
  agent: AgentNode as any, forge: ForgeNode as any,
  webui_generator: WebUiGeneratorNode as any, webapi_generator: WebApiGeneratorNode as any,
  mcp_generator: McpGeneratorNode as any,
}

function labelFor(agent: Agent | PipelineAgent): string {
  if (agent === 'product_forge') return 'Product Forge'
  if (agent === 'webui_generator') return 'Web UI Generator'
  if (agent === 'webapi_generator') return 'Web API Generator'
  if (agent === 'mcp_generator') return 'MCP Generator'
  return AGENT_META[agent].label
}

let nodeCounter = 0

interface Props {
  workflowId: string | null
  onNew: () => void
  onSaved: (id: string) => void
  // Lifted to App.tsx (not local state here) specifically because saving a
  // brand-new, never-before-saved workflow changes `activeWorkflowId` from
  // null to a real id, which changes this page's own `key` in App.tsx and
  // remounts WorkflowCanvas entirely -- a plain useState here would silently
  // reset back to its default, undoing whatever the user had just set right
  // before hitting Save.
  autoMode: boolean
  onAutoModeChange: (auto: boolean) => void
}

export default function WorkflowPage({ workflowId, onNew, onSaved, autoMode, onAutoModeChange }: Props) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvas workflowId={workflowId} onNew={onNew} onSaved={onSaved}
                       autoMode={autoMode} onAutoModeChange={onAutoModeChange} />
    </ReactFlowProvider>
  )
}

function WorkflowCanvas({ workflowId, onNew, onSaved, autoMode, onAutoModeChange }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<any>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [name, setName] = useState('Untitled workflow')
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null)
  const [running, setRunning] = useState(false)
  const [loading, setLoading] = useState(!!workflowId)
  const [preview, setPreview] = useState<Artifact | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const runIdRef = useRef<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { screenToFlowPosition } = useReactFlow()

  const updateNodeData = useCallback((id: string, patch: Record<string, unknown>) => {
    setNodes((nds) => nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)))
  }, [setNodes])

  const deleteNode = useCallback((id: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== id))
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id))
  }, [setNodes, setEdges])

  const continueNode = useCallback((id: string) => {
    if (!workflowId || !runIdRef.current) return
    continueWorkflowNode(workflowId, runIdRef.current, id)
  }, [workflowId])

  const onPreview = useCallback((artifact: Artifact) => setPreview(artifact), [])

  const wireNode = useCallback((n: {
    id: string; agent: Agent | PipelineAgent; position: { x: number; y: number }
    libraryItemId?: string; url?: string; question?: string; prompt?: string; videoVoice?: string
    videoSplit?: boolean
    productIdea?: string; draftMode?: boolean; artifactStages?: string[]; projectName?: string
    apiLanguage?: string; apiAuthType?: string; mcpInstructions?: string
  }): Node<any> => {
    const onChange = (patch: Record<string, unknown>) => updateNodeData(n.id, patch)
    const onDelete = () => deleteNode(n.id)
    const onContinue = () => continueNode(n.id)

    if (n.agent === 'product_forge') {
      const data: ForgeNodeData = {
        projectName: n.projectName, productIdea: n.productIdea, draftMode: n.draftMode,
        artifactStages: n.artifactStages && n.artifactStages.length > 0 ? n.artifactStages : DEFAULT_ARTIFACT_STAGES,
        onChange, onDelete, onContinue,
      }
      return { id: n.id, type: 'forge', position: n.position, data }
    }
    if (n.agent === 'webui_generator') {
      const data: WebUiGeneratorNodeData = { projectName: n.projectName, onChange, onDelete, onContinue, onPreview }
      return { id: n.id, type: 'webui_generator', position: n.position, data }
    }
    if (n.agent === 'webapi_generator') {
      const data: WebApiGeneratorNodeData = {
        projectName: n.projectName, apiLanguage: n.apiLanguage, apiAuthType: n.apiAuthType,
        onChange, onDelete, onContinue, onPreview,
      }
      return { id: n.id, type: 'webapi_generator', position: n.position, data }
    }
    if (n.agent === 'mcp_generator') {
      // No Preview button here on purpose -- its previewUrl is a raw MCP
      // protocol endpoint (see MCPGenerator/mcp_config.py's project_url),
      // not a browsable page, so embedding it would just show a broken/
      // meaningless iframe rather than anything useful.
      const data: McpGeneratorNodeData = {
        projectName: n.projectName, mcpInstructions: n.mcpInstructions, onChange, onDelete, onContinue,
      }
      return { id: n.id, type: 'mcp_generator', position: n.position, data }
    }
    const data: AgentNodeData = {
      agent: n.agent, libraryItemId: n.libraryItemId, url: n.url, question: n.question, prompt: n.prompt,
      videoVoice: n.videoVoice, videoSplit: n.videoSplit, onChange, onDelete, onPreview,
    }
    return { id: n.id, type: 'agent', position: n.position, data }
  }, [updateNodeData, deleteNode, continueNode, onPreview])

  // Loads the requested workflow (if any) exactly once on mount -- the
  // parent remounts this whole page with a fresh `key` whenever the
  // selected workflow changes, so there's no separate "switch" case to
  // handle here.
  useEffect(() => {
    if (!workflowId) return
    getWorkflow(workflowId).then((def) => {
      if ('error' in def) { setStatus({ text: def.error, error: true }); setLoading(false); return }
      setName(def.name)
      setNodes(def.nodes.map(wireNode))
      setEdges(def.edges.map((e) => ({ id: e.id, source: e.source, target: e.target })))
      setLoading(false)

      // Reattach to whatever run is already in progress for this workflow --
      // without this, any remount (re-selecting the same workflow from the
      // sidebar, a page reload) loses all connection to a run that's still
      // actually going on the backend, and just shows the pristine
      // never-run definition instead.
      getLatestWorkflowRun(workflowId).then((latest) => {
        if ('error' in latest || latest.run_id === null) return
        runIdRef.current = latest.run_id
        applyRunStatus(latest)
        if (latest.run_status === 'running' || latest.run_status === 'paused') {
          setRunning(true)
          pollRef.current = setInterval(pollRunStatus, 2000)
          const label = currentNodeLabel(latest.current_node_id)
          setStatus({
            text: latest.run_status === 'paused'
              ? 'Paused for review — click "Continue" on the waiting node when ready.'
              : `Running workflow...${label ? ` (${label})` : ''}`,
          })
        } else if (latest.run_status === 'complete') {
          setStatus({ text: 'Run complete.' })
        } else if (latest.run_status === 'error') {
          setStatus({ text: 'Run failed — see the node for details.', error: true })
        }
      })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const onConnect = useCallback((connection: Connection) => setEdges((eds) => addEdge(connection, eds)), [setEdges])

  function onDragOver(e: React.DragEvent) { e.preventDefault() }
  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    const agent = e.dataTransfer.getData('application/agent') as Agent | PipelineAgent
    if (!agent) return
    const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
    const id = `node_${++nodeCounter}_${Date.now()}`
    setNodes((nds) => [...nds, wireNode({ id, agent, position })])
  }

  async function handleSave(silent = false): Promise<string> {
    const def = await saveWorkflow({
      workflow_id: workflowId ?? undefined, name,
      nodes: nodes.map((n) => {
        const agent: Agent | PipelineAgent = n.data.agent ?? (
          n.type === 'forge' ? 'product_forge'
          : n.type === 'webapi_generator' ? 'webapi_generator'
          : n.type === 'mcp_generator' ? 'mcp_generator'
          : 'webui_generator'
        )
        return {
          id: n.id, agent, label: labelFor(agent), position: n.position,
          libraryItemId: n.data.libraryItemId, url: n.data.url, question: n.data.question, prompt: n.data.prompt,
          videoVoice: n.data.videoVoice, videoSplit: n.data.videoSplit,
          productIdea: n.data.productIdea, draftMode: n.data.draftMode, artifactStages: n.data.artifactStages,
          projectName: n.data.projectName, apiLanguage: n.data.apiLanguage, apiAuthType: n.data.apiAuthType,
          mcpInstructions: n.data.mcpInstructions,
        }
      }),
      edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
    })
    if (!silent) setStatus({ text: 'Workflow saved.' })
    onSaved(def.workflow_id)
    return def.workflow_id
  }

  function applyRunStatus(runStatus: WorkflowRunStatus) {
    setNodes((nds) => nds.map((n) => {
      const ns = runStatus.nodes.find((x) => x.node_id === n.id)
      if (!ns) return n
      return {
        ...n,
        data: {
          ...n.data,
          runStatus: ns.status,
          runSummary: ns.summary ?? undefined,
          runLog: ns.log,
          runDownload: ns.extra?.download,
          runDownloads: ns.extra?.downloads,
          previewUrl: ns.extra?.preview_url,
        },
      }
    }))
  }

  // Names which node is actually running right now, so the top status line
  // can say "Running workflow... (Video Creator)" instead of a static
  // "Running workflow..." that gives no sense of progress or of whether
  // it's stuck -- looked up from the canvas's own nodes (agent/type never
  // change mid-run) rather than needing the backend to resend it.
  function currentNodeLabel(currentNodeId: string | null): string | null {
    if (!currentNodeId) return null
    const n = nodes.find((x) => x.id === currentNodeId)
    if (!n) return null
    const agent: Agent | PipelineAgent | undefined = n.data.agent ?? (
      n.type === 'forge' ? 'product_forge'
        : n.type === 'webapi_generator' ? 'webapi_generator'
        : n.type === 'mcp_generator' ? 'mcp_generator'
        : n.type === 'webui_generator' ? 'webui_generator'
        : undefined
    )
    return agent ? labelFor(agent) : null
  }

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    setRunning(false)
  }

  async function pollRunStatus() {
    if (!workflowId || !runIdRef.current) return
    const runStatus = await getWorkflowRunStatus(workflowId, runIdRef.current)
    if ('error' in runStatus) { stopPolling(); setStatus({ text: runStatus.error, error: true }); return }
    applyRunStatus(runStatus)
    if (runStatus.run_status === 'paused') {
      setStatus({ text: 'Paused for review — click "Continue" on the waiting node when ready.' })
    } else if (runStatus.run_status === 'complete') {
      stopPolling()
      setStatus({ text: 'Run complete.' })
    } else if (runStatus.run_status === 'error') {
      stopPolling()
      setStatus({ text: 'Run failed — see the node for details.', error: true })
    } else {
      const label = currentNodeLabel(runStatus.current_node_id)
      setStatus({ text: `Running workflow...${label ? ` (${label})` : ''}` })
    }
  }

  function validateNodes(): string | null {
    for (const n of nodes) {
      if (n.type === 'forge') {
        if (!n.data.projectName?.trim()) return 'Every Product Forge node needs a project name before running.'
        if (!n.data.productIdea?.trim()) return 'Every Product Forge node needs a product idea before running.'
      }
      if (n.type === 'webui_generator' && !n.data.projectName?.trim()) {
        return 'Every Web UI Generator node needs a project name before running.'
      }
      if (n.type === 'webapi_generator' && !n.data.projectName?.trim()) {
        return 'Every Web API Generator node needs a project name before running.'
      }
      if (n.type === 'mcp_generator') {
        if (!n.data.projectName?.trim()) return 'Every MCP Generator node needs a project name before running.'
        if (!n.data.mcpInstructions?.trim()) {
          return 'Every MCP Generator node needs instructions stating its exact database/API source before running.'
        }
      }
    }
    return null
  }

  async function handleRun() {
    const validationError = validateNodes()
    if (validationError) { setStatus({ text: validationError, error: true }); return }
    setRunning(true)
    setStatus({ text: 'Saving workflow...' })
    // Run always saves first -- otherwise Run would execute whatever was
    // last saved to disk, silently ignoring anything typed since (a new
    // question, a changed prompt, a freshly attached file) unless the user
    // remembered to click Save first. This is what makes Run alone
    // sufficient: combined with the backend re-asking pdf_parser's question
    // fresh on every run (see server.py's _reanswer_pdf_item), whatever's
    // currently on the canvas is exactly what gets run, every time.
    const runningWorkflowId = await handleSave(true)
    setNodes((nds) => nds.map((n) => ({
      ...n, data: {
        ...n.data, runStatus: 'pending', runSummary: undefined, runLog: undefined,
        runDownload: undefined, runDownloads: undefined, previewUrl: undefined,
      },
    })))
    setStatus({ text: 'Starting workflow run...' })
    const started = await startWorkflowRun(runningWorkflowId, autoMode)
    if ('error' in started) { setRunning(false); setStatus({ text: started.error, error: true }); return }
    runIdRef.current = started.run_id
    pollRef.current = setInterval(pollRunStatus, 2000)
    pollRunStatus()
  }

  if (loading) return null

  return (
    <div className="flex flex-1 min-h-0 flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-slate-200 bg-white px-4 py-2">
        <input value={name} onChange={(e) => setName(e.target.value)}
               className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-800 outline-none focus:border-indigo-500" />
        {workflowId && (
          <button onClick={onNew} title="Close this workflow"
                  className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
            <X size={14} /> Close
          </button>
        )}
        <button onClick={onNew}
                className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
          <Plus size={14} /> New
        </button>
        <button onClick={() => handleSave()}
                className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
          <Save size={14} /> Save
        </button>
        <button onClick={handleRun} disabled={running}
                className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
          <Play size={14} /> Run
        </button>
        <label title='Off = pause for review after every step (HITL). On = run straight through (HOTL).'
               className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600">
          <Zap size={14} className={autoMode ? 'text-amber-500' : 'text-slate-400'} />
          Auto Mode
          <input type="checkbox" checked={autoMode} disabled={running}
                 onChange={(e) => onAutoModeChange(e.target.checked)} />
        </label>
        {status && <span className={`ml-2 text-sm ${status.error ? 'text-red-500' : 'text-slate-500 italic'}`}>{status.text}</span>}
        <ContentModelPicker />
      </div>

      <RightPreviewPanel
        artifact={preview}
        onClose={() => setPreview(null)}
        main={
          <div ref={wrapperRef} className="flex-1 bg-slate-50" onDragOver={onDragOver} onDrop={onDrop}>
            <ReactFlow
              nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              onConnect={onConnect} nodeTypes={nodeTypes} fitView colorMode="light"
            >
              <Background />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
          </div>
        }
      />
    </div>
  )
}
