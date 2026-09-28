// @ts-nocheck
/**
 * DataChat.config.ts — Fill in for each project.
 * Configures the AI-powered data chat interface.
 */

export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  // Base URL for the API server (default: proxied via Vite to localhost:8080)
  apiBaseUrl: '/api',

  // Accent color for user bubbles and interactive elements
  accentColor: '{{ACCENT_COLOR}}',

  // Context type determines how data is provided to the chat:
  //   'structured'   — schema + rows provided in initialContext (e.g. from a data grid)
  //   'document'     — text content provided in initialContext (e.g. pre-loaded document)
  //   'custom'       — arbitrary context string in initialContext
  //   'upload-excel' — user uploads an Excel file, parsed via /api/ingest/excel
  //   'upload-pdf'   — user uploads a PDF file, parsed via /api/ingest/pdf
  contextType: '{{CONTEXT_TYPE}}' as 'structured' | 'document' | 'custom' | 'upload-excel' | 'upload-pdf',

  // Pre-loaded context (null if contextType is upload-*)
  // For 'structured': { schema: [{name, type}], sampleRows: [...], metadata: {totalRows} }
  // For 'document': { text: "full text", metadata: {title, pages} }
  // For 'custom': { text: "any context string" }
  initialContext: null as any,

  // Suggested prompts shown as clickable chips when chat is empty
  suggestedPrompts: [
    '{{PROMPT_1}}',
    '{{PROMPT_2}}',
    '{{PROMPT_3}}',
    '{{PROMPT_4}}',
  ],

  // Optional: override the system prompt sent to the LLM
  // Leave null to use the default context-aware system prompt
  systemPromptOverride: null as string | null,
}
