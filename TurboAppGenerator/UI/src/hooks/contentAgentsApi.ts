// Typed fetch wrappers for the ContentAgents backend, mounted in-process on
// this same server under /content-agents (see API/server.py and
// ContentAgents/ui/server.py's `router`). Ported from the original
// standalone ContentAgents app's api.ts — same endpoints, just every
// request/href prefixed with API_BASE since this now lives inside
// TurboAppGenerator's own single-page app instead of its own iframe.
// Workflow-tab types/functions live in workflowApi.ts instead -- Workflow is
// its own top-level backend module now, not part of ContentAgents.

export const API_BASE = '/content-agents'
export const apiUrl = (path: string): string => `${API_BASE}${path}`

export type Agent =
  | 'excel_parser' | 'pdf_parser' | 'image_parser' | 'media_parser' | 'site_crawler'
  | 'excel_creator' | 'pdf_creator' | 'ppt_creator' | 'visualization_agent' | 'video_creator'

export const READER_AGENTS: Agent[] = ['excel_parser', 'pdf_parser', 'image_parser', 'media_parser', 'site_crawler']
export const CREATOR_AGENTS: Agent[] = ['excel_creator', 'pdf_creator', 'ppt_creator', 'visualization_agent', 'video_creator']
export const LIBRARY_AGENTS: Agent[] = [...READER_AGENTS, 'excel_creator', 'pdf_creator', 'ppt_creator', 'visualization_agent', 'video_creator']

// Must match video_creator/run.py's VOICES -- local, offline Windows SAPI5
// voices only, no cloud TTS/API key/cost.
export const VIDEO_VOICES = ['David', 'Hazel', 'Zira'] as const

export interface LibraryItem {
  item_id: string
  agent: Agent
  filename: string
  uploaded_at: string
  // What was actually typed/asked to produce this item (see server.py's
  // library_create_item) -- only the fields that were actually submitted are
  // present, e.g. a video_creator item has brief/voice but not question.
  input?: { brief?: string; context?: string; question?: string; voice?: string; slides?: string }
}

export interface LibraryItemDetail extends LibraryItem {
  metadata: Record<string, unknown>
}

async function parseJsonSafe(resp: Response): Promise<any> {
  const raw = await resp.text()
  try {
    return JSON.parse(raw)
  } catch {
    return { error: raw.slice(0, 500) || `Request failed with HTTP ${resp.status}.` }
  }
}

async function request(url: string, init?: RequestInit): Promise<any> {
  const resp = await fetch(apiUrl(url), init)
  return parseJsonSafe(resp)
}

// --- Library ---

export function listLibraryItems(): Promise<{ items: LibraryItem[] }> {
  return request('/api/library/items')
}

export function getLibraryItem(itemId: string): Promise<LibraryItemDetail | { error: string }> {
  return request(`/api/library/items/${itemId}`)
}

// Generation runs in a background thread server-side and is polled, not
// awaited in one long request -- see server.py's LIBRARY_ITEM_RUNS. Needed
// because video_creator alone can take 5-20+ minutes; holding one HTTP
// request open that long previously blocked the WHOLE server (confirmed:
// a plain GET / hung for minutes during a real video generation), not just
// this one call, and gave the UI no way to show real progress meanwhile.
export interface LibraryItemRunStatus {
  status: 'running' | 'complete' | 'error'
  log: string[]
  // Present once status is 'complete': a single item, or several at once
  // for video_creator split mode -- see server.py's _create_video_series_items.
  result?: LibraryItemDetail | { items: LibraryItemDetail[] } | null
  error?: string | null
}

export function createLibraryItem(agent: Agent, fields: {
  file?: File
  url?: string
  max_pages?: number
  max_depth?: number
  keyframe_interval?: number
  brief?: string
  context?: string
  question?: string
  voice?: string
  split?: boolean
  slides?: number
}): Promise<{ run_id: string } | { error: string }> {
  const formData = new FormData()
  formData.append('agent', agent)
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined) formData.append(key, value instanceof File ? value : String(value))
  }
  return request('/api/library/items', { method: 'POST', body: formData })
}

export function getLibraryItemRunStatus(runId: string): Promise<LibraryItemRunStatus | { error: string }> {
  return request(`/api/library/items/runs/${runId}/status`)
}

// Convenience wrapper for callers that don't show their own live progress
// log (e.g. a Workflow canvas node's compact "attach a library item"
// control) -- submits, polls to completion internally, and resolves with
// the same shape createLibraryItem used to return directly, before
// generation moved to a background job. UtilityAgentsPage polls manually
// instead of using this, since it shows the log/status as the job runs.
export async function createLibraryItemAndWait(
  agent: Agent,
  fields: Parameters<typeof createLibraryItem>[1],
  onLog?: (log: string[]) => void,
): Promise<LibraryItemDetail | { items: LibraryItemDetail[] } | { error: string }> {
  const started = await createLibraryItem(agent, fields)
  if ('error' in started) return started
  // eslint-disable-next-line no-constant-condition
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 2000))
    const runStatus = await getLibraryItemRunStatus(started.run_id)
    if (!('status' in runStatus)) return runStatus
    onLog?.(runStatus.log)
    if (runStatus.status === 'running') continue
    if (runStatus.status === 'error') return { error: runStatus.error || 'Something went wrong.' }
    return runStatus.result!
  }
}

export function updateLibraryMetadata(itemId: string, metadata: string): Promise<{ ok: boolean } | { error: string }> {
  const formData = new FormData()
  formData.append('metadata', metadata)
  return request(`/api/library/items/${itemId}/metadata`, { method: 'PUT', body: formData })
}

// video_creator only -- re-renders original.mp4 directly from this item's
// CURRENT metadata.json (the storyboard, likely just hand-edited via the
// metadata panel/Save button) with no LLM call at all. Same run/poll
// pattern as createLibraryItem -- see getLibraryItemRunStatus.
export function rerenderVideoItem(itemId: string): Promise<{ run_id: string } | { error: string }> {
  return request(`/api/library/items/${itemId}/rerender`, { method: 'POST' })
}

// video_creator only -- a plain-English read view of the storyboard JSON,
// computed deterministically server-side (no LLM call). An alternative
// editing surface to the raw JSON for users who'd rather not risk breaking
// it by hand -- see server.py's storyboard_to_narrative.
export function getLibraryItemNarrative(itemId: string): Promise<{ narrative: string } | { error: string }> {
  return request(`/api/library/items/${itemId}/narrative`)
}

// video_creator only -- turns a hand-edited narrative back into an updated
// storyboard JSON via one targeted LLM call (not the full directing
// critique loop, so meaningfully faster). Saves the result to
// metadata.json but does NOT re-render -- call rerenderVideoItem afterward
// to actually produce the updated video. Same run/poll pattern as
// createLibraryItem -- see getLibraryItemRunStatus.
export function applyNarrativeEdit(itemId: string, narrative: string): Promise<{ run_id: string } | { error: string }> {
  const formData = new FormData()
  formData.append('narrative', narrative)
  return request(`/api/library/items/${itemId}/narrative`, { method: 'POST', body: formData })
}

// Re-runs pdf_parser's question-answering pass against an already-attached
// item's original file -- for reusing a pre-existing library item (the
// "pick existing" path never gets to ask a question up front) or for
// changing/adding a question after the fact without re-uploading.
export function reanswerLibraryItem(itemId: string, question: string): Promise<LibraryItemDetail | { error: string }> {
  const formData = new FormData()
  formData.append('question', question)
  return request(`/api/library/items/${itemId}/question`, { method: 'POST', body: formData })
}

export function deleteLibraryItem(itemId: string): Promise<{ ok: boolean }> {
  return request(`/api/library/items/${itemId}`, { method: 'DELETE' })
}

export function libraryDownloadUrl(itemId: string): string {
  return apiUrl(`/api/library/items/${itemId}/download`)
}

// --- Chat ---

export function startLibraryChat(itemId: string): Promise<{ chat_id: string; answer: string } | { error: string }> {
  return request(`/api/library/items/${itemId}/chat`, { method: 'POST' })
}

export function sendChatMessage(chatId: string, message: string): Promise<{ answer: string } | { error?: string; detail?: string }> {
  const formData = new FormData()
  formData.append('chat_id', chatId)
  formData.append('message', message)
  return request('/api/chat/message', { method: 'POST', body: formData })
}

export function endChat(chatId: string): Promise<{ ok: boolean }> {
  return request(`/api/chat/${chatId}`, { method: 'DELETE' })
}

// --- Local model picker (governs which Bedrock Claude model ContentAgents'
// own Claude-Code-CLI subprocess uses -- a distinct control from
// TurboAppGenerator's own global LiteLLM/Bedrock model picker in the header) ---

export interface ModelChoice { id: string; label: string }

export function listModels(): Promise<{ choices: ModelChoice[]; current: string }> {
  return request('/api/models')
}

export function selectModel(model: string): Promise<{ ok: boolean } | { error: string }> {
  return request('/api/models/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model }),
  })
}
