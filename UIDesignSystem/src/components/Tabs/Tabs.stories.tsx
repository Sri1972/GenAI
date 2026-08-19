import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Tabs } from './Tabs'
import { Badge } from '../Badge/Badge'

const meta: Meta<typeof Tabs> = {
  title: 'Components/Tabs',
  component: Tabs,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
  argTypes: {
    variant: { control: 'select', options: ['line', 'pill'] },
  },
}
export default meta
type Story = StoryObj<typeof Tabs>

const items = [
  { key: 'overview',  label: 'Overview',  content: <p style={{ padding: '16px 0', fontSize: 14, color: '#374151' }}>Overview content panel.</p> },
  { key: 'analytics', label: 'Analytics', badge: 4, content: <p style={{ padding: '16px 0', fontSize: 14, color: '#374151' }}>Analytics panel with 4 new items.</p> },
  { key: 'reports',   label: 'Reports',   content: <p style={{ padding: '16px 0', fontSize: 14, color: '#374151' }}>Reports panel content.</p> },
  { key: 'settings',  label: 'Settings',  disabled: true },
]

export const Line: Story = {
  args: { items, defaultKey: 'overview', variant: 'line' },
}

export const Pill: Story = {
  args: { items, defaultKey: 'analytics', variant: 'pill' },
  parameters: { backgrounds: { default: 'page' } },
}

export const NoBadges: Story = {
  args: {
    items: [
      { key: 'all',      label: 'All Vehicles' },
      { key: 'active',   label: 'Active'       },
      { key: 'inactive', label: 'Inactive'     },
      { key: 'service',  label: 'In Service'   },
    ],
    defaultKey: 'all',
    variant: 'line',
  },
}
