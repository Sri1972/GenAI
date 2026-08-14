// @ts-nocheck
/**
 * CardGrid.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 * Valid badge variants: default | success | warning | error | info | accent
 */
export const config = {
  tableName: '{{TABLE_NAME}}',       // SQLite table name — data auto-fetched from /api/data/{tableName}
  dataExport: null as any[] | null,  // null = use tableName API

  pageTitle: '{{PAGE_TITLE}}',

  // Primary card heading field
  nameField: '{{NAME_FIELD}}',

  // Secondary line below the name — set to null if not needed
  subtitleField: {{SUBTITLE_FIELD}},

  // URL field for card image — set to null if no image
  imageField: {{IMAGE_FIELD}},

  // Field used as the coloured badge — set to null if not needed
  badgeField: {{BADGE_FIELD}},

  // Maps each badge value to a valid variant
  // Valid variants: default | success | warning | error | info | accent
  badgeColors: {
    // Example: 'Active': 'success', 'Inactive': 'error', 'Pending': 'warning'
    {{BADGE_COLORS}}
  } as Record<string, 'default'|'success'|'warning'|'error'|'info'|'accent'>,

  // Metrics shown at the bottom of each card (2–3 max)
  metrics: [
    // Example: { field: 'salary', label: 'Salary', format: 'currency' }
    // format: 'number' | 'currency' | 'percent'
    {{METRICS}}
  ],

  // Fields included in the search box
  searchFields: [{{SEARCH_FIELDS}}],

  // Dropdown filters
  filters: [
    // Example: { label: 'Position', field: 'position', options: ['Forward', 'Midfielder', 'Defender'] }
    {{FILTERS}}
  ],
} as const
