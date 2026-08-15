import type { Meta, StoryObj } from '@storybook/react'
import { SearchBar } from './SearchBar'

const meta: Meta<typeof SearchBar> = {
  title: 'Components/SearchBar',
  component: SearchBar,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
  argTypes: {
    disabled:  { control: 'boolean' },
    fullWidth: { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof SearchBar>

export const Default: Story = {
  args: { placeholder: 'Search drivers, vehicles…' },
}

export const FullWidth: Story = {
  args: { placeholder: 'Search…', fullWidth: true },
  decorators: [Story => <div style={{ width: 500, padding: 16 }}><Story /></div>],
}

export const Disabled: Story = {
  args: { placeholder: 'Search disabled', disabled: true },
}

export const WithValue: Story = {
  args: { defaultValue: 'James', placeholder: 'Search…' },
}
