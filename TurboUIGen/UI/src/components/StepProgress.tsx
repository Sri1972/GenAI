import { Check, Loader2 } from 'lucide-react'
import { GenerateStep } from '../types'

const PIPELINE: { id: string; label: string; figmaOnly?: boolean }[] = [
  { id: 'figma_api',        label: 'Fetching Figma design data',             figmaOnly: true },
  { id: 'screenshot_start', label: 'Exporting Figma frames',                 figmaOnly: true },
  { id: 'llm_codegen',      label: 'LLM building website from frames',       figmaOnly: true },
  { id: 'llm',              label: 'LLM generating project files' },
  { id: 'write',            label: 'Writing files to disk' },
  { id: 'install',          label: 'Running npm install' },
  { id: 'start',            label: 'Starting dev server' },
  { id: 'ready',            label: 'App ready!' },
]

const STEP_MAP: Record<string, string> = {
  figma_api_done:     'figma_api',
  screenshot_done:    'screenshot_start',
  llm_analysis:       'llm_codegen',
  llm_analysis_done:  'llm_codegen',
}

interface Props {
  current: GenerateStep
  log?: string[]
  hasFigma?: boolean
}

export default function StepProgress({ current, log = [], hasFigma = false }: Props) {
  const visibleSteps = PIPELINE.filter(s => {
    if (s.figmaOnly && !hasFigma) return false
    if (s.id === 'llm' && hasFigma) return false
    return true
  })

  const normalised = (current && STEP_MAP[current]) ? STEP_MAP[current] : current
  const idx = visibleSteps.findIndex(s => s.id === normalised)

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {visibleSteps.map((s, i) => {
          const done   = idx > i || current === 'ready'
          const active = idx === i
          return (
            <div key={s.id} className="flex items-center gap-3">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${
                done ? 'bg-emerald-500' : active ? 'bg-indigo-500' : 'bg-slate-200'
              }`}>
                {done
                  ? <Check size={11} className="text-white" />
                  : active
                    ? <Loader2 size={11} className="text-white animate-spin" />
                    : <span className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                }
              </div>
              <span className={`text-xs ${
                done ? 'text-emerald-700' : active ? 'text-indigo-700' : 'text-slate-500'
              }`}>{s.label}</span>
            </div>
          )
        })}
      </div>

      {log.length > 0 && (
        <div className="bg-slate-100 rounded-lg p-2.5 max-h-32 overflow-y-auto space-y-0.5">
          {log.map((line, i) => (
            <div key={i} className="text-xs text-slate-600 font-mono leading-relaxed">
              <span className="text-slate-400 mr-1">›</span>{line}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
