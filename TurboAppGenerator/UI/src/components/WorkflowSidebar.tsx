import { useEffect, useState } from 'react'
import { Trash2, Hammer, Zap, Server, Plug, LucideIcon } from 'lucide-react'
import { Agent, READER_AGENTS, CREATOR_AGENTS } from '../hooks/contentAgentsApi'
import { PipelineAgent, WorkflowDefinition, listWorkflows, deleteWorkflow } from '../hooks/workflowApi'
import { AgentTileContent } from './ContentAgentsSidebar'
import ConfirmDialog from './ConfirmDialog'

const PIPELINE_AGENTS: PipelineAgent[] = ['product_forge', 'webui_generator', 'webapi_generator', 'mcp_generator']
const PIPELINE_META: Record<PipelineAgent, { label: string; icon: LucideIcon }> = {
  product_forge: { label: 'Product Forge', icon: Hammer },
  webui_generator: { label: 'Web UI Generator', icon: Zap },
  webapi_generator: { label: 'Web API Generator', icon: Server },
  mcp_generator: { label: 'MCP Generator', icon: Plug },
}

interface Props {
  activeWorkflowId: string | null
  onSelect: (id: string) => void
  onNew: () => void
}

export default function WorkflowSidebar({ activeWorkflowId, onSelect, onNew }: Props) {
  const [saved, setSaved] = useState<WorkflowDefinition[]>([])
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const refresh = () => { listWorkflows().then((d) => setSaved(d.workflows)).catch(() => {}) }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [])

  function requestDelete(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    setConfirmDeleteId(id)
  }

  async function handleDelete(id: string) {
    setConfirmDeleteId(null)
    await deleteWorkflow(id)
    if (activeWorkflowId === id) onNew()
    refresh()
  }

  return (
    <>
    <aside className="w-56 h-full flex-shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">
      <div className="px-3 pt-3 pb-1 flex-shrink-0">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
          Workflow
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        <p className="mb-1.5 mt-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Readers / Parsers</p>
        <div className="grid grid-cols-2 gap-1.5">
          {READER_AGENTS.map((a) => <PaletteTile key={a} agent={a} />)}
        </div>

        <p className="mb-1.5 mt-4 px-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Creators</p>
        <div className="grid grid-cols-2 gap-1.5">
          {CREATOR_AGENTS.map((a) => <PaletteTile key={a} agent={a} />)}
        </div>

        <p className="mb-1.5 mt-4 px-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Cross-App Pipeline</p>
        <div className="grid grid-cols-2 gap-1.5">
          {PIPELINE_AGENTS.map((a) => <PipelinePaletteTile key={a} agent={a} />)}
        </div>

        <p className="mb-1 mt-5 px-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Saved workflows</p>
        {saved.length === 0 && <p className="px-2 text-xs text-slate-400">None yet.</p>}
        {saved.map((wf) => {
          const isActive = activeWorkflowId === wf.workflow_id
          return (
            <div
              key={wf.workflow_id}
              onClick={() => onSelect(wf.workflow_id)}
              style={isActive ? { boxShadow: 'inset 2px 0 0 #4f46e5' } : undefined}
              className={`mb-0.5 flex items-center gap-1 rounded-md px-2 py-1.5 cursor-pointer transition-colors ${
                isActive ? 'bg-indigo-50' : 'hover:bg-slate-100'
              }`}
            >
              <span className={`flex-1 truncate text-xs ${isActive ? 'text-indigo-700 font-medium' : 'text-slate-600'}`}>{wf.name}</span>
              <button onClick={(e) => requestDelete(wf.workflow_id, e)} className="text-slate-400 hover:text-red-500">
                <Trash2 size={12} />
              </button>
            </div>
          )
        })}
      </div>
    </aside>

    <ConfirmDialog
      open={!!confirmDeleteId}
      title={`Delete "${saved.find((wf) => wf.workflow_id === confirmDeleteId)?.name ?? ''}"?`}
      message="This workflow and all its saved runs will be permanently removed."
      details={['This cannot be undone.']}
      confirmLabel="Delete"
      danger
      onConfirm={() => confirmDeleteId && handleDelete(confirmDeleteId)}
      onCancel={() => setConfirmDeleteId(null)}
    />
    </>
  )
}

// Same Visio-stencil tile look as ContentAgentsSidebar's picker, just
// draggable onto the canvas instead of clickable.
function PaletteTile({ agent }: { agent: Agent }) {
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData('application/agent', agent)}
      className="flex cursor-grab flex-col items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-1.5 py-3 text-center shadow-sm transition-colors active:cursor-grabbing hover:border-indigo-300"
    >
      <AgentTileContent agent={agent} />
    </div>
  )
}

function PipelinePaletteTile({ agent }: { agent: PipelineAgent }) {
  const { label, icon: Icon } = PIPELINE_META[agent]
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData('application/agent', agent)}
      className="flex cursor-grab flex-col items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-1.5 py-3 text-center shadow-sm transition-colors active:cursor-grabbing hover:border-indigo-300"
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-50">
        <Icon size={18} className="text-rose-500" />
      </div>
      <span className="text-[11px] leading-tight text-slate-600">{label}</span>
    </div>
  )
}
