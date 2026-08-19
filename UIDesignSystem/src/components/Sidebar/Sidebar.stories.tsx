import type { Meta, StoryObj } from '@storybook/react'
import React from 'react' // required for JSX
import { Sidebar, SidebarItem } from './Sidebar'
import { Avatar } from '../Avatar/Avatar'

// ─── SVG Icon set (16×16, currentColor) ──────────────────────────────────────

const IconHome = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
    <polyline points="9 22 9 12 15 12 15 22"/>
  </svg>
)

const IconPDLC = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
    <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
  </svg>
)

const IconWorkflow = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>
    <path d="M6 9v6M13 6h-1a4 4 0 0 0-4 4v1M21 15V9a2 2 0 0 0-2-2h-1"/>
  </svg>
)

const IconBriefcase = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
  </svg>
)

const IconFolder = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
  </svg>
)

const IconUsers = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)

const IconGlobe = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <line x1="2" y1="12" x2="22" y2="12"/>
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
  </svg>
)

const IconBarChart = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10"/>
    <line x1="12" y1="20" x2="12" y2="4"/>
    <line x1="6"  y1="20" x2="6"  y2="14"/>
    <line x1="2"  y1="20" x2="22" y2="20"/>
  </svg>
)

const IconSettings = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </svg>
)

const IconIntegrations = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22V12m0 0V2m0 10H2m10 0h10"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
)

const IconShield = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
  </svg>
)

// ─── Nav items ────────────────────────────────────────────────────────────────

const lightNav: SidebarItem[] = [
  { label: 'Home',          icon: <IconHome />,    active: false },
  { label: 'PDLC',          icon: <IconPDLC /> },
  { label: 'TMO Workflow',  icon: <IconWorkflow /> },
  {
    label: 'PMO',
    icon: <IconBriefcase />,
    active: true,
    subItems: [
      { label: 'Projects',         active: false },
      { label: 'Resources',        active: false },
      { label: 'Allocation',       active: true  },
      { label: 'Submit Timesheet', active: false },
      { label: 'Global Holiday',   active: false },
      { label: 'NitroWiz',         active: false },
    ],
  },
]

const collapsedNav: SidebarItem[] = [
  { label: 'Home',         icon: <IconHome />,         active: true  },
  { label: 'PMO',          icon: <IconBriefcase /> },
  { label: 'Integrations', icon: <IconIntegrations /> },
  { label: 'Shield',       icon: <IconShield /> },
  { label: 'PDLC',         icon: <IconPDLC />,          active: false },
]

const darkNav: SidebarItem[] = [
  { label: 'Dashboard',  icon: <IconHome />,     active: true  },
  { label: 'Analytics',  icon: <IconBarChart />, badge: 3      },
  { label: 'Reports',    icon: <IconFolder />                  },
  { label: 'Vehicles',   icon: <IconGlobe />                   },
  { label: 'Drivers',    icon: <IconUsers />                   },
  { label: 'Settings',   icon: <IconSettings />                },
]

// ─── Meta ─────────────────────────────────────────────────────────────────────

const meta: Meta<typeof Sidebar> = {
  title: 'Layout/Sidebar',
  component: Sidebar,
  tags: ['autodocs'],
  parameters: { layout: 'fullscreen' },
  argTypes: {
    collapsed: { control: 'boolean' },
    theme:     { control: 'select', options: ['light', 'dark'] },
  },
}
export default meta
type Story = StoryObj<typeof Sidebar>

// ─── Stories ──────────────────────────────────────────────────────────────────

export const LightExpanded: Story = {
  name: 'Light — Expanded (like screenshot)',
  parameters: { backgrounds: { default: 'page' } },
  render: () => (
    <div style={{ display: 'flex', height: '100vh' }}>
      <Sidebar theme="light" items={lightNav} />
      <div style={{ flex: 1, padding: 32, background: '#EFEFE5', fontSize: 14, color: '#374151' }}>
        Main content area
      </div>
    </div>
  ),
}

export const LightCollapsed: Story = {
  name: 'Light — Collapsed (icon rail)',
  parameters: { backgrounds: { default: 'page' } },
  render: () => (
    <div style={{ display: 'flex', height: '100vh' }}>
      <Sidebar theme="light" collapsed items={collapsedNav} />
      <div style={{ flex: 1, padding: 32, background: '#EFEFE5', fontSize: 14, color: '#374151' }}>
        Main content area
      </div>
    </div>
  ),
}

export const LightBothModes: Story = {
  name: 'Light — Expanded + Collapsed side by side',
  parameters: { backgrounds: { default: 'page' } },
  render: () => (
    <div style={{ display: 'flex', height: '100vh', gap: 0 }}>
      <Sidebar theme="light" items={lightNav} />
      <Sidebar theme="light" collapsed items={collapsedNav} />
      <div style={{ flex: 1, padding: 32, background: '#EFEFE5', fontSize: 14, color: '#374151' }}>
        Both modes side by side
      </div>
    </div>
  ),
}

export const LightWithSections: Story = {
  name: 'Light — With section headings',
  parameters: { backgrounds: { default: 'page' } },
  render: () => (
    <div style={{ display: 'flex', height: '100vh' }}>
      <Sidebar
        theme="light"
        sections={[
          {
            heading: 'Navigation',
            items: [
              { label: 'Home',     icon: <IconHome />,      active: true  },
              { label: 'PDLC',     icon: <IconPDLC />                     },
              { label: 'Workflow', icon: <IconWorkflow />                  },
            ],
          },
          {
            heading: 'Analytics',
            items: [
              { label: 'Reports',  icon: <IconFolder />,   badge: 2       },
              { label: 'Charts',   icon: <IconBarChart />                  },
            ],
          },
          {
            heading: 'Admin',
            items: [
              { label: 'Settings', icon: <IconSettings />                  },
            ],
          },
        ]}
        footer={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 4px' }}>
            <Avatar name="Srikanth C" size="sm" status="online" />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Srikanth C</div>
              <div style={{ fontSize: 11, color: '#9CA3AF' }}>Admin</div>
            </div>
          </div>
        }
      />
      <div style={{ flex: 1, padding: 32, background: '#EFEFE5', fontSize: 14, color: '#374151' }}>
        Main content
      </div>
    </div>
  ),
}

export const DarkExpanded: Story = {
  name: 'Dark — Expanded',
  parameters: { backgrounds: { default: 'dark' } },
  render: () => (
    <div style={{ display: 'flex', height: '100vh' }}>
      <Sidebar theme="dark" items={darkNav} />
      <div style={{ flex: 1, padding: 32, background: '#111827', fontSize: 14, color: '#D1D5DB' }}>
        Main content area
      </div>
    </div>
  ),
}

export const DarkCollapsed: Story = {
  name: 'Dark — Collapsed',
  parameters: { backgrounds: { default: 'dark' } },
  render: () => (
    <div style={{ display: 'flex', height: '100vh' }}>
      <Sidebar theme="dark" collapsed items={darkNav} />
      <div style={{ flex: 1, padding: 32, background: '#111827', fontSize: 14, color: '#D1D5DB' }}>
        Main content area
      </div>
    </div>
  ),
}
