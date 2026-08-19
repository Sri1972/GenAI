import type { Preview } from '@storybook/react'

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: 'page',
      values: [
        { name: 'page',    value: '#EFEFE5' },
        { name: 'white',   value: '#FFFFFF' },
        { name: 'sidebar', value: '#132445' },
        { name: 'dark',    value: '#111827' },
      ],
    },
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    docs: {
      theme: undefined,
    },
  },
}

export default preview
