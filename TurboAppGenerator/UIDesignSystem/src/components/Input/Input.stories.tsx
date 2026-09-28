import type { Meta, StoryObj } from '@storybook/react'
import { Input } from './Input'

const meta: Meta<typeof Input> = {
  title: 'Components/Input',
  component: Input,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
  argTypes: {
    type:     { control: 'select', options: ['text', 'email', 'password', 'number', 'search'] },
    disabled: { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof Input>

export const Default: Story = {
  args: { label: 'Full Name', placeholder: 'Enter your name' },
}

export const WithHint: Story = {
  args: { label: 'Email', placeholder: 'name@company.com', type: 'email', hint: 'We will never share your email.' },
}

export const WithError: Story = {
  args: { label: 'Password', type: 'password', defaultValue: 'abc', error: 'Password must be at least 8 characters.' },
}

export const WithPrefix: Story = {
  args: { label: 'Website', placeholder: 'yoursite.com', prefix: 'https://' },
}

export const WithSuffix: Story = {
  args: { label: 'Amount', placeholder: '0.00', suffix: 'USD', type: 'number' },
}

export const Disabled: Story = {
  args: { label: 'Read Only', defaultValue: 'Cannot edit this', disabled: true },
}

export const Search: Story = {
  args: { placeholder: 'Search records…', type: 'search' },
}
