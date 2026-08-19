import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Header } from './Header'
import { Button } from '../Button/Button'
import { Avatar } from '../Avatar/Avatar'

const meta: Meta<typeof Header> = {
  title: 'Layout/Header',
  component: Header,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' }, layout: 'fullscreen' },
}
export default meta
type Story = StoryObj<typeof Header>

export const Default: Story = {
  args: { brandName: 'Mobility Global' },
}

export const WithNav: Story = {
  args: {
    brandName: 'Mobility Global',
    nav: [
      { label: 'Dashboard', active: true },
      { label: 'Analytics' },
      { label: 'Reports' },
      { label: 'Settings' },
    ],
  },
}

export const WithActions: Story = {
  args: {
    brandName: 'Mobility Global',
    nav: [
      { label: 'Dashboard', active: true },
      { label: 'Analytics' },
      { label: 'Reports' },
    ],
    actions: (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Button variant="secondary" size="sm">Invite</Button>
        <Button variant="primary"   size="sm">New Report</Button>
        <Avatar name="Srikanth C" size="sm" status="online" />
      </div>
    ),
  },
}
