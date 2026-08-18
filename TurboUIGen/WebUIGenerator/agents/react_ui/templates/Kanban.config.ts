// @ts-nocheck
/**
 * Kanban.config.ts — Drag-and-drop Kanban board.
 * Works for: project management, sales pipelines, hiring workflows, issue tracking, etc.
 *
 * RULES:
 * - columns[] defines the lanes (e.g. To Do, In Progress, Done)
 * - tableName fetches cards from the API
 * - statusField maps each card to its column
 * - Cards show a title, optional subtitle, badges, and assignee
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  tableName: '{{TABLE_NAME}}',

  // Column definitions — each represents a Kanban lane
  columns: [
    { id: '{{COL_1_ID}}', title: '{{COL_1_TITLE}}', color: '{{COL_1_COLOR}}' },
    { id: '{{COL_2_ID}}', title: '{{COL_2_TITLE}}', color: '{{COL_2_COLOR}}' },
    { id: '{{COL_3_ID}}', title: '{{COL_3_TITLE}}', color: '{{COL_3_COLOR}}' },
    // Add more columns as needed
  ],

  // Field mappings
  statusField: '{{STATUS_FIELD}}',    // field that maps card to column id
  titleField: '{{TITLE_FIELD}}',      // card title
  subtitleField: '{{SUBTITLE_FIELD}}', // optional card subtitle (null if none)
  priorityField: '{{PRIORITY_FIELD}}', // optional priority badge (null if none)
  assigneeField: '{{ASSIGNEE_FIELD}}', // optional assignee name (null if none)
  dateField: '{{DATE_FIELD}}',         // optional due date (null if none)

  // Priority badge colors
  priorityColors: {
    'high': '#DC2626',
    'medium': '#D97706',
    'low': '#059669',
  },

  // Accent color for the board
  accentColor: '{{ACCENT_COLOR}}',
} as const
