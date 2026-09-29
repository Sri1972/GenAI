// Typed fetch wrappers for the Data Quality Agent backend, mounted
// in-process on this same server under /data-quality (see API/server.py
// and DataQualityAgent/dq_server.py's `router`). Self-contained -- this
// agent is fully independent of WebUIGenerator/WebAPIGenerator by design,
// same reasoning as LandDAgent's own hook file.

export const DATA_QUALITY_API_BASE = '/data-quality'
const apiUrl = (path: string): string => `${DATA_QUALITY_API_BASE}${path}`

export type SourceKind = 'excel' | 'delimited' | 'parquet' | 'database'
export type Language = 'python' | 'java'
export type DbType = 'postgresql' | 'mysql' | 'sqlserver' | 'oracle' | 'sqlite'

// Parquet is Python-only -- see DataQualityAgent/run.py's PARQUET_LANGUAGES.
export const PARQUET_LANGUAGES: Language[] = ['python']

export interface DataQualityItem {
  item_id: string
  title: string
  source_kind: SourceKind
  language: Language
  created_at: string
}

export interface DqFile {
  path: string
  content: string
}

export interface DqCheck {
  name: string
  passed: boolean
  detail: string
}

export interface DqResult {
  passed: boolean
  checks: DqCheck[]
  summary: string
}

export interface LastResult {
  returncode: number
  stdout: string
  stderr: string
  dq_result: DqResult | null
  ran_at: string
}

export interface DataQualityItemDetail extends DataQualityItem {
  rules: string
  run: { entry: string }
  source_meta: Record<string, unknown>
  validation_error: string | null
  credentials_saved?: boolean
  files: DqFile[]
  last_result: LastResult | null
}

// Generate/regenerate and run both happen in a background thread server-side
// and are polled, not awaited in one long request -- same reasoning as every
// other agent in this app: an LLM call or a subprocess run inside an
// `async def` route would block the whole server's event loop.
export interface DqRunStatus {
  status: 'running' | 'complete' | 'error'
  log: string[]
  result?: DataQualityItemDetail | null
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

export interface CreateItemFields {
  // Becomes the folder name on disk -- letters, numbers, hyphens,
  // underscores only, no spaces (validated server-side too).
  project_name: string
  source_kind: SourceKind
  language: Language
  rules: string
  file?: File
  s3_path?: string
  has_header?: boolean
  pasted_columns?: string
  delimiter?: string
  db_type?: DbType
  host?: string
  port?: string
  database?: string
  username?: string
  password?: string
  table?: string
  pasted_schema?: string
  save_credentials?: boolean
}

export function createItem(fields: CreateItemFields): Promise<{ run_id: string } | { error: string }> {
  const formData = new FormData()
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined) continue
    formData.append(key, value instanceof File ? value : String(value))
  }
  return request('/api/items', { method: 'POST', body: formData })
}

export function getRunStatus(runId: string): Promise<DqRunStatus | { error: string }> {
  return request(`/api/items/runs/${runId}/status`)
}

export function listItems(): Promise<{ items: DataQualityItem[] } | { error: string }> {
  return request('/api/items')
}

export function getItem(itemId: string): Promise<DataQualityItemDetail | { error: string }> {
  return request(`/api/items/${itemId}`)
}

export function updateFile(itemId: string, path: string, content: string): Promise<{ ok: boolean } | { error: string }> {
  const formData = new FormData()
  formData.append('path', path)
  formData.append('content', content)
  return request(`/api/items/${itemId}/file`, { method: 'PUT', body: formData })
}

export function runItem(itemId: string, password?: string): Promise<{ run_id: string } | { error: string }> {
  const formData = new FormData()
  if (password) formData.append('password', password)
  return request(`/api/items/${itemId}/run`, { method: 'POST', body: formData })
}

export function deleteItem(itemId: string): Promise<{ ok: boolean }> {
  return request(`/api/items/${itemId}`, { method: 'DELETE' })
}

// Safe to do freely -- the project name is never fed into code generation,
// so nothing inside the generated files references it. Just a folder
// rename + an item.json update server-side. Returns the renamed item
// (its item_id is now newName) or an error.
export function renameItem(itemId: string, newName: string): Promise<DataQualityItemDetail | { error: string }> {
  const formData = new FormData()
  formData.append('new_name', newName)
  return request(`/api/items/${itemId}/rename`, { method: 'PUT', body: formData })
}

export function downloadUrl(itemId: string): string {
  return apiUrl(`/api/items/${itemId}/download`)
}
