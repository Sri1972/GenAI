import { RoundtablePersona } from '../../hooks/useApi'
import { Recap, DiagramArtifact } from '../../hooks/useRoundtableStream'
import { avatarFill, avatarText, initials } from './personaColor'

type PMap = Record<string, RoundtablePersona>

export default function RecapScreen({ recap, contributions, peopleCount, diagram, drawing, approved, pmap, onRunAgain, onRead, onDraw, onApprove, onBuildApp }: {
  recap: Recap
  contributions: number
  peopleCount: number
  diagram: DiagramArtifact | null
  drawing: boolean
  approved: boolean
  pmap: PMap
  onRunAgain: () => void
  onRead: () => void
  onDraw: () => void
  onApprove: () => void
  onBuildApp?: () => void
}) {
  return (
    <div className="rt h-full overflow-y-auto">
      <div style={{ maxWidth: 640, margin: '0 auto', padding: '64px 32px 90px' }}>
        <div style={{ fontSize: 13.5, color: 'var(--rt-ink3)' }}>
          {contributions} contributions · {peopleCount} colleagues
        </div>
        <h1 className="rt-serif" style={{ fontSize: 38, lineHeight: 1.15, letterSpacing: '-0.02em', marginTop: 10 }}>
          {recap.headline}
        </h1>

        {recap.sections && recap.sections.length > 0 ? (
          <div style={{ marginTop: 30 }}>
            {recap.sections.filter(s => (s.items || []).length > 0).map((s, i) => (
              <div key={i} style={{ marginTop: i ? 24 : 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>{s.bucket}</div>
                <ul style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {s.items.map((it, k) => (
                    <li key={k} style={{ display: 'flex', gap: 8, fontSize: 15, lineHeight: 1.5 }}>
                      <span style={{ color: 'var(--rt-accent)' }}>•</span><span>{it}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ marginTop: 32 }}>
            <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>The decision</div>
            <div style={{ fontSize: 19, lineHeight: 1.5, letterSpacing: '-0.015em', marginTop: 8 }}>{recap.decision}</div>
            <p style={{ fontSize: 15, lineHeight: 1.65, marginTop: 12, color: 'var(--rt-ink)' }}>{recap.argument}</p>
          </div>
        )}

        <div style={{ borderTop: '1px solid var(--rt-divider)', margin: '36px 0' }} />

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>Who's doing what</div>
          <div style={{ marginTop: 14 }}>
            {recap.commitments.map((c, i) => {
              const p = Object.values(pmap).find(x => x.name.toLowerCase() === (c.who || '').toLowerCase())
              const hue = p?.hue ?? 275
              return (
                <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginTop: i ? 18 : 0 }}>
                  <span style={{ width: 32, height: 32, borderRadius: 99, flexShrink: 0, display: 'grid', placeItems: 'center', background: avatarFill(hue), color: avatarText(hue), fontSize: 12, fontWeight: 600 }}>
                    {initials(c.who || '?')}
                  </span>
                  <div>
                    <div style={{ fontSize: 15.5, lineHeight: 1.5 }}>{c.what}</div>
                    <div style={{ fontSize: 12.5, color: 'var(--rt-ink3)', marginTop: 2 }}>{c.who}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--rt-divider)', margin: '36px 0' }} />

        <div>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>Still open</div>
          <div style={{ marginTop: 13 }}>
            {recap.still_open.map((o, i) => (
              <div key={i} style={{ fontSize: 15, lineHeight: 1.6, marginTop: i ? 13 : 0 }}>{o}</div>
            ))}
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--rt-divider)', margin: '36px 0' }} />
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>The diagram</div>
          {diagram ? (
            <>
              <div style={{ fontSize: 12.5, color: 'var(--rt-ink2)', margin: '4px 0 10px' }}>{diagram.detail} — does this match your understanding?</div>
              <iframe src={diagram.url} title="Diagram" style={{ width: '100%', height: 360, border: '1px solid var(--rt-hair)', borderRadius: 12, background: '#fff' }} />
              <div className="flex items-center gap-2" style={{ marginTop: 10 }}>
                <button onClick={onApprove} disabled={approved}
                  style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px', borderRadius: 9, background: approved ? 'oklch(0.94 0.03 155)' : 'var(--rt-accent)', color: approved ? 'oklch(0.4 0.1 155)' : '#fff' }}>
                  {approved ? '✓ Approved — saved to artifacts' : 'Approve'}
                </button>
                <button onClick={onDraw} disabled={drawing}
                  style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px', borderRadius: 9, background: '#fff', border: '1px solid var(--rt-hair)', color: 'var(--rt-ink)' }}>
                  {drawing ? 'Drawing…' : 'Draw again'}
                </button>
                <a href={diagram.url} target="_blank" rel="noopener" style={{ marginLeft: 'auto', fontSize: 13, fontWeight: 600, color: 'var(--rt-accent)' }}>Open full size ↗</a>
              </div>
            </>
          ) : (
            <div style={{ marginTop: 6 }}>
              <p style={{ fontSize: 13.5, color: 'var(--rt-ink2)', lineHeight: 1.5, marginBottom: 10 }}>
                No diagram was drawn — most discussions are prose. Want one anyway to confirm the shape of what was decided?
              </p>
              <button onClick={onDraw} disabled={drawing}
                style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px', borderRadius: 9, background: 'var(--rt-accent)', color: '#fff' }}>
                {drawing ? 'Drawing…' : 'Draw this up'}
              </button>
            </div>
          )}
        </div>

        {onBuildApp && (
          <div style={{ marginTop: 40, background: 'var(--rt-accent-tint)', border: '1px solid oklch(0.72 0.1 275)', borderRadius: 13, padding: 20 }}>
            <div style={{ fontSize: 15, fontWeight: 600 }}>Turn this into an app</div>
            <div style={{ fontSize: 13.5, color: 'var(--rt-ink2)', margin: '4px 0 12px', lineHeight: 1.5 }}>
              Hand this decision to the app builder — it'll open a new prototype in this project, briefed on what the room decided and the files you shared.
            </div>
            <button onClick={onBuildApp} style={{ background: 'var(--rt-accent)', color: '#fff', fontSize: 14, fontWeight: 600, padding: '12px 22px', borderRadius: 11 }}>
              Build an app from this decision →
            </button>
          </div>
        )}

        <div className="flex gap-3" style={{ marginTop: 24 }}>
          <button onClick={onRunAgain} style={{ background: '#fff', border: '1px solid var(--rt-hair)', color: 'var(--rt-ink)', fontSize: 14, fontWeight: 600, padding: '12px 22px', borderRadius: 11 }}>Run it again</button>
          <button onClick={onRead} style={{ background: '#fff', border: '1px solid var(--rt-hair)', color: 'var(--rt-ink)', fontSize: 14, fontWeight: 600, padding: '12px 22px', borderRadius: 11 }}>Read the conversation</button>
        </div>
      </div>
    </div>
  )
}
