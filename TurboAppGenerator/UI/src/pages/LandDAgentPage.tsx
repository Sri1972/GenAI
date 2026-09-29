import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Save, Loader2, RefreshCw, Download, Pencil, Eye } from 'lucide-react'
import {
  createItem, downloadUrl, getItem, getRunStatus, listPersonas, regenerateItem,
  updateContent, updateInput, LandDItemDetail, LandDRunStatus, Persona,
} from '../hooks/landDApi'
import ProgressLog from '../workflows/nodes/ProgressLog'

const POLL_INTERVAL_MS = 2000

interface Props {
  activeItemId: string | null
  onSelect: (itemId: string | null) => void
  onChanged: () => void
}

export default function LandDAgentPage({ activeItemId, onSelect, onChanged }: Props) {
  const [personas, setPersonas] = useState<Persona[]>([])

  // Create-form state
  const [topic, setTopic] = useState('')
  const [persona, setPersona] = useState('')
  const [instructions, setInstructions] = useState('')

  // Shared job state (generate + regenerate both poll through this)
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState<string[] | undefined>(undefined)
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Open-item state
  const [item, setItem] = useState<LandDItemDetail | null>(null)
  const [editTopic, setEditTopic] = useState('')
  const [editPersona, setEditPersona] = useState('')
  const [editInstructions, setEditInstructions] = useState('')
  const [contentMode, setContentMode] = useState<'preview' | 'edit'>('preview')
  const [contentText, setContentText] = useState('')

  useEffect(() => {
    listPersonas().then(r => {
      if ('personas' in r) {
        setPersonas(r.personas)
        setPersona(prev => prev || r.personas[0]?.id || '')
      }
    })
  }, [])

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }
  useEffect(() => stopPolling, [])

  useEffect(() => {
    stopPolling()
    setStatus(null)
    setLog(undefined)
    if (!activeItemId) { setItem(null); return }
    getItem(activeItemId).then(r => {
      if ('error' in r) { setStatus({ text: r.error, error: true }); return }
      setItem(r)
      setEditTopic(r.topic)
      setEditPersona(r.persona)
      setEditInstructions(r.instructions)
      setContentText(r.content)
      setContentMode('preview')
    })
  }, [activeItemId])

  // Shared by handleGenerate and handleRegenerate -- both submit a job and
  // poll GET .../runs/{run_id}/status the same way (see landDApi.ts),
  // differing only in what happens once it completes. Mirrors
  // UtilityAgentsPage's own startPolling helper.
  function startPolling(runId: string, onDone: (result: LandDItemDetail) => void | Promise<void>) {
    const poll = async () => {
      const runStatus: LandDRunStatus | { error: string } = await getRunStatus(runId)
      if (!('status' in runStatus)) {
        stopPolling(); setBusy(false); setStatus({ text: runStatus.error, error: true }); return
      }
      setLog(runStatus.log)
      if (runStatus.status === 'running') return
      stopPolling()
      setBusy(false)
      setLog(undefined)
      if (runStatus.status === 'error') {
        setStatus({ text: runStatus.error || 'Something went wrong.', error: true })
        return
      }
      setStatus(null)
      await onDone(runStatus.result!)
    }
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS)
    poll()
  }

  async function handleGenerate() {
    if (!topic.trim() || busy) return
    setBusy(true)
    setLog(undefined)
    setStatus({ text: 'Writing your content -- this calls Claude once...' })
    const started = await createItem(topic, persona, instructions)
    if ('error' in started) { setBusy(false); setStatus({ text: started.error, error: true }); return }
    startPolling(started.run_id, async (result) => {
      setTopic('')
      setInstructions('')
      onChanged()
      onSelect(result.item_id)
    })
  }

  async function handleRegenerate() {
    if (!activeItemId || busy) return
    const saveResult = await updateInput(activeItemId, editTopic, editPersona, editInstructions)
    if ('error' in saveResult) { setStatus({ text: saveResult.error, error: true }); return }
    setBusy(true)
    setLog(undefined)
    setStatus({ text: 'Regenerating content from your edited topic/instructions...' })
    const started = await regenerateItem(activeItemId)
    if ('error' in started) { setBusy(false); setStatus({ text: started.error, error: true }); return }
    startPolling(started.run_id, async (result) => {
      setItem(result)
      setContentText(result.content)
      setContentMode('preview')
      onChanged()
    })
  }

  async function handleSaveContent() {
    if (!activeItemId) return
    const result = await updateContent(activeItemId, contentText)
    if ('error' in result) { setStatus({ text: result.error, error: true }); return }
    setItem(prev => prev && { ...prev, content: contentText })
    setStatus({ text: 'Content saved.' })
    setContentMode('preview')
  }

  const personaLabel = (id: string) => personas.find(p => p.id === id)?.label || id

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-6">
      {!activeItemId ? (
        // ── Create view ──────────────────────────────────────────────
        <div className="mx-auto max-w-4xl rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Generate L&amp;D content</h2>
          <p className="mb-4 text-xs text-slate-500">
            Type a technical topic or use case. Pick the trainer persona that best matches what you need.
          </p>

          <Field label="Topic">
            <input
              value={topic} onChange={e => setTopic(e.target.value)}
              placeholder='e.g. "AWS EC2 — what is it, how do I set it up"'
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-500"
            />
          </Field>

          <Field label="Trainer persona">
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {personas.map(p => (
                <button
                  key={p.id}
                  onClick={() => setPersona(p.id)}
                  className={`rounded-lg border p-2.5 text-left transition-colors ${
                    persona === p.id ? 'border-sky-500 bg-sky-50' : 'border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <div className={`text-xs font-semibold ${persona === p.id ? 'text-sky-700' : 'text-slate-700'}`}>{p.label}</div>
                  <div className="mt-0.5 text-[11px] leading-snug text-slate-500">{p.description}</div>
                </button>
              ))}
            </div>
          </Field>

          <Field label="Additional instructions (optional)">
            <textarea
              value={instructions} onChange={e => setInstructions(e.target.value)} rows={10}
              placeholder="e.g. Keep it under 500 words, focus on the networking angle, target audience is QA engineers"
              className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-500"
            />
          </Field>

          <button
            onClick={handleGenerate}
            disabled={busy || !topic.trim()}
            className="mt-1 flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-40"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : null}
            Generate
          </button>

          {status && (
            <p className={`mt-3 text-xs ${status.error ? 'text-red-600' : 'text-slate-500'}`}>{status.text}</p>
          )}
          <ProgressLog log={log} />
        </div>
      ) : !item ? (
        <div className="mx-auto max-w-4xl rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading...</div>
      ) : (
        // ── Item view -- two columns: edit form on the left (fixed,
        // comfortable width), generated content on the right using
        // whatever's left of the panel (this is the long-lived reading
        // surface, so it's the one that should get the real estate). ──
        <div className="flex h-full gap-5">
          <div className="w-[380px] flex-shrink-0 overflow-y-auto">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Topic &amp; persona</p>
              <Field label="Topic">
                <input
                  value={editTopic} onChange={e => setEditTopic(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-500"
                />
              </Field>
              <Field label="Trainer persona">
                <div className="grid grid-cols-1 gap-2">
                  {personas.map(p => {
                    const isCurrent = p.id === editPersona
                    return (
                      <button
                        key={p.id}
                        onClick={() => setEditPersona(p.id)}
                        disabled={!isCurrent}
                        title={!isCurrent ? 'Persona is locked after creation -- start a new item to use a different persona.' : undefined}
                        className={`rounded-lg border p-2.5 text-left transition-colors ${
                          isCurrent ? 'border-sky-500 bg-sky-50' : 'cursor-not-allowed border-slate-200 opacity-40'
                        }`}
                      >
                        <div className={`text-xs font-semibold ${isCurrent ? 'text-sky-700' : 'text-slate-700'}`}>{p.label}</div>
                        <div className="mt-0.5 text-[11px] leading-snug text-slate-500">{p.description}</div>
                      </button>
                    )
                  })}
                </div>
              </Field>
              <p className="mb-3 -mt-1 text-[11px] text-slate-400">
                Persona is locked after creation -- start a new item (left sidebar) to use a different one.
              </p>
              <Field label="Additional instructions (optional)">
                <textarea
                  value={editInstructions} onChange={e => setEditInstructions(e.target.value)} rows={10}
                  className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-sky-500"
                />
              </Field>
              <button
                onClick={handleRegenerate}
                disabled={busy}
                title="Saves your edits, then regenerates the content from them -- one Claude call, no critique loop."
                className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-40"
              >
                {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Regenerate
              </button>
              {status && (
                <p className={`mt-3 text-xs ${status.error ? 'text-red-600' : 'text-slate-500'}`}>{status.text}</p>
              )}
              <ProgressLog log={log} />
            </div>
          </div>

          <div className="min-w-0 flex-1 overflow-y-auto">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Generated content ({personaLabel(item.persona)})
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setContentMode(m => (m === 'preview' ? 'edit' : 'preview'))}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                  >
                    {contentMode === 'preview' ? <><Pencil size={12} /> Edit</> : <><Eye size={12} /> Preview</>}
                  </button>
                  <a
                    href={downloadUrl(item.item_id)}
                    className="flex items-center gap-1 text-xs text-sky-600 hover:underline"
                  >
                    <Download size={12} /> Download .md
                  </a>
                </div>
              </div>

              {contentMode === 'edit' ? (
                <>
                  <textarea
                    value={contentText} onChange={e => setContentText(e.target.value)} rows={26}
                    className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-sky-500"
                  />
                  <button
                    onClick={handleSaveContent}
                    className="mt-3 flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
                  >
                    <Save size={14} /> Save content
                  </button>
                </>
              ) : (
                <div className="prose-ld">
                  <ReactMarkdown components={MARKDOWN_COMPONENTS}>{item.content}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      {children}
    </label>
  )
}

// Hand-styled Markdown rendering (no Tailwind typography plugin installed
// in this app) -- covers exactly the elements the personas' system prompts
// in LandDAgent/run.py are instructed to produce: headings, lists, fenced
// code, bold/italic, links.
const MARKDOWN_COMPONENTS = {
  h1: (p: any) => <h1 className="mb-3 mt-5 text-lg font-bold text-slate-800" {...p} />,
  h2: (p: any) => <h2 className="mb-2 mt-5 text-base font-bold text-slate-800" {...p} />,
  h3: (p: any) => <h3 className="mb-2 mt-4 text-sm font-semibold text-slate-800" {...p} />,
  p: (p: any) => <p className="mb-3 text-sm leading-relaxed text-slate-700" {...p} />,
  ul: (p: any) => <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-slate-700" {...p} />,
  ol: (p: any) => <ol className="mb-3 list-decimal space-y-1 pl-5 text-sm text-slate-700" {...p} />,
  li: (p: any) => <li className="leading-relaxed" {...p} />,
  strong: (p: any) => <strong className="font-semibold text-slate-800" {...p} />,
  a: (p: any) => <a className="text-sky-600 hover:underline" target="_blank" rel="noreferrer" {...p} />,
  blockquote: (p: any) => <blockquote className="mb-3 border-l-2 border-slate-300 pl-3 text-sm italic text-slate-500" {...p} />,
  code: ({ inline, ...p }: any) =>
    inline
      ? <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[12px] text-slate-800" {...p} />
      : <code className="block font-mono text-[12px] text-slate-800" {...p} />,
  pre: (p: any) => <pre className="mb-3 overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-3" {...p} />,
  hr: () => <hr className="my-4 border-slate-200" />,
}
