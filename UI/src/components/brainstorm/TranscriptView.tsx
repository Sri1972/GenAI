import { ArrowLeft } from 'lucide-react'
import { MeetingDetail, RoundtablePersona } from '../../hooks/useApi'
import { AGREED_DOT } from './personaColor'

type PMap = Record<string, RoundtablePersona>

function label(who: string, pmap: PMap): { name: string; role: string } {
  if (who === 'chair') return { name: 'Facilitator', role: 'keeping time' }
  if (who === 'you') return { name: 'You', role: '' }
  const p = pmap[who]
  return { name: p?.name ?? who.charAt(0).toUpperCase() + who.slice(1), role: p?.role ?? '' }
}

export default function TranscriptView({ detail, pmap, onBack }: {
  detail: MeetingDetail; pmap: PMap; onBack: () => void
}) {
  return (
    <div className="rt h-full min-h-0 flex flex-col">
      <div className="flex items-center gap-2" style={{ padding: '16px 30px 0' }}>
        <button onClick={onBack} className="p-1.5 rounded-lg hover:bg-black/5" style={{ color: 'var(--rt-ink2)' }}><ArrowLeft size={16} /></button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="rt-serif" style={{ fontSize: 22, lineHeight: 1.2, letterSpacing: '-0.01em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{detail.topic || 'Meeting'}</div>
        </div>
        <span style={{ fontSize: 11.5, fontWeight: 600, padding: '3px 9px', borderRadius: 99,
          background: detail.complete ? 'oklch(0.94 0.04 155)' : 'oklch(0.94 0.02 85)',
          color: detail.complete ? 'oklch(0.4 0.1 155)' : 'var(--rt-ink3)' }}>
          {detail.complete ? 'Completed' : 'Unfinished'}
        </span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto" style={{ padding: '12px 30px 40px' }}>
        <div style={{ maxWidth: 680, margin: '0 auto' }}>
          {/* Recap first, if the meeting reached one */}
          {detail.recap && (
            <div style={{ background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 13, padding: 20, marginBottom: 24 }}>
              <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>Decision</div>
              <div className="rt-serif" style={{ fontSize: 22, lineHeight: 1.2, margin: '6px 0 8px' }}>{detail.recap.headline}</div>
              {detail.recap.sections && detail.recap.sections.length > 0 ? (
                detail.recap.sections.filter(s => (s.items || []).length > 0).map((s, i) => (
                  <div key={i} style={{ marginTop: i ? 12 : 4 }}>
                    <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--rt-ink3)' }}>{s.bucket}</div>
                    {s.items.map((it, k) => <div key={k} style={{ fontSize: 13.5, lineHeight: 1.5, marginTop: 3 }}>• {it}</div>)}
                  </div>
                ))
              ) : (
                <div style={{ fontSize: 15, lineHeight: 1.5 }}>{detail.recap.decision}</div>
              )}
              {detail.recap.still_open?.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>Still open</div>
                  {detail.recap.still_open.map((o, i) => <div key={i} style={{ fontSize: 13.5, lineHeight: 1.5, marginTop: 4 }}>• {o}</div>)}
                </div>
              )}
            </div>
          )}

          {detail.usage && detail.usage.totals.cost_usd > 0 && (
            <div className="rt-tnum" style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', alignItems: 'baseline', fontSize: 12.5, color: 'var(--rt-ink3)', background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 12, padding: '12px 16px', marginBottom: 20 }}>
              <span style={{ fontWeight: 600, color: 'var(--rt-ink)' }}>Cost ${detail.usage.totals.cost_usd.toFixed(detail.usage.totals.cost_usd < 0.01 ? 4 : 2)}</span>
              <span>{Math.round((detail.usage.totals.input_tokens + detail.usage.totals.output_tokens) / 1000)}k tokens</span>
              <span style={{ color: 'var(--rt-ink2)' }}>{detail.usage.by_model.map(m => (m.model || '—').replace(/^claude-/, '').split('-').slice(0, 2).join(' ')).join(' · ')}</span>
            </div>
          )}

          {detail.turns.length === 0 && <p style={{ fontSize: 13.5, color: 'var(--rt-ink3)' }}>No turns were recorded for this meeting.</p>}

          {detail.turns.map((t, i) => {
            const isChair = t.who === 'chair'
            const { name, role } = label(t.who, pmap)
            return (
              <div key={i} style={{ padding: '16px 0', opacity: isChair ? 0.6 : 1 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em', color: isChair ? 'var(--rt-chair)' : 'var(--rt-ink)' }}>{name}</span>
                  {role && <span style={{ fontSize: 12.5, color: 'var(--rt-ink3)' }}>{role}</span>}
                  {t.why && <span style={{ fontSize: 12.5, fontStyle: 'italic', color: 'oklch(0.62 0.012 70)' }}>· {t.why}</span>}
                  {t.at && <span className="rt-tnum" style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--rt-faint)' }}>{t.at}</span>}
                </div>
                {t.quote && (
                  <div style={{ borderLeft: '2px solid oklch(0.84 0.04 275)', paddingLeft: 10, margin: '8px 0', fontSize: 13.5, color: 'var(--rt-ink2)' }}>
                    {t.quoteRole ? `${t.quoteRole}: ` : ''}"{t.quote.slice(0, 110)}{t.quote.length > 110 ? '…' : ''}"
                  </div>
                )}
                <div style={{ fontSize: 15.5, lineHeight: 1.62, marginTop: 6, whiteSpace: 'pre-wrap', color: isChair ? 'var(--rt-chair)' : 'var(--rt-ink)' }}>{t.text}</div>
                {t.note && <div style={{ fontSize: 12.5, color: 'oklch(0.6 0.012 70)', marginTop: 6 }}>{t.note}</div>}
              </div>
            )
          })}

          {detail.agreed.length > 0 && (
            <div style={{ marginTop: 24, borderTop: '1px solid var(--rt-divider)', paddingTop: 18 }}>
              <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)', marginBottom: 8 }}>Agreed</div>
              {detail.agreed.map((a, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, marginTop: i ? 10 : 0 }}>
                  <span style={{ width: 6, height: 6, borderRadius: 99, marginTop: 6, flexShrink: 0, background: AGREED_DOT[a.type] || AGREED_DOT.decision }} />
                  <div><div style={{ fontSize: 13.5, lineHeight: 1.5 }}>{a.text}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--rt-ink3)' }}>{a.who}{a.at ? ` · ${a.at}` : ''}</div></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
