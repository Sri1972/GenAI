import { useState } from 'react'
import { X, Plus } from 'lucide-react'
import { RoundtablePersona, CreateMeetingBody, EngagementMode, MeetingSummary, AgendaTemplate } from '../../hooks/useApi'
import { avatarFill, avatarText, initials } from './personaColor'

function timeAgo(when: number): string {
  if (!when) return ''
  const secs = Math.max(0, Date.now() / 1000 - when)
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`
  return `${Math.floor(secs / 86400)}d ago`
}

const DURATIONS = [
  { label: '5 min', value: 5 }, { label: '10 min', value: 12 }, { label: '20 min', value: 20 },
]

export default function SetupScreen({ personas, templates = [], onStart, onToast, defaultMode = 'collaborate', pastMeetings = [], onOpenMeeting }: {
  personas: RoundtablePersona[]
  templates?: AgendaTemplate[]
  onStart: (body: CreateMeetingBody) => void
  onToast: (msg: string) => void
  defaultMode?: EngagementMode
  pastMeetings?: MeetingSummary[]
  onOpenMeeting?: (id: string) => void
}) {
  const [topic, setTopic] = useState('')
  const [selected, setSelected] = useState<string[]>(['product', 'engineering', 'design'])
  const [duration, setDuration] = useState(12)
  const [turnOrder, setTurnOrder] = useState<'open' | 'round'>('open')
  const [mode, setMode] = useState<EngagementMode>(defaultMode)
  const [architecture, setArchitecture] = useState<'classic' | 'debate'>('classic')
  const [templateId, setTemplateId] = useState('')
  const [agenda, setAgenda] = useState<string[]>([])
  const [customizing, setCustomizing] = useState(false)
  const [advanced, setAdvanced] = useState(false)

  const toggle = (id: string) =>
    setSelected(prev => prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id])

  const applyTemplate = (t: AgendaTemplate) => {
    setTemplateId(t.id); setAgenda([...t.buckets]); setSelected([...t.people]); setDuration(t.duration)
  }
  const setBucket = (i: number, v: string) => setAgenda(a => a.map((b, k) => k === i ? v : b))
  const removeBucket = (i: number) => setAgenda(a => a.filter((_, k) => k !== i))
  const addBucket = () => setAgenda(a => [...a, ''])

  const start = () => {
    if (!topic.trim()) return onToast('Tell them what you need to work out')
    if (selected.length < 2) return onToast('You need at least two people in the room')
    onStart({
      topic: topic.trim(), people: selected, duration_minutes: duration, turn_order: turnOrder,
      diagram: true, mode, agenda: agenda.map(b => b.trim()).filter(Boolean), architecture,
    })
  }

  return (
    <div className="rt h-full overflow-y-auto">
      <div className="mx-auto" style={{ maxWidth: 660, padding: '56px 32px 90px' }}>
        <h1 className="rt-serif" style={{ fontSize: 42, lineHeight: 1.1, letterSpacing: '-0.02em' }}>
          What do you need to work out?
        </h1>
        <p style={{ fontSize: 16.5, lineHeight: 1.6, color: 'var(--rt-ink2)', maxWidth: 520, marginTop: 14, textWrap: 'pretty' } as any}>
          Write it the way you'd say it to a colleague. Your team will talk it through, disagree where they disagree, and hand you back a decision.
        </p>

        {/* Meeting type (sets the personas, length, and the write-up structure) */}
        {templates.length > 0 && (
          <div style={{ marginTop: 22 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--rt-ink2)', marginBottom: 8 }}>Meeting type</div>
            <div className="flex flex-wrap gap-2">
              {templates.map(t => {
                const on = templateId === t.id
                return (
                  <button key={t.id} onClick={() => { applyTemplate(t); setCustomizing(false) }}
                    style={{
                      background: on ? 'var(--rt-accent-tint)' : '#fff',
                      border: `1px solid ${on ? 'oklch(0.72 0.1 275)' : 'var(--rt-hair)'}`,
                      borderRadius: 99, padding: '8px 14px', fontSize: 13.5,
                      color: on ? 'var(--rt-accent-hover)' : 'var(--rt-ink2)', fontWeight: on ? 600 : 400,
                    }}>
                    {t.name}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Topic */}
        <textarea
          value={topic} onChange={e => setTopic(e.target.value)}
          placeholder="e.g. Should we build note sharing or full-text search next?"
          style={{
            width: '100%', minHeight: 118, padding: '18px 20px', borderRadius: 14, marginTop: 18,
            background: '#fff', border: '1px solid var(--rt-hair)', fontSize: 16.5, lineHeight: 1.6,
            resize: 'vertical', outline: 'none', fontFamily: 'inherit', color: 'var(--rt-ink)',
          }}
        />

        {/* Notes structure — the OUTPUT shape, not something to fill in. Preview by default. */}
        <div style={{ marginTop: 24, background: 'oklch(0.985 0.004 85)', border: '1px solid var(--rt-hair)', borderRadius: 12, padding: '14px 16px' }}>
          <div className="flex items-center" style={{ gap: 8 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--rt-ink2)' }}>How your notes will be organized</div>
              <div style={{ fontSize: 12.5, color: 'var(--rt-ink3)', marginTop: 2 }}>
                The Facilitator sorts the write-up into these sections at the end. You don't fill these in.
              </div>
            </div>
            {agenda.length > 0 && (
              <button onClick={() => setCustomizing(c => !c)} style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--rt-accent)' }}>
                {customizing ? 'Done' : 'Customize'}
              </button>
            )}
          </div>

          {agenda.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--rt-ink3)', marginTop: 10 }}>Pick a meeting type above to set this.</div>
          ) : !customizing ? (
            <div className="flex flex-wrap" style={{ gap: 6, marginTop: 10 }}>
              {agenda.filter(b => b.trim()).map((b, i) => (
                <span key={i} style={{ fontSize: 12.5, color: 'var(--rt-ink2)', background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 99, padding: '4px 11px' }}>{b}</span>
              ))}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
              {agenda.map((b, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, color: 'var(--rt-faint)', width: 18, textAlign: 'right' }}>{i + 1}.</span>
                  <input value={b} onChange={e => setBucket(i, e.target.value)} placeholder="Section name"
                    style={{ flex: 1, background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 9, padding: '7px 11px', fontSize: 13.5, outline: 'none', fontFamily: 'inherit', color: 'var(--rt-ink)' }} />
                  <button onClick={() => removeBucket(i)} style={{ color: 'var(--rt-faint)', padding: 4 }}><X size={14} /></button>
                </div>
              ))}
              <button onClick={addBucket} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600, color: 'var(--rt-accent)', marginTop: 2, alignSelf: 'flex-start', paddingLeft: 24 }}>
                <Plus size={12} /> Add section
              </button>
            </div>
          )}
        </div>

        {/* Who's in the room */}
        <h2 className="rt-serif" style={{ fontSize: 26, marginTop: 46, letterSpacing: '-0.01em' }}>
          Who should be in the room?
        </h2>
        <p style={{ fontSize: 14.5, color: 'var(--rt-ink2)', marginTop: 4 }}>
          Tap to add or remove. Four or five is a conversation; eight is a queue.
        </p>
        <div className="flex flex-wrap gap-2.5 mt-4">
          {personas.map(p => {
            const on = selected.includes(p.id)
            return (
              <button key={p.id} onClick={() => toggle(p.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px 10px 10px', borderRadius: 99,
                  background: on ? 'var(--rt-accent-tint)' : '#fff',
                  border: `1px solid ${on ? 'oklch(0.72 0.1 275)' : 'var(--rt-hair)'}`,
                  opacity: on ? 1 : 0.5, transition: 'background .14s, border-color .14s, opacity .14s',
                }}>
                <span style={{
                  width: 34, height: 34, borderRadius: 99, display: 'grid', placeItems: 'center',
                  background: avatarFill(p.hue), color: avatarText(p.hue), fontSize: 12.5, fontWeight: 600,
                }}>{initials(p.name)}</span>
                <span style={{ textAlign: 'left', lineHeight: 1.2 }}>
                  <span style={{ display: 'block', fontSize: 14.5, fontWeight: 600, letterSpacing: '-0.01em' }}>{p.name}</span>
                  <span style={{ display: 'block', fontSize: 12.5, color: 'var(--rt-ink3)' }}>{p.role}</span>
                </span>
              </button>
            )
          })}
        </div>

        {/* Duration */}
        <div style={{ marginTop: 32 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--rt-ink2)', marginBottom: 8 }}>How long should they take?</div>
          <div className="flex gap-2">
            {DURATIONS.map(d => (
              <button key={d.value} onClick={() => setDuration(d.value)}
                style={{
                  padding: '9px 17px', borderRadius: 10, fontSize: 14, fontWeight: 600,
                  border: `1px solid ${duration === d.value ? 'transparent' : 'var(--rt-hair)'}`,
                  background: duration === d.value ? 'var(--rt-accent)' : '#fff',
                  color: duration === d.value ? '#fff' : 'var(--rt-ink2)',
                }}>{d.label}</button>
            ))}
          </div>
        </div>

        {/* Mode */}
        <div style={{ marginTop: 28 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--rt-ink2)', marginBottom: 8 }}>How involved do you want to be?</div>
          <div className="flex gap-2.5">
            {([
              ['collaborate', 'Collaborate', 'They check in with you and pause at milestones to steer.'],
              ['autopilot', 'Autopilot', 'They run it start to finish; you review the recap at the end.'],
            ] as const).map(([val, title, desc]) => (
              <button key={val} onClick={() => setMode(val)} style={{
                flex: 1, textAlign: 'left', padding: '12px 14px', borderRadius: 11,
                border: `1px solid ${mode === val ? 'oklch(0.72 0.1 275)' : 'var(--rt-hair)'}`,
                background: mode === val ? 'var(--rt-accent-tint)' : '#fff',
              }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{title}</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.4, color: 'var(--rt-ink2)', marginTop: 2 }}>{desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Engine (A/B) */}
        <div style={{ marginTop: 28 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--rt-ink2)', marginBottom: 8 }}>
            Meeting engine <span style={{ fontWeight: 400, color: 'var(--rt-ink3)' }}>· experiment</span>
          </div>
          <div className="flex gap-2.5">
            {([
              ['classic', 'Classic', 'Facilitator-run: homework, then a coordinated turn-by-turn discussion.'],
              ['debate', 'Debate', 'SDK-native: parallel positions, then structured rounds of see-and-revise with a rotating skeptic. No coordinator.'],
            ] as const).map(([val, title, desc]) => (
              <button key={val} onClick={() => setArchitecture(val)} style={{
                flex: 1, textAlign: 'left', padding: '12px 14px', borderRadius: 11,
                border: `1px solid ${architecture === val ? 'oklch(0.72 0.1 275)' : 'var(--rt-hair)'}`,
                background: architecture === val ? 'var(--rt-accent-tint)' : '#fff',
              }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{title}</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.4, color: 'var(--rt-ink2)', marginTop: 2 }}>{desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div style={{ marginTop: 30 }}>
          <button onClick={start}
            style={{
              background: 'var(--rt-accent)', color: '#fff', fontSize: 16, fontWeight: 600,
              padding: '15px 28px', borderRadius: 12, boxShadow: '0 2px 10px oklch(0.5 0.14 275 / 0.25)',
            }}>
            Start the meeting
          </button>
          <div style={{ fontSize: 13, color: 'var(--rt-ink3)', marginTop: 10 }}>
            {selected.length} {selected.length === 1 ? 'person' : 'people'} · {duration === 12 ? 10 : duration} minutes · you can interrupt at any point
          </div>
        </div>

        {/* Advanced */}
        <button onClick={() => setAdvanced(a => !a)}
          style={{ fontSize: 13, fontWeight: 600, color: 'var(--rt-ink3)', marginTop: 22 }}>
          {advanced ? 'Hide the details' : 'There are a couple of details you can change'}
        </button>
        {advanced && (
          <div style={{ background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 13, padding: 20, marginTop: 12 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 10 }}>How turns are taken</div>
            {([
              ['open', 'Speak up when you have something to add', 'People come in where they\'re relevant, and can hand off to each other. Sounds like a real discussion.'],
              ['round', 'Go round the table in order', 'Everyone speaks every round, whether or not they have anything to add. Predictable, and reads like it.'],
            ] as const).map(([val, title, desc]) => (
              <button key={val} onClick={() => setTurnOrder(val)} style={{
                display: 'block', width: '100%', textAlign: 'left', padding: '12px 14px', borderRadius: 10, marginTop: 8,
                border: `1px solid ${turnOrder === val ? 'oklch(0.72 0.1 275)' : 'var(--rt-hair)'}`,
                background: turnOrder === val ? 'oklch(0.97 0.018 275)' : '#fff',
              }}>
                <div style={{ fontSize: 13.5, fontWeight: 600 }}>{title}</div>
                <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--rt-ink2)' }}>{desc}</div>
              </button>
            ))}
            <div style={{ fontSize: 12.5, color: 'var(--rt-ink3)', marginTop: 12 }}>
              Your team can read from the reference files you've added to this project. Nothing is written back to them.
            </div>
          </div>
        )}

        {/* Past meetings */}
        {pastMeetings.length > 0 && (
          <div style={{ marginTop: 46 }}>
            <div style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--rt-ink3)', marginBottom: 10 }}>Past meetings</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {pastMeetings.map(m => (
                <button key={m.id} onClick={() => onOpenMeeting?.(m.id)}
                  style={{ textAlign: 'left', background: '#fff', border: '1px solid var(--rt-hair)', borderRadius: 11, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, color: 'var(--rt-ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.topic || 'Untitled meeting'}</div>
                    <div style={{ fontSize: 12, color: 'var(--rt-ink3)', marginTop: 2 }}>{m.turns} turns · {timeAgo(m.when)}</div>
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 99, flexShrink: 0,
                    background: m.complete ? 'oklch(0.94 0.04 155)' : 'oklch(0.94 0.02 85)',
                    color: m.complete ? 'oklch(0.4 0.1 155)' : 'var(--rt-ink3)' }}>
                    {m.complete ? 'Completed' : 'Unfinished'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
