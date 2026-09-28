import { Check } from 'lucide-react'

// Both generators' orchestrators emit a "crew:Stage N/M — <detail>" line at
// the start of every top-level pipeline stage (WebUIGenerator/agents/
// orchestrator.py, WebAPIGenerator/api_agents/api_orchestrator.py) — this is
// the one place that parses it into structured stage info instead of letting
// it fall through to the generic log-line stripping.
export interface CrewStageInfo {
  current: number
  total: number
  detail: string
}

export function parseCrewStage(line: string): CrewStageInfo | null {
  const m = line.match(/^crew:Stage (\d+)\/(\d+)\s*[-—]\s*(.*)$/)
  if (!m) return null
  return { current: Number(m[1]), total: Number(m[2]), detail: m[3].trim() }
}

interface Props {
  /** Ordered display names for stage 1..N. A missing entry falls back to "Stage N". */
  names: string[]
  stageInfo: CrewStageInfo | null
  /** True once the whole pipeline has finished — marks every stage complete regardless of stageInfo. */
  done?: boolean
}

export default function StageProgress({ names, stageInfo, done = false }: Props) {
  const total = stageInfo?.total ?? names.length
  const current = stageInfo?.current ?? 0 // 0 = nothing reported yet

  if (total === 0) return null

  return (
    <div className="space-y-2">
      {Array.from({ length: total }, (_, i) => {
        const n = i + 1
        const complete = done || n < current
        const running = !done && n === current
        const label = names[i] || `Stage ${n}`
        return (
          <div key={n} className="flex items-start gap-2">
            {complete ? (
              <Check size={14} className="text-emerald-500 flex-shrink-0 mt-0.5" />
            ) : running ? (
              <span className="w-3.5 h-3.5 rounded-full bg-indigo-500 animate-pulse flex-shrink-0 mt-0.5" />
            ) : (
              <span className="w-3.5 h-3.5 rounded-full border-2 border-slate-300 flex-shrink-0 mt-0.5" />
            )}
            <span className={`text-xs ${
              complete ? 'text-emerald-700 font-medium' : running ? 'text-indigo-700 font-medium' : 'text-slate-400'
            }`}>
              {label}
              {running && stageInfo?.detail && (
                <span className="block text-slate-500 font-normal italic">{stageInfo.detail}</span>
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}
