import { BuildLogRun, DockerStatus, FigmaProject, GenerateResult, HistoryEvent, McpStatus, Project, WireframeMode, WireframeResult } from '../types'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  const text = await res.text()
  let data: any
  try { data = JSON.parse(text) } catch { throw new Error(`Server error: ${text.slice(0, 200)}`) }
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`)
  return data as T
}

export const api = {
  listProjects: () =>
    request<Project[]>('/api/projects'),

  generate: (prompt: string, projectName?: string, figmaUrl?: string, instructions?: string) =>
    request<GenerateResult>('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_name: projectName, figma_url: figmaUrl || null, instructions: instructions || '' }),
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

  refine: (projectName: string, prompt: string, comment?: string, instructions?: string) =>
    request<GenerateResult>(`/api/refine/${projectName}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_name: projectName, comment: comment || '', instructions: instructions || '' }),
    }),

  getHistory: (name: string) =>
    request<HistoryEvent[]>(`/api/projects/${name}/history`),

  getScreenshots: (name: string) =>
    request<{ screenshots: { filename: string; data: string; mimetype: string }[]; count: number }>(
      `/api/projects/${name}/screenshots`
    ),

  getBuildLog: (name: string) =>
    request<{ runs: BuildLogRun[] }>(`/api/projects/${name}/buildlog`),

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
