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

export interface PipelineAgent {
  id:          string
  description: string
  stages:      string[]
}

export interface PipelineSkill {
  key:         string
  description: string
  categories:  string[]
}

export interface PipelineInfo {
  agents: PipelineAgent[]
  skills: PipelineSkill[]
}

export interface ModelChoice {
  id: string
  label: string
}

export interface ModelsResponse {
  litellm: ModelChoice[]
  bedrock: ModelChoice[]
  current: { provider: string; model: string }
  using_fallback: boolean
}

export interface ApiProjectEntry {
  name:        string
  title?:      string
  description?: string
  language:    'python' | 'java' | null
  authType:    'none' | 'basic' | 'api_key' | 'jwt' | null
  rateLimit?:  number
  port:        number | null
  status:      'draft' | 'running' | 'stopped' | 'start_failed'
  createdAt?:  string
}

export interface ApiExample {
  entity:      string | null
  method:      string
  path:        string
  description: string
  curl:        string
  body:        Record<string, any> | null
}

export interface ApiGenerateResult {
  projectName:  string
  title:        string
  description:  string
  port:         number | null
  url:          string | null
  files:        string[]
  warning?:     string
}

// /api/generate always returns immediately with just this — the real result only
// shows up later via polling GET /api/jobs/{requestId} (see JobStatus below).
export interface GenerateStart {
  requestId:   string
  status:      string
  projectName: string | null
}

export interface JobStatus {
  requestId:   string
  status:      'running' | 'completed' | 'failed'
  projectName: string | null
  result?:     ApiGenerateResult
  error?:      string | null
}

export interface ApiArchitectureEntity {
  name: string
  table?: string
  fields?: { name: string; type: string; required?: boolean; description?: string }[]
  relationships?: { type: string; entity: string; foreignKey?: string }[]
}

export interface ApiArchitectureEndpoint {
  method: string
  path: string
  description?: string
  auth_required?: boolean
  rate_limit?: string
}

export interface ApiArchitecture {
  projectName?: string
  title?:       string
  description?: string
  entities?:    ApiArchitectureEntity[]
  endpoints?:   ApiArchitectureEndpoint[]
  auth?:        { type?: string; description?: string }
  pagination?:  string
  database?:    string
}

export interface ApiDetailsEndpoint extends ApiArchitectureEndpoint {
  custom: boolean
}

export interface ApiDetailsMcpTool {
  name:        string
  description: string
}

export interface ApiDetailsMcpCustomEndpoint {
  path:        string
  description: string
}

export interface ApiDetailsResponse {
  hasArchitecture:    boolean
  entities:           ApiArchitectureEntity[]
  endpoints:          ApiDetailsEndpoint[]
  hasMcp:             boolean
  mcpTools:           ApiDetailsMcpTool[]
  mcpCustomEndpoints: ApiDetailsMcpCustomEndpoint[]
}

export interface ApiUsageRecentEntry {
  ts:          number
  client_id:   string
  method:      string
  path:        string
  status_code: number
  duration_ms: number
}

export interface ApiRateLimitStatus {
  limit:         number
  windowSeconds: number
  used:          number
  remaining:     number | null
}

export interface ApiUsageSummary {
  total_requests:    number
  requests_last_24h: number
  error_count:       number
  error_rate:        number
  by_endpoint:       Record<string, number>
  by_client:         Record<string, number>
  recent:            ApiUsageRecentEntry[]
  rate_limit?:       ApiRateLimitStatus
}

// ── MCP Generator ── (unrelated to McpStatus above, which is the Figma MCP
// bridge health check — these describe a generated MCP-server *project*)

export interface McpProjectEntry {
  name:       string
  title?:     string
  sourceType: 'datastore' | 'api' | 'both' | null
  port:       number | null
  status:     'draft' | 'running' | 'stopped' | 'start_failed'
  createdAt?: string
  // Set only for a datastore source — the name of the standalone WebAPIGenerator
  // project (visible in the Web API tab) this MCP server's tools call over HTTP.
  backingApiProject?: string | null
}

export interface McpTableColumn {
  name:        string
  type:        string
  primaryKey:  boolean
  notNull:     boolean
  description?: string
}

export interface McpForeignKey {
  column:            string
  referencesTable:   string
  referencesColumn:  string
}

export interface McpTable {
  name:        string
  description?: string
  columns:     McpTableColumn[]
  foreignKeys: McpForeignKey[]
}

// ── Database Explorer tab (live SQLite snapshot for a project) ──

export interface DbExplorerTable extends McpTable {
  rowCount:   number
  sampleRows: Record<string, unknown>[]
}

export interface DbExplorerResponse {
  hasDatabase: boolean
  dbName?:     string
  dbPath?:     string
  tables?:     DbExplorerTable[]
}

export interface McpEndpointParameter {
  name:     string
  in:       string
  required: boolean
  type:     string
}

export interface McpEndpoint {
  method:      string
  path:        string
  summary?:    string
  description?: string
  parameters:  McpEndpointParameter[]
  hasRequestBody?: boolean
}

export interface McpToolParameter {
  name:        string
  type:        string
  required:    boolean
  description?: string
}

export interface McpTool {
  name:        string
  description: string
  method:      string
  path:        string
  kind?:       'list' | 'detail' | 'custom'
  // Set only for kind: 'custom' (business-logic/join tools designed from
  // instructions) — the actual read-only SQL and its bound parameters,
  // editable in the Metadata tab.
  sql?:         string
  parameters?:  McpToolParameter[]
}

export interface McpMetadata {
  sourceType:   'datastore' | 'api' | 'both'
  instructions?: string
  datastore:  {
    dbPath: string; tables: McpTable[]
    backingApiProject?: string | null
    backingApiBaseUrl?: string | null
  } | null
  api:        { baseUrl: string; authType: string; endpoints: McpEndpoint[] } | null
  tools:      McpTool[]
}

export interface McpIntrospectSqliteResult {
  tables: McpTable[]
}

export interface McpIntrospectApiResult {
  found:    boolean
  baseUrl?: string
  endpoints?: McpEndpoint[]
}

export interface McpGenerateResult {
  projectName: string
  port:        number | null
  url:         string | null
  running:     boolean
  tools:       McpTool[]
}
