// @ts-nocheck
/**
 * DetailPage.config.ts — Master-detail layout.
 * Left panel shows a searchable list of items. Clicking an item shows full details in the right panel.
 * Works for: product details, employee profiles, order details, case management, etc.
 *
 * RULES:
 * - tableName fetches items from the API
 * - listFields define what shows in the left-panel list items
 * - detailSections define the right-panel layout when an item is selected
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  tableName: '{{TABLE_NAME}}',

  // List panel config (left side)
  listTitleField: '{{LIST_TITLE_FIELD}}',
  listSubtitleField: '{{LIST_SUBTITLE_FIELD}}',  // null if none
  listBadgeField: '{{LIST_BADGE_FIELD}}',        // null if none
  listBadgeColors: {
    '{{BADGE_VAL_1}}': '{{BADGE_COLOR_1}}',
    '{{BADGE_VAL_2}}': '{{BADGE_COLOR_2}}',
  },
  searchFields: ['{{SEARCH_FIELD_1}}', '{{SEARCH_FIELD_2}}'],

  // Detail panel config (right side)
  detailTitleField: '{{DETAIL_TITLE_FIELD}}',
  detailSubtitleField: '{{DETAIL_SUBTITLE_FIELD}}', // null if none
  detailSections: [
    {
      title: '{{SECTION_1_TITLE}}',
      type: 'fields',  // 'fields' | 'table' | 'text'
      fields: [
        { key: '{{FIELD_1_KEY}}', label: '{{FIELD_1_LABEL}}', format: 'text' },
        { key: '{{FIELD_2_KEY}}', label: '{{FIELD_2_LABEL}}', format: 'currency' },
        // format: 'text' | 'number' | 'currency' | 'percent' | 'date' | 'badge'
      ],
    },
    // Add more sections as needed
  ],

  accentColor: '{{ACCENT_COLOR}}',
} as const
