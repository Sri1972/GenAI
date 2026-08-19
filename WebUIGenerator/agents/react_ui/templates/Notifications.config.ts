// @ts-nocheck
/**
 * Notifications.config.ts — Notification center / inbox.
 * Works for: alerts, messages, system notifications, approval queues, etc.
 *
 * RULES:
 * - tableName fetches notifications from the API
 * - Each notification has a title, message, timestamp, type, and read/unread status
 * - Supports filtering by type and marking as read
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  tableName: '{{TABLE_NAME}}',

  // Field mappings
  titleField: '{{TITLE_FIELD}}',
  messageField: '{{MESSAGE_FIELD}}',
  timestampField: '{{TIMESTAMP_FIELD}}',
  typeField: '{{TYPE_FIELD}}',         // notification category (null if none)
  readField: '{{READ_FIELD}}',         // boolean field for read/unread status (null if none)
  priorityField: '{{PRIORITY_FIELD}}', // null if none

  // Type icons/colors
  typeConfig: {
    '{{TYPE_1}}': { icon: '{{ICON_1}}', color: '{{TYPE_1_COLOR}}' },
    '{{TYPE_2}}': { icon: '{{ICON_2}}', color: '{{TYPE_2_COLOR}}' },
    '{{TYPE_3}}': { icon: '{{ICON_3}}', color: '{{TYPE_3_COLOR}}' },
  },

  accentColor: '{{ACCENT_COLOR}}',

  // Available icons: 'bell', 'mail', 'alert', 'check', 'info', 'warning', 'error', 'message', 'calendar', 'user'
} as const
