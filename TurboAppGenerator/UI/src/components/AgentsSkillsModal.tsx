/**
 * AgentsSkillsModal — read-only reference panel listing the generation
 * pipeline's agents and available pre-built UI skills.
 *
 * Data comes from /api/pipeline-info, which reads directly from
 * orchestrator.STAGES and skills.registry.SKILL_REGISTRY — this is a
 * display-only view, not a separate source of truth.
 */
import { useEffect, useState } from 'react'
import { Bot, Blocks, X, Loader2 } from 'lucide-react'
import { api } from '../hooks/useApi'
import { PipelineInfo } from '../types'

function titleCase(id: string): string {
  return id.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ')
}

export default function AgentsSkillsModal({ onClose }: { onClose: () => void }) {
  const [info, setInfo] = useState<PipelineInfo | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.getPipelineInfo().then(setInfo).catch(e => setError(e.message || 'Failed to load'))
  }, [])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-[720px] max-w-[95vw] h-[80vh] flex flex-col bg-white border border-slate-200 rounded-xl shadow-2xl">

        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 flex-shrink-0">
          <Bot size={14} className="text-indigo-600 flex-shrink-0" />
          <span className="text-sm font-semibold text-slate-800 flex-1">Agents &amp; Skills</span>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-700 transition-colors p-1 rounded">
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4">
          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
          )}
          {!info && !error && (
            <div className="flex items-center justify-center gap-2 text-slate-400 text-sm py-10">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          )}

          {info && (
            <>
              {/* Agents */}
              <div className="mb-6">
                <div className="flex items-center gap-1.5 mb-2">
                  <Bot size={12} className="text-indigo-500" />
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    Pipeline Agents ({info.agents.length})
                  </span>
                </div>
                <div className="space-y-2">
                  {info.agents.map(a => (
                    <div key={a.id} className="rounded-lg border border-slate-200 px-3 py-2.5">
                      <div className="text-sm font-medium text-slate-800">{titleCase(a.id)}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{a.description}</div>
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {a.stages.map(s => (
                          <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 font-medium">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Skills */}
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Blocks size={12} className="text-emerald-500" />
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    UI Skills ({info.skills.length})
                  </span>
                  <span className="text-[10px] text-slate-400">— pre-built templates the pipeline reuses when a page matches</span>
                </div>
                <div className="space-y-2">
                  {info.skills.map(s => (
                    <div key={s.key} className="rounded-lg border border-slate-200 px-3 py-2.5">
                      <div className="text-sm font-medium text-slate-800 font-mono">{s.key}</div>
                      <div className="text-xs text-slate-500 mt-0.5">{s.description}</div>
                      {s.categories.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {s.categories.map(c => (
                            <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600 font-medium">
                              {c}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
