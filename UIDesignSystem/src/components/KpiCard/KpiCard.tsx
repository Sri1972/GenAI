import React from 'react'
import { colors, usage, components, radius, shadow } from '../../tokens'

export interface KpiCardProps {
  label: string
  value: string | number
  change?: string
  changeType?: 'positive' | 'negative' | 'neutral'
  icon?: React.ReactNode
  prefix?: string
  suffix?: string
}

export function KpiCard({ label, value, change, changeType = 'neutral', icon, prefix, suffix }: KpiCardProps) {
  const changeColors = {
    positive: colors.semantic.success,
    negative: colors.semantic.error,
    neutral:  usage.mutedText,
  }
  const changeBg = {
    positive: colors.semantic.successBg,
    negative: colors.semantic.errorBg,
    neutral:  colors.neutral.lightGray,
  }

  return (
    <div style={{
      background: usage.cardBackground,
      borderRadius: radius.lg,
      boxShadow: shadow.sm,
      border: `1px solid ${usage.border}`,
      padding: components.cardPadding,
      fontFamily: 'Inter, sans-serif',
      minWidth: 180,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: usage.mutedText }}>{label}</span>
        {icon && (
          <span style={{
            width: 36, height: 36, borderRadius: radius.md,
            background: colors.semantic.infoBg,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: colors.primary.forwardBlue, fontSize: 18,
          }}>
            {icon}
          </span>
        )}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: usage.primaryText, lineHeight: 1 }}>
        {prefix && <span style={{ fontSize: 16, fontWeight: 500 }}>{prefix}</span>}
        {value}
        {suffix && <span style={{ fontSize: 14, fontWeight: 500, marginLeft: 2 }}>{suffix}</span>}
      </div>
      {change && (
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 4,
          marginTop: 8, padding: '2px 8px', borderRadius: radius.full,
          background: changeBg[changeType], color: changeColors[changeType],
          fontSize: 12, fontWeight: 600,
        }}>
          {changeType === 'positive' ? '↑' : changeType === 'negative' ? '↓' : '→'} {change}
        </div>
      )}
    </div>
  )
}
