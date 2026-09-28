import React from 'react'
import { colors, usage, components, shadow } from '../../tokens'

export interface HeaderProps {
  brandName?: string
  logo?: React.ReactNode
  nav?: { label: string; active?: boolean }[]
  actions?: React.ReactNode
  onNavClick?: (label: string) => void
}

export function Header({ brandName = 'Mobility Global', logo, nav = [], actions, onNavClick }: HeaderProps) {
  return (
    <header style={{
      height: components.headerHeight,
      background: usage.headerBackground,
      boxShadow: shadow.sm,
      display: 'flex',
      alignItems: 'center',
      padding: '0 24px',
      gap: 32,
      fontFamily: 'Inter, sans-serif',
      borderBottom: `1px solid ${usage.border}`,
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
        {logo ? logo : (
          <div style={{
            width: 32, height: 32, borderRadius: 6,
            background: colors.primary.vitalBlue,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontWeight: 800, fontSize: 14, letterSpacing: -0.5,
          }}>
            MG
          </div>
        )}
        <span style={{ fontWeight: 700, fontSize: 16, color: usage.primaryText }}>
          {brandName}
        </span>
      </div>

      {/* Nav */}
      {nav.length > 0 && (
        <nav style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
          {nav.map(item => (
            <button
              key={item.label}
              onClick={() => onNavClick?.(item.label)}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                border: 'none',
                background: item.active ? usage.hoverBg : 'transparent',
                color: item.active ? usage.activeNav : usage.secondaryText,
                fontWeight: item.active ? 600 : 400,
                fontSize: 14,
                cursor: 'pointer',
                fontFamily: 'Inter, sans-serif',
                transition: 'background 0.15s',
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
      )}

      {/* Actions */}
      {actions && <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>{actions}</div>}
    </header>
  )
}
