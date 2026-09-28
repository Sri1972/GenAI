import React from 'react'
import { colors, usage } from '../../tokens'

export interface BreadcrumbItem {
  label: string
  href?: string
  onClick?: () => void
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[]
  separator?: React.ReactNode
}

export function Breadcrumb({ items, separator = '/' }: BreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: 'Inter, sans-serif', fontSize: 13 }}>
      {items.map((item, i) => {
        const isLast = i === items.length - 1
        return (
          <React.Fragment key={i}>
            {i > 0 && (
              <span style={{ color: usage.mutedText, userSelect: 'none', fontSize: 11 }}>
                {separator}
              </span>
            )}
            {isLast ? (
              <span style={{ fontWeight: 600, color: usage.primaryText }}>
                {item.label}
              </span>
            ) : (
              <button
                onClick={item.onClick}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  color: colors.primary.forwardBlue,
                  fontFamily: 'Inter, sans-serif',
                  fontSize: 13,
                  textDecoration: 'none',
                }}
              >
                {item.label}
              </button>
            )}
          </React.Fragment>
        )
      })}
    </nav>
  )
}
