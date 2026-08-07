import React from 'react'
import { colors, radius } from '../../tokens'

export type AlertVariant = 'info' | 'success' | 'warning' | 'error'

export interface AlertProps {
  variant?: AlertVariant
  title?: string
  message: string
  dismissible?: boolean
  onDismiss?: () => void
}

const variantMap: Record<AlertVariant, { bg: string; color: string; border: string; icon: string }> = {
  info:    { bg: colors.semantic.infoBg,    color: colors.semantic.info,    border: colors.semantic.info,    icon: 'ℹ' },
  success: { bg: colors.semantic.successBg, color: colors.semantic.success, border: colors.semantic.success, icon: '✓' },
  warning: { bg: colors.semantic.warningBg, color: colors.semantic.warning, border: colors.semantic.warning, icon: '⚠' },
  error:   { bg: colors.semantic.errorBg,   color: colors.semantic.error,   border: colors.semantic.error,   icon: '✕' },
}

export function Alert({ variant = 'info', title, message, dismissible = false, onDismiss }: AlertProps) {
  const { bg, color, border, icon } = variantMap[variant]

  return (
    <div style={{
      display: 'flex',
      gap: 12,
      alignItems: 'flex-start',
      padding: '14px 16px',
      borderRadius: radius.md,
      background: bg,
      border: `1px solid ${border}`,
      fontFamily: 'Inter, sans-serif',
    }}>
      <span style={{
        flexShrink: 0,
        width: 20, height: 20,
        borderRadius: '50%',
        background: color,
        color: '#fff',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 12,
        fontWeight: 700,
        marginTop: 1,
      }}>
        {icon}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && (
          <div style={{ fontWeight: 700, fontSize: 14, color, marginBottom: 2 }}>{title}</div>
        )}
        <div style={{ fontSize: 14, color, lineHeight: 1.5 }}>{message}</div>
      </div>
      {dismissible && (
        <button onClick={onDismiss} style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color, fontSize: 18, lineHeight: 1, padding: 0, flexShrink: 0,
        }}>×</button>
      )}
    </div>
  )
}
