// @ts-nocheck
/**
 * KpiDashboard.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 * Valid Badge directions: 'up' | 'down' | 'neutral'
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',

  // KPI summary cards — 4 recommended (static values computed from data)
  kpiCards: [
    { label: '{{KPI_1_LABEL}}', value: '{{KPI_1_VALUE}}', change: '{{KPI_1_CHANGE}}', direction: '{{KPI_1_DIR}}' as 'up'|'down'|'neutral', icon: '{{KPI_1_ICON}}' },
    { label: '{{KPI_2_LABEL}}', value: '{{KPI_2_VALUE}}', change: '{{KPI_2_CHANGE}}', direction: '{{KPI_2_DIR}}' as 'up'|'down'|'neutral', icon: '{{KPI_2_ICON}}' },
    { label: '{{KPI_3_LABEL}}', value: '{{KPI_3_VALUE}}', change: '{{KPI_3_CHANGE}}', direction: '{{KPI_3_DIR}}' as 'up'|'down'|'neutral', icon: '{{KPI_3_ICON}}' },
    { label: '{{KPI_4_LABEL}}', value: '{{KPI_4_VALUE}}', change: '{{KPI_4_CHANGE}}', direction: '{{KPI_4_DIR}}' as 'up'|'down'|'neutral', icon: '{{KPI_4_ICON}}' },
  ],

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
