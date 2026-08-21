import { useCallback, useRef, useState } from 'react'

// ── Wire event types (match agent_session.py) ─────────────────────────────────
export type AgentEvent =
  | { type: 'start'; project: string }
  | { type: 'phase'; phase: string }
  | { type: 'text'; content: string }
  | { type: 'thinking'; content: string }
  | { type: 'tool_use'; tool_name: string; tool_input: any; tool_use_id: string }
  | { type: 'tool_result'; tool_use_id: string; content: any; is_error: boolean }
  | { type: 'result'; session_id: string | null; cost_usd: number; num_turns?: number }
  | { type: 'app_ready'; preview_url: string; port: number; qa: any }
  | { type: 'done'; session_id: string | null }
  | { type: 'error'; error: string }

export interface ToolCall {
  toolUseId: string
  toolName: string
  toolInput: any
  result?: string
  isError?: boolean
}

// `dev: true` items only show in developer view.
export type ChatItem =
  | { kind: 'user'; content: string }
  | { kind: 'assistant'; content: string; streaming?: boolean }   // Claude's natural narration
  | { kind: 'thinking'; content: string; streaming?: boolean }    // Claude's native thinking
  | { kind: 'note'; content: string }
  | { kind: 'error'; content: string }
  | { kind: 'tool'; call: ToolCall; dev: true }

export interface AgentStreamState {
  items: ChatItem[]
  running: boolean
  activity: string | null      // ephemeral "what the platform is doing right now" line
  previewUrl: string | null
  sessionId: string | null
}

// The deterministic Python steps (Claude doesn't narrate these). Keep only the meaningful
// ones, in plain language; drop granular noise.
function friendlyPhase(phase: string): string | null {
  const p = phase.toLowerCase()
  if (p.includes('skeleton') || p.includes('preparing')) return 'Preparing your workspace…'
  if (p === 'finalizing' || p.includes('putting')) return 'Putting your app together…'
  if (p.startsWith('install') || p.includes('modules')) return 'Installing the building blocks…'
  if (p === 'start' || p.includes('starting')) return 'Starting your app…'
  if (p === 'qa' || p.includes('checking')) return 'Checking that everything works…'
  if (p === 'healing') return 'Polishing a few details…'
  return null
}

function stringifyResult(content: any): string {
  if (typeof content === 'string') return content
  try { return JSON.stringify(content, null, 2) } catch { return String(content) }
}

// A friendly one-line activity for what the agent is doing right now, from its tool call —
// this is what "condensing the thinking stream" looks like: no jargon, no wall of text.
function friendlyTool(name: string, input: any): string {
  const fp = String(input?.file_path || '')
  if (name === 'Write' || name === 'Edit' || name === 'MultiEdit') {
    if (/schema\.sql|seed\.sql|\/api\//.test(fp)) return 'Setting up the data…'
    if (/pages\//.test(fp)) return 'Building a page…'
    if (/components\//.test(fp)) return 'Building a component…'
    return 'Building the app…'
  }
  if (name.startsWith('mcp__dataset__')) return 'Analyzing your data…'
  if (name === 'mcp__turboui__run_qa' || name === 'mcp__turboui__tsc_check') return 'Checking everything works…'
  if (name.startsWith('mcp__turboui__validate') || name.startsWith('mcp__turboui__check')) return 'Double-checking the setup…'
  if (name.startsWith('mcp__turboui__')) return 'Getting the app running…'
  if (name === 'Task') return 'Bringing in a specialist…'
  if (name === 'Skill') return 'Using a special capability…'
  if (name === 'Bash') return 'Running a quick step…'
  if (['Read', 'Glob', 'Grep'].includes(name)) return 'Looking things over…'
  return 'Working on it…'
}

export function useAgentStream(project: string) {
  const [items, setItems] = useState<ChatItem[]>([])
  const [running, setRunning] = useState(false)
  const [activity, setActivity] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null)

  const push = useCallback((it: ChatItem) => setItems(prev => [...prev, it]), [])

  // Append a streaming delta into the current bubble of matching kind, else start a new one.
  const appendDelta = useCallback((kind: 'assistant' | 'thinking', delta: string) => {
    setItems(prev => {
      const last = prev[prev.length - 1]
      if (last && last.kind === kind && last.streaming) {
        return [...prev.slice(0, -1), { ...last, content: last.content + delta }]
      }
      // finalize any other streaming bubble, then open a new one
      const finalized = prev.map(it =>
        (it.kind === 'assistant' || it.kind === 'thinking') && it.streaming ? { ...it, streaming: false } : it
      )
      return [...finalized, { kind, content: delta, streaming: true }]
    })
  }, [])

  const finalizeStreaming = useCallback(() => {
    setItems(prev => prev.map(it =>
      (it.kind === 'assistant' || it.kind === 'thinking') && it.streaming ? { ...it, streaming: false } : it
    ))
  }, [])

  const handleEvent = useCallback((ev: AgentEvent) => {
    switch (ev.type) {
      case 'start': break
      case 'phase':
        setActivity(friendlyPhase(ev.phase))   // ephemeral; cleared when Claude produces content
        break
      case 'text': setActivity(null); appendDelta('assistant', ev.content); break
      // Condense raw thinking to a single rolling activity line — no thinking bubbles.
      case 'thinking': setActivity('Thinking it through…'); break
      case 'tool_use':
        finalizeStreaming()
        setActivity(friendlyTool(ev.tool_name, ev.tool_input))
        push({ kind: 'tool', dev: true, call: { toolUseId: ev.tool_use_id, toolName: ev.tool_name, toolInput: ev.tool_input } })
        break
      case 'tool_result':
        setItems(prev => prev.map(it =>
          it.kind === 'tool' && it.call.toolUseId === ev.tool_use_id
            ? { ...it, call: { ...it.call, result: stringifyResult(ev.content), isError: ev.is_error } }
            : it
        ))
        break
      case 'result':
        if (ev.session_id) setSessionId(ev.session_id)
        finalizeStreaming()
        break
      case 'app_ready':
        finalizeStreaming()
        setActivity(null)
        if (ev.preview_url) setPreviewUrl(ev.preview_url)   // reveal preview once; HMR keeps it live
        break
      case 'done':
        if (ev.session_id) setSessionId(ev.session_id)
        finalizeStreaming()
        setActivity(null)
        break
      case 'error':
        finalizeStreaming()
        setActivity(null)
        push({ kind: 'error', content: friendlyError(ev.error) })
        break
    }
  }, [push, appendDelta, finalizeStreaming])

  const send = useCallback(async (message: string, provider?: string, mode?: string) => {
    if (running || !message.trim()) return
    push({ kind: 'user', content: message })
    setRunning(true)
    try {
      const res = await fetch(`/api/agent/${encodeURIComponent(project)}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, provider: provider || null, mode: mode || null }),
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)
      const reader = res.body.getReader()
      readerRef.current = reader
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const t = line.trim()
          if (t.startsWith('data: ')) {
            try { handleEvent(JSON.parse(t.slice(6))) } catch { /* ignore malformed */ }
          }
        }
      }
    } catch (e: any) {
      push({ kind: 'error', content: `Lost connection to the builder. ${e?.message || ''}`.trim() })
    } finally {
      setRunning(false)
      setActivity(null)
      readerRef.current = null
    }
  }, [project, running, handleEvent, push])

  const interrupt = useCallback(async () => {
    try { await fetch(`/api/agent/${encodeURIComponent(project)}/interrupt`, { method: 'POST' }) } catch { /* noop */ }
    try { readerRef.current?.cancel() } catch { /* noop */ }
  }, [project])

  const state: AgentStreamState = { items, running, activity, previewUrl, sessionId }
  return { ...state, send, interrupt }
}

function friendlyError(raw: string): string {
  if (/schema\.sql/i.test(raw)) return "The build didn't finish setting up your data. Try sending your request again, with a bit more detail about what the app should show."
  if (/vite|dev server|port/i.test(raw)) return "The app was built but had trouble starting up. Try again in a moment."
  return "Something went wrong while building. Please try again."
}
