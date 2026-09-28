import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { KpiCard } from './KpiCard'

const meta: Meta<typeof KpiCard> = {
  title: 'Components/KpiCard',
  component: KpiCard,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
  argTypes: {
    changeType: { control: 'select', options: ['positive', 'negative', 'neutral'] },
  },
}
export default meta
type Story = StoryObj<typeof KpiCard>

export const Revenue: Story = {
  args: { label: 'Total Revenue', value: '2.4M', prefix: '$', change: '12.5% vs last month', changeType: 'positive' },
}

export const Users: Story = {
  args: { label: 'Active Users', value: '18,420', change: '3.2% vs last month', changeType: 'positive', icon: '👤' },
}

export const Churn: Story = {
  args: { label: 'Churn Rate', value: '4.1', suffix: '%', change: '0.8% increase', changeType: 'negative' },
}

export const Neutral: Story = {
  args: { label: 'Avg Session', value: '5m 32s', change: 'No change', changeType: 'neutral', icon: '⏱' },
}

export const Dashboard: Story = {
  render: () => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, padding: 16 }}>
      <KpiCard label="Total Revenue"  value="$2.4M"  change="+12.5%"  changeType="positive" icon="💰" />
      <KpiCard label="Active Users"   value="18,420" change="+3.2%"   changeType="positive" icon="👤" />
      <KpiCard label="Churn Rate"     value="4.1%"   change="+0.8%"   changeType="negative" icon="📉" />
      <KpiCard label="Avg Session"    value="5m 32s" change="No change" changeType="neutral" icon="⏱" />
    </div>
  ),
}
