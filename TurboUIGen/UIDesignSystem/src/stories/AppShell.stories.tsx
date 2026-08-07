import type { Meta, StoryObj } from '@storybook/react'
import React, { useState } from 'react'
import { Header }      from '../components/Header/Header'
import { Sidebar }     from '../components/Sidebar/Sidebar'
import { Footer }      from '../components/Footer/Footer'
import { KpiCard }     from '../components/KpiCard/KpiCard'
import { DataTable }   from '../components/DataTable/DataTable'
import { Badge }       from '../components/Badge/Badge'
import { Button }      from '../components/Button/Button'
import { SearchBar }   from '../components/SearchBar/SearchBar'
import { Tabs }        from '../components/Tabs/Tabs'
import { Breadcrumb }  from '../components/Breadcrumb/Breadcrumb'
import { Avatar }      from '../components/Avatar/Avatar'

const navItems = [
  { label: 'Dashboard', icon: '⊞', active: true  },
  { label: 'Analytics', icon: '📊', badge: 3      },
  { label: 'Reports',   icon: '📄'                },
  { label: 'Vehicles',  icon: '🚗'                },
  { label: 'Drivers',   icon: '👤'                },
  { label: 'Settings',  icon: '⚙'                },
]

const columns = [
  { key: 'id',      header: 'ID',      width: 60 },
  { key: 'driver',  header: 'Driver',  width: 180 },
  { key: 'region',  header: 'Region'  },
  { key: 'trips',   header: 'Trips',   align: 'right' as const },
  { key: 'revenue', header: 'Revenue', align: 'right' as const },
  { key: 'status',  header: 'Status',  render: (v: unknown) => (
    <Badge label={String(v)} variant={v === 'Active' ? 'success' : v === 'On Trip' ? 'info' : 'warning'} dot />
  )},
]

const rows = [
  { id: '001', driver: 'James Martinez', region: 'West Coast', trips: 142, revenue: '$14,200', status: 'Active'  },
  { id: '002', driver: 'Sarah Chen',     region: 'Northeast',  trips: 98,  revenue: '$9,800',  status: 'On Trip' },
  { id: '003', driver: 'Mike Johnson',   region: 'Midwest',    trips: 217, revenue: '$21,700', status: 'Active'  },
  { id: '004', driver: 'Ana García',     region: 'Southwest',  trips: 64,  revenue: '$6,400',  status: 'Offline' },
  { id: '005', driver: 'Tom Williams',   region: 'Southeast',  trips: 183, revenue: '$18,300', status: 'Active'  },
]

function AppShellDemo() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'Inter, sans-serif' }}>
      <Header
        brandName="Mobility Global"
        nav={[{ label: 'Dashboard', active: true }, { label: 'Analytics' }, { label: 'Reports' }]}
        actions={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Button variant="primary" size="sm">+ New Report</Button>
            <Avatar name="Srikanth C" size="sm" status="online" />
          </div>
        }
      />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar items={navItems} />
        <main style={{ flex: 1, overflowY: 'auto', background: '#EFEFE5', padding: 24 }}>
          <Breadcrumb items={[{ label: 'Dashboard' }, { label: 'Fleet Overview' }]} />
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#132445', margin: '16px 0 20px' }}>Fleet Overview</h1>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
            <KpiCard label="Total Revenue"  value="$2.4M"  change="+12.5%"  changeType="positive" icon="💰" />
            <KpiCard label="Active Drivers" value="18,420" change="+3.2%"   changeType="positive" icon="👤" />
            <KpiCard label="Trips Today"    value="3,841"  change="+8.1%"   changeType="positive" icon="🚗" />
            <KpiCard label="Incidents"      value="4"      change="-2 vs avg" changeType="positive" icon="⚠" />
          </div>

          <div style={{ background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: '#132445', margin: 0 }}>Driver Performance</h2>
              <div style={{ display: 'flex', gap: 8 }}>
                <SearchBar placeholder="Search drivers…" />
                <Button variant="secondary" size="sm">Export</Button>
              </div>
            </div>
            <Tabs
              variant="line"
              items={[
                { key: 'all',      label: 'All Drivers',  badge: rows.length },
                { key: 'active',   label: 'Active'   },
                { key: 'inactive', label: 'Inactive' },
              ]}
              defaultKey="all"
            />
            <div style={{ marginTop: 16 }}>
              <DataTable columns={columns} rows={rows} striped />
            </div>
          </div>
        </main>
      </div>
      <Footer
        brand="Mobility Global"
        links={[{ label: 'Privacy' }, { label: 'Terms' }, { label: 'Support' }]}
        variant="light"
      />
    </div>
  )
}

const meta: Meta = {
  title: 'Foundation/App Shell',
  parameters: { layout: 'fullscreen', backgrounds: { default: 'page' } },
}
export default meta

export const FullDashboard: StoryObj = {
  render: () => <AppShellDemo />,
}
