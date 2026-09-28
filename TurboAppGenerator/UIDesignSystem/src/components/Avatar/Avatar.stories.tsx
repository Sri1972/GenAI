import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Avatar, AvatarGroup } from './Avatar'

const meta: Meta<typeof Avatar> = {
  title: 'Components/Avatar',
  component: Avatar,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
  argTypes: {
    size:   { control: 'select', options: ['xs', 'sm', 'md', 'lg', 'xl'] },
    shape:  { control: 'select', options: ['circle', 'square'] },
    status: { control: 'select', options: [undefined, 'online', 'offline', 'busy', 'away'] },
  },
}
export default meta
type Story = StoryObj<typeof Avatar>

export const Initials: Story = {
  args: { name: 'Srikanth C', size: 'md' },
}

export const Online: Story = {
  args: { name: 'Sarah Chen', size: 'lg', status: 'online' },
}

export const Square: Story = {
  args: { name: 'Tom Williams', size: 'md', shape: 'square' },
}

export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', padding: 16 }}>
      <Avatar name="Srikanth C" size="xs" />
      <Avatar name="Srikanth C" size="sm" />
      <Avatar name="Srikanth C" size="md" />
      <Avatar name="Srikanth C" size="lg" />
      <Avatar name="Srikanth C" size="xl" />
    </div>
  ),
}

export const AllStatuses: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: 16, alignItems: 'center', padding: 16 }}>
      <Avatar name="Alice"   size="lg" status="online"  />
      <Avatar name="Bob"     size="lg" status="busy"    />
      <Avatar name="Carol"   size="lg" status="away"    />
      <Avatar name="Dan"     size="lg" status="offline" />
    </div>
  ),
}

export const Group: Story = {
  render: () => (
    <div style={{ padding: 16 }}>
      <AvatarGroup
        size="md"
        avatars={[
          { name: 'Alice Baker' },
          { name: 'Bob Chen' },
          { name: 'Carol Diaz' },
          { name: 'Dan Evans' },
          { name: 'Eve Fisher' },
          { name: 'Frank Green' },
        ]}
        max={4}
      />
    </div>
  ),
}
