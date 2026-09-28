import type { Meta, StoryObj } from '@storybook/react'
import React, { useState } from 'react'
import { Pagination } from './Pagination'

const meta: Meta<typeof Pagination> = {
  title: 'Components/Pagination',
  component: Pagination,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
}
export default meta
type Story = StoryObj<typeof Pagination>

export const Default: Story = {
  args: { total: 120, page: 1, pageSize: 10 },
}

export const MiddlePage: Story = {
  args: { total: 250, page: 7, pageSize: 10 },
}

export const FewPages: Story = {
  args: { total: 40, page: 2, pageSize: 10 },
}

export const Interactive: Story = {
  render: () => {
    const [page, setPage] = useState(1)
    return (
      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'flex-start' }}>
        <p style={{ fontSize: 14, color: '#374151', margin: 0 }}>Page {page} of 25 (250 records)</p>
        <Pagination total={250} page={page} pageSize={10} onChange={setPage} />
      </div>
    )
  },
}
