import { useEffect, useState } from 'react'
import { Handle, Position, useNodeConnections } from '@xyflow/react'
import { CheckCircle2, XCircle, Loader2, Download, Eye, FileCheck2, X, Globe, Trash2, Link2, HelpCircle, Play } from 'lucide-react'
import {
  Agent, READER_AGENTS, VIDEO_VOICES, LibraryItem, libraryDownloadUrl, listLibraryItems, createLibraryItemAndWait,
  getLibraryItem, reanswerLibraryItem,
} from '../../hooks/contentAgentsApi'
import { workflowApiUrl } from '../../hooks/workflowApi'
import { AGENT_META } from '../../components/ContentAgentsSidebar'
import ContentFileDropzone from '../../components/ContentFileDropzone'
import { Artifact, libraryItemArtifactKind } from '../../components/ArtifactPreview'
import ProgressLog from './ProgressLog'

const FILE_ACCEPT: Partial<Record<Agent, string>> = {
  excel_parser: '.xlsx',
  pdf_parser: '.pdf',
  image_parser: 'image/*',
  media_parser: 'video/*,audio/*',
}

// Only pdf_parser's own extraction prompt actually branches on a question
// today (see server.py's library_create_item) -- showing this field for
// agents that would silently ignore it would be misleading.
const SUPPORTS_QUESTION: Partial<Record<Agent, true>> = { pdf_parser: true }

// Agents whose output is meant to be viewed/played directly rather than
// saved-then-opened -- server.py serves their file inline (no forced
// download) for exactly this reason, see download_workflow_output.
const INLINE_VIEW_LABEL: Partial<Record<Agent, string>> = {
  visualization_agent: 'Open visualization ↗',
  video_creator: 'Open video ↗',
}

// What each creator agent's output actually is, for the multi-source
// combine-prompt placeholder below -- keeps that example accurate no matter
// which creator node it's shown on, instead of hardcoding one format (a
// stale "build a PPT" example showed up even on a Video Creator node).
const OUTPUT_NOUN: Partial<Record<Agent, string>> = {
  excel_creator: 'spreadsheet',
  pdf_creator: 'PDF report',
  visualization_agent: 'chart',
  video_creator: 'video',
}

export interface AgentNodeData extends Record<string, unknown> {
  agent: Agent
  libraryItemId?: string
  url?: string
  question?: string
  prompt?: string
  videoVoice?: string
  videoSplit?: boolean
  runStatus?: 'ok' | 'error' | 'running'
  runSummary?: string
  runLog?: string[]
  runDownload?: string
  runDownloads?: { label: string; url: string }[]
  onChange: (patch: Partial<AgentNodeData>) => void
  onDelete: () => void
  onPreview: (artifact: Artifact) => void
}

export default function AgentNode({ data }: { data: AgentNodeData }) {
  const { agent } = data
  const { label, icon: Icon } = AGENT_META[agent]
  const isReader = (READER_AGENTS as string[]).includes(agent)
  const isCrawler = agent === 'site_crawler'
  const supportsQuestion = !!SUPPORTS_QUESTION[agent]
  const incomingConnections = useNodeConnections({ handleType: 'target' })
  const [items, setItems] = useState<LibraryItem[]>([])
  // A dropped/picked file sits here first -- attachFile only actually runs
  // (and spends a Claude call) once the user explicitly clicks Run, so
  // dropping a file onto a not-yet-saved, not-yet-decided workflow never
  // silently kicks off work.
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [attachedName, setAttachedName] = useState<string | null>(null)
  const [attaching, setAttaching] = useState(false)
  const [attachError, setAttachError] = useState<string | null>(null)
  const [urlInput, setUrlInput] = useState('')
  // undefined = not loaded yet, null = loaded but no answer exists (outline
  // only). Fetched fresh whenever the attached item changes -- including
  // "pick existing", which never goes through attachFile -- so the question
  // box's status always reflects what's actually in that item's metadata,
  // not what the user merely typed into this box.
  const [answer, setAnswer] = useState<string | null | undefined>(undefined)
  const [reanswering, setReanswering] = useState(false)
  const [reanswerError, setReanswerError] = useState<string | null>(null)

  const refreshItems = () => {
    if (isReader) listLibraryItems().then((d) => setItems(d.items.filter((it) => it.agent === agent)))
  }
  useEffect(refreshItems, [agent])

  useEffect(() => {
    setReanswerError(null)
    if (!supportsQuestion || !data.libraryItemId) { setAnswer(undefined); return }
    let cancelled = false
    getLibraryItem(data.libraryItemId).then((d) => {
      if (cancelled) return
      setAnswer('error' in d ? undefined : ((d.metadata as Record<string, unknown>)?.answer as string | null | undefined) ?? null)
    })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.libraryItemId, supportsQuestion])

  async function askQuestion() {
    if (!data.libraryItemId) return
    setReanswering(true)
    setReanswerError(null)
    const result = await reanswerLibraryItem(data.libraryItemId, data.question ?? '')
    setReanswering(false)
    if ('error' in result) { setReanswerError(result.error); return }
    setAnswer(((result.metadata as Record<string, unknown>)?.answer as string | null | undefined) ?? null)
  }

  async function attachFile(file: File) {
    setAttaching(true)
    setAttachError(null)
    const result = await createLibraryItemAndWait(agent, { file, question: data.question || undefined })
    setAttaching(false)
    // "items" only ever comes back for a split video_creator request, which
    // reader nodes (the only callers of attachFile/attachUrl) never make --
    // guarded here just to satisfy the shared return type, not because it's
    // expected to trigger.
    if ('error' in result) { setAttachError(result.error); return }
    if ('items' in result) { setAttachError('Unexpected response from server.'); return }
    setAttachedName(result.filename)
    setPendingFile(null)
    data.onChange({ libraryItemId: result.item_id })
    refreshItems()
  }

  async function attachUrl() {
    if (!urlInput.trim()) return
    setAttaching(true)
    setAttachError(null)
    const result = await createLibraryItemAndWait(agent, { url: urlInput.trim(), max_pages: 20 })
    setAttaching(false)
    if ('error' in result) { setAttachError(result.error); return }
    if ('items' in result) { setAttachError('Unexpected response from server.'); return }
    setAttachedName(result.filename)
    data.onChange({ libraryItemId: result.item_id })
    refreshItems()
  }

  function clearAttachment() {
    setAttachedName(null)
    setAttachError(null)
    setPendingFile(null)
    data.onChange({ libraryItemId: undefined })
  }

  const attachedFilename = data.libraryItemId
    ? items.find((it) => it.item_id === data.libraryItemId)?.filename ?? attachedName
    : null

  return (
    <div className="w-72 rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center gap-2 rounded-t-xl border-b border-slate-200 bg-slate-50 px-3 py-2">
        <Icon size={15} className="shrink-0 text-indigo-500" />
        <span className="flex-1 truncate text-sm font-medium text-slate-800">{label}</span>
        <StatusIcon status={data.runStatus} />
        <button
          onClick={data.onDelete}
          title="Delete this step"
          className="shrink-0 rounded-md p-0.5 text-slate-400 hover:bg-slate-200 hover:text-red-500"
        >
          <Trash2 size={14} />
        </button>
      </div>

      <div className="p-3">
        {isReader ? (
          <div className="space-y-2">
            {supportsQuestion && !attaching && (
              // Shown for BOTH the not-yet-attached state (question applies
              // the moment attachFile runs) and the already-attached state
              // (question applies via the "Ask" button below, against the
              // item's own stored original file) -- so switching to "pick
              // existing" never silently drops the ability to ask one, and
              // the answer preview makes it obvious whether a question
              // actually took effect instead of leaving that to guesswork.
              <div className="space-y-1.5 rounded-md border border-slate-200 bg-slate-50 p-2">
                <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-slate-400">
                  <HelpCircle size={11} /> Question (optional)
                </div>
                <textarea
                  value={data.question ?? ''}
                  onChange={(e) => data.onChange({ question: e.target.value })}
                  placeholder='What should this pull out? e.g. "List every row with its name, category, and total as columns." Leave blank for a generic outline.'
                  rows={2}
                  className="w-full resize-none rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-indigo-500"
                />
                {data.libraryItemId && (
                  <>
                    <button
                      onClick={askQuestion}
                      disabled={reanswering}
                      className="flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
                    >
                      {reanswering && <Loader2 size={11} className="animate-spin" />} Ask
                    </button>
                    {!reanswering && answer !== undefined && (
                      answer === null ? (
                        <p className="text-[11px] italic text-amber-600">No question answered yet — this item only has a generic outline.</p>
                      ) : (
                        <p className="text-[11px] text-slate-500">Answer: {answer.length > 160 ? `${answer.slice(0, 160)}…` : answer}</p>
                      )
                    )}
                    {reanswerError && <p className="text-[11px] text-red-500">{reanswerError}</p>}
                  </>
                )}
              </div>
            )}

            {data.libraryItemId ? (
              // A source is attached (either just uploaded/crawled here, or picked from the library) --
              // show a compact summary instead of the pickers.
              <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-2">
                <FileCheck2 size={14} className="shrink-0 text-emerald-500" />
                <span className="flex-1 truncate text-xs text-emerald-700">{attachedFilename ?? data.libraryItemId}</span>
                {!isCrawler && (
                  <button
                    onClick={() => data.onPreview({
                      url: libraryDownloadUrl(data.libraryItemId!), title: attachedFilename ?? label,
                      kind: libraryItemArtifactKind(agent, attachedFilename ?? ''),
                    })}
                    className="text-slate-400 hover:text-indigo-600" title="Preview"
                  >
                    <Eye size={13} />
                  </button>
                )}
                <button onClick={clearAttachment} className="text-slate-400 hover:text-slate-600" title="Change source">
                  <X size={13} />
                </button>
              </div>
            ) : attaching ? (
              <div className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-4 text-xs text-slate-500">
                <Loader2 size={14} className="animate-spin" /> Adding to library…
              </div>
            ) : isCrawler ? (
              <div className="flex gap-1.5">
                <input
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://example.com"
                  className="flex-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-indigo-500"
                />
                <button onClick={attachUrl} className="flex items-center gap-1 rounded-md bg-indigo-600 px-2 text-xs font-medium text-white hover:bg-indigo-500">
                  <Globe size={12} /> Crawl
                </button>
              </div>
            ) : pendingFile ? (
              <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
                <span className="flex-1 truncate text-xs text-slate-700">{pendingFile.name}</span>
                <button onClick={() => setPendingFile(null)} className="text-slate-400 hover:text-slate-600" title="Remove">
                  <X size={13} />
                </button>
                <button onClick={() => attachFile(pendingFile)} className="flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500">
                  <Play size={12} /> Run
                </button>
              </div>
            ) : (
              <ContentFileDropzone compact accept={FILE_ACCEPT[agent]} onFile={setPendingFile} />
            )}

            {attachError && <p className="text-xs text-red-500">{attachError}</p>}

            {items.length > 0 && !attaching && !data.libraryItemId && (
              <>
                <p className="text-center text-[10px] uppercase tracking-wider text-slate-400">or pick existing</p>
                <select
                  value=""
                  onChange={(e) => e.target.value && data.onChange({ libraryItemId: e.target.value })}
                  className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-indigo-500"
                >
                  <option value="">Select a library item…</option>
                  {items.map((it) => <option key={it.item_id} value={it.item_id}>{it.filename}</option>)}
                </select>
              </>
            )}
          </div>
        ) : (
          <>
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-400">
              <Link2 size={11} />
              {incomingConnections.length === 0
                ? 'No sources connected yet'
                : `${incomingConnections.length} source${incomingConnections.length > 1 ? 's' : ''} connected`}
            </div>
            <textarea
              value={data.prompt ?? ''}
              onChange={(e) => data.onChange({ prompt: e.target.value })}
              placeholder={
                incomingConnections.length > 1
                  ? `How should the connected sources be combined into the final output? e.g. "Cross-reference the Excel budget with the PDF report to build the final ${OUTPUT_NOUN[agent] ?? 'output'}."`
                  : 'What should this step do with the content?'
              }
              rows={incomingConnections.length > 1 ? 5 : 3}
              className="w-full resize-none rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-indigo-500"
            />
            {agent === 'video_creator' && (
              <>
                <select
                  value={data.videoVoice ?? ''}
                  onChange={(e) => data.onChange({ videoVoice: e.target.value || undefined })}
                  className="mt-1.5 w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 outline-none focus:border-indigo-500"
                >
                  <option value="">No narration (silent video)</option>
                  {VIDEO_VOICES.map((v) => <option key={v} value={v}>{v} narration voice</option>)}
                </select>
                <label className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={!!data.videoSplit}
                    onChange={(e) => data.onChange({ videoSplit: e.target.checked || undefined })}
                  />
                  Split into ~5-minute parts instead of one long video
                </label>
              </>
            )}
          </>
        )}

        {data.runSummary && (
          <p className={`mt-2 text-xs ${data.runStatus === 'error' ? 'text-red-500' : 'text-slate-500'}`}>{data.runSummary}</p>
        )}
        <ProgressLog log={data.runLog} />
        {data.runDownloads && data.runDownloads.length > 0 ? (
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
            {data.runDownloads.map((d) => (
              <span key={d.url} className="flex items-center gap-2">
                <a href={workflowApiUrl(d.url)} target="_blank" rel="noreferrer"
                   className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
                  <Download size={12} /> {d.label}
                </a>
                <button onClick={() => data.onPreview({
                          url: workflowApiUrl(d.url), title: `${label} – ${d.label}`,
                          kind: libraryItemArtifactKind(agent, ''),
                        })}
                        className="flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600" title="Preview">
                  <Eye size={12} />
                </button>
              </span>
            ))}
          </div>
        ) : data.runDownload && (
          <div className="mt-1 flex items-center gap-2">
            {INLINE_VIEW_LABEL[agent] ? (
              <a href={workflowApiUrl(data.runDownload)} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
                <Download size={12} /> {INLINE_VIEW_LABEL[agent]}
              </a>
            ) : (
              <a href={workflowApiUrl(data.runDownload)} download className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
                <Download size={12} /> Download output
              </a>
            )}
            <button onClick={() => data.onPreview({ url: workflowApiUrl(data.runDownload!), title: label, kind: libraryItemArtifactKind(agent, '') })}
                    className="flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600" title="Preview">
              <Eye size={12} /> Preview
            </button>
          </div>
        )}
      </div>

      {isReader && <Handle type="source" position={Position.Right} />}
      {!isReader && <Handle type="target" position={Position.Left} />}
    </div>
  )
}

function StatusIcon({ status }: { status?: 'ok' | 'error' | 'running' }) {
  if (status === 'running') return <Loader2 size={14} className="ml-auto animate-spin text-slate-400" />
  if (status === 'ok') return <CheckCircle2 size={14} className="ml-auto text-emerald-500" />
  if (status === 'error') return <XCircle size={14} className="ml-auto text-red-500" />
  return null
}
