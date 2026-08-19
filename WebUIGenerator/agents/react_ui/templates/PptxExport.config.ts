// @ts-nocheck
/**
 * PptxExport.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 */
export const config = {
  pageTitle: '{{PAGE_TITLE}}',

  // File name prefix — downloaded as "{prefix}-YYYY-MM-DD.pptx"
  filenamePrefix: '{{FILENAME_PREFIX}}',

  // Slide themes — 2-3 options
  themes: [
    { id: 'corporate',   name: 'Corporate Blue',  description: 'Professional blue',  bg: '#FFFFFF', accent: '#0064D2', textColor: '#1F2937' },
    { id: 'dark',        name: 'Dark Mode',        description: 'Dark background',    bg: '#1F2937', accent: '#3B82F6', textColor: '#F9FAFB' },
    { id: 'light',       name: 'Light Modern',     description: 'Clean minimal',      bg: '#F8FAFC', accent: '#6366F1', textColor: '#1F2937' },
  ],

  // Slide definitions — one entry per content slide (cover is auto-generated)
  slides: [
    {
      id: 'slide1',
      title: '{{SLIDE_1_TITLE}}',
      description: '{{SLIDE_1_DESCRIPTION}}',
      dataKey: 'data1',   // must match a key in dataMap below
      bulletTemplate: (row: any): string => `{{SLIDE_1_BULLET_TEMPLATE}}`,
    },
    {
      id: 'slide2',
      title: '{{SLIDE_2_TITLE}}',
      description: '{{SLIDE_2_DESCRIPTION}}',
      dataKey: 'data2',
      bulletTemplate: (row: any): string => `{{SLIDE_2_BULLET_TEMPLATE}}`,
    },
  ],

  // Data tables for each slide — keyed by slide.dataKey
  // tableName values come from schema.sql — data auto-fetched from /api/data/{tableName}
  dataTableNames: {
    data1: '{{TABLE_NAME_1}}',
    data2: '{{TABLE_NAME_2}}',
  },
  dataMap: {
    data1: null as any[] | null,   // null = use dataTableNames API
    data2: null as any[] | null,   // null = use dataTableNames API
  },
}
