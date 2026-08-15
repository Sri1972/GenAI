import type { Meta, StoryObj } from '@storybook/react'
import { Badge } from './Badge'

const meta: Meta<typeof Badge> = {
  title: 'Components/Badge',
  component: Badge,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
  argTypes: {
    variant: { control: 'select', options: ['default', 'success', 'warning', 'error', 'info', 'accent'] },
    size:    { control: 'select', options: ['sm', 'md'] },
    dot:     { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof Badge>

export const Default: Story = { args: { label: 'Default' } }
export const Success: Story = { args: { label: 'Active',    variant: 'success' } }
export const Warning: Story = { args: { label: 'Pending',   variant: 'warning' } }
export const Error:   Story = { args: { label: 'Failed',    variant: 'error'   } }
export const Info:    Story = { args: { label: 'Info',      variant: 'info'    } }
export const Accent:  Story = { args: { label: 'Premium',   variant: 'accent'  } }
export const WithDot: Story = { args: { label: 'Live',      variant: 'success', dot: true } }

export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: 16 }}>
      <Badge label="Default" />
      <Badge label="Active"  variant="success" dot />
      <Badge label="Pending" variant="warning" dot />
      <Badge label="Failed"  variant="error"   dot />
      <Badge label="Info"    variant="info"    dot />
      <Badge label="Premium" variant="accent"  />
    </div>
  ),
}
