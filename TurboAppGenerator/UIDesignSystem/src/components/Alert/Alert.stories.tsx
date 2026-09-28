import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Alert } from './Alert'

const meta: Meta<typeof Alert> = {
  title: 'Components/Alert',
  component: Alert,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
  argTypes: {
    variant:     { control: 'select', options: ['info', 'success', 'warning', 'error'] },
    dismissible: { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof Alert>

export const Info: Story = {
  args: { variant: 'info', title: 'Information', message: 'Your data was last synced 5 minutes ago.' },
}

export const Success: Story = {
  args: { variant: 'success', title: 'Report Generated', message: 'Your report has been successfully created and is ready to download.' },
}

export const Warning: Story = {
  args: { variant: 'warning', title: 'Action Required', message: 'Your subscription expires in 7 days. Please renew to avoid service interruption.' },
}

export const Error: Story = {
  args: { variant: 'error', title: 'Sync Failed', message: 'Unable to connect to the data source. Please check your credentials and try again.' },
}

export const NoTitle: Story = {
  args: { variant: 'info', message: 'This is a simple alert without a title.' },
}

export const Dismissible: Story = {
  args: { variant: 'success', title: 'Upload Complete', message: '42 records were imported successfully.', dismissible: true },
}

export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 16, maxWidth: 560 }}>
      <Alert variant="info"    title="Info"    message="Informational message for the user." />
      <Alert variant="success" title="Success" message="Operation completed successfully." />
      <Alert variant="warning" title="Warning" message="Please review before continuing." />
      <Alert variant="error"   title="Error"   message="Something went wrong. Please try again." />
    </div>
  ),
}
