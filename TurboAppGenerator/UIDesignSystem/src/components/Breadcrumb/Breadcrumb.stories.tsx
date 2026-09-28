import type { Meta, StoryObj } from '@storybook/react'
import { Breadcrumb } from './Breadcrumb'

const meta: Meta<typeof Breadcrumb> = {
  title: 'Components/Breadcrumb',
  component: Breadcrumb,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
}
export default meta
type Story = StoryObj<typeof Breadcrumb>

export const Default: Story = {
  args: {
    items: [
      { label: 'Dashboard' },
      { label: 'Reports' },
      { label: 'Q2 Fleet Summary' },
    ],
  },
}

export const TwoLevels: Story = {
  args: {
    items: [
      { label: 'Drivers' },
      { label: 'James Martinez' },
    ],
  },
}

export const CustomSeparator: Story = {
  args: {
    items: [
      { label: 'Home' },
      { label: 'Analytics' },
      { label: 'Regional' },
      { label: 'West Coast' },
    ],
    separator: '›',
  },
}
