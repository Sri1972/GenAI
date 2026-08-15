import React from 'react'
import { colors, usage, components, radius } from '../../tokens'

export type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'accent'
export type BadgeSize    = 'sm' | 'md'

export interface BadgeProps {
  label: string
  variant?: BadgeVariant
  size?: BadgeSize
  dot?: boolean
}

const variantMap: Record<BadgeVariant, { bg: string; color: string }> = {
  default: { bg: colors.neutral.lightGray,    color: usage.primaryText },
  success: { bg: colors.semantic.successBg,   color: colors.semantic.success  },
  warning: { bg: colors.semantic.warningBg,   color: colors.semantic.warning  },
  error:   { bg: colors.semantic.errorBg,     color: colors.semantic.error    },
  info:    { bg: colors.semantic.infoBg,      color: colors.semantic.info     },
  accent:  { bg: colors.accent.softLilac,     color: colors.accent.steadyLilac },
}

export function Badge({ label, variant = 'default', size = 'md', dot = false }: BadgeProps) {
  const { bg, color } = variantMap[variant]
  const style: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    height: size === 'sm' ? 18 : components.badgeHeight,
    padding: size === 'sm' ? '0 7px' : '0 10px',
    borderRadius: radius.full,
    background: bg,
    color,
    fontSize: size === 'sm' ? 11 : 12,
    fontWeight: 600,
    fontFamily: 'Inter, sans-serif',
    whiteSpace: 'nowrap',
  }
  return (
    <span style={style}>
      {dot && (
        <span style={{
          width: 6, height: 6,
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
        }} />
      )}
      {label}
    </span>
  )
}
