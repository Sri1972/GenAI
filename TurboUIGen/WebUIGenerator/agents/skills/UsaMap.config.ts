// @ts-nocheck
/**
 * UsaMap.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 */
export const config = {
  tableName: '{{TABLE_NAME}}',             // SQLite table name — data auto-fetched from /api/data/{tableName}
  dataExport: null as any[] | null,        // null = use tableName API

  // Field containing state name (full e.g. 'California') or abbreviation (e.g. 'CA')
  stateField: '{{STATE_FIELD}}',

  // Numeric field that determines colour intensity
  valueField: '{{VALUE_FIELD}}',

  title: '{{CHART_TITLE}}',

  // Colour ramp: 'blue' | 'green' | 'orange' | 'purple'
  colorScheme: '{{COLOR_SCHEME}}' as 'blue' | 'green' | 'orange' | 'purple',

  // Set to null if no dropdown filter needed, otherwise the field name string
  filterField: {{FILTER_FIELD}},
} as const
