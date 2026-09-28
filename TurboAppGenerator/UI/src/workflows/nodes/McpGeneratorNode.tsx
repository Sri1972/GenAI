import { Handle, Position, useNodeConnections } from '@xyflow/react'
import { CheckCircle2, XCircle, Loader2, Plug, Trash2, ExternalLink, PlayCircle, Link2 } from 'lucide-react'
import ProgressLog from './ProgressLog'

export interface McpGeneratorNodeData extends Record<string, unknown> {
  projectName?: string
  mcpInstructions?: string
  runStatus?: 'ok' | 'error' | 'running' | 'awaiting_review'
  runSummary?: string
  runLog?: string[]
  previewUrl?: string | null
  onChange: (patch: Partial<McpGeneratorNodeData>) => void
  onDelete: () => void
  onContinue: () => void
}

export default function McpGeneratorNode({ data }: { data: McpGeneratorNodeData }) {
  const incomingConnections = useNodeConnections({ handleType: 'target' })
  const started = data.runStatus !== undefined

  return (
    <div className="w-80 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 rounded-t-xl border-b border-slate-200 bg-amber-50 px-3 py-2">
        <Plug size={15} className="shrink-0 text-amber-500" />
        <span className="flex-1 truncate text-sm font-medium text-slate-800">MCP Generator</span>
        <StatusIcon status={data.runStatus} />
        <button
          onClick={data.onDelete}
          title="Delete this step"
          className="shrink-0 rounded-md p-0.5 text-slate-400 hover:bg-slate-200 hover:text-red-500"
        >
          <Trash2 size={14} />
        </button>
      </div>

      <div className="p-3">
        <div className="mb-1.5 flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-400">
          <Link2 size={11} />
          {incomingConnections.length === 0
            ? 'No sources connected (optional context)'
            : `${incomingConnections.length} source${incomingConnections.length > 1 ? 's' : ''} connected (extra context)`}
        </div>

        <p className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-400">Project name *</p>
        <input
          value={data.projectName ?? ''}
          onChange={(e) => data.onChange({ projectName: e.target.value })}
          placeholder="e.g. auto-forecast-mcp"
          disabled={started}
          className={`w-full rounded-md border bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-amber-500 disabled:bg-slate-50 disabled:text-slate-400 ${
            data.projectName?.trim() ? 'border-slate-300' : 'border-red-300'
          }`}
        />

        <p className="mb-1.5 mt-2 text-[10px] uppercase tracking-wider text-slate-400">
          Instructions * — must state the exact source
        </p>
        <textarea
          value={data.mcpInstructions ?? ''}
          onChange={(e) => data.onChange({ mcpInstructions: e.target.value })}
          placeholder={'e.g. "Build an MCP server for the API at http://127.0.0.1:8400. It uses Basic Auth -- username admin, password ****. Discover its real endpoints yourself."'}
          rows={4}
          disabled={started}
          className={`w-full resize-none rounded-md border bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-amber-500 disabled:bg-slate-50 disabled:text-slate-400 ${
            data.mcpInstructions?.trim() ? 'border-slate-300' : 'border-red-300'
          }`}
        />
        <p className="mt-1.5 text-[10px] text-slate-400">
          Must name an exact database file path and/or API base URL (with credentials if it needs auth) —
          endpoints/tables are discovered automatically, never guessed. Connect a Product Forge node above for
          extra business context; it can't substitute for the source itself.
        </p>

        {data.runStatus === 'awaiting_review' && (
          <button
            onClick={data.onContinue}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg bg-amber-500 px-3 py-2 text-sm font-medium text-white hover:bg-amber-400"
          >
            <PlayCircle size={14} /> Review done — Continue
          </button>
        )}

        {data.runSummary && (
          <p className={`mt-2 text-xs ${data.runStatus === 'error' ? 'text-red-500' : 'text-slate-500'}`}>{data.runSummary}</p>
        )}
        {data.previewUrl && (
          <a href={data.previewUrl} target="_blank" rel="noreferrer"
             className="mt-1 flex items-center gap-1 text-xs text-amber-600 hover:underline">
            <ExternalLink size={12} /> Open MCP server
          </a>
        )}
        <ProgressLog log={data.runLog} />
      </div>

      <Handle type="target" position={Position.Left} />
    </div>
  )
}

function StatusIcon({ status }: { status?: string }) {
  if (status === 'running') return <Loader2 size={14} className="ml-auto animate-spin text-slate-400" />
  if (status === 'ok') return <CheckCircle2 size={14} className="ml-auto text-emerald-500" />
  if (status === 'error') return <XCircle size={14} className="ml-auto text-red-500" />
  return null
}
