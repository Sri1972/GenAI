import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { ProgressBar } from './ProgressBar'

const meta: Meta<typeof ProgressBar> = {
  title: 'Components/ProgressBar',
  component: ProgressBar,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
  argTypes: {
    variant:   { control: 'select', options: ['default', 'success', 'warning', 'error'] },
    size:      { control: 'select', options: ['sm', 'md', 'lg'] },
    value:     { control: { type: 'range', min: 0, max: 100, step: 1 } },
    animated:  { control: 'boolean' },
    showValue: { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof ProgressBar>

export const Default: Story = {
  args: { value: 65, label: 'Upload Progress', showValue: true },
}

export const Success: Story = {
  args: { value: 100, variant: 'success', label: 'Completed', showValue: true },
}

export const Warning: Story = {
  args: { value: 72, variant: 'warning', label: 'Disk Usage', showValue: true },
}

export const Error: Story = {
  args: { value: 95, variant: 'error', label: 'Error Rate', showValue: true },
}

export const Sizes: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16, maxWidth: 400 }}>
      <ProgressBar value={55} size="sm" label="Small (sm)" showValue />
      <ProgressBar value={55} size="md" label="Medium (md)" showValue />
      <ProgressBar value={55} size="lg" label="Large (lg)" showValue />
    </div>
  ),
}

export const Dashboard: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 16, maxWidth: 400 }}>
      <ProgressBar value={82}  label="Fleet Utilization"  showValue variant="default"  size="md" animated />
      <ProgressBar value={100} label="Deliveries Complete" showValue variant="success"  size="md" animated />
      <ProgressBar value={68}  label="Fuel Efficiency"    showValue variant="warning"  size="md" animated />
      <ProgressBar value={12}  label="Incident Rate"      showValue variant="error"    size="md" animated />
    </div>
  ),
}
