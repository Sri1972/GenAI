// @ts-nocheck
/**
 * ExcelParser.config.ts — Fill in for each project.
 * Minimal config since the skill is fully self-contained (data comes from user upload).
 */

export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  // Accent color for the upload zone and active tab indicator
  accentColor: '{{ACCENT_COLOR}}',

  // Maximum rows to use for chart generation (larger sheets are sampled)
  maxChartRows: 5000,

  // Chart color palette — 10 colors used for series/slices/bars
  chartColors: [
    '{{COLOR_1}}', '{{COLOR_2}}', '{{COLOR_3}}', '{{COLOR_4}}', '{{COLOR_5}}',
    '{{COLOR_6}}', '{{COLOR_7}}', '{{COLOR_8}}', '{{COLOR_9}}', '{{COLOR_10}}'
  ],
}
