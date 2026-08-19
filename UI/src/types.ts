export interface Project {
  name: string
  title: string
  port: number | null
  url: string | null
  running: boolean
  files: number
  hasApp: boolean
  type?: 'react' | 'html'
  source?: 'figma' | 'figma+prompt' | 'prompt'
  sourceLabel?: string
  figmaUrl?: string
  prompt?: string
  backendType?: 'python' | 'java'
}

export interface GenerateResult {
  projectName: string
  title: string
  description: string
  port: number
  url: string
  files: string[]
}

export interface HistoryEvent {
  event: string
  detail: string
  figmaUrl: string
  prompt: string
  comment?: string
  instructions?: string
  timestamp: string
}

export type GenerateStep =
  | 'llm' | 'write' | 'install' | 'start' | 'ready' | 'done'
  | 'figma_api' | 'figma_api_done'
  | 'screenshot_start' | 'screenshot_done'
  | 'llm_analysis' | 'llm_analysis_done' | 'llm_codegen'
  | null

export interface McpStatus {
  mcp_server:      boolean
  relay_connected: boolean
  tools:           number
}

export interface WireframeResult {
  result:        string
  log:           string[]
  requestId:     string
  figma_url?:    string       // shareable Figma URL returned after successful build
  project_name?: string       // the project name used/created for this run
  error?:        string       // human-readable error message
  error_code?:   string       // NO_MCP_SERVER | NO_FIGMA_FILE | BRIDGE_NOT_CONNECTED | EXISTING_FRAMES
  needs_confirm?: boolean     // true when existing frames found and mode=new
  frame_count?:  number
  frame_names?:  string
  message?:      string       // confirmation prompt to show user
}

export type WireframeMode = 'new' | 'edit' | 'replace'

export interface BuildLogRun {
  timestamp:  string
  event:      string
  duration_s: number
  lines:      string[]
}

export interface FigmaProjectHistoryEntry {
  timestamp:    string
  prompt:       string
  mode:         string
  screens?:     string[]
  instructions?: string
}

export interface DockerStatus {
  dockerAvailable:  boolean
  imageExists:      boolean
  imageTag:         string | null
  containerStatus:  'running' | 'exited' | 'none' | string
  containerName:    string | null
  hostPort:         number | null
  builtAt:          string | null
  containerUrl:     string | null
}

export interface FigmaProject {
  name:       string
  title:      string
  created_at: string
  updated_at: string
  screens:    string[]
  figma_url:  string
  notes:      string
  history:    FigmaProjectHistoryEntry[]
}
