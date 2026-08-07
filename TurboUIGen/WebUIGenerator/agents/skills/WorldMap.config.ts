// @ts-nocheck
/**
 * WorldMap.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 *
 * region options (zoom to a continent or stay world-wide):
 *   'world' | 'europe' | 'asia' | 'north-america' | 'south-america'
 *   'americas' | 'africa' | 'middle-east' | 'southeast-asia' | 'oceania'
 */
export const config = {
  tableName: '{{TABLE_NAME}}',             // SQLite table name — data auto-fetched from /api/data/{tableName}
  dataExport: null as any[] | null,        // null = use tableName API

  // ISO-2 country code field (e.g. 'US', 'DE', 'JP')
  countryCodeField: '{{COUNTRY_CODE_FIELD}}',

  // Numeric field that drives colour intensity
  valueField: '{{VALUE_FIELD}}',

  // Country name field — used in the tooltip and top-10 table
  labelField: '{{LABEL_FIELD}}',

  title: '{{CHART_TITLE}}',

  // Colour ramp: 'blue' | 'green' | 'orange' | 'purple' | 'red'
  colorScheme: '{{COLOR_SCHEME}}' as 'blue' | 'green' | 'orange' | 'purple' | 'red',

  // Map region to zoom into. Use 'world' for a full world map.
  // Options: 'world' | 'europe' | 'asia' | 'north-america' | 'south-america'
  //          'americas' | 'africa' | 'middle-east' | 'southeast-asia' | 'oceania'
  region: '{{REGION}}' as 'world' | 'europe' | 'asia' | 'north-america' | 'south-america' | 'americas' | 'africa' | 'middle-east' | 'southeast-asia' | 'oceania',

  // Dropdown filter field — set to null if not needed
  filterField: {{FILTER_FIELD}},
} as const
