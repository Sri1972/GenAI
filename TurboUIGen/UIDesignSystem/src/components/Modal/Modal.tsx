import React from 'react'
import { colors, usage, radius, shadow } from '../../tokens'

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl'

export interface ModalProps {
  open: boolean
  title?: string
  size?: ModalSize
  children?: React.ReactNode
  footer?: React.ReactNode
  onClose?: () => void
}

const widths: Record<ModalSize, number> = { sm: 400, md: 560, lg: 720, xl: 900 }

export function Modal({ open, title, size = 'md', children, footer, onClose }: ModalProps) {
  if (!open) return null

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Inter, sans-serif',
    }} onClick={e => { if (e.target === e.currentTarget) onClose?.() }}>
      <div style={{
        width: widths[size],
        maxWidth: 'calc(100vw - 32px)',
        maxHeight: 'calc(100vh - 64px)',
        background: usage.cardBackground,
        borderRadius: radius.xl,
        boxShadow: shadow.xl,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '20px 24px',
          borderBottom: `1px solid ${usage.border}`,
        }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: usage.primaryText }}>
            {title}
          </span>
          {onClose && (
            <button onClick={onClose} style={{
              width: 32, height: 32, borderRadius: radius.md,
              border: 'none', background: 'transparent',
              cursor: 'pointer', fontSize: 20, color: usage.mutedText,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              lineHeight: 1,
            }}>×</button>
          )}
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>{children}</div>

        {/* Footer */}
        {footer && (
          <div style={{
            padding: '16px 24px',
            borderTop: `1px solid ${usage.border}`,
            display: 'flex', gap: 8, justifyContent: 'flex-end',
          }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
