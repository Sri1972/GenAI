import { CheckCircle2, Lightbulb, Info, ArrowRight } from 'lucide-react'
import { TurboSummary } from '../../utils/turboSummary'

/** The builder's end-of-build summary, rendered as a scannable card. */
export default function SummaryCard({ summary }: { summary: TurboSummary }) {
  const built = summary.built?.filter(Boolean) ?? []
  const assumed = summary.assumed?.filter(Boolean) ?? []
  const next = summary.next?.filter(Boolean) ?? []
  const howToUse = summary.howToUse?.trim()
  if (!built.length && !assumed.length && !next.length && !howToUse) return null

  return (
    <div className="mt-2 rounded-xl border border-violet-200 bg-violet-50/60 overflow-hidden">
      {built.length > 0 && (
        <div className="px-3.5 py-2.5">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-violet-700 mb-1.5">What I built</div>
          <ul className="space-y-1">
            {built.map((b, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" /><span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {howToUse && (
        <div className="px-3.5 py-2.5 border-t border-violet-100 flex items-start gap-2">
          <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
          <div><span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">How to use it </span>
            <span className="text-sm text-slate-700">{howToUse}</span></div>
        </div>
      )}
      {assumed.length > 0 && (
        <div className="px-3.5 py-2.5 border-t border-violet-100">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1">
            <Info className="w-3.5 h-3.5" /> What I assumed
          </div>
          <ul className="space-y-0.5">
            {assumed.map((a, i) => <li key={i} className="text-sm text-slate-600 pl-5">{a}</li>)}
          </ul>
        </div>
      )}
      {next.length > 0 && (
        <div className="px-3.5 py-2.5 border-t border-violet-100">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-violet-700 mb-1">Suggested next</div>
          <ul className="space-y-1">
            {next.map((n, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <ArrowRight className="w-3.5 h-3.5 text-violet-500 mt-0.5 shrink-0" /><span>{n}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
