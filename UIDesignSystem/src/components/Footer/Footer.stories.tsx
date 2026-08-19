import type { Meta, StoryObj } from '@storybook/react'
import { Footer } from './Footer'

const meta: Meta<typeof Footer> = {
  title: 'Layout/Footer',
  component: Footer,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
  argTypes: {
    variant: { control: 'select', options: ['light', 'dark'] },
  },
}
export default meta
type Story = StoryObj<typeof Footer>

export const Light: Story = {
  args: {
    variant: 'light',
    brand: 'Mobility Global',
    links: [{ label: 'Privacy' }, { label: 'Terms' }, { label: 'Support' }],
  },
  parameters: { backgrounds: { default: 'page' } },
}

export const Dark: Story = {
  args: {
    variant: 'dark',
    brand: 'Mobility Global',
    links: [{ label: 'Privacy' }, { label: 'Terms' }, { label: 'Support' }],
  },
  parameters: { backgrounds: { default: 'dark' } },
}
