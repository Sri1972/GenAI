// @ts-nocheck
/**
 * SettingsForm.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values.
 *
 * Field types: 'text' | 'email' | 'number' | 'password' | 'select' | 'toggle' | 'textarea'
 */
export const config = {
  pageTitle:    '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  sections: [
    {
      title:       '{{SECTION_1_TITLE}}',
      description: '{{SECTION_1_DESC}}',
      icon:        '{{SECTION_1_ICON}}',   // emoji or null
      fields: [
        {
          key:          '{{FIELD_1_KEY}}',
          label:        '{{FIELD_1_LABEL}}',
          type:         '{{FIELD_1_TYPE}}',  // 'text'|'email'|'number'|'select'|'toggle'|'textarea'
          placeholder:  '{{FIELD_1_PLACEHOLDER}}',
          defaultValue: '{{FIELD_1_DEFAULT}}',
          required:     {{FIELD_1_REQUIRED}},
          hint:         '{{FIELD_1_HINT}}',
          options: [    // only for type='select'
            // { value: '{{OPT_VALUE}}', label: '{{OPT_LABEL}}' },
          ],
        },
        // Add more fields as needed
      ],
    },
    // Add more sections as needed
  ],
} as const
