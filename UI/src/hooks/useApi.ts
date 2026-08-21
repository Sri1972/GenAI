import { BuildLogRun, DockerStatus, FigmaProject, GenerateResult, HistoryEvent, McpStatus, Project, WireframeMode, WireframeResult } from '../types'

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

// ── Unified workspace "Project" (new model) ───────────────────────────────────
export interface WorkspaceInput { name: string; size: number }
export interface WorkspaceWebapp { appId: string; key: string; previewUrl: string }
export type EngagementMode = 'collaborate' | 'autopilot'
export interface WorkspaceProject {
  slug: string
  name: string
  description: string
  defaultMode: EngagementMode
  created: string
  updated: string
  webapps: string[]
  inputs: WorkspaceInput[]
}

export const workspaces = {
  list: () => request<WorkspaceProject[]>('/api/workspaces'),

  create: (name: string, description = '') =>
    request<WorkspaceProject>('/api/workspaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description }),
    }),

  get: (slug: string) => request<WorkspaceProject>(`/api/workspaces/${slug}`),

  setDefaultMode: (slug: string, mode: EngagementMode) =>
    request<WorkspaceProject>(`/api/workspaces/${slug}/default-mode`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }),
    }),

  remove: (slug: string) =>
    request<{ status: string; slug: string }>(`/api/workspaces/${slug}`, { method: 'DELETE' }),

  listInputs: (slug: string) => request<WorkspaceInput[]>(`/api/workspaces/${slug}/inputs`),

  uploadInput: (slug: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<WorkspaceInput>(`/api/workspaces/${slug}/inputs`, { method: 'POST', body: form })
  },

  deleteInput: (slug: string, filename: string) =>
    request<{ status: string; name: string }>(
      `/api/workspaces/${slug}/inputs/${encodeURIComponent(filename)}`, { method: 'DELETE' }),

  listWebapps: (slug: string) => request<WorkspaceWebapp[]>(`/api/workspaces/${slug}/webapps`),

  createWebapp: (slug: string) =>
    request<WorkspaceWebapp>(`/api/workspaces/${slug}/webapps`, { method: 'POST' }),

  renameWebapp: (slug: string, appId: string, newName: string) =>
    request<WorkspaceWebapp>(`/api/workspaces/${slug}/webapps/${encodeURIComponent(appId)}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    }),

  deleteWebapp: (slug: string, appId: string) =>
    request<{ status: string; appId: string }>(
      `/api/workspaces/${slug}/webapps/${encodeURIComponent(appId)}`, { method: 'DELETE' }),
}

// ── Brainstorming roundtable ──────────────────────────────────────────────────
export interface RoundtablePersona { id: string; name: string; role: string; hue: number; knows: string }

export interface AgendaTemplate { id: string; name: string; buckets: string[]; people: string[]; duration: number }

export interface CreateMeetingBody {
  topic: string
  people: string[]
  duration_minutes?: number
  turn_order?: 'open' | 'round'
  diagram?: boolean
  provider?: string | null
  mode?: EngagementMode
  agenda?: string[]
  architecture?: 'classic' | 'debate'
}

export interface MeetingSummary { id: string; topic: string; people: string[]; turns: number; complete: boolean; when: number }
export interface MeetingTurn { who: string; text: string; why?: string; at?: string; note?: string; sources?: string[]; quote?: string; quoteRole?: string }
export interface RecapSection { bucket: string; items: string[] }
export interface MeetingRecap { headline: string; decision?: string; argument?: string; sections?: RecapSection[]; commitments: { who: string; what: string }[]; still_open: string[] }
export interface MeetingUsage {
  by_person: { who: string; name: string; model: string; input_tokens: number; output_tokens: number; cache_read_tokens: number; cost_usd: number; turns: number }[]
  by_model: { model: string; input_tokens: number; output_tokens: number; cache_read_tokens: number; cost_usd: number }[]
  facilitator: { input_tokens: number; output_tokens: number; cost_usd: number }
  totals: { input_tokens: number; output_tokens: number; cache_read_tokens: number; cost_usd: number }
}
export interface MeetingDetail {
  id: string; complete: boolean; topic: string; people: string[]
  turns: MeetingTurn[]; agreed: { text: string; type: string; who: string; at: string }[]; recap: MeetingRecap | null
  usage?: MeetingUsage | null
}

export const roundtable = {
  personas: () => request<RoundtablePersona[]>('/api/roundtable/personas'),

  agendaTemplates: () => request<AgendaTemplate[]>('/api/roundtable/agenda-templates'),

  meetings: (project: string) => request<MeetingSummary[]>(`/api/roundtable/${project}/meetings`),

  meeting: (project: string, mid: string) =>
    request<MeetingDetail>(`/api/roundtable/${project}/meetings/${encodeURIComponent(mid)}`),

  createMeeting: (project: string, body: CreateMeetingBody) =>
    request<{ meetingId: string; topic: string; people: string[] }>(
      `/api/roundtable/${project}/meetings`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      }),

  interject: (project: string, mid: string, text: string, target = 'all') =>
    request<{ status: string }>(`/api/roundtable/${project}/meetings/${mid}/interject`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, target }),
    }),

  hold: (project: string, mid: string, paused: boolean) =>
    request<{ status: string }>(`/api/roundtable/${project}/meetings/${mid}/hold`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paused }),
    }),

  wrapUp: (project: string, mid: string) =>
    request<{ status: string }>(`/api/roundtable/${project}/meetings/${mid}/wrap_up`, { method: 'POST' }),

  continue: (project: string, mid: string) =>
    request<{ status: string }>(`/api/roundtable/${project}/meetings/${mid}/continue`, { method: 'POST' }),

  artifactUrl: (project: string, mid: string, name: string) =>
    `/api/roundtable/${project}/meetings/${mid}/artifact/${encodeURIComponent(name)}`,

  drawDiagram: (project: string, mid: string) =>
    request<{ file: string | null; url?: string; detail: string }>(
      `/api/roundtable/${project}/meetings/${mid}/diagram`, { method: 'POST' }),

  promote: (project: string, mid: string, name: string) =>
    request<{ status: string; artifact: string }>(
      `/api/roundtable/${project}/meetings/${mid}/artifact/${encodeURIComponent(name)}/promote`,
      { method: 'POST' }),
}

export const api = {
  listProjects: () =>
    request<Project[]>('/api/projects'),

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

  rename: (name: string, newName: string) =>
    request<{ name: string; oldName: string }>(`/api/projects/${name}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName }),
    }),

  getJobStatus: (requestId: string) =>
    request<{ requestId: string; status: string; projectName?: string; result?: any; error?: string }>(
      `/api/jobs/${requestId}`
    ),

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
