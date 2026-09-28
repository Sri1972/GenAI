import React, { useState } from 'react'
import { components, radius } from '../../tokens'

export interface SidebarItem {
  label: string
  icon?: React.ReactNode
  active?: boolean
  badge?: string | number
  subItems?: Omit<SidebarItem, 'icon' | 'subItems'>[]
  onClick?: () => void
}

export interface SidebarSection {
  heading?: string
  items: SidebarItem[]
}

export interface SidebarProps {
  sections?: SidebarSection[]
  items?: SidebarItem[]
  footer?: React.ReactNode
  collapsed?: boolean
  theme?: 'light' | 'dark'
}

// ─── Theme tokens ────────────────────────────────────────────────────────────

const themes = {
  light: {
    bg:            '#FFFFFF',
    border:        '1px solid #E5E7EB',
    sectionLabel:  '#9CA3AF',
    itemText:      '#374151',
    itemTextActive:'#0064D2',
    iconColor:     '#6B7280',
    iconActive:    '#0064D2',
    activeBg:      'rgba(0, 100, 210, 0.08)',
    activeAccent:  '#0064D2',
    hoverBg:       'rgba(0, 100, 210, 0.05)',
    badgeBg:       '#0064D2',
    badgeText:     '#FFFFFF',
    footerBorder:  '#E5E7EB',
    subItemText:   '#6B7280',
    subItemActive: '#0064D2',
    subItemActiveBg:'rgba(0, 100, 210, 0.06)',
  },
  dark: {
    bg:            '#132445',
    border:        'none',
    sectionLabel:  'rgba(255,255,255,0.35)',
    itemText:      'rgba(255,255,255,0.72)',
    itemTextActive:'#B8EAF5',
    iconColor:     'rgba(255,255,255,0.55)',
    iconActive:    '#B8EAF5',
    activeBg:      'rgba(0,100,210,0.22)',
    activeAccent:  '#0064D2',
    hoverBg:       'rgba(255,255,255,0.06)',
    badgeBg:       '#0064D2',
    badgeText:     '#FFFFFF',
    footerBorder:  'rgba(255,255,255,0.12)',
    subItemText:   'rgba(255,255,255,0.5)',
    subItemActive: '#B8EAF5',
    subItemActiveBg:'rgba(0,100,210,0.15)',
  },
}

// ─── Sub-item ─────────────────────────────────────────────────────────────────

function SubNavItem({ item, t }: { item: Omit<SidebarItem, 'icon' | 'subItems'>; t: typeof themes.light }) {
  return (
    <button
      onClick={item.onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        width: '100%',
        height: 34,
        padding: '0 12px 0 44px',
        border: 'none',
        borderRadius: radius.md,
        background: item.active ? t.subItemActiveBg : 'transparent',
        color: item.active ? t.subItemActive : t.subItemText,
        fontSize: 13,
        fontWeight: item.active ? 600 : 400,
        cursor: 'pointer',
        fontFamily: 'Inter, sans-serif',
        textAlign: 'left',
        transition: 'background 0.12s, color 0.12s',
      }}
    >
      <span style={{
        width: 5, height: 5,
        borderRadius: '50%',
        background: item.active ? t.subItemActive : t.subItemText,
        marginRight: 10,
        flexShrink: 0,
        opacity: item.active ? 1 : 0.5,
      }} />
      {item.label}
    </button>
  )
}

// ─── Nav item ─────────────────────────────────────────────────────────────────

function NavItem({
  item, collapsed, t,
}: { item: SidebarItem; collapsed: boolean; t: typeof themes.light }) {
  const hasChildren = item.subItems && item.subItems.length > 0
  const anyChildActive = hasChildren && item.subItems!.some(s => s.active)
  const isExpanded = item.active || anyChildActive

  const [localExpanded, setLocalExpanded] = useState(isExpanded)
  const showChildren = hasChildren && (localExpanded || isExpanded)

  return (
    <div>
      <button
        onClick={() => { item.onClick?.(); if (hasChildren) setLocalExpanded(e => !e) }}
        title={collapsed ? item.label : undefined}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          width: '100%',
          height: 40,
          padding: collapsed ? '0' : '0 12px',
          justifyContent: collapsed ? 'center' : 'flex-start',
          borderRadius: radius.md,
          border: 'none',
          background: (item.active || anyChildActive) ? t.activeBg : 'transparent',
          color: (item.active || anyChildActive) ? t.itemTextActive : t.itemText,
          fontWeight: (item.active || anyChildActive) ? 600 : 400,
          fontSize: 14,
          cursor: 'pointer',
          fontFamily: 'Inter, sans-serif',
          textAlign: 'left',
          transition: 'background 0.12s, color 0.12s',
          position: 'relative',
        }}
      >
        {/* Active accent bar */}
        {!collapsed && (item.active || anyChildActive) && (
          <span style={{
            position: 'absolute',
            left: 0, top: 6, bottom: 6,
            width: 3,
            borderRadius: 999,
            background: t.activeAccent,
          }} />
        )}

        {/* Icon */}
        {item.icon && (
          <span style={{
            flexShrink: 0,
            width: collapsed ? 40 : 20,
            height: collapsed ? 40 : 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: collapsed ? radius.md : 0,
            background: collapsed && (item.active || anyChildActive) ? t.activeBg : 'transparent',
            color: (item.active || anyChildActive) ? t.iconActive : t.iconColor,
            transition: 'color 0.12s',
          }}>
            {item.icon}
          </span>
        )}

        {/* Label */}
        {!collapsed && <span style={{ flex: 1, lineHeight: 1.2 }}>{item.label}</span>}

        {/* Badge */}
        {!collapsed && item.badge !== undefined && (
          <span style={{
            background: t.badgeBg,
            color: t.badgeText,
            fontSize: 10,
            fontWeight: 700,
            borderRadius: radius.full,
            minWidth: 18,
            height: 18,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 5px',
            flexShrink: 0,
          }}>
            {item.badge}
          </span>
        )}

        {/* Chevron for expandable items */}
        {!collapsed && hasChildren && (
          <span style={{
            color: t.iconColor,
            fontSize: 10,
            transform: showChildren ? 'rotate(90deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
            flexShrink: 0,
            lineHeight: 1,
          }}>
            ▶
          </span>
        )}
      </button>

      {/* Sub-items */}
      {!collapsed && showChildren && (
        <div style={{ marginTop: 2, marginBottom: 2 }}>
          {item.subItems!.map((sub, i) => (
            <SubNavItem key={i} item={sub} t={t} />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export function Sidebar({
  sections, items, footer, collapsed = false, theme = 'light',
}: SidebarProps) {
  const t = themes[theme]
  const normalizedSections: SidebarSection[] = sections ?? (items ? [{ items }] : [])

  return (
    <aside style={{
      width: collapsed ? 64 : components.sidebarWidth,
      minHeight: '100vh',
      background: t.bg,
      borderRight: t.border,
      display: 'flex',
      flexDirection: 'column',
      padding: collapsed ? '12px 4px' : '12px 8px',
      fontFamily: 'Inter, sans-serif',
      transition: 'width 0.2s',
      flexShrink: 0,
      boxSizing: 'border-box',
    }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {normalizedSections.map((section, i) => (
          <div key={i} style={{ marginBottom: 4 }}>
            {!collapsed && section.heading && (
              <div style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: 1.1,
                color: t.sectionLabel,
                padding: '10px 12px 4px',
                textTransform: 'uppercase',
              }}>
                {section.heading}
              </div>
            )}
            {collapsed && section.heading && i > 0 && (
              <div style={{
                height: 1,
                background: theme === 'light' ? '#F3F4F6' : 'rgba(255,255,255,0.08)',
                margin: '8px 8px',
              }} />
            )}
            {section.items.map((item, j) => (
              <NavItem key={j} item={item} collapsed={collapsed} t={t} />
            ))}
          </div>
        ))}
      </div>

      {footer && (
        <div style={{
          borderTop: `1px solid ${t.footerBorder}`,
          paddingTop: 12,
          marginTop: 8,
        }}>
          {footer}
        </div>
      )}
    </aside>
  )
}
