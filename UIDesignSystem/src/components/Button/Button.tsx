import React from 'react'
import { colors, components, radius } from '../../tokens'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize    = 'sm' | 'md' | 'lg'

export interface ButtonProps {
  children: React.ReactNode
  variant?: ButtonVariant
  size?: ButtonSize
  disabled?: boolean
  loading?: boolean
  fullWidth?: boolean
  onClick?: () => void
}

const heights: Record<ButtonSize, number> = {
  sm: components.buttonHeightSm,
  md: components.buttonHeightMd,
  lg: components.buttonHeightLg,
}

const fontSizes: Record<ButtonSize, number> = { sm: 13, md: 14, lg: 16 }
const paddings:  Record<ButtonSize, string>  = { sm: '0 12px', md: '0 20px', lg: '0 28px' }

const variants: Record<ButtonVariant, React.CSSProperties> = {
  primary: {
    background: colors.primary.forwardBlue,
    color: colors.neutral.white,
    border: 'none',
  },
  secondary: {
    background: colors.neutral.white,
    color: colors.primary.vitalBlue,
    border: `1.5px solid ${colors.primary.vitalBlue}`,
  },
  ghost: {
    background: 'transparent',
    color: colors.primary.forwardBlue,
    border: `1.5px solid transparent`,
  },
  danger: {
    background: colors.semantic.error,
    color: colors.neutral.white,
    border: 'none',
  },
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  fullWidth = false,
  onClick,
}: ButtonProps) {
  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: heights[size],
    padding: paddings[size],
    fontSize: fontSizes[size],
    fontWeight: 600,
    fontFamily: 'Inter, sans-serif',
    borderRadius: radius.md,
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    transition: 'opacity 0.15s, background 0.15s',
    width: fullWidth ? '100%' : undefined,
    ...variants[variant],
  }

  return (
    <button style={base} disabled={disabled || loading} onClick={onClick}>
      {loading && (
        <span style={{
          width: 14, height: 14,
          border: `2px solid currentColor`,
          borderTopColor: 'transparent',
          borderRadius: '50%',
          display: 'inline-block',
          animation: 'spin 0.7s linear infinite',
        }} />
      )}
      {children}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </button>
  )
}
