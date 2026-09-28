// @ts-nocheck
/**
 * AiChat.config.ts — Fill in for each project.
 * Replace every {{PLACEHOLDER}} with real values from the project data.
 */

export const config = {
  pageTitle: '{{PAGE_TITLE}}',
  pageSubtitle: '{{PAGE_SUBTITLE}}',

  // Personas — each one is a selectable AI assistant with its own prompts
  personas: [
    {
      id: '{{PERSONA_1_ID}}',
      name: '{{PERSONA_1_NAME}}',
      role: '{{PERSONA_1_ROLE}}',
      description: '{{PERSONA_1_DESCRIPTION}}',
      accentColor: '{{PERSONA_1_COLOR}}',
      prompts: [
        { id: 'p1a', label: '{{PROMPT_1A_LABEL}}', question: '{{PROMPT_1A_QUESTION}}' },
        { id: 'p1b', label: '{{PROMPT_1B_LABEL}}', question: '{{PROMPT_1B_QUESTION}}' },
        { id: 'p1c', label: '{{PROMPT_1C_LABEL}}', question: '{{PROMPT_1C_QUESTION}}' },
        { id: 'p1d', label: '{{PROMPT_1D_LABEL}}', question: '{{PROMPT_1D_QUESTION}}' },
      ],
    },
    {
      id: '{{PERSONA_2_ID}}',
      name: '{{PERSONA_2_NAME}}',
      role: '{{PERSONA_2_ROLE}}',
      description: '{{PERSONA_2_DESCRIPTION}}',
      accentColor: '{{PERSONA_2_COLOR}}',
      prompts: [
        { id: 'p2a', label: '{{PROMPT_2A_LABEL}}', question: '{{PROMPT_2A_QUESTION}}' },
        { id: 'p2b', label: '{{PROMPT_2B_LABEL}}', question: '{{PROMPT_2B_QUESTION}}' },
        { id: 'p2c', label: '{{PROMPT_2C_LABEL}}', question: '{{PROMPT_2C_QUESTION}}' },
      ],
    },
  ],

  // Pre-built responses keyed by the exact question string
  // The skill also does fuzzy matching on substrings
  responses: {
    '{{RESPONSE_KEY_1}}': '{{RESPONSE_VALUE_1}}',
    '{{RESPONSE_KEY_2}}': '{{RESPONSE_VALUE_2}}',
    '{{RESPONSE_KEY_3}}': '{{RESPONSE_VALUE_3}}',
    '{{RESPONSE_KEY_4}}': '{{RESPONSE_VALUE_4}}',
    '{{RESPONSE_KEY_5}}': '{{RESPONSE_VALUE_5}}',
    '{{RESPONSE_KEY_6}}': '{{RESPONSE_VALUE_6}}',
  } as Record<string, string>,

  // Used when the question doesn't match any key
  fallbackResponse: '{{FALLBACK_RESPONSE}}',

  // Optional caption in the right panel (or null)
  exportCaption: '{{EXPORT_CAPTION}}',
} as const
