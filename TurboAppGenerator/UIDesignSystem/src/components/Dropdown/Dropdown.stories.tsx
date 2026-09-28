import type { Meta, StoryObj } from '@storybook/react'
import React, { useState } from 'react'
import { Dropdown } from './Dropdown'

const meta: Meta<typeof Dropdown> = {
  title: 'Components/Dropdown',
  component: Dropdown,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'white' } },
}
export default meta
type Story = StoryObj<typeof Dropdown>

const regionOptions = [
  { value: 'west',      label: 'West Coast'  },
  { value: 'northeast', label: 'Northeast'   },
  { value: 'midwest',   label: 'Midwest'     },
  { value: 'southwest', label: 'Southwest'   },
  { value: 'southeast', label: 'Southeast'   },
]

export const Default: Story = {
  args: { options: regionOptions, label: 'Region', placeholder: 'Select a region…' },
}

export const WithValue: Story = {
  args: { options: regionOptions, label: 'Region', value: 'northeast' },
}

export const WithError: Story = {
  args: { options: regionOptions, label: 'Region', error: 'Please select a region.' },
}

export const Disabled: Story = {
  args: { options: regionOptions, label: 'Region', value: 'midwest', disabled: true },
}

export const Interactive: Story = {
  render: () => {
    const [val, setVal] = useState('')
    return (
      <div style={{ width: 280, padding: 16 }}>
        <Dropdown options={regionOptions} label="Region" value={val} onChange={setVal}
          placeholder="Select a region…" />
        {val && <p style={{ marginTop: 8, fontSize: 13, color: '#374151' }}>Selected: <b>{val}</b></p>}
      </div>
    )
  },
}
