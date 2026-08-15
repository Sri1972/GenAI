import React, { useState } from 'react'
import { colors, usage, components } from '../../tokens'

export interface TabItem {
  key: string
  label: string
  badge?: string | number
  disabled?: boolean
  content?: React.ReactNode
}

export type TabVariant = 'line' | 'pill'

export interface TabsProps {
  items: TabItem[]
  defaultKey?: string
  activeKey?: string
  variant?: TabVariant
  onChange?: (key: string) => void
}

export function Tabs({ items, defaultKey, activeKey: controlledKey, variant = 'line', onChange }: TabsProps) {
  const [internalKey, setInternalKey] = useState(defaultKey ?? items[0]?.key)
  const active = controlledKey ?? internalKey

  function handleClick(key: string) {
    setInternalKey(key)
    onChange?.(key)
  }

  const activeTab = items.find(t => t.key === active)

  return (
    <div style={{ fontFamily: 'Inter, sans-serif' }}>
      <div style={{
        display: 'flex',
        gap: variant === 'pill' ? 4 : 0,
        height: components.tabHeight,
        borderBottom: variant === 'line' ? `1px solid ${usage.border}` : 'none',
        background: variant === 'pill' ? colors.neutral.lightGray : 'transparent',
        borderRadius: variant === 'pill' ? 8 : 0,
        padding: variant === 'pill' ? 4 : 0,
        alignItems: 'center',
      }}>
        {items.map(tab => {
          const isActive = tab.key === active
          const tabStyle: React.CSSProperties = variant === 'line'
            ? {
                padding: '0 20px',
                height: '100%',
                border: 'none',
                borderBottom: isActive ? `2px solid ${usage.activeNav}` : '2px solid transparent',
                background: 'transparent',
                color: isActive ? usage.activeNav : usage.secondaryText,
                fontWeight: isActive ? 700 : 400,
                cursor: tab.disabled ? 'not-allowed' : 'pointer',
                opacity: tab.disabled ? 0.45 : 1,
                fontSize: 14,
                fontFamily: 'Inter, sans-serif',
                transition: 'border-color 0.15s, color 0.15s',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                whiteSpace: 'nowrap',
              }
            : {
                padding: '0 16px',
                height: 32,
                border: 'none',
                borderRadius: 6,
                background: isActive ? colors.neutral.white : 'transparent',
                color: isActive ? usage.primaryText : usage.mutedText,
                fontWeight: isActive ? 700 : 400,
                cursor: tab.disabled ? 'not-allowed' : 'pointer',
                opacity: tab.disabled ? 0.45 : 1,
                fontSize: 14,
                fontFamily: 'Inter, sans-serif',
                boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                whiteSpace: 'nowrap',
              }

          return (
            <button key={tab.key} style={tabStyle} disabled={tab.disabled}
              onClick={() => !tab.disabled && handleClick(tab.key)}>
              {tab.label}
              {tab.badge !== undefined && (
                <span style={{
                  background: isActive ? colors.primary.forwardBlue : usage.mutedText,
                  color: '#fff',
                  fontSize: 10,
                  fontWeight: 700,
                  borderRadius: 999,
                  minWidth: 16,
                  height: 16,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 4px',
                }}>
                  {tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {activeTab?.content && (
        <div style={{ padding: '16px 0' }}>
          {activeTab.content}
        </div>
      )}
    </div>
  )
}
