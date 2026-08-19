// @ts-nocheck
/**
 * Calendar.config.ts — Monthly calendar view with events.
 * Works for: meeting schedules, project deadlines, event planning, booking calendars, etc.
 *
 * RULES:
 * - tableName fetches events from the API
 * - Each event has a date, title, and optional category/color
 * - View supports month navigation and click-to-view-details
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  tableName: '{{TABLE_NAME}}',

  // Field mappings
  dateField: '{{DATE_FIELD}}',        // date/datetime field (ISO format)
  titleField: '{{TITLE_FIELD}}',      // event title shown on calendar
  categoryField: '{{CATEGORY_FIELD}}', // optional category for color coding (null if none)
  descriptionField: '{{DESCRIPTION_FIELD}}', // optional description shown in detail panel (null if none)
  timeField: '{{TIME_FIELD}}',        // optional time display (null if none)

  // Category colors — maps category value to hex color
  categoryColors: {
    '{{CAT_1}}': '{{CAT_1_COLOR}}',
    '{{CAT_2}}': '{{CAT_2_COLOR}}',
    '{{CAT_3}}': '{{CAT_3_COLOR}}',
  },

  // Default color when no category match
  defaultColor: '{{DEFAULT_COLOR}}',
  accentColor: '{{ACCENT_COLOR}}',

  // Week start: 0=Sunday, 1=Monday
  weekStartsOn: 0,
} as const
