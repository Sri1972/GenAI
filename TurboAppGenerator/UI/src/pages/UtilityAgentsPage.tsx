import { useEffect, useRef, useState } from 'react'
import { Trash2, Eye, FolderOpen, UploadCloud, Save, MessageSquarePlus, Loader2, ExternalLink, Clapperboard } from 'lucide-react'
import {
  Agent, LibraryItem, LibraryItemDetail, VIDEO_VOICES, applyNarrativeEdit, createLibraryItem, deleteLibraryItem,
  getLibraryItem, getLibraryItemNarrative, getLibraryItemRunStatus, libraryDownloadUrl, listLibraryItems,
  rerenderVideoItem, startLibraryChat, updateLibraryMetadata,
} from '../hooks/contentAgentsApi'
import { AGENT_META } from '../components/ContentAgentsSidebar'
import { Artifact, libraryItemArtifactKind } from '../components/ArtifactPreview'
import ConfirmDialog from '../components/ConfirmDialog'
import ContentChatPanel from '../components/ContentChatPanel'
import ContentFileDropzone from '../components/ContentFileDropzone'
import ContentModelPicker from '../components/ContentModelPicker'
import RightPreviewPanel from '../components/RightPreviewPanel'
import ProgressLog from '../workflows/nodes/ProgressLog'

// How often the Utility Agents tab polls a running job's status -- same
// cadence as the Workflow canvas's own polling (see WorkflowPage.tsx), so
// both surfaces feel consistent.
const POLL_INTERVAL_MS = 2000

const FILE_ACCEPT: Partial<Record<Agent, string>> = {
  excel_parser: '.xlsx',
  pdf_parser: '.pdf',
  image_parser: 'image/*',
  media_parser: 'video/*,audio/*',
}

// Agents whose output is meant to be viewed/played directly rather than
// saved-then-opened -- server.py serves their file inline (no forced
// download) for exactly this reason, see library_download_item.
const INLINE_VIEW_LABEL: Partial<Record<Agent, string>> = {
  visualization_agent: 'Open visualization ↗',
  video_creator: 'Open video ↗',
}

export default function UtilityAgentsPage({ agent }: { agent: Agent }) {
  const meta = AGENT_META[agent]
  const [preview, setPreview] = useState<Artifact | null>(null)

  // Switching agents leaves any previous agent's preview behind otherwise.
  useEffect(() => setPreview(null), [agent])

  return (
    <RightPreviewPanel
      artifact={preview}
      onClose={() => setPreview(null)}
      main={
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-3xl">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 className="mb-1 text-base font-semibold text-slate-800">{meta.label}</h2>
                <p className="text-sm text-slate-500">
                  Persisted library: add once, review/edit the drafted metadata, then chat about it anytime.
                </p>
              </div>
              <ContentModelPicker />
            </div>
          </div>
          <AgentWorkspace agent={agent} onPreview={setPreview} />
        </div>
      }
    />
  )
}

// ── Library-backed agents (upload/crawl/brief -> metadata -> chat) ──────────

function AgentWorkspace({ agent, onPreview }: { agent: Agent; onPreview: (a: Artifact) => void }) {
  const [items, setItems] = useState<LibraryItem[]>([])
  const [currentItemId, setCurrentItemId] = useState<string | null>(null)
  const [currentInput, setCurrentInput] = useState<LibraryItem['input'] | null>(null)
  const [metadataText, setMetadataText] = useState('')
  // video_creator only -- an alternative, plain-English editing surface for
  // the storyboard JSON above (see server.py's storyboard_to_narrative).
  // Reset to 'json'/blank whenever metadataText is freshly set from the
  // server (new item opened, generated, or re-rendered) since a narrative
  // fetched for a PRIOR storyboard would otherwise silently go stale.
  const [metadataView, setMetadataView] = useState<'json' | 'narrative'>('json')
  const [narrativeText, setNarrativeText] = useState('')
  const [narrativeLoading, setNarrativeLoading] = useState(false)
  const [chat, setChat] = useState<{ chatId: string; answer: string } | null>(null)
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null)
  // Guards handleAdd against being re-entered while its request is still
  // in flight -- canAdd below only reflects whether the form is FILLED IN,
  // not whether a submission is currently running, so without this the
  // "Add to library" button stayed clickable (and looked "done") the whole
  // time a slow request (e.g. video_creator's real render, up to a minute)
  // was still working server-side.
  const [adding, setAdding] = useState(false)
  // Live progress lines from the background job while `adding` is true --
  // see server.py's LIBRARY_ITEM_RUNS/on_progress. `pollRef` holds the
  // setInterval handle so handleAdd/the agent-switch effect/unmount can all
  // stop it -- generation keeps running server-side either way (it's a
  // detached background thread), this only stops US watching it.
  const [log, setLog] = useState<string[] | undefined>(undefined)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const [file, setFile] = useState<File | null>(null)
  const [url, setUrl] = useState('')
  const [maxPages, setMaxPages] = useState('20')
  const [brief, setBrief] = useState('')
  const [context, setContext] = useState('')
  const [question, setQuestion] = useState('')
  const [voice, setVoice] = useState('')
  const [split, setSplit] = useState(false)
  const [slides, setSlides] = useState('')

  const isCrawler = agent === 'site_crawler'
  const isVizAgent = agent === 'visualization_agent'
  const isVideoAgent = agent === 'video_creator'
  const isPptAgent = agent === 'ppt_creator'
  const isCreator = agent === 'excel_creator' || agent === 'pdf_creator' || agent === 'video_creator'
  // Only pdf_parser's own extraction prompt branches on a question today
  // (see server.py's library_create_item) -- showing this for agents that
  // would silently ignore it would be misleading.
  const supportsQuestion = agent === 'pdf_parser'

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  useEffect(() => {
    stopPolling()
    setCurrentItemId(null)
    setCurrentInput(null)
    setChat(null)
    setStatus(null)
    setAdding(false)
    setLog(undefined)
    setFile(null)
    setUrl('')
    setBrief('')
    setContext('')
    setQuestion('')
    setVoice('')
    setSplit(false)
    setSlides('')
    refreshList()
    return stopPolling
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent])

  async function refreshList() {
    const data = await listLibraryItems()
    setItems(data.items.filter((it) => it.agent === agent))
  }

  async function handleAdd() {
    if (adding) return
    setAdding(true)
    setLog(undefined)
    // Generation runs server-side in a background thread and is polled
    // below (see server.py's LIBRARY_ITEM_RUNS) -- this call itself returns
    // almost immediately with a run_id, it does NOT wait for the actual
    // work. video_creator's render step is real per-frame headless-browser
    // rendering + ffmpeg encoding (5-20+ minutes for a real video), so the
    // live log underneath is what actually shows it's working, not this
    // static line -- this is just the initial framing while the first
    // status poll is still in flight.
    setStatus({
      text: isVideoAgent && split
        ? 'Writing and rendering the video in ~5-minute parts -- this can take several minutes, longer with more parts...'
        : agent === 'video_creator'
        ? 'Directing the video, then rendering it -- this can take several minutes...'
        : 'Adding to library and drafting metadata... this calls Claude once.',
    })
    const started = isCrawler
      ? await createLibraryItem(agent, { url, max_pages: Number(maxPages) || 20 })
      : isVizAgent
      ? await createLibraryItem(agent, { brief, context: context || undefined, file: file || undefined })
      : isPptAgent
      ? await createLibraryItem(agent, { brief, file: file || undefined, slides: slides ? Number(slides) : undefined })
      : isCreator
      ? await createLibraryItem(agent, {
          brief, context: context || undefined,
          voice: isVideoAgent ? (voice || undefined) : undefined,
          split: isVideoAgent ? split : undefined,
        })
      : await createLibraryItem(agent, { file: file!, question: question || undefined })

    if ('error' in started) { setAdding(false); setStatus({ text: started.error, error: true }); return }

    startPolling(started.run_id, async (result) => {
      setFile(null); setUrl(''); setBrief(''); setContext(''); setQuestion(''); setVoice(''); setSplit(false); setSlides('')
      await refreshList()
      if ('items' in result) {
        // Split mode created several items at once -- nothing single to open
        // into the metadata panel below, so just confirm what happened and
        // let the user pick individual parts from "Previously added".
        setStatus({ text: `Created ${result.items.length} video part(s) -- see them below in "Previously added".` })
        setCurrentItemId(null)
        setCurrentInput(null)
        if (result.items.length > 0) {
          onPreview({
            url: libraryDownloadUrl(result.items[0].item_id), title: result.items[0].filename,
            kind: libraryItemArtifactKind(agent, result.items[0].filename),
          })
        }
        return
      }
      setCurrentItemId(result.item_id)
      setCurrentInput(result.input ?? null)
      setMetadataText(JSON.stringify(result.metadata, null, 2))
      setMetadataView('json')
      onPreview({ url: libraryDownloadUrl(result.item_id), title: result.filename, kind: libraryItemArtifactKind(agent, result.filename) })
    })
  }

  // Shared by handleAdd and handleRerenderVideo -- both submit a job and
  // poll GET .../runs/{run_id}/status the same way (see server.py's
  // LIBRARY_ITEM_RUNS), differing only in what happens once it completes.
  function startPolling(runId: string, onDone: (result: LibraryItemDetail | { items: LibraryItemDetail[] }) => void | Promise<void>) {
    const poll = async () => {
      const runStatus = await getLibraryItemRunStatus(runId)
      // A plain fetch-level failure (`{ error }`, from parseJsonSafe) never
      // has a `status` field -- a real LibraryItemRunStatus always does,
      // even when ITS OWN status is "error". Checking for `status`'s
      // absence (rather than `error`'s presence, which both shapes could
      // have) is what lets TS narrow `runStatus.error` to a plain `string`
      // in this branch instead of `string | null | undefined`.
      if (!('status' in runStatus)) {
        stopPolling(); setAdding(false); setStatus({ text: runStatus.error, error: true }); return
      }
      setLog(runStatus.log)
      if (runStatus.status === 'running') return
      stopPolling()
      setAdding(false)
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

  async function handleRerenderVideo() {
    if (!currentItemId || adding) return
    // Save whatever's in the textarea right now first, so the render uses
    // the actual current edit, not a stale on-disk copy from before it.
    const saveResult = await updateLibraryMetadata(currentItemId, metadataText)
    if ('error' in saveResult) { setStatus({ text: saveResult.error, error: true }); return }
    setAdding(true)
    setLog(undefined)
    setStatus({ text: 'Re-rendering the video from this storyboard JSON...' })
    const started = await rerenderVideoItem(currentItemId)
    if ('error' in started) { setAdding(false); setStatus({ text: started.error, error: true }); return }
    startPolling(started.run_id, async (result) => {
      await refreshList()
      if ('items' in result) return // never happens for a single-item rerender
      setMetadataText(JSON.stringify(result.metadata, null, 2))
      setMetadataView('json')
      // Cache-bust -- the download URL is otherwise identical to the one
      // already showing in the preview panel, so the browser would happily
      // keep showing the OLD cached video instead of fetching the new one.
      onPreview({
        url: `${libraryDownloadUrl(result.item_id)}?t=${Date.now()}`, title: result.filename,
        kind: libraryItemArtifactKind(agent, result.filename),
      })
    })
  }

  // Switching to the narrative tab -- saves whatever's in the JSON textarea
  // first (same reasoning as handleRerenderVideo: the narrative is computed
  // server-side from metadata.json on disk, so a stale on-disk copy would
  // silently show the WRONG narrative otherwise), then fetches the
  // deterministic plain-English view of it.
  async function handleShowNarrative() {
    if (!currentItemId) return
    const saveResult = await updateLibraryMetadata(currentItemId, metadataText)
    if ('error' in saveResult) { setStatus({ text: saveResult.error, error: true }); return }
    setMetadataView('narrative')
    setNarrativeLoading(true)
    const result = await getLibraryItemNarrative(currentItemId)
    setNarrativeLoading(false)
    if ('error' in result) { setStatus({ text: result.error, error: true }); return }
    setNarrativeText(result.narrative)
  }

  // Turns the (possibly hand-edited) narrative back into an updated
  // storyboard JSON via one targeted LLM call -- see server.py's
  // apply_narrative. This only updates metadata.json, it does NOT
  // re-render -- switches back to the JSON tab afterward so the user can
  // review the result, then use "Re-render video from this JSON" to
  // actually produce the updated video.
  async function handleApplyNarrative() {
    if (!currentItemId || adding) return
    setAdding(true)
    setLog(undefined)
    setStatus({ text: 'Updating the storyboard JSON from your edited narrative...' })
    const started = await applyNarrativeEdit(currentItemId, narrativeText)
    if ('error' in started) { setAdding(false); setStatus({ text: started.error, error: true }); return }
    startPolling(started.run_id, async (result) => {
      await refreshList()
      if ('items' in result) return // never happens for a narrative edit
      setMetadataText(JSON.stringify(result.metadata, null, 2))
      setMetadataView('json')
      setStatus({ text: 'Storyboard JSON updated from the narrative -- review it, then re-render to update the video.' })
    })
  }

  async function handleOpen(itemId: string) {
    const data = await getLibraryItem(itemId)
    if ('error' in data) { setStatus({ text: data.error, error: true }); return }
    setCurrentItemId(itemId)
    setCurrentInput(data.input ?? null)
    setMetadataText(JSON.stringify(data.metadata, null, 2))
    setMetadataView('json')
    setChat(null)
    onPreview({ url: libraryDownloadUrl(itemId), title: data.filename, kind: libraryItemArtifactKind(agent, data.filename) })
  }

  async function handleDelete(itemId: string) {
    setConfirmDeleteId(null)
    await deleteLibraryItem(itemId)
    if (currentItemId === itemId) { setCurrentItemId(null); setCurrentInput(null); setChat(null) }
    refreshList()
  }

  async function handleSaveMetadata() {
    if (!currentItemId) return
    const result = await updateLibraryMetadata(currentItemId, metadataText)
    setStatus('error' in result ? { text: result.error, error: true } : { text: 'Metadata saved.' })
  }

  async function handleStartChat() {
    if (!currentItemId) return
    setStatus({ text: 'Starting chat with this metadata...' })
    const result = await startLibraryChat(currentItemId)
    setStatus(null)
    if ('error' in result) { setStatus({ text: result.error, error: true }); return }
    setChat({ chatId: result.chat_id, answer: result.answer })
  }

  const canAdd = isCrawler ? !!url.trim()
    : isVizAgent ? !!brief.trim()
    : isPptAgent ? !!brief.trim()
    : isCreator ? !!brief.trim()
    : !!file

  return (
    <>
    <div className="mx-auto max-w-3xl">
      <div className="rounded-xl border border-slate-200 bg-white p-5">
        {isCrawler ? (
          <>
            <Field label="Start URL">
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com"
                     className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
            <Field label="Max pages">
              <input value={maxPages} onChange={(e) => setMaxPages(e.target.value)} type="number"
                     className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
          </>
        ) : isVizAgent ? (
          <>
            <Field label="What should this visualize?">
              <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={2}
                        placeholder="e.g. Revenue by region over the last 6 months, or Top 50 most populous countries"
                        className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
            <Field label="Data file (.csv, .json, or .xlsx) (optional)">
              <ContentFileDropzone accept=".csv,.json,.xlsx" fileName={file?.name} onFile={setFile} />
            </Field>
            <p className="my-2 text-center text-[11px] uppercase tracking-wider text-slate-400">or paste data instead</p>
            <Field label="Pasted data (CSV or JSON) (optional)">
              <textarea value={context} onChange={(e) => setContext(e.target.value)} rows={4}
                        placeholder={'name,revenue\nEast,1000\nWest,800'}
                        className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
            <p className="mb-3 text-xs text-slate-400">
              Leave both blank and Claude will try to supply well-known data itself (e.g. public statistics) --
              it'll say so plainly in the result rather than guess if it doesn't actually know the answer.
            </p>
          </>
        ) : isPptAgent ? (
          <>
            <Field label="Content brief">
              <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={3}
                        placeholder="What should the deck be about?"
                        className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
            <Field label="Target slide count (optional)">
              <input value={slides} onChange={(e) => setSlides(e.target.value)} type="number" placeholder="e.g. 6"
                     className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
            <Field label="Template (.pptx or .pdf, optional)">
              <ContentFileDropzone accept=".pptx,.pdf" fileName={file?.name} onFile={setFile} />
            </Field>
          </>
        ) : isCreator ? (
          <>
            <Field label="Content brief">
              <textarea value={brief} onChange={(e) => setBrief(e.target.value)} rows={3}
                        placeholder="What should this file contain?"
                        className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
            <Field label="Reference content (optional)">
              <textarea value={context} onChange={(e) => setContext(e.target.value)} rows={3}
                        placeholder="Paste content from another source to base this on"
                        className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
            </Field>
            {isVideoAgent && (
              <Field label="Narration voice (optional)">
                <select value={voice} onChange={(e) => setVoice(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500">
                  <option value="">No narration (silent video)</option>
                  {VIDEO_VOICES.map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </Field>
            )}
            {isVideoAgent && (
              <label className="mb-3 flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={split} onChange={(e) => setSplit(e.target.checked)} />
                Split into ~5-minute videos instead of one long video (each part ends at a natural point, e.g. 4:56 or 5:10)
              </label>
            )}
          </>
        ) : (
          <>
            {supportsQuestion && (
              <Field label="Question (optional)">
                <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2}
                          placeholder='What should this pull out? e.g. "List every row with its name, category, and total as columns." Leave blank for a generic outline.'
                          className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500" />
              </Field>
            )}
            <Field label="Upload a file to the library">
              <ContentFileDropzone accept={FILE_ACCEPT[agent]} fileName={file?.name} onFile={setFile} />
            </Field>
          </>
        )}
        <button
          onClick={handleAdd}
          disabled={!canAdd || adding}
          className="mt-2 flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
        >
          {adding ? <Loader2 size={15} className="animate-spin" /> : <UploadCloud size={15} />}
          {adding ? 'Working...' : 'Add to library'}
        </button>
      </div>

      {status && (
        <p className={`mt-3 text-sm ${status.error ? 'text-red-500' : 'text-slate-500 italic'}`}>{status.text}</p>
      )}
      <ProgressLog log={log} />

      <div className="mt-5">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Previously added</p>
        {items.length === 0 ? (
          <p className="text-sm text-slate-500">No items yet.</p>
        ) : (
          <div className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white">
            {items.map((it) => (
              <div key={it.item_id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <span className="flex-1 truncate text-slate-700">{it.filename}</span>
                <span className="text-xs text-slate-400">{new Date(it.uploaded_at).toLocaleString()}</span>
                <button onClick={() => onPreview({ url: libraryDownloadUrl(it.item_id), title: it.filename, kind: libraryItemArtifactKind(agent, it.filename) })}
                        title="Preview" className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-indigo-600">
                  <Eye size={14} />
                </button>
                <a href={libraryDownloadUrl(it.item_id)} target="_blank" rel="noreferrer"
                   title={INLINE_VIEW_LABEL[agent] ?? 'Download file'}
                   className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50">
                  <ExternalLink size={14} />
                </a>
                <button onClick={() => handleOpen(it.item_id)} className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-700"><FolderOpen size={14} /> Open</button>
                <button onClick={() => setConfirmDeleteId(it.item_id)} className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-red-500 hover:bg-red-50"><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
        )}
      </div>

      {currentItemId && (
        <div className="mt-5 rounded-xl border border-slate-200 bg-white p-5">
          {currentInput && Object.keys(currentInput).length > 0 && (
            <div className="mb-4 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Original request</p>
              {(Object.entries(currentInput) as [string, string][]).map(([key, value]) => (
                <div key={key}>
                  <p className="text-[10px] uppercase tracking-wider text-slate-400">{key}</p>
                  <p className="whitespace-pre-wrap text-xs text-slate-600">{value}</p>
                </div>
              ))}
            </div>
          )}
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                {isVideoAgent
                  ? metadataView === 'narrative'
                    ? 'Narrative (plain-English — edit this instead of the JSON, then update)'
                    : 'Storyboard JSON (exactly what the video was directed+rendered from — edit freely, then Save)'
                  : 'Metadata (LLM-drafted — edit freely, then Save)'}
              </p>
              {isVideoAgent && (
                <div className="flex overflow-hidden rounded-md border border-slate-300 text-xs">
                  <button
                    onClick={() => setMetadataView('json')}
                    className={`px-2 py-1 ${metadataView === 'json' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
                  >
                    JSON
                  </button>
                  <button
                    onClick={handleShowNarrative}
                    className={`px-2 py-1 ${metadataView === 'narrative' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
                  >
                    Narrative
                  </button>
                </div>
              )}
            </div>
            <a href={libraryDownloadUrl(currentItemId)} target="_blank" rel="noreferrer" className="text-xs text-indigo-600 hover:underline">
              {INLINE_VIEW_LABEL[agent] ?? 'Download file'}
            </a>
          </div>
          {isVideoAgent && metadataView === 'narrative' ? (
            <>
              {narrativeLoading ? (
                <div className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-8 text-sm text-slate-400">
                  <Loader2 size={14} className="animate-spin" /> Loading narrative...
                </div>
              ) : (
                <textarea
                  value={narrativeText}
                  onChange={(e) => setNarrativeText(e.target.value)}
                  rows={14}
                  className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500"
                />
              )}
              <div className="mt-3 flex gap-2">
                <button
                  onClick={handleApplyNarrative}
                  disabled={adding || narrativeLoading}
                  title="Turns your edited narrative back into the storyboard JSON via one targeted Claude call -- no critique loop, so faster than directing from scratch. Re-render the video afterward to see it."
                  className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-40"
                >
                  {adding ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Update JSON from narrative
                </button>
              </div>
            </>
          ) : (
            <>
              <textarea
                value={metadataText}
                onChange={(e) => setMetadataText(e.target.value)}
                rows={14}
                className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-indigo-500"
              />
              <div className="mt-3 flex gap-2">
                <button onClick={handleSaveMetadata} className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"><Save size={14} /> Save metadata</button>
                {isVideoAgent && (
                  <button
                    onClick={handleRerenderVideo}
                    disabled={adding}
                    title="Renders the video again straight from this JSON -- no directing/Claude call, just the deterministic render step."
                    className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-40"
                  >
                    {adding ? <Loader2 size={14} className="animate-spin" /> : <Clapperboard size={14} />} Re-render video from this JSON
                  </button>
                )}
                <button onClick={handleStartChat} className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500">
                  <MessageSquarePlus size={14} /> Start chat with this metadata
                </button>
              </div>
            </>
          )}
          {chat && <ContentChatPanel chatId={chat.chatId} initialAnswer={chat.answer} onNewChat={() => setChat(null)} />}
        </div>
      )}
    </div>

    <ConfirmDialog
      open={!!confirmDeleteId}
      title={`Delete "${items.find((it) => it.item_id === confirmDeleteId)?.filename ?? ''}"?`}
      message="This library item and its files will be permanently removed."
      details={['This cannot be undone.']}
      confirmLabel="Delete"
      danger
      onConfirm={() => confirmDeleteId && handleDelete(confirmDeleteId)}
      onCancel={() => setConfirmDeleteId(null)}
    />
    </>
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
