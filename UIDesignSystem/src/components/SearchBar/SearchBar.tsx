import React, { useState } from 'react'
import { colors, usage, components, radius } from '../../tokens'

export interface SearchBarProps {
  placeholder?: string
  value?: string
  defaultValue?: string
  disabled?: boolean
  fullWidth?: boolean
  onSearch?: (value: string) => void
  onChange?: (value: string) => void
}

export function SearchBar({ placeholder = 'Search…', value: controlled, defaultValue = '', disabled = false, fullWidth = false, onSearch, onChange }: SearchBarProps) {
  const [internal, setInternal] = useState(defaultValue)
  const val = controlled ?? internal

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setInternal(e.target.value)
    onChange?.(e.target.value)
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === 'Enter') onSearch?.(val)
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      height: components.inputHeight,
      border: `1.5px solid ${usage.border}`,
      borderRadius: radius.full,
      background: disabled ? colors.neutral.lightGray : colors.neutral.white,
      overflow: 'hidden',
      width: fullWidth ? '100%' : 280,
      fontFamily: 'Inter, sans-serif',
      transition: 'border-color 0.15s',
    }}>
      <span style={{
        padding: '0 12px 0 14px',
        color: usage.mutedText,
        fontSize: 15,
        flexShrink: 0,
        lineHeight: 1,
      }}>
        🔍
      </span>
      <input
        type="search"
        value={val}
        placeholder={placeholder}
        disabled={disabled}
        onChange={handleChange}
        onKeyDown={handleKey}
        style={{
          flex: 1,
          height: '100%',
          border: 'none',
          outline: 'none',
          background: 'transparent',
          fontSize: 14,
          color: usage.primaryText,
          fontFamily: 'Inter, sans-serif',
        }}
      />
      {val && (
        <button
          onClick={() => { setInternal(''); onChange?.('') }}
          style={{
            padding: '0 12px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            color: usage.mutedText,
            fontSize: 16,
            lineHeight: 1,
          }}
        >
          ×
        </button>
      )}
    </div>
  )
}
