// @ts-nocheck
/**
 * ActivityFeed.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values.
 *
 * Works for: news feed, audit log, match results, notifications, event history.
 */
export const config = {
  pageTitle:    '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  tableName: '{{TABLE_NAME}}',             // SQLite table name — data auto-fetched from /api/data/{tableName}
  dataExport: null as any[] | null,        // null = use tableName API

  // Required field mappings
  dateField:     '{{DATE_FIELD}}',     // ISO date string field — used for sorting + grouping
  titleField:    '{{TITLE_FIELD}}',    // primary text shown on each item
  subtitleField: '{{SUBTITLE_FIELD}}', // secondary text (or null)

  // Badge
  badgeField:  {{BADGE_FIELD}},        // string field value shown as badge (or null)
  badgeColors: {                        // map field value → 'default'|'success'|'warning'|'error'|'info'|'accent'
    // '{{VALUE_1}}': 'success',
    // '{{VALUE_2}}': 'warning',
  } as Record<string, string>,

  // Detail / body text (optional — shown collapsible below title)
  detailField: {{DETAIL_FIELD}},       // string field or null

  // Icon / accent color per item (optional)
  iconField:          {{ICON_FIELD}},          // emoji field per row (or null — uses defaultIcon)
  defaultIcon:        '{{DEFAULT_ICON}}',       // emoji shown when iconField is null, e.g. '📋'
  accentColorField:   {{ACCENT_COLOR_FIELD}},   // hex color field per row (or null)
  defaultAccentColor: '{{DEFAULT_ACCENT}}',     // fallback hex, e.g. '#0064D2'

  // Extra metadata shown as label: value pairs below the body
  metaFields: [
    // { field: '{{META_FIELD_1}}', label: '{{META_LABEL_1}}' },
  ] as Array<{ field: string; label: string }>,

  // Optional link label field (shows a "→" clickable label)
  linkLabelField: {{LINK_LABEL_FIELD}},

  // Search: fields included in text search
  searchFields: ['{{TITLE_FIELD}}'] as string[],

  // Filter dropdown: a categorical field to filter by (or null)
  filterField: {{FILTER_FIELD}},
} as const
