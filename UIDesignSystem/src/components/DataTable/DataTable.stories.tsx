import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { DataTable } from './DataTable'
import { Badge } from '../Badge/Badge'

const meta: Meta<typeof DataTable> = {
  title: 'Components/DataTable',
  component: DataTable,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
  argTypes: {
    striped: { control: 'boolean' },
    loading: { control: 'boolean' },
  },
}
export default meta
type Story = StoryObj<typeof DataTable>

const columns = [
  { key: 'id',     header: 'ID',       width: 60 },
  { key: 'name',   header: 'Driver',   width: 200 },
  { key: 'region', header: 'Region'               },
  { key: 'trips',  header: 'Trips',    align: 'right' as const },
  { key: 'status', header: 'Status',   render: (v: unknown) => (
    <Badge label={String(v)} variant={v === 'Active' ? 'success' : v === 'On Trip' ? 'info' : 'warning'} dot />
  )},
]

const rows = [
  { id: '001', name: 'James Martinez', region: 'West Coast', trips: 142, status: 'Active'  },
  { id: '002', name: 'Sarah Chen',     region: 'Northeast',  trips: 98,  status: 'On Trip' },
  { id: '003', name: 'Mike Johnson',   region: 'Midwest',    trips: 217, status: 'Active'  },
  { id: '004', name: 'Ana García',     region: 'Southwest',  trips: 64,  status: 'Offline' },
  { id: '005', name: 'Tom Williams',   region: 'Southeast',  trips: 183, status: 'Active'  },
]

export const Default: Story = {
  args: { columns, rows },
}

export const Striped: Story = {
  args: { columns, rows, striped: true },
}

export const Loading: Story = {
  args: { columns, rows: [], loading: true },
}

export const Empty: Story = {
  args: { columns, rows: [], emptyMessage: 'No drivers found. Try adjusting your filters.' },
}
