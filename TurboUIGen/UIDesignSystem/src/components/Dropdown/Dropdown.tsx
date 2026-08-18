import React, { useState, useRef, useEffect } from 'react'
import { colors, usage, components, radius, shadow } from '../../tokens'

export interface DropdownOption {
  value: string
  label: string
  disabled?: boolean
}

export interface DropdownProps {
  options: DropdownOption[]
  value?: string
  placeholder?: string
  label?: string
  disabled?: boolean
  error?: string
  onChange?: (value: string) => void
}

export function Dropdown({ options, value, placeholder = 'Select…', label, disabled = false, error, onChange }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selected = options.find(o => o.value === value)

  return (
    <div ref={ref} style={{ position: 'relative', fontFamily: 'Inter, sans-serif' }}>
      {label && (
        <div style={{ fontSize: 13, fontWeight: 600, color: usage.primaryText, marginBottom: 4 }}>
          {label}
        </div>
      )}
      <button
        onClick={() => !disabled && setOpen(o => !o)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
          height: components.inputHeight,
          padding: '0 12px',
          border: `1.5px solid ${error ? colors.semantic.error : open ? usage.focusRing : usage.border}`,
          borderRadius: radius.md,
          background: disabled ? colors.neutral.lightGray : colors.neutral.white,
          color: selected ? usage.primaryText : usage.mutedText,
          fontSize: 14,
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontFamily: 'Inter, sans-serif',
        }}
      >
        <span>{selected?.label ?? placeholder}</span>
        <span style={{
          fontSize: 10, color: usage.mutedText,
          transform: open ? 'rotate(180deg)' : 'none',
          transition: 'transform 0.15s',
        }}>▼</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          marginTop: 4,
          background: colors.neutral.white,
          border: `1px solid ${usage.border}`,
          borderRadius: radius.md,
          boxShadow: shadow.md,
          zIndex: 100,
          overflow: 'hidden',
        }}>
          {options.map(opt => (
            <button
              key={opt.value}
              disabled={opt.disabled}
              onClick={() => { onChange?.(opt.value); setOpen(false) }}
              style={{
                display: 'block',
                width: '100%',
                padding: '10px 14px',
                textAlign: 'left',
                border: 'none',
                background: opt.value === value ? usage.hoverBg : 'transparent',
                color: opt.disabled ? usage.mutedText : usage.primaryText,
                fontSize: 14,
                cursor: opt.disabled ? 'not-allowed' : 'pointer',
                fontFamily: 'Inter, sans-serif',
                fontWeight: opt.value === value ? 600 : 400,
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {error && <div style={{ fontSize: 12, color: colors.semantic.error, marginTop: 4 }}>{error}</div>}
    </div>
  )
}
