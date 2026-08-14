// @ts-nocheck
/**
 * PdfExport.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 */
export const config = {
  pageTitle:      '{{PAGE_TITLE}}',
  reportTitle:    '{{REPORT_TITLE}}',
  subtitle:       '{{REPORT_SUBTITLE}}',   // shown on cover page under title
  author:         '{{AUTHOR_NAME}}',       // optional — leave '' to omit
  filenamePrefix: '{{FILENAME_PREFIX}}',   // e.g. 'quarterly-review' → 'quarterly-review-2026-06-17.pdf'

  // Table style: 'striped' | 'grid' | 'plain'
  theme: '{{TABLE_THEME}}',

  // Hex colour used for header bars and table headers
  accentColor: '{{ACCENT_COLOR}}',   // e.g. '#0064D2'

  // One entry per page / section in the PDF (after the cover page)
  sections: [
    {
      title:       '{{SECTION_1_TITLE}}',
      description: '{{SECTION_1_DESCRIPTION}}',
      tableName:   '{{TABLE_NAME_1}}',       // SQLite table name — data auto-fetched from /api/data/{tableName}
      dataExport:  null as any[] | null,     // null = use tableName API
      // Column definitions
      // format: 'text' | 'number' | 'currency' | 'percent' | 'date'
      // pdfWidth: optional column width in mm (omit for auto)
      columns: [
        { key: '{{COL_1_KEY}}', header: '{{COL_1_HEADER}}', format: '{{COL_1_FORMAT}}' },
        { key: '{{COL_2_KEY}}', header: '{{COL_2_HEADER}}', format: '{{COL_2_FORMAT}}' },
        { key: '{{COL_3_KEY}}', header: '{{COL_3_HEADER}}', format: '{{COL_3_FORMAT}}' },
      ],
    },
    {
      title:       '{{SECTION_2_TITLE}}',
      description: '{{SECTION_2_DESCRIPTION}}',
      tableName:   '{{TABLE_NAME_2}}',       // SQLite table name — data auto-fetched from /api/data/{tableName}
      dataExport:  null as any[] | null,     // null = use tableName API
      columns: [
        { key: '{{COL_4_KEY}}', header: '{{COL_4_HEADER}}', format: '{{COL_4_FORMAT}}' },
        { key: '{{COL_5_KEY}}', header: '{{COL_5_HEADER}}', format: '{{COL_5_FORMAT}}' },
      ],
    },
  ],
}
