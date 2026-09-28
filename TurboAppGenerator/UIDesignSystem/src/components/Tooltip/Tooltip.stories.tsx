import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { Tooltip } from './Tooltip'
import { Button } from '../Button/Button'

const meta: Meta<typeof Tooltip> = {
  title: 'Components/Tooltip',
  component: Tooltip,
  tags: ['autodocs'],
  parameters: { backgrounds: { default: 'page' } },
  argTypes: {
    placement: { control: 'select', options: ['top', 'bottom', 'left', 'right'] },
  },
}
export default meta
type Story = StoryObj<typeof Tooltip>

export const Default: Story = {
  args: { content: 'This is a tooltip', placement: 'top' },
  render: (args) => (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
      <Tooltip {...args}>
        <Button>Hover me</Button>
      </Tooltip>
    </div>
  ),
}

export const AllPlacements: Story = {
  render: () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48, padding: 64, placeItems: 'center' }}>
      <Tooltip content="Top tooltip"    placement="top">    <Button size="sm">Top</Button>    </Tooltip>
      <Tooltip content="Bottom tooltip" placement="bottom"> <Button size="sm">Bottom</Button> </Tooltip>
      <Tooltip content="Left tooltip"   placement="left">   <Button size="sm">Left</Button>   </Tooltip>
      <Tooltip content="Right tooltip"  placement="right">  <Button size="sm">Right</Button>  </Tooltip>
    </div>
  ),
}
