import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './Button'

const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
  argTypes: {
    variant:   { control: 'select', options: ['primary', 'secondary', 'ghost', 'danger'] },
    size:      { control: 'select', options: ['sm', 'md', 'lg'] },
    disabled:  { control: 'boolean' },
    loading:   { control: 'boolean' },
    fullWidth: { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: { children: 'Primary Button', variant: 'primary', size: 'md' },
}

export const Secondary: Story = {
  args: { children: 'Secondary Button', variant: 'secondary', size: 'md' },
}

export const Ghost: Story = {
  args: { children: 'Ghost Button', variant: 'ghost', size: 'md' },
}

export const Danger: Story = {
  args: { children: 'Delete', variant: 'danger', size: 'md' },
}

export const Small: Story = {
  args: { children: 'Small', variant: 'primary', size: 'sm' },
}

export const Large: Story = {
  args: { children: 'Large', variant: 'primary', size: 'lg' },
}

export const Loading: Story = {
  args: { children: 'Saving…', variant: 'primary', size: 'md', loading: true },
}

export const Disabled: Story = {
  args: { children: 'Disabled', variant: 'primary', size: 'md', disabled: true },
}

export const FullWidth: Story = {
  args: { children: 'Full Width Button', variant: 'primary', size: 'md', fullWidth: true },
  decorators: [Story => <div style={{ width: 400 }}><Story /></div>],
}

export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', padding: 16 }}>
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="danger">Danger</Button>
    </div>
  ),
}

export const AllSizes: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', padding: 16 }}>
      <Button variant="primary" size="sm">Small</Button>
      <Button variant="primary" size="md">Medium</Button>
      <Button variant="primary" size="lg">Large</Button>
    </div>
  ),
}
