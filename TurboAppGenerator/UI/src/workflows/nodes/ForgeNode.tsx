import { Handle, Position } from '@xyflow/react'
import { CheckCircle2, XCircle, Loader2, Hammer, Trash2, PlayCircle, PauseCircle } from 'lucide-react'
import ProgressLog from './ProgressLog'

// Mirrors ProductForge/config/agents.json's pipeline order/names -- see
// FORGE_ARTIFACT_STAGES in ContentAgents/ui/server.py for the backend twin
// of this list. "ideation" is the only non-artifact stage and always runs
// regardless of selection, so it isn't offered here.
export const FORGE_ARTIFACT_STAGES: { id: string; name: string }[] = [
  { id: 'prd', name: 'PRD' },
  { id: 'trd', name: 'TRD' },
  { id: 'design', name: 'Solution Design' },
  { id: 'stories', name: 'Epics & Stories' },
  { id: 'tasks', name: 'Tasks' },
  { id: 'specs', name: 'Specs' },
  { id: 'test_cases', name: 'Test Cases' },
  { id: 'review', name: 'Review' },
]

// The 4 that actually reach a Web UI Generator node (see _combine_forge_artifacts
// in server.py) -- everything else is only ever saved inside Forge itself.
export const DEFAULT_ARTIFACT_STAGES = ['prd', 'trd', 'design', 'specs']

export interface ForgeNodeData extends Record<string, unknown> {
  projectName?: string
  productIdea?: string
  draftMode?: boolean
  artifactStages?: string[]
  runStatus?: 'ok' | 'error' | 'running' | 'awaiting_review'
  runSummary?: string
  runLog?: string[]
  onChange: (patch: Partial<ForgeNodeData>) => void
  onDelete: () => void
  onContinue: () => void
}

export default function ForgeNode({ data }: { data: ForgeNodeData }) {
  const started = data.runStatus !== undefined
  const locked = data.runStatus === 'running' || data.runStatus === 'awaiting_review' || data.runStatus === 'ok'
  const selected = data.artifactStages ?? DEFAULT_ARTIFACT_STAGES

  function toggleStage(id: string) {
    const next = selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]
    data.onChange({ artifactStages: next })
  }

  return (
    <div className="w-80 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 rounded-t-xl border-b border-slate-200 bg-rose-50 px-3 py-2">
        <Hammer size={15} className="shrink-0 text-rose-500" />
        <span className="flex-1 truncate text-sm font-medium text-slate-800">Product Forge</span>
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
        {!locked ? (
          <>
            <p className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-400">Project name *</p>
            <input
              value={data.projectName ?? ''}
              onChange={(e) => data.onChange({ projectName: e.target.value })}
              placeholder="e.g. oem-dealer-portal"
              disabled={started}
              className={`mb-2.5 w-full rounded-md border bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-indigo-500 disabled:bg-slate-50 disabled:text-slate-400 ${
                data.projectName?.trim() ? 'border-slate-300' : 'border-red-300'
              }`}
            />

            <p className="mb-1.5 text-[10px] uppercase tracking-wider text-slate-400">Product idea</p>
            <textarea
              value={data.productIdea ?? ''}
              onChange={(e) => data.onChange({ productIdea: e.target.value })}
              placeholder='e.g. "A to-do app for household chores with reminders and points"'
              rows={3}
              disabled={started}
              className="w-full resize-none rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-indigo-500 disabled:bg-slate-50 disabled:text-slate-400"
            />
            <label className="mt-2 flex items-center gap-1.5 text-xs text-slate-500">
              <input
                type="checkbox"
                checked={!!data.draftMode}
                disabled={started}
                onChange={(e) => data.onChange({ draftMode: e.target.checked })}
              />
              Draft mode (cheaper/faster model, skips critique-refine)
            </label>

            <p className="mb-1 mt-3 text-[10px] uppercase tracking-wider text-slate-400">Artifacts to generate</p>
            <div className="grid grid-cols-2 gap-x-2 gap-y-1">
              {FORGE_ARTIFACT_STAGES.map((stage) => (
                <label key={stage.id} className="flex items-center gap-1.5 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={selected.includes(stage.id)}
                    disabled={started}
                    onChange={() => toggleStage(stage.id)}
                  />
                  {stage.name}
                </label>
              ))}
            </div>
            <p className="mt-1.5 text-[10px] text-slate-400">
              Only PRD / TRD / Design / Specs are forwarded to a connected Web UI Generator — the rest just stay in Forge.
            </p>
          </>
        ) : (
          <>
            <p className="truncate text-xs font-medium text-slate-700" title={data.projectName}>{data.projectName}</p>
            <p className="mt-0.5 truncate text-xs text-slate-500" title={data.productIdea}>{data.productIdea}</p>
            <p className="mt-1 truncate text-[10px] text-slate-400">
              Generating: {selected.map((id) => FORGE_ARTIFACT_STAGES.find((s) => s.id === id)?.name ?? id).join(', ')}
            </p>
          </>
        )}

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
        <ProgressLog log={data.runLog} />
      </div>

      <Handle type="source" position={Position.Right} />
    </div>
  )
}

function StatusIcon({ status }: { status?: string }) {
  if (status === 'running') return <Loader2 size={14} className="ml-auto animate-spin text-slate-400" />
  if (status === 'awaiting_review') return <PauseCircle size={14} className="ml-auto text-amber-500" />
  if (status === 'ok') return <CheckCircle2 size={14} className="ml-auto text-emerald-500" />
  if (status === 'error') return <XCircle size={14} className="ml-auto text-red-500" />
  return null
}
