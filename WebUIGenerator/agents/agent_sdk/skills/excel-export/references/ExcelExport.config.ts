// @ts-nocheck
/**
 * ExcelExport.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',

  // Downloaded file name: "{filename}-YYYY-MM-DD.xlsx"
  filename: '{{FILENAME_PREFIX}}',

  // One entry per worksheet tab in the Excel file
  sheets: [
    {
      name: '{{SHEET_1_NAME}}',
      tableName: '{{TABLE_NAME_1}}',          // SQLite table name — data auto-fetched from /api/data/{tableName}
      dataExport: null as any[] | null,       // null = use tableName API
      // Column definitions — key = field name, header = column heading
      // format: 'text' | 'number' | 'currency' | 'percent' | 'date'
      // width: optional character width for the column
      columns: [
        { key: '{{COL_1_KEY}}', header: '{{COL_1_HEADER}}', format: '{{COL_1_FORMAT}}' },
        { key: '{{COL_2_KEY}}', header: '{{COL_2_HEADER}}', format: '{{COL_2_FORMAT}}' },
        { key: '{{COL_3_KEY}}', header: '{{COL_3_HEADER}}', format: '{{COL_3_FORMAT}}' },
        // Add more columns as needed
      ],
    },
    {
      name: '{{SHEET_2_NAME}}',
      tableName: '{{TABLE_NAME_2}}',          // SQLite table name — data auto-fetched from /api/data/{tableName}
      dataExport: null as any[] | null,       // null = use tableName API
      columns: [
        { key: '{{COL_4_KEY}}', header: '{{COL_4_HEADER}}', format: '{{COL_4_FORMAT}}' },
        { key: '{{COL_5_KEY}}', header: '{{COL_5_HEADER}}', format: '{{COL_5_FORMAT}}' },
      ],
    },
  ],
}
