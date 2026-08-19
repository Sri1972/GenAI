import React from 'react'
import { colors, usage, radius } from '../../tokens'

export type ProgressVariant = 'default' | 'success' | 'warning' | 'error'
export type ProgressSize    = 'sm' | 'md' | 'lg'

export interface ProgressBarProps {
  value: number
  max?: number
  variant?: ProgressVariant
  size?: ProgressSize
  label?: string
  showValue?: boolean
  animated?: boolean
}

const fillColors: Record<ProgressVariant, string> = {
  default: colors.primary.forwardBlue,
  success: colors.semantic.success,
  warning: colors.semantic.warning,
  error:   colors.semantic.error,
}

const heights: Record<ProgressSize, number> = { sm: 4, md: 8, lg: 12 }

export function ProgressBar({ value, max = 100, variant = 'default', size = 'md', label, showValue = false, animated = false }: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))

  return (
    <div style={{ fontFamily: 'Inter, sans-serif' }}>
      {(label || showValue) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          {label && <span style={{ fontSize: 13, fontWeight: 500, color: usage.primaryText }}>{label}</span>}
          {showValue && <span style={{ fontSize: 13, color: usage.mutedText }}>{Math.round(pct)}%</span>}
        </div>
      )}
      <div style={{
        height: heights[size],
        borderRadius: radius.full,
        background: colors.neutral.lightGray,
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          borderRadius: radius.full,
          background: fillColors[variant],
          transition: animated ? 'width 0.6s cubic-bezier(0.4,0,0.2,1)' : 'none',
        }} />
      </div>
    </div>
  )
}
