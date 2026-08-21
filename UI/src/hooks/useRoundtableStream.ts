import { useCallback, useRef, useState } from 'react'
import { roundtable, CreateMeetingBody } from './useApi'

// ── wire shapes (match API/roundtable_routes.py _serialize) ───────────────────
export interface RoundTurn {
  id?: string; who: string; text: string; why?: string; at?: string
  note?: string; thinking?: string; sources?: string[]; quote?: string; quoteRole?: string
}
export interface AgreedItem { text: string; type: string; who: string; at: string }
export interface RecapSection { bucket: string; items: string[] }
export interface Recap {
  headline: string; decision?: string; argument?: string; sections?: RecapSection[]
  commitments: { who: string; what: string }[]; still_open: string[]
}
export interface DiagramArtifact { file: string; url: string; detail: string }
export interface UsagePerson {
  who: string; name: string; model: string
  input_tokens: number; output_tokens: number; cache_read_tokens: number; cost_usd: number; turns: number
}
export interface UsageModel {
  model: string; input_tokens: number; output_tokens: number; cache_read_tokens: number; cost_usd: number
}
export interface Usage {
  by_person: UsagePerson[]
  by_model: UsageModel[]
  facilitator: { input_tokens: number; output_tokens: number; cost_usd: number }
  totals: { input_tokens: number; output_tokens: number; cache_read_tokens: number; cost_usd: number }
}

type Ev =
  | { type: 'turn'; turn: RoundTurn }
  | { type: 'preparing'; who: string[]; buckets?: Record<string, string[]> }
  | { type: 'activity'; who: string; text: string }
  | { type: 'prepared'; who: string }
  | { type: 'usage'; usage: Usage }
  | { type: 'round'; n: number; of: number }
  | { type: 'speaking'; who: string }
  | { type: 'passed'; who: string }
  | { type: 'question'; who: string; text: string; at: string }
  | { type: 'agreed'; item: AgreedItem }
  | { type: 'recap'; recap: Recap }
  | { type: 'diagram'; file: string | null; url?: string; detail: string }
  | { type: 'checkpoint'; kind: string }
  | { type: 'done'; summary?: any }
  | { type: 'error'; error: string }

export interface RoundtableState {
  meetingId: string | null
  turns: RoundTurn[]
  agreed: AgreedItem[]
  speaking: string | null      // who is composing right now (drives halo + thinking dots)
  spoken: string[]             // who has spoken at least once
  running: boolean
  paused: boolean
  awaitingYou: string | null   // a colleague asked YOU something
  preparing: string[] | null   // people doing their agenda homework before opening
  prepBuckets: Record<string, string[]>  // what each is researching
  activity: Record<string, string>       // live "what they're doing right now" line, per person
  prepared: string[]           // who has finished their homework
  round: { n: number; of: number } | null  // debate engine: current round
  usage: Usage | null          // running token/cost picture
  checkpoint: string | null    // collaborate mode: the Chair paused for your steer ('halfway'|'closing')
  recap: Recap | null
  diagram: DiagramArtifact | null
  drawing: boolean
  approved: boolean
  error: string | null
}

const initial: RoundtableState = {
  meetingId: null, turns: [], agreed: [], speaking: null, spoken: [],
  running: false, paused: false, awaitingYou: null, preparing: null,
  prepBuckets: {}, activity: {}, prepared: [], round: null, usage: null,
  checkpoint: null, recap: null, diagram: null,
  drawing: false, approved: false, error: null,
}

export function useRoundtableStream(project: string) {
  const [s, setS] = useState<RoundtableState>(initial)
  const midRef = useRef<string | null>(null)
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null)

  const patch = useCallback((p: Partial<RoundtableState>) => setS(prev => ({ ...prev, ...p })), [])

  const handle = useCallback((ev: Ev) => {
    setS(prev => {
      switch (ev.type) {
        case 'speaking':
          return { ...prev, speaking: ev.who, checkpoint: null }
        case 'preparing':
          return { ...prev, preparing: ev.who, prepBuckets: ev.buckets || {}, activity: {}, prepared: [] }
        case 'activity':
          return { ...prev, activity: { ...prev.activity, [ev.who]: ev.text } }
        case 'prepared':
          return prev.prepared.includes(ev.who) ? prev : { ...prev, prepared: [...prev.prepared, ev.who] }
        case 'usage':
          return { ...prev, usage: ev.usage }
        case 'round':
          return { ...prev, round: { n: ev.n, of: ev.of }, preparing: null }
        case 'turn': {
          const who = ev.turn.who
          const spoken = who !== 'chair' && who !== 'you' && !prev.spoken.includes(who)
            ? [...prev.spoken, who] : prev.spoken
          // The first prepared opening ends the homework phase — fold the cards away.
          return { ...prev, turns: [...prev.turns, ev.turn], speaking: null, spoken,
                   preparing: null, activity: {}, prepared: [] }
        }
        case 'passed':
          return { ...prev, speaking: null }
        case 'question':
          return { ...prev, awaitingYou: ev.who }
        case 'checkpoint':
          return { ...prev, checkpoint: ev.kind }
        case 'agreed':
          return { ...prev, agreed: [ev.item, ...prev.agreed] }
        case 'recap':
          return { ...prev, recap: ev.recap }
        case 'diagram':
          return ev.file && ev.url
            ? { ...prev, diagram: { file: ev.file, url: ev.url, detail: ev.detail } }
            : prev
        case 'done':
          return { ...prev, running: false, speaking: null }
        case 'error':
          return { ...prev, error: ev.error, running: false }
        default:
          return prev
      }
    })
  }, [])

  const start = useCallback(async (body: CreateMeetingBody) => {
    setS({ ...initial, running: true })
    try {
      const { meetingId } = await roundtable.createMeeting(project, body)
      midRef.current = meetingId
      patch({ meetingId })
      const res = await fetch(`/api/roundtable/${encodeURIComponent(project)}/meetings/${meetingId}/stream`, {
        method: 'POST',
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      const reader = res.body.getReader()
      readerRef.current = reader
      const dec = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() || ''
        for (const line of lines) {
          const t = line.trim()
          if (t.startsWith('data: ')) {
            try { handle(JSON.parse(t.slice(6))) } catch { /* ignore */ }
          }
        }
      }
    } catch (e: any) {
      handle({ type: 'error', error: e?.message || 'Lost connection to the room.' })
    } finally {
      setS(prev => ({ ...prev, running: false }))
      readerRef.current = null
    }
  }, [project, patch, handle])

  const hold = useCallback(async (paused: boolean) => {
    patch({ paused })
    const mid = midRef.current
    if (mid) { try { await roundtable.hold(project, mid, paused) } catch {} }
  }, [project, patch])

  const interject = useCallback(async (text: string, target = 'all') => {
    const mid = midRef.current
    if (!mid || !text.trim()) return
    // The backend echoes the "you" turn (from its inbox) — don't also add it locally or it
    // shows twice. Just clear the waiting/checkpoint state.
    setS(prev => ({ ...prev, awaitingYou: null, checkpoint: null }))
    try { await roundtable.interject(project, mid, text.trim(), target) } catch {}
    // resume so the loop picks it up
    await hold(false)
  }, [project, hold])

  const continueMeeting = useCallback(async () => {
    const mid = midRef.current
    setS(prev => ({ ...prev, checkpoint: null }))
    if (mid) { try { await roundtable.continue(project, mid) } catch {} }
  }, [project])

  const wrapUp = useCallback(async () => {
    const mid = midRef.current
    if (mid) { try { await roundtable.wrapUp(project, mid) } catch {} }
  }, [project])

  const drawDiagram = useCallback(async () => {
    const mid = midRef.current
    if (!mid) return
    setS(prev => ({ ...prev, drawing: true }))
    try {
      const r = await roundtable.drawDiagram(project, mid)
      setS(prev => ({
        ...prev, drawing: false, approved: false,
        diagram: r.file && r.url ? { file: r.file, url: r.url, detail: r.detail } : prev.diagram,
      }))
    } catch { setS(prev => ({ ...prev, drawing: false })) }
  }, [project])

  const approveDiagram = useCallback(async () => {
    const mid = midRef.current
    if (!mid || !s.diagram) return
    try { await roundtable.promote(project, mid, s.diagram.file); setS(prev => ({ ...prev, approved: true })) } catch {}
  }, [project, s.diagram])

  return { ...s, start, interject, hold, wrapUp, drawDiagram, approveDiagram, continueMeeting }
}
