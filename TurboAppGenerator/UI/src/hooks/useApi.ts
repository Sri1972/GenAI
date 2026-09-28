import { ApiArchitecture, ApiDetailsResponse, ApiExample, ApiProjectEntry, ApiUsageSummary, BuildLogRun, DbExplorerResponse, DockerStatus, FigmaProject, GenerateResult, GenerateStart, HistoryEvent, JobStatus, McpStatus, McpProjectEntry, McpIntrospectSqliteResult, McpIntrospectApiResult, McpMetadata, ModelsResponse, PipelineInfo, Project, WireframeMode, WireframeResult } from '../types'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  const text = await res.text()
  let data: any
  try { data = JSON.parse(text) } catch { throw new Error(`Server error: ${text.slice(0, 200)}`) }
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
  return data as T
}

export interface DraftResult {
  architecture: Record<string, any>
  markdown: string
  projectName: string
  title: string
  pageCount: number
}

export const api = {
  // Mounted in-process now (see server.py) — no start/stop, just a health
  // check so the tab can show a clear error if the mount itself failed.
  getForgeStatus: () =>
    request<{ installed: boolean; error: string | null }>('/api/forge/status'),

  listProjects: () =>
    request<Project[]>('/api/projects'),

  getPipelineInfo: () =>
    request<PipelineInfo>('/api/pipeline-info'),

  getModels: () =>
    request<ModelsResponse>('/api/models'),

  selectModel: (provider: string, model: string) =>
    request<{ ok: boolean; error: string | null }>('/api/models/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider, model }),
    }),

  draft: (prompt: string, projectName?: string, instructions?: string) =>
    request<DraftResult>('/api/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_name: projectName || null, instructions: instructions || '' }),
    }),

  getDraft: (projectName: string) =>
    request<DraftResult | null>(`/api/projects/${projectName}/draft`),

  generate: (prompt: string, projectName?: string, figmaUrl?: string, instructions?: string, architecture?: Record<string, any>, backendType?: string) =>
    request<GenerateResult>('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_name: projectName, figma_url: figmaUrl || null, instructions: instructions || '', architecture: architecture || null, backend_type: backendType || 'python' }),
    }),

  generateApi: (prompt: string, projectName: string, apiOptions: Record<string, any>, instructions?: string) =>
    request<GenerateStart>('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_name: projectName, mode: 'api', api_options: apiOptions, instructions: instructions || '' }),
    }),

  createApiProject: (name: string) =>
    request<{ name: string }>('/api/webapi/projects/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  listApiProjects: () =>
    request<ApiProjectEntry[]>('/api/webapi/projects'),

  startApiProject: (name: string) =>
    request<{ name: string; port: number; url: string | null; running: boolean }>(`/api/webapi/start/${name}`, { method: 'POST' }),

  stopApiProject: (name: string) =>
    request<{ name: string; running: boolean }>(`/api/webapi/stop/${name}`, { method: 'POST' }),

  deleteApiProject: (name: string) =>
    request<{ deleted: string }>(`/api/webapi/projects/${name}`, { method: 'DELETE' }),

  refineApiProject: (name: string, prompt: string, instructions?: string, comment?: string) =>
    request<GenerateStart>(`/api/webapi/projects/${name}/refine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, instructions: instructions || '', comment: comment || '' }),
    }),

  getApiHistory: (name: string) =>
    request<HistoryEvent[]>(`/api/webapi/projects/${name}/history`),

  renameApiProject: (name: string, newName: string) =>
    request<{ name: string; oldName: string }>(`/api/webapi/projects/${name}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    }),

  getApiUsage: (name: string) =>
    request<ApiUsageSummary>(`/api/webapi/projects/${name}/usage`),

  resetApiUsage: (name: string) =>
    request<{ reset: boolean }>(`/api/webapi/projects/${name}/usage/reset`, { method: 'POST' }),

  // Verifies Basic Auth credentials via the same-origin usage proxy (avoids CORS —
  // the browser never talks to the generated API's port directly) without
  // throwing, so the custom login form (ApiGeneratorPage.tsx) can distinguish
  // "wrong password" from "API unreachable".
  verifyApiAuth: async (name: string, username: string, password: string): Promise<{ ok: boolean; status: number }> => {
    const res = await fetch(`/api/webapi/projects/${name}/usage`, {
      headers: { Authorization: 'Basic ' + btoa(`${username}:${password}`) },
    })
    return { ok: res.ok, status: res.status }
  },

  getApiBuildLog: (name: string) =>
    request<{ runs: BuildLogRun[] }>(`/api/webapi/projects/${name}/buildlog`),

  getApiArchitecture: (name: string) =>
    request<{ architecture: ApiArchitecture | null; exists: boolean }>(`/api/webapi/projects/${name}/architecture`),

  getApiArchitectureHtmlUrl: (name: string) => `/api/webapi/projects/${name}/architecture.html`,

  getApiExamples: (name: string) =>
    request<{ examples: ApiExample[] }>(`/api/webapi/projects/${name}/examples`),

  // ── API Docker — opt-in, mirrors the Web UI docker/* endpoints ──────────────

  getApiDockerStatus: (name: string) =>
    request<DockerStatus>(`/api/webapi/projects/${name}/docker/status`),

  buildApiDockerImage: (name: string) =>
    request<DockerStatus & { requestId: string }>(`/api/webapi/projects/${name}/docker/build`, { method: 'POST' }),

  downloadApiDockerImage: (name: string) => {
    const a = document.createElement('a')
    a.href = `/api/webapi/projects/${name}/docker/download`
    a.download = `${name}.tar`
    a.click()
  },

  runApiDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/webapi/projects/${name}/docker/run`, { method: 'POST' }),

  stopApiDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/webapi/projects/${name}/docker/stop`, { method: 'POST' }),

  startApiDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/webapi/projects/${name}/docker/start`, { method: 'POST' }),

  deleteApiDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/webapi/projects/${name}/docker/container`, { method: 'DELETE' }),

  // ── MCP Generator ────────────────────────────────────────────────────────

  listMcpProjects: () =>
    request<McpProjectEntry[]>('/api/mcp/projects'),

  createMcpProject: (name: string) =>
    request<{ name: string }>('/api/mcp/projects/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  introspectSqlite: (dbPath: string) =>
    request<McpIntrospectSqliteResult>('/api/mcp/introspect/sqlite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dbPath }),
    }),

  introspectApi: (baseUrl: string, username?: string, password?: string) =>
    request<McpIntrospectApiResult>('/api/mcp/introspect/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ baseUrl, username: username || null, password: password || null }),
    }),

  introspectApiFromSpec: (baseUrl: string, spec: Record<string, any>) =>
    request<McpIntrospectApiResult>('/api/mcp/introspect/api/from-spec', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ baseUrl, spec }),
    }),

  generateMcp: (projectName: string, sourceType: 'datastore' | 'api' | 'both', sourceConfig: Record<string, any>, instructions = '', comment = '') =>
    request<GenerateStart>('/api/mcp/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName, sourceType, sourceConfig, instructions, comment }),
    }),

  startMcpProject: (name: string) =>
    request<{ name: string; port: number; url: string | null; running: boolean }>(`/api/mcp/start/${name}`, { method: 'POST' }),

  stopMcpProject: (name: string) =>
    request<{ name: string; running: boolean }>(`/api/mcp/stop/${name}`, { method: 'POST' }),

  deleteMcpProject: (name: string) =>
    request<{ deleted: string }>(`/api/mcp/projects/${name}`, { method: 'DELETE' }),

  renameMcpProject: (name: string, newName: string) =>
    request<{ name: string; oldName: string }>(`/api/mcp/projects/${name}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    }),

  getMcpBuildLog: (name: string) =>
    request<BuildLogRun[]>(`/api/mcp/projects/${name}/buildlog`),

  getMcpHistory: (name: string) =>
    request<HistoryEvent[]>(`/api/mcp/projects/${name}/history`),

  getMcpMetadata: (name: string) =>
    request<McpMetadata>(`/api/mcp/projects/${name}/metadata`),

  chatWithMcp: (name: string, messages: { role: string; content: string }[]) =>
    request<{ reply: string; toolCalls: { name: string; args: Record<string, any>; result: string }[] }>(
      `/api/mcp/projects/${name}/chat`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
      }
    ),

  createProject: (name: string) =>
    request<{ name: string }>('/api/projects/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  start: (name: string) =>
    request<Project>(`/api/start/${name}`, { method: 'POST' }),

  stop: (name: string) =>
    request<Project>(`/api/stop/${name}`, { method: 'POST' }),

  delete: (name: string) =>
    request<{ deleted: string }>(`/api/delete/${name}`, { method: 'DELETE' }),

  getDeleteProgress: (name: string) =>
    request<{ inProgress: boolean; log: string[] }>(`/api/delete/progress/${name}`),

  rename: (name: string, newName: string) =>
    request<{ name: string; oldName: string }>(`/api/projects/${name}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    }),

  getJobStatus: (requestId: string) =>
    request<JobStatus>(`/api/jobs/${requestId}`),

  getActiveJobs: () =>
    request<{ jobs: { requestId: string; status: string; projectName?: string }[] }>('/api/jobs'),

  getProgressByProject: (projectName: string) =>
    request<{ id: string; log: string[] }>(`/api/generate/progress/project/${projectName}`),

  getProgress: (requestId: string) =>
    request<{ log: string[] }>(`/api/generate/progress/${requestId}`),

  refine: (projectName: string, prompt: string, comment?: string, instructions?: string, architecture?: Record<string, any>, backendType?: string) =>
    request<GenerateResult>(`/api/refine/${projectName}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_name: projectName, comment: comment || '', instructions: instructions || '', architecture: architecture || null, backend_type: backendType || 'python' }),
    }),

  getHistory: (name: string) =>
    request<HistoryEvent[]>(`/api/projects/${name}/history`),

  getScreenshots: (name: string) =>
    request<{ screenshots: { filename: string; data: string; mimetype: string }[]; count: number }>(
      `/api/projects/${name}/screenshots`
    ),

  getBuildLog: (name: string) =>
    request<{ runs: BuildLogRun[] }>(`/api/projects/${name}/buildlog`),

  getArchitecture: (name: string) =>
    request<{ markdown: string; exists: boolean }>(`/api/projects/${name}/architecture`),

  getArchitectureHtmlUrl: (name: string) => `/api/projects/${name}/architecture.html`,

  getApiDetails: (name: string) =>
    request<ApiDetailsResponse>(`/api/projects/${name}/api-details`),

  getDbExplorer: (name: string) =>
    request<DbExplorerResponse>(`/api/projects/${name}/db-explorer`),

  // ── Figma Wireframe ────────────────────────────────────────────────────────

  getMcpStatus: () =>
    request<McpStatus>('/api/figma/mcp/status'),

  generateWireframe: (prompt: string, mode: WireframeMode, applyBrand = false, projectName?: string, instructions?: string, confirmed = false) =>
    request<WireframeResult>('/api/figma/wireframe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, mode, apply_brand: applyBrand, confirmed, project_name: projectName ?? '', instructions: instructions || '' }),
    }),

  getWireframeProgress: (requestId: string) =>
    request<{ log: string[] }>(`/api/generate/progress/${requestId}`),

  webappDiscover: (url: string, loginUsername = '', loginPassword = '', projectName = '') =>
    request<{ pages: { title: string; url: string; nav_label: string; depth: number }[]; count: number; max_depth: number }>(
      `/api/figma/webapp-discover?url=${encodeURIComponent(url)}&max_pages=20&nav_depth=2` +
      (loginUsername  ? `&login_username=${encodeURIComponent(loginUsername)}`   : '') +
      (loginPassword  ? `&login_password=${encodeURIComponent(loginPassword)}`   : '') +
      (projectName    ? `&project_name=${encodeURIComponent(projectName)}`        : '')
    ),

  getWebappScreenshots: (projectName: string) =>
    request<{ screenshots: { filename: string; data: string; mimetype: string }[]; count: number }>(
      `/api/figma/webapp-screenshots/${encodeURIComponent(projectName)}`
    ),

  webappToFigma: (url: string, projectName: string, maxPages: number, navClickDepth: number, instructions: string, loginUsername = '', loginPassword = '') =>
    request<WireframeResult>('/api/figma/webapp-to-figma', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, project_name: projectName, max_pages: maxPages, nav_click_depth: navClickDepth, instructions, login_username: loginUsername, login_password: loginPassword }),
    }),

  // ── Figma Mockup Projects ──────────────────────────────────────────────────

  listFigmaProjects: () =>
    request<FigmaProject[]>('/api/figma/projects'),

  createFigmaProject: (name: string) =>
    request<FigmaProject>('/api/figma/projects/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    }),

  updateFigmaProject: (name: string, prompt: string, mode: WireframeMode, screens?: string[], figma_url?: string, notes?: string) =>
    request<FigmaProject>(`/api/figma/projects/${name}/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, mode, screens: screens ?? [], figma_url: figma_url ?? '', notes: notes ?? '' }),
    }),

  deleteFigmaProject: (name: string) =>
    request<{ deleted: string }>(`/api/figma/projects/${name}`, { method: 'DELETE' }),

  getFigmaBuildLog: (name: string) =>
    request<{ log: string[]; timestamp: string | null }>(`/api/figma/projects/${name}/buildlog`),

  // ── Docker ─────────────────────────────────────────────────────────────────

  getDockerStatus: (name: string) =>
    request<DockerStatus>(`/api/projects/${name}/docker/status`),

  buildDockerImage: (name: string) =>
    request<DockerStatus & { requestId: string }>(`/api/projects/${name}/docker/build`, { method: 'POST' }),

  downloadDockerImage: (name: string) => {
    const a = document.createElement('a')
    a.href = `/api/projects/${name}/docker/download`
    a.download = `${name}.tar`
    a.click()
  },

  runDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/projects/${name}/docker/run`, { method: 'POST' }),

  stopDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/projects/${name}/docker/stop`, { method: 'POST' }),

  startDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/projects/${name}/docker/start`, { method: 'POST' }),

  deleteDockerContainer: (name: string) =>
    request<DockerStatus>(`/api/projects/${name}/docker/container`, { method: 'DELETE' }),
}
