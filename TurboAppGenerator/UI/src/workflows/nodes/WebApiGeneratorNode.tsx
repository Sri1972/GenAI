import { Handle, Position, useNodeConnections } from '@xyflow/react'
import { CheckCircle2, XCircle, Loader2, Server, Trash2, ExternalLink, Eye, PlayCircle, Link2 } from 'lucide-react'
import { Artifact } from '../../components/ArtifactPreview'
import ProgressLog from './ProgressLog'

export interface WebApiGeneratorNodeData extends Record<string, unknown> {
  projectName?: string
  apiLanguage?: string
  apiAuthType?: string
  runStatus?: 'ok' | 'error' | 'running' | 'awaiting_review'
  runSummary?: string
  runLog?: string[]
  previewUrl?: string | null
  onChange: (patch: Partial<WebApiGeneratorNodeData>) => void
  onDelete: () => void
  onContinue: () => void
  onPreview: (artifact: Artifact) => void
}

export default function WebApiGeneratorNode({ data }: { data: WebApiGeneratorNodeData }) {
  const incomingConnections = useNodeConnections({ handleType: 'target' })
  const started = data.runStatus !== undefined

  return (
    <div className="w-80 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 rounded-t-xl border-b border-slate-200 bg-emerald-50 px-3 py-2">
        <Server size={15} className="shrink-0 text-emerald-500" />
        <span className="flex-1 truncate text-sm font-medium text-slate-800">Web API Generator</span>
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
            ? 'Connect a Product Forge node'
            : 'Requirements connected'}
        </div>

        <p className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-400">Project name *</p>
        <input
          value={data.projectName ?? ''}
          onChange={(e) => data.onChange({ projectName: e.target.value })}
          placeholder="e.g. oem-dealer-api"
          disabled={started}
          className={`w-full rounded-md border bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-emerald-500 disabled:bg-slate-50 disabled:text-slate-400 ${
            data.projectName?.trim() ? 'border-slate-300' : 'border-red-300'
          }`}
        />

        <div className="mt-2 flex gap-2">
          <label className="flex-1">
            <span className="mb-1 block text-[10px] uppercase tracking-wider text-slate-400">Language</span>
            <select
              value={data.apiLanguage ?? 'python'}
              disabled={started}
              onChange={(e) => data.onChange({ apiLanguage: e.target.value })}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-emerald-500 disabled:bg-slate-50 disabled:text-slate-400"
            >
              <option value="python">Python (FastAPI)</option>
              <option value="java">Java (Spring Boot)</option>
            </select>
          </label>
          <label className="flex-1">
            <span className="mb-1 block text-[10px] uppercase tracking-wider text-slate-400">Auth</span>
            <select
              value={data.apiAuthType ?? 'none'}
              disabled={started}
              onChange={(e) => data.onChange({ apiAuthType: e.target.value })}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-emerald-500 disabled:bg-slate-50 disabled:text-slate-400"
            >
              <option value="none">None</option>
              <option value="basic">Basic Auth</option>
            </select>
          </label>
        </div>

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
          <div className="mt-1 flex items-center gap-3">
            <a href={data.previewUrl} target="_blank" rel="noreferrer"
               className="flex items-center gap-1 text-xs text-emerald-600 hover:underline">
              <ExternalLink size={12} /> Open generated API
            </a>
            <button onClick={() => data.onPreview({ url: data.previewUrl!, title: data.projectName || 'Web API Generator', kind: 'live' })}
                    className="flex items-center gap-1 text-xs text-slate-500 hover:text-emerald-600" title="Preview">
              <Eye size={12} /> Preview
            </button>
          </div>
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
