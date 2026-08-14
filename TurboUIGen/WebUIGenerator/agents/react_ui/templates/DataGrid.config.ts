// @ts-nocheck
/**
 * DataGrid.config.ts — FILL IN for each project.
 *
 * Replace every {{PLACEHOLDER}} with real values from this project's data.
 * Valid badgeColors variants: default | success | warning | error | info | accent
 */
export const config = {
  // Data source — use tableName to fetch from API (preferred)
  tableName: '{{TABLE_NAME}}',   // SQLite table name — data auto-fetched from /api/data/{tableName}
  dataExport: null as any[] | null,  // null = use tableName API

  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  // Field used as the React list key — must be unique per row
  rowKey: '{{ROW_KEY_FIELD}}',

  // Fields included in the global search box
  searchFields: [{{SEARCH_FIELDS}}],

  // Dropdown filters above the table
  filters: [
    // Example:
    // { label: 'Region', field: 'region', options: ['Americas', 'Europe', 'Asia Pacific'] },
    {{FILTERS}}
  ],

  // Column definitions — drives headers, sorting, and cell rendering
  columns: [
    // type options: 'text' | 'number' | 'currency' | 'percent' | 'badge' | 'progress' | 'date'
    {{COLUMNS}}
  ],

  defaultSort: { key: '{{DEFAULT_SORT_KEY}}', dir: '{{DEFAULT_SORT_DIR}}' as const },

  csvFilename: '{{CSV_FILENAME}}',
} as const
