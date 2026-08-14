// @ts-nocheck
/**
 * KpiDashboard.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 * Valid Badge directions: 'up' | 'down' | 'neutral'
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',

  // KPI summary cards — fetched from API at runtime
  // Option A: fetch from a dedicated KPI table (set kpiTableName)
  // Option B: static values (set kpiCards array directly)
  kpiTableName: '{{KPI_TABLE}}' as string | null,  // e.g. 'kpis' — set to null if using static kpiCards
  kpiMapping: {
    label: '{{KPI_LABEL_FIELD}}',       // e.g. 'metric'
    value: '{{KPI_VALUE_FIELD}}',       // e.g. 'value'
    change: '{{KPI_CHANGE_FIELD}}',     // e.g. 'change_pct'
    direction: '{{KPI_DIR_FIELD}}',     // e.g. 'direction'
  },
  kpiCards: null as any[] | null,       // null = fetch from kpiTableName; or provide static array

  // Left chart — 'bar' or 'donut'
  chart1: {
    type: '{{CHART1_TYPE}}' as 'bar' | 'donut',
    title: '{{CHART1_TITLE}}',
    tableName: '{{CHART1_TABLE}}',       // API table to fetch chart1 data from
    labelField: '{{CHART1_LABEL_FIELD}}',
    valueField: '{{CHART1_VALUE_FIELD}}',
    data: null as any[] | null,          // auto-fetched from API
    valueFormat: '{{CHART1_FORMAT}}',
  },

  // Right chart — 'line'
  chart2: {
    type: 'line' as const,
    title: '{{CHART2_TITLE}}',
    tableName: '{{CHART2_TABLE}}',       // API table to fetch chart2 data from
    xField: '{{CHART2_X_FIELD}}',
    series: [
      { label: '{{SERIES_1_LABEL}}', color: '{{SERIES_1_COLOR}}', field: '{{SERIES_1_VALUE_FIELD}}' },
    ],
    yFormat: '{{CHART2_Y_FORMAT}}',
    data: null as any[] | null,          // auto-fetched from API
  },

  // Optional bottom table — tableName to fetch, or null to hide
  tableName: null as string | null,      // set to a table name for bottom data table
  tableColumns: null as Array<{key:string, header:string}> | null,
} as const
