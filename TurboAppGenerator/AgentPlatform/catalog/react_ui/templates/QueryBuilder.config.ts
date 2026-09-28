// @ts-nocheck
/**
 * QueryBuilder.config.ts — FILL IN for each project.
 *
 * Replace every {{PLACEHOLDER}} with real values from this project's data.
 * Columns and their types are NOT configured here — they are discovered at
 * runtime from GET /api/metadata for tableName, so this skill stays
 * domain-agnostic.
 */
export const config = {
  // SQLite table name — data queried from /api/{tableName}
  tableName: '{{TABLE_NAME}}',

  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  // Filename used when exporting query results to CSV
  csvFilename: '{{CSV_FILENAME}}',
} as const
