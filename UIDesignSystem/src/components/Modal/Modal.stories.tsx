import type { Meta, StoryObj } from '@storybook/react'
import React, { useState } from 'react'
import { Modal } from './Modal'
import { Button } from '../Button/Button'

const meta: Meta<typeof Modal> = {
  title: 'Components/Modal',
  component: Modal,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
  argTypes: {
    size: { control: 'select', options: ['sm', 'md', 'lg', 'xl'] },
    open: { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof Modal>

export const Default: Story = {
  args: {
    open: true,
    title: 'Confirm Action',
    children: <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: '#374151' }}>
      Are you sure you want to delete this record? This action cannot be undone and all associated data will be permanently removed.
    </p>,
    footer: (
      <>
        <Button variant="secondary" size="sm">Cancel</Button>
        <Button variant="danger"    size="sm">Delete</Button>
      </>
    ),
  },
}

export const Large: Story = {
  args: {
    open: true,
    title: 'Create New Report',
    size: 'lg',
    children: <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <p style={{ margin: 0, fontSize: 14, color: '#374151' }}>Configure your report settings below.</p>
      <div style={{ height: 200, background: '#F4F4F4', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF' }}>
        Report configuration form
      </div>
    </div>,
    footer: (
      <>
        <Button variant="secondary" size="sm">Cancel</Button>
        <Button variant="primary"   size="sm">Create Report</Button>
      </>
    ),
  },
}

export const Interactive: Story = {
  render: () => {
    const [open, setOpen] = useState(false)
    return (
      <div style={{ padding: 24 }}>
        <Button onClick={() => setOpen(true)}>Open Modal</Button>
        <Modal
          open={open}
          title="Edit Profile"
          onClose={() => setOpen(false)}
          footer={
            <>
              <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary" size="sm" onClick={() => setOpen(false)}>Save Changes</Button>
            </>
          }
        >
          <p style={{ margin: 0, fontSize: 14, color: '#374151' }}>Modal content here. Click outside or × to close.</p>
        </Modal>
      </div>
    )
  },
}
