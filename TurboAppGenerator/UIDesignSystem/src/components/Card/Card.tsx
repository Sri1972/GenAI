import React from 'react'
import { colors, usage, components, radius, shadow } from '../../tokens'

export interface CardProps {
  title?: string
  subtitle?: string
  children?: React.ReactNode
  footer?: React.ReactNode
  elevation?: 'flat' | 'sm' | 'md' | 'lg'
  padding?: 'none' | 'sm' | 'md' | 'lg'
  style?: React.CSSProperties
}

const elevationMap = {
  flat: 'none',
  sm:   shadow.sm,
  md:   shadow.md,
  lg:   shadow.lg,
}
const paddingMap = {
  none: 0,
  sm:   16,
  md:   components.cardPadding,
  lg:   32,
}

export function Card({
  title, subtitle, children, footer,
  elevation = 'sm', padding = 'md', style,
}: CardProps) {
  const cardStyle: React.CSSProperties = {
    background: usage.cardBackground,
    borderRadius: radius.lg,
    boxShadow: elevationMap[elevation],
    border: `1px solid ${usage.border}`,
    overflow: 'hidden',
    fontFamily: 'Inter, sans-serif',
    ...style,
  }
  const bodyStyle: React.CSSProperties = { padding: paddingMap[padding] }

  return (
    <div style={cardStyle}>
      {(title || subtitle) && (
        <div style={{ padding: `${components.cardPadding}px ${components.cardPadding}px 0`, borderBottom: children ? `1px solid ${usage.divider}` : undefined, paddingBottom: children ? 16 : undefined, marginBottom: children ? 0 : undefined }}>
          {title    && <div style={{ fontSize: 16, fontWeight: 700, color: usage.primaryText }}>{title}</div>}
          {subtitle && <div style={{ fontSize: 13, color: usage.mutedText, marginTop: 2 }}>{subtitle}</div>}
        </div>
      )}
      <div style={bodyStyle}>{children}</div>
      {footer && (
        <div style={{ padding: `12px ${components.cardPadding}px`, borderTop: `1px solid ${usage.divider}`, background: colors.neutral.lightGray }}>
          {footer}
        </div>
      )}
    </div>
  )
}
