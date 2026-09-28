import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Card } from './Card'
import { Button } from '../Button/Button'

const meta: Meta<typeof Card> = {
  title: 'Components/Card',
  component: Card,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
  argTypes: {
    elevation: { control: 'select', options: ['flat', 'sm', 'md', 'lg'] },
    padding:   { control: 'select', options: ['none', 'sm', 'md', 'lg'] },
  },
}
export default meta
type Story = StoryObj<typeof Card>

export const Default: Story = {
  args: {
    title: 'Card Title',
    subtitle: 'Supporting subheader text',
    children: <p style={{ margin: 0, fontSize: 14, color: '#374151' }}>Card body content goes here. This can be any React node.</p>,
  },
}

export const WithFooter: Story = {
  args: {
    title: 'Confirm Action',
    children: <p style={{ margin: 0, fontSize: 14, color: '#374151' }}>Are you sure you want to proceed? This cannot be undone.</p>,
    footer: (
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Button variant="secondary" size="sm">Cancel</Button>
        <Button variant="primary"   size="sm">Confirm</Button>
      </div>
    ),
  },
}

export const ElevationLg: Story = {
  args: {
    title: 'High Elevation',
    elevation: 'lg',
    children: <p style={{ margin: 0, fontSize: 14, color: '#374151' }}>Large shadow variant.</p>,
  },
}

export const Flat: Story = {
  args: {
    title: 'Flat Card',
    elevation: 'flat',
    children: <p style={{ margin: 0, fontSize: 14, color: '#374151' }}>No shadow, border only.</p>,
  },
}
