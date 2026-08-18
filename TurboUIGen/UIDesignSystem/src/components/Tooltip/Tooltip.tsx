import React, { useState } from 'react'
import { colors, radius } from '../../tokens'

export type TooltipPlacement = 'top' | 'bottom' | 'left' | 'right'

export interface TooltipProps {
  content: string
  children: React.ReactNode
  placement?: TooltipPlacement
  delay?: number
}

export function Tooltip({ content, children, placement = 'top', delay = 300 }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(null)

  function show() {
    const t = setTimeout(() => setVisible(true), delay)
    setTimer(t)
  }
  function hide() {
    if (timer) clearTimeout(timer)
    setVisible(false)
  }

  const offsetMap: Record<TooltipPlacement, React.CSSProperties> = {
    top:    { bottom: '100%', left: '50%', transform: 'translateX(-50%)', marginBottom: 6 },
    bottom: { top: '100%',   left: '50%', transform: 'translateX(-50%)', marginTop: 6 },
    left:   { right: '100%', top: '50%',  transform: 'translateY(-50%)', marginRight: 6 },
    right:  { left: '100%',  top: '50%',  transform: 'translateY(-50%)', marginLeft: 6 },
  }

  return (
    <div style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={show} onMouseLeave={hide}>
      {children}
      {visible && (
        <div style={{
          position: 'absolute',
          ...offsetMap[placement],
          background: colors.primary.vitalBlue,
          color: '#fff',
          fontSize: 12,
          fontWeight: 500,
          fontFamily: 'Inter, sans-serif',
          padding: '5px 10px',
          borderRadius: radius.md,
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          zIndex: 9999,
          boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        }}>
          {content}
        </div>
      )}
    </div>
  )
}
