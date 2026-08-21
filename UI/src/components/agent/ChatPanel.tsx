import { useEffect, useRef, useState } from 'react'
import { Send, Square, Wrench, CheckCircle2, XCircle, User, Sparkles, ChevronRight, Loader2 } from 'lucide-react'
import { useAgentStream, ChatItem, ToolCall } from '../../hooks/useAgentStream'
import Markdown from './Markdown'
import SummaryCard from './SummaryCard'
import { splitSummary } from '../../utils/turboSummary'

const PROVIDERS = [
  { id: 'local', label: 'Local (Claude)' },
  { id: 'bedrock', label: 'Bedrock' },
  { id: 'litellm', label: 'LiteLLM' },
]

// ── Developer-only raw tool card ──────────────────────────────────────────────
function ToolCard({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(false)
  const done = call.result !== undefined
  const shortInput = (() => {
    const fp = call.toolInput?.file_path || call.toolInput?.subagent_type || call.toolInput?.command
    return fp ? String(fp).replace(/^.*\/generated\/web-apps\/[^/]+\//, '') : ''
  })()
  return (
    <div className={`rounded-lg border text-xs ${call.isError ? 'border-red-200 bg-red-50' : 'border-sky-200 bg-sky-50'}`}>
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left">
        <ChevronRight className={`w-3 h-3 text-slate-400 transition-transform ${open ? 'rotate-90' : ''}`} />
        {done
          ? (call.isError ? <XCircle className="w-3.5 h-3.5 text-red-500" /> : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />)
          : <Loader2 className="w-3.5 h-3.5 text-sky-500 animate-spin" />}
        <Wrench className="w-3 h-3 text-slate-500" />
        <span className="font-medium text-slate-700">{call.toolName.replace('mcp__turboui__', '')}</span>
        {shortInput && <span className="text-slate-400 truncate">{shortInput}</span>}
      </button>
      {open && (
        <div className="px-2.5 pb-2 space-y-1.5">
          <pre className="bg-white/70 rounded p-2 overflow-x-auto text-slate-600">{JSON.stringify(call.toolInput, null, 2)}</pre>
          {done && <pre className={`rounded p-2 overflow-x-auto ${call.isError ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-600'}`}>
            {call.result!.slice(0, 2000)}{call.result!.length > 2000 ? '\n… (truncated)' : ''}
          </pre>}
        </div>
      )}
    </div>
  )
}

function Item({ it, dev }: { it: ChatItem; dev: boolean }) {
  switch (it.kind) {
    case 'user':
      return (
        <div className="flex gap-2.5 flex-row-reverse">
          <div className="shrink-0 w-7 h-7 rounded-full grid place-items-center bg-indigo-100"><User className="w-4 h-4 text-indigo-600" /></div>
          <div className="max-w-[85%] rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap bg-indigo-600 text-white">{it.content}</div>
        </div>
      )
    case 'assistant': {
      const { text, summary } = splitSummary(it.content)
      return (
        <div className="flex gap-2.5">
          <div className="shrink-0 w-7 h-7 rounded-full grid place-items-center bg-violet-100"><Sparkles className="w-4 h-4 text-violet-600" /></div>
          <div className="max-w-[88%] rounded-2xl px-3.5 py-2 bg-white border border-slate-200">
            {text && <Markdown>{text}</Markdown>}
            {it.streaming && <span className="inline-block w-1.5 h-4 ml-0.5 bg-violet-400 animate-pulse align-middle" />}
            {summary && <SummaryCard summary={summary} />}
          </div>
        </div>
      )
    }
    case 'thinking':
      return dev ? (
        <div className="flex gap-2.5 pl-9">
          <div className="max-w-[88%] border-l-2 border-slate-200 pl-3">
            <Markdown muted>{it.content}</Markdown>
          </div>
        </div>
      ) : null
    case 'note':
      return <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">{it.content}</div>
    case 'error':
      return <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{it.content}</div>
    case 'tool':
      return dev ? <ToolCard call={it.call} /> : null
  }
}

export default function ChatPanel({ project, onPreview, initialMessage, defaultMode = 'collaborate' }: { project: string; onPreview?: (url: string) => void; initialMessage?: string; defaultMode?: 'collaborate' | 'autopilot' }) {
  const { items, running, activity, previewUrl, send, interrupt } = useAgentStream(project)
  const [input, setInput] = useState('')
  const [provider, setProvider] = useState('local')
  const [mode, setMode] = useState<'collaborate' | 'autopilot'>(defaultMode)
  const [dev, setDev] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const seededRef = useRef(false)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [items, activity])
  useEffect(() => { if (previewUrl && onPreview) onPreview(previewUrl) }, [previewUrl, onPreview])
  // Handoff seed: send the brainstorm decision as the opening message, exactly once.
  useEffect(() => {
    if (initialMessage && !seededRef.current) {
      seededRef.current = true
      send(initialMessage, provider, mode)
    }
  }, [initialMessage, send, provider, mode])

  const submit = () => { if (!running && input.trim()) { send(input.trim(), provider, mode); setInput('') } }
  const onKey = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }

  const visible = dev ? items : items.filter(it => it.kind !== 'tool')
  const empty = items.length === 0
  // gentle "working" hint only when nothing is actively streaming and no explicit activity
  const lastStreaming = [...visible].reverse().find(it => (it.kind === 'assistant' || it.kind === 'thinking') && (it as any).streaming)
  const showWorking = running && !lastStreaming && !activity

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-3 bg-slate-50">
        {empty && (
          <div className="h-full grid place-items-center text-center text-slate-400">
            <div>
              <Sparkles className="w-8 h-8 mx-auto mb-3 text-violet-300" />
              <p className="text-sm">Describe the app you'd like to build.</p>
              <p className="text-xs mt-1">I'll build it, run it, and you can keep chatting to change it.</p>
            </div>
          </div>
        )}
        {visible.map((it, i) => <Item key={i} it={it} dev={dev} />)}
        {activity && (
          <div className="flex items-center gap-2.5 pl-1 text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
            <span className="text-sm">{activity}</span>
          </div>
        )}
        {showWorking && (
          <div className="flex items-center gap-2.5 pl-1 text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
            <span className="text-sm">Working on it…</span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t border-slate-200 bg-white p-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-slate-400">Model:</span>
          <select value={provider} onChange={e => setProvider(e.target.value)}
                  className="text-xs border border-slate-200 rounded px-1.5 py-1 text-slate-600">
            {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
          </select>
          <span className="text-xs text-slate-400 ml-1">Mode:</span>
          <select value={mode} onChange={e => setMode(e.target.value as any)} disabled={items.length > 0}
                  title={items.length > 0 ? 'Mode is set when the build starts' : 'How involved you want to be'}
                  className="text-xs border border-slate-200 rounded px-1.5 py-1 text-slate-600 disabled:opacity-50">
            <option value="collaborate">Collaborate</option>
            <option value="autopilot">Autopilot</option>
          </select>
          <label className="ml-auto flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer select-none">
            <input type="checkbox" checked={dev} onChange={e => setDev(e.target.checked)} className="accent-violet-600" />
            Developer view
          </label>
        </div>
        <div className="flex items-end gap-2">
          <textarea
            value={input} onChange={e => setInput(e.target.value)} onKeyDown={onKey}
            disabled={running} rows={2}
            placeholder={running ? 'Building…' : 'Describe or change the app…  (Enter to send)'}
            className="flex-1 resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-200 disabled:bg-slate-50"
          />
          {running
            ? <button onClick={interrupt} className="shrink-0 w-10 h-10 grid place-items-center rounded-lg bg-red-500 text-white hover:bg-red-600"><Square className="w-4 h-4" /></button>
            : <button onClick={submit} disabled={!input.trim()} className="shrink-0 w-10 h-10 grid place-items-center rounded-lg bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-40"><Send className="w-4 h-4" /></button>}
        </div>
      </div>
    </div>
  )
}
