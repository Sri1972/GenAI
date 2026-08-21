import { useEffect, useRef, useState } from 'react'
import { RoundtablePersona } from '../../hooks/useApi'
import { RoundtableState, Usage } from '../../hooks/useRoundtableStream'
import { avatarFill, avatarText, initials, hueFor, AGREED_DOT } from './personaColor'

interface Actions {
  interject: (text: string, target?: string) => void
  hold: (paused: boolean) => void
  wrapUp: () => void
  drawDiagram: () => void
  approveDiagram: () => void
  continueMeeting: () => void
}

type PMap = Record<string, RoundtablePersona>

function fmt(sec: number) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function tok(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}k`
  return `${n}`
}
function usd(n: number) {
  if (n === 0) return '$0.00'
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
}
// Strip the provider/version noise so a model badge reads "Sonnet", "Haiku", etc.
function modelShort(m: string) {
  if (!m || m === '—') return 'default'
  const s = m.toLowerCase()
  for (const k of ['opus', 'sonnet', 'haiku', 'fable']) if (s.includes(k)) return k[0].toUpperCase() + k.slice(1)
  return m.replace(/^claude-/, '').split('-').slice(0, 2).join(' ')
}

export default function RoomScreen({ st, actions, pmap, seats, topic, duration }: {
  st: RoundtableState; actions: Actions; pmap: PMap; seats: string[]; topic: string; duration: number
}) {
  const [elapsed, setElapsed] = useState(0)
  const [detail, setDetail] = useState<number | null>(null)
  const [input, setInput] = useState('')
  const [target, setTarget] = useState('all')
  const [focused, setFocused] = useState(false)
  const [showUsage, setShowUsage] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const totalSec = (duration === 12 ? 12 : duration) * 60

  // cosmetic client-side clock: advances while running and not paused
  useEffect(() => {
    if (!st.running || st.paused) return
    const t = setInterval(() => setElapsed(e => Math.min(totalSec, e + 1)), 1000)
    return () => clearInterval(t)
  }, [st.running, st.paused, totalSec])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [st.turns, st.speaking])

  const cycleTarget = () => {
    const order = ['all', ...seats]
    setTarget(t => order[(order.indexOf(t) + 1) % order.length])
  }
  const targetLabel = target === 'all' ? 'to everyone' : `to ${pmap[target]?.name ?? target}`

  const onFocus = () => { setFocused(true); actions.hold(true) }
  const onBlur = () => { if (!input.trim()) { setFocused(false); actions.hold(false) } }
  const send = () => {
    if (!input.trim()) return
    actions.interject(input.trim(), target)
    setInput(''); setFocused(false)
  }

  const pct = Math.min(1, elapsed / totalSec)

  return (
    <div className="rt h-full min-h-0 flex">
      {/* LEFT: the room */}
      <div className="flex-1 min-w-0 min-h-0 flex flex-col">
        {/* header */}
        <div className="flex items-center gap-3" style={{ padding: '16px 30px 0' }}>
          <div style={{ flex: 1, fontSize: 13.5, color: 'var(--rt-ink2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{topic}</div>
          <div className="flex items-center gap-2 rt-tnum" style={{ fontSize: 13.5, color: 'var(--rt-ink2)' }}>
            <span style={{
              width: 22, height: 22, borderRadius: 99,
              background: `conic-gradient(var(--rt-accent) ${pct * 360}deg, oklch(0.92 0.01 85) 0)`,
            }} />
            {fmt(elapsed)} of {duration === 12 ? 10 : duration} min
          </div>
          {st.round && (
            <span style={{ fontSize: 12, fontWeight: 600, padding: '4px 10px', borderRadius: 99,
              background: 'oklch(0.95 0.03 275)', color: 'oklch(0.45 0.12 275)' }}>
              Round {st.round.n} of {st.round.of}
            </span>
          )}
          {st.usage && (
            <div style={{ position: 'relative' }}>
              <button onClick={() => setShowUsage(v => !v)} title="Model, tokens & cost for this meeting"
                className="rt-tnum" style={{
                  display: 'flex', alignItems: 'center', gap: 7, fontSize: 12.5, padding: '5px 10px',
                  borderRadius: 8, border: '1px solid var(--rt-hair)', background: showUsage ? 'var(--rt-accent-tint)' : '#fff',
                  color: 'var(--rt-ink2)', cursor: 'pointer',
                }}>
                <span style={{ fontWeight: 600, color: 'var(--rt-ink)' }}>{usd(st.usage.totals.cost_usd)}</span>
                <span style={{ color: 'var(--rt-ink3)' }}>·</span>
                <span>{tok(st.usage.totals.input_tokens + st.usage.totals.output_tokens)} tok</span>
              </button>
              {showUsage && <UsagePanel usage={st.usage} onClose={() => setShowUsage(false)} />}
            </div>
          )}
          <button onClick={() => actions.hold(!st.paused)} style={btn(false)}>{st.paused ? 'Carry on' : 'Hold it'}</button>
          <button onClick={actions.wrapUp} style={btn(true)}>Wrap up</button>
        </div>

        {/* table */}
        <div className="flex justify-center flex-wrap" style={{ gap: 30, padding: '22px 30px 20px' }}>
          {['chair', ...seats].map(id => {
            const p = pmap[id]
            const hue = hueFor(id)
            const speaking = st.speaking === id
            const hasSpoken = st.spoken.includes(id)
            const opacity = speaking ? 1 : hasSpoken ? 0.72 : id === 'chair' ? 0.85 : 0.45
            return (
              <div key={id} className="text-center" style={{ width: 96, opacity, transition: 'opacity .35s', cursor: id !== 'chair' && st.running ? 'pointer' : 'default' }}
                   onClick={() => { if (id !== 'chair' && st.running) setTarget(id) }}>
                <div style={{ position: 'relative', width: 62, height: 62, margin: '0 auto' }}>
                  {speaking && <div className="rt-breathe" style={{ position: 'absolute', inset: 0, borderRadius: 99, background: 'var(--rt-accent)' }} />}
                  <div style={{
                    position: 'relative', width: 50, height: 50, margin: '6px auto', borderRadius: 99, display: 'grid', placeItems: 'center',
                    background: avatarFill(hue), color: avatarText(hue), fontSize: 16, fontWeight: 600,
                    border: `2px solid ${speaking ? 'var(--rt-accent)' : hasSpoken ? 'oklch(0.86 0.05 275)' : 'transparent'}`,
                    transform: speaking ? 'scale(1.06)' : 'none', transition: 'transform .35s',
                  }}>{initials(p?.name ?? (id === 'chair' ? 'Facilitator' : id))}</div>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em' }}>{p?.name ?? (id === 'chair' ? 'Facilitator' : id)}</div>
                <div style={{ fontSize: 11.5, color: 'var(--rt-ink3)' }}>{p?.role ?? (id === 'chair' ? 'Keeping time' : '')}</div>
              </div>
            )
          })}
        </div>

        {/* transcript */}
        <div className="flex-1 min-h-0 overflow-y-auto" style={{ padding: '8px 30px 20px' }}>
          <div style={{ maxWidth: 680, margin: '0 auto' }}>
            {st.turns.map((t, i) => {
              const latest = i === st.turns.length - 1
              const isChair = t.who === 'chair'
              const isYou = t.who === 'you'
              const p = pmap[t.who]
              const name = isChair ? 'Facilitator' : isYou ? 'You' : p?.name ?? t.who
              const role = isChair ? 'keeping time' : isYou ? '' : p?.role ?? ''
              const bodySize = latest ? 17.5 : 15.5
              const opacity = isChair ? 0.5 : latest ? 1 : 0.62
              return (
                <div key={i} className="rt-rise" style={{ padding: '18px 0', opacity }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: latest ? 16.5 : 15, fontWeight: 600, letterSpacing: '-0.01em', color: isChair ? 'var(--rt-chair)' : 'var(--rt-ink)' }}>{name}</span>
                    {role && <span style={{ fontSize: 12.5, color: 'var(--rt-ink3)' }}>{role}</span>}
                    {t.why && <span style={{ fontSize: 12.5, fontStyle: 'italic', color: 'oklch(0.62 0.012 70)' }}>· {t.why}</span>}
                    {t.at && <span className="rt-tnum" style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--rt-faint)' }}>{t.at}</span>}
                  </div>
                  {t.quote && (
                    <div style={{ borderLeft: '2px solid oklch(0.84 0.04 275)', paddingLeft: 10, margin: '8px 0', fontSize: 13.5, color: 'var(--rt-ink2)' }}>
                      {t.quoteRole ? `${t.quoteRole}: ` : ''}"{t.quote.slice(0, 110)}{t.quote.length > 110 ? '…' : ''}"
                    </div>
                  )}
                  <div style={{ fontSize: bodySize, lineHeight: 1.62, marginTop: 6, color: isChair ? 'var(--rt-chair)' : 'var(--rt-ink)', textWrap: 'pretty' } as any}>{t.text}</div>
                  {(t.note || t.thinking || (t.sources && t.sources.length > 0)) && (
                    <div className="flex items-center flex-wrap" style={{ gap: 16, marginTop: 8 }}>
                      {t.note && <span style={{ fontSize: 12.5, color: 'oklch(0.6 0.012 70)' }}>{t.note}</span>}
                      {(t.thinking || (t.sources && t.sources.length > 0)) && (
                        <button onClick={() => setDetail(detail === i ? null : i)} style={{ fontSize: 12.5, fontWeight: 600, color: 'oklch(0.55 0.09 275)' }}>
                          {detail === i ? 'Hide' : 'Why they said that'}
                        </button>
                      )}
                    </div>
                  )}
                  {detail === i && (
                    <div className="rt-rise" style={{ background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 12, padding: '15px 17px', marginTop: 10 }}>
                      {t.thinking && <>
                        <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--rt-ink3)' }}>What was going through their mind</div>
                        <div style={{ fontSize: 13.5, lineHeight: 1.6, marginTop: 4 }}>{t.thinking}</div>
                      </>}
                      {t.sources && t.sources.length > 0 && <>
                        <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--rt-ink3)', marginTop: t.thinking ? 12 : 0 }}>What they looked at</div>
                        <ul style={{ fontSize: 13, marginTop: 4, paddingLeft: 16, listStyle: 'disc' }}>
                          {t.sources.map((s, k) => <li key={k}>{s}</li>)}
                        </ul>
                      </>}
                    </div>
                  )}
                </div>
              )
            })}
            {st.preparing && st.preparing.length > 0 && (
              <div style={{ padding: '14px 0 40px' }}>
                <div style={{ fontSize: 11.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--rt-ink3)', marginBottom: 12 }}>
                  Doing their homework
                </div>
                <div style={{ display: 'grid', gap: 10 }}>
                  {st.preparing.map(id => {
                    const done = st.prepared.includes(id)
                    const line = st.activity[id]
                    const hue = hueFor(id)
                    const buckets = st.prepBuckets[id] || []
                    return (
                      <div key={id} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 12, padding: '12px 14px' }}>
                        <div style={{ width: 34, height: 34, flexShrink: 0, borderRadius: 99, display: 'grid', placeItems: 'center', background: avatarFill(hue), color: avatarText(hue), fontSize: 12.5, fontWeight: 600, position: 'relative' }}>
                          {!done && <div className="rt-breathe" style={{ position: 'absolute', inset: -3, borderRadius: 99, background: `oklch(0.7 0.12 ${hue})` }} />}
                          <span style={{ position: 'relative' }}>{initials(pmap[id]?.name ?? id)}</span>
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                            <span style={{ fontSize: 13.5, fontWeight: 600 }}>{pmap[id]?.name ?? id}</span>
                            {buckets.length > 0 && <span style={{ fontSize: 12, color: 'var(--rt-ink3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>· {buckets.join(', ')}</span>}
                          </div>
                          <div style={{ fontSize: 13, color: done ? 'oklch(0.5 0.1 155)' : 'var(--rt-ink2)', marginTop: 3, fontStyle: done ? 'normal' : 'italic' }}>
                            {done ? '✓ ready to open' : (line ? `${line}…` : 'getting started…')}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
            {st.speaking && (
              <div style={{ padding: '18px 0 40px', fontSize: 14, color: 'var(--rt-ink3)' }}>
                {(pmap[st.speaking]?.name ?? 'Someone')} is thinking
                <span className="rt-dot" style={{ marginLeft: 6 }}>·</span>
                <span className="rt-dot" style={{ animationDelay: '.18s' }}>·</span>
                <span className="rt-dot" style={{ animationDelay: '.36s' }}>·</span>
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        {/* composer */}
        <div style={{ padding: '0 30px 22px' }}>
          <div style={{ maxWidth: 680, margin: '0 auto' }}>
            {st.checkpoint && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'var(--rt-accent-tint)', border: '1px solid oklch(0.72 0.1 275)', borderRadius: 12, padding: '10px 14px', marginBottom: 10 }}>
                <span style={{ flex: 1, fontSize: 13.5, color: 'var(--rt-ink)' }}>
                  {st.checkpoint === 'closing'
                    ? 'The room is ready to wrap up — steer below, or continue to the recap.'
                    : 'The room paused to check with you — say something to steer, or continue.'}
                </span>
                <button onClick={actions.continueMeeting}
                  style={{ fontSize: 13, fontWeight: 600, padding: '8px 16px', borderRadius: 9, background: 'var(--rt-accent)', color: '#fff' }}>Continue</button>
              </div>
            )}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, background: '#fff', borderRadius: 14, padding: '6px 6px 6px 16px',
              border: `1px solid ${focused ? 'oklch(0.72 0.1 275)' : 'var(--rt-hair)'}`,
              boxShadow: focused ? '0 0 0 4px var(--rt-accent-ring)' : 'none', transition: 'box-shadow .15s, border-color .15s',
            }}>
              <input
                value={input} onChange={e => setInput(e.target.value)} onFocus={onFocus} onBlur={onBlur}
                onKeyDown={e => { if (e.key === 'Enter') send() }}
                placeholder={focused ? 'Go ahead — they\'re waiting' : 'Say something…'}
                disabled={!st.running}
                style={{ flex: 1, border: 'none', outline: 'none', fontSize: 15.5, background: 'transparent', fontFamily: 'inherit' }}
              />
              <button onClick={cycleTarget} style={{ fontSize: 13, fontWeight: 600, color: 'var(--rt-accent)', background: 'oklch(0.965 0.015 275)', borderRadius: 9, padding: '8px 12px' }}>{targetLabel} ▾</button>
              <button onClick={send} disabled={!input.trim() || !st.running}
                style={{ fontSize: 13.5, fontWeight: 600, borderRadius: 10, padding: '9px 16px',
                  background: input.trim() && st.running ? 'var(--rt-accent)' : 'oklch(0.94 0.008 85)',
                  color: input.trim() && st.running ? '#fff' : 'var(--rt-faint)' }}>Say it</button>
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--rt-ink3)', minHeight: 17, marginTop: 6 }}>
              {!st.running ? 'The meeting has finished.' : focused ? 'Everyone\'s waiting. The clock is stopped.' : 'Start typing and they\'ll wait for you.'}
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT: artifact panel */}
      <ArtifactPanel st={st} actions={actions} />
    </div>
  )
}

function ArtifactPanel({ st, actions }: { st: RoundtableState; actions: Actions }) {
  const canDraw = !!st.recap && !st.running
  return (
    <aside style={{ width: 320, flexShrink: 0, borderLeft: '1px solid var(--rt-hair)', background: '#fff', overflowY: 'auto' }}>
      <div style={{ padding: '16px 18px' }}>
        <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>Agreed so far</div>
        {st.agreed.length === 0 ? (
          <p style={{ fontSize: 13, color: 'var(--rt-ink3)', marginTop: 8, lineHeight: 1.5 }}>Nothing settled yet. Decisions and firm commitments land here as they're made.</p>
        ) : (
          <div style={{ marginTop: 10 }}>
            {st.agreed.map((a, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginTop: i ? 12 : 0 }}>
                <span style={{ width: 6, height: 6, borderRadius: 99, marginTop: 6, flexShrink: 0, background: AGREED_DOT[a.type] || AGREED_DOT.decision }} />
                <div>
                  <div style={{ fontSize: 13.5, lineHeight: 1.5 }}>{a.text}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--rt-ink3)', marginTop: 2 }}>{a.who}{a.at ? ` · ${a.at}` : ''}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {(st.diagram || canDraw || st.drawing) && (
        <div style={{ borderTop: '1px solid var(--rt-hair)', padding: '16px 18px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)' }}>Diagram</div>
          {st.diagram ? (
            <>
              <div style={{ fontSize: 12.5, color: 'var(--rt-ink2)', margin: '4px 0 8px' }}>{st.diagram.detail} — does this match your understanding?</div>
              <iframe src={st.diagram.url} title="Diagram" style={{ width: '100%', height: 240, border: '1px solid var(--rt-hair)', borderRadius: 10, background: '#fff' }} />
              <div className="flex items-center gap-2" style={{ marginTop: 8 }}>
                <button onClick={actions.approveDiagram} disabled={st.approved}
                  style={{ fontSize: 12.5, fontWeight: 600, padding: '6px 12px', borderRadius: 8, background: st.approved ? 'oklch(0.94 0.03 155)' : 'var(--rt-accent)', color: st.approved ? 'oklch(0.4 0.1 155)' : '#fff' }}>
                  {st.approved ? '✓ Approved' : 'Approve'}
                </button>
                <button onClick={actions.drawDiagram} disabled={st.drawing}
                  style={{ fontSize: 12.5, fontWeight: 600, padding: '6px 12px', borderRadius: 8, background: '#fff', border: '1px solid var(--rt-hair)', color: 'var(--rt-ink)' }}>
                  {st.drawing ? 'Drawing…' : 'Draw again'}
                </button>
                <a href={st.diagram.url} target="_blank" rel="noopener" style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 600, color: 'var(--rt-accent)' }}>Open ↗</a>
              </div>
            </>
          ) : st.drawing ? (
            <p style={{ fontSize: 12.5, color: 'var(--rt-ink3)', marginTop: 8 }}>Drawing the diagram…</p>
          ) : (
            <>
              <p style={{ fontSize: 12.5, color: 'var(--rt-ink3)', margin: '4px 0 8px', lineHeight: 1.5 }}>Want a picture of what the room settled?</p>
              <button onClick={actions.drawDiagram}
                style={{ fontSize: 12.5, fontWeight: 600, padding: '6px 12px', borderRadius: 8, background: 'var(--rt-accent)', color: '#fff' }}>Draw this up</button>
            </>
          )}
        </div>
      )}
    </aside>
  )
}

function btn(primary: boolean): React.CSSProperties {
  return {
    fontSize: 13.5, fontWeight: 600, borderRadius: 10, padding: '9px 16px',
    background: primary ? 'var(--rt-accent)' : '#fff', color: primary ? '#fff' : 'var(--rt-ink)',
    border: primary ? 'none' : '1px solid var(--rt-hair)',
  }
}

function UsagePanel({ usage, onClose }: { usage: Usage; onClose: () => void }) {
  const rows = [...usage.by_person].sort((a, b) => b.cost_usd - a.cost_usd)
  const th: React.CSSProperties = { fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--rt-ink3)', textAlign: 'right', padding: '0 0 6px' }
  const td: React.CSSProperties = { fontSize: 12.5, textAlign: 'right', padding: '5px 0', whiteSpace: 'nowrap' }
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 40 }} />
      <div className="rt-tnum" style={{
        position: 'absolute', top: 'calc(100% + 8px)', right: 0, zIndex: 41, width: 360,
        background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 12, padding: 16,
        boxShadow: '0 12px 40px oklch(0 0 0 / 0.14)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--rt-ink)' }}>This meeting so far</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--rt-ink)' }}>{usd(usage.totals.cost_usd)}</span>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead><tr>
            <th style={{ ...th, textAlign: 'left' }}>Who</th>
            <th style={th}>Model</th><th style={th}>In</th><th style={th}>Out</th><th style={th}>Cost</th>
          </tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.who} style={{ borderTop: '1px solid var(--rt-divider)' }}>
                <td style={{ ...td, textAlign: 'left', fontWeight: 600 }}>{r.name}</td>
                <td style={{ ...td, color: 'var(--rt-ink3)' }}>{modelShort(r.model)}</td>
                <td style={td}>{tok(r.input_tokens)}</td>
                <td style={td}>{tok(r.output_tokens)}</td>
                <td style={td}>{usd(r.cost_usd)}</td>
              </tr>
            ))}
            {(usage.facilitator.input_tokens > 0 || usage.facilitator.output_tokens > 0) && (
              <tr style={{ borderTop: '1px solid var(--rt-divider)' }}>
                <td style={{ ...td, textAlign: 'left', color: 'var(--rt-ink2)' }}>Facilitator</td>
                <td style={{ ...td, color: 'var(--rt-ink3)' }}>ops</td>
                <td style={td}>{tok(usage.facilitator.input_tokens)}</td>
                <td style={td}>{tok(usage.facilitator.output_tokens)}</td>
                <td style={td}>{usd(usage.facilitator.cost_usd)}</td>
              </tr>
            )}
          </tbody>
        </table>
        {usage.totals.cache_read_tokens > 0 && (
          <div style={{ fontSize: 11, color: 'var(--rt-ink3)', marginTop: 8 }}>
            {tok(usage.totals.cache_read_tokens)} tokens read from cache (not billed at full rate)
          </div>
        )}
      </div>
    </>
  )
}
