// @ts-nocheck
/**
 * TabLayout.config.ts — Tabbed page layout.
 * Each tab can contain any mix of: charts, tables, card grids, KPI rows, or custom sections.
 *
 * RULES:
 * - Each tab has a title (shown in the tab bar) and a sections[] array.
 * - Each section has a type and its own config matching that type.
 * - Supported section types: 'chart', 'table', 'kpi-row', 'cards', 'text'
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',
  accentColor: '{{ACCENT_COLOR}}',

  tabs: [
    {
      title: '{{TAB_1_TITLE}}',
      sections: [
        // Example chart section:
        // { type: 'chart', chartType: 'line', title: 'Monthly Trend', data: [...], xField: 'month', series: [...] },
        // Example table section:
        // { type: 'table', title: 'Details', data: [...], columns: [{key:'name',header:'Name'}, ...] },
        // Example KPI row:
        // { type: 'kpi-row', kpis: [{label:'Revenue', value:'$1.2M', change:'+12%', direction:'up'}] },
        // Example text/heading:
        // { type: 'text', content: 'Summary paragraph or heading text here.' },
      ],
    },
    // Add more tabs as needed
  ],
} as const
