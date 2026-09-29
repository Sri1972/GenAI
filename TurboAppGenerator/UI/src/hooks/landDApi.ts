// Typed fetch wrappers for the Tech L&D Agent backend, mounted in-process on
// this same server under /land-d (see API/server.py and
// LandDAgent/l_and_d_server.py's `router`). Self-contained -- LandDAgent is
// its own top-level module (like WebUIGenerator/WebAPIGenerator/
// MCPGenerator), not part of ContentAgents, so this doesn't extend
// contentAgentsApi.ts even though the generate/poll/edit shape is similar.

export const LAND_D_API_BASE = '/land-d'
const apiUrl = (path: string): string => `${LAND_D_API_BASE}${path}`

export interface Persona {
  id: string
  label: string
  description: string
}

export interface LandDItem {
  item_id: string
  title: string
  topic: string
  persona: string
  instructions: string
  created_at: string
}

export interface LandDItemDetail extends LandDItem {
  content: string
}

// Generation/regeneration run in a background thread server-side and are
// polled, not awaited in one long request -- same reasoning as
// ContentAgents' LibraryItemRunStatus (see contentAgentsApi.ts): an LLM call
// inside an `async def` route would block this whole process's event loop.
export interface LandDRunStatus {
  status: 'running' | 'complete' | 'error'
  log: string[]
  result?: LandDItemDetail | null
  error?: string | null
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

export function listPersonas(): Promise<{ personas: Persona[] } | { error: string }> {
  return request('/api/personas')
}

export function listItems(): Promise<{ items: LandDItem[] } | { error: string }> {
  return request('/api/items')
}

export function getItem(itemId: string): Promise<LandDItemDetail | { error: string }> {
  return request(`/api/items/${itemId}`)
}

export function createItem(topic: string, persona: string, instructions: string): Promise<{ run_id: string } | { error: string }> {
  const formData = new FormData()
  formData.append('topic', topic)
  formData.append('persona', persona)
  formData.append('instructions', instructions)
  return request('/api/items', { method: 'POST', body: formData })
}

export function getRunStatus(runId: string): Promise<LandDRunStatus | { error: string }> {
  return request(`/api/items/runs/${runId}/status`)
}

// Direct edit-and-save of the generated Markdown -- no LLM call.
export function updateContent(itemId: string, content: string): Promise<{ ok: boolean } | { error: string }> {
  const formData = new FormData()
  formData.append('content', content)
  return request(`/api/items/${itemId}`, { method: 'PUT', body: formData })
}

// Updates the saved topic/persona/instructions only -- call right before
// regenerateItem(), same save-then-render two-step as video_creator's
// rerender-from-JSON flow in contentAgentsApi.ts.
export function updateInput(itemId: string, topic: string, persona: string, instructions: string): Promise<{ ok: boolean } | { error: string }> {
  const formData = new FormData()
  formData.append('topic', topic)
  formData.append('persona', persona)
  formData.append('instructions', instructions)
  return request(`/api/items/${itemId}/input`, { method: 'PUT', body: formData })
}

export function regenerateItem(itemId: string): Promise<{ run_id: string } | { error: string }> {
  return request(`/api/items/${itemId}/regenerate`, { method: 'POST' })
}

export function deleteItem(itemId: string): Promise<{ ok: boolean }> {
  return request(`/api/items/${itemId}`, { method: 'DELETE' })
}

export function downloadUrl(itemId: string): string {
  return apiUrl(`/api/items/${itemId}/download`)
}
