// Typed fetch wrappers for the Workflow backend -- mounted in-process on this
// same server under /workflows (see API/server.py and
// Workflow/workflow_server.py's `router`). Split out of contentAgentsApi.ts
// because Workflow is its own top-level module now, not part of
// ContentAgents -- it orchestrates Product Forge and the generators as much
// as it does ContentAgents' reader/creator agents.

import type { Agent } from './contentAgentsApi'

export const WORKFLOW_API_BASE = '/workflows'
export const workflowApiUrl = (path: string): string => `${WORKFLOW_API_BASE}${path}`

async function parseJsonSafe(resp: Response): Promise<any> {
  const raw = await resp.text()
  try {
    return JSON.parse(raw)
  } catch {
    return { error: raw.slice(0, 500) || `Request failed with HTTP ${resp.status}.` }
  }
}

async function request(url: string, init?: RequestInit): Promise<any> {
  const resp = await fetch(workflowApiUrl(url), init)
  return parseJsonSafe(resp)
}

// Cross-app pipeline nodes -- distinct from the 8 content Agent kinds
// (those drive the standalone Utility Agents tab; these only make sense on
// the Workflow canvas, orchestrating Product Forge and the generators, all
// native TurboAppGenerator features this app is embedded inside of).
export type PipelineAgent = 'product_forge' | 'webui_generator' | 'webapi_generator' | 'mcp_generator'

export interface WorkflowNodeConfig {
  id: string
  agent: Agent | PipelineAgent
  label: string
  position: { x: number; y: number }
  // Reader config
  libraryItemId?: string
  url?: string
  question?: string
  // Creator config
  prompt?: string
  // product_forge config
  productIdea?: string
  draftMode?: boolean
  artifactStages?: string[]  // undefined/empty = every stage (Forge's own default)
  // webui_generator / webapi_generator / mcp_generator config
  projectName?: string
  // webapi_generator-only config
  apiLanguage?: string  // "python" | "java"
  apiAuthType?: string  // "none" | "basic"
  // mcp_generator-only config -- the actual source (DB path / API URL +
  // creds) has to be stated here directly; a connected Forge node's
  // PRD/TRD/Specs is optional extra context, never a substitute for this.
  mcpInstructions?: string
}

export interface WorkflowEdgeConfig {
  id: string
  source: string
  target: string
}

export interface WorkflowDefinition {
  workflow_id: string
  name: string
  nodes: WorkflowNodeConfig[]
  edges: WorkflowEdgeConfig[]
  updated_at: string
}

// --- Async workflow runs: start, then poll status, then (in HITL mode)
// continue a node that's paused awaiting review. ---

export interface WorkflowRunNodeStatus {
  node_id: string
  status: 'pending' | 'running' | 'awaiting_review' | 'ok' | 'error'
  summary: string | null
  log?: string[]
  extra: {
    download?: string; preview_url?: string | null; forge_session_id?: string
    downloads?: { label: string; url: string }[]  // split video_creator node -- one entry per part
  }
}

export interface WorkflowRunStatus {
  run_id: string
  run_status: 'running' | 'paused' | 'complete' | 'error'
  awaiting_node_id: string | null
  current_node_id: string | null
  nodes: WorkflowRunNodeStatus[]
}

export function listWorkflows(): Promise<{ workflows: WorkflowDefinition[] }> {
  return request('/api/workflows')
}

export function getWorkflow(workflowId: string): Promise<WorkflowDefinition | { error: string }> {
  return request(`/api/workflows/${workflowId}`)
}

export function saveWorkflow(def: Omit<WorkflowDefinition, 'workflow_id' | 'updated_at'> & { workflow_id?: string }): Promise<WorkflowDefinition> {
  return request('/api/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(def),
  })
}

export function deleteWorkflow(workflowId: string): Promise<{ ok: boolean }> {
  return request(`/api/workflows/${workflowId}`, { method: 'DELETE' })
}

export function startWorkflowRun(workflowId: string, autoMode: boolean): Promise<{ run_id: string } | { error: string }> {
  return request(`/api/workflows/${workflowId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_mode: autoMode }),
  })
}

export function getWorkflowRunStatus(workflowId: string, runId: string): Promise<WorkflowRunStatus | { error: string }> {
  return request(`/api/workflows/${workflowId}/runs/${runId}/status`)
}

// Lets a freshly (re)mounted canvas reattach to whatever run is already in
// progress for this workflow -- e.g. after switching tabs and back, or
// re-selecting the same workflow from the sidebar -- instead of only the
// browser tab that originally clicked Run ever being able to see it.
export function getLatestWorkflowRun(workflowId: string): Promise<WorkflowRunStatus | { run_id: null } | { error: string }> {
  return request(`/api/workflows/${workflowId}/runs/latest`)
}

export function continueWorkflowNode(workflowId: string, runId: string, nodeId: string): Promise<{ ok: boolean } | { error: string }> {
  return request(`/api/workflows/${workflowId}/runs/${runId}/continue/${nodeId}`, { method: 'POST' })
}
