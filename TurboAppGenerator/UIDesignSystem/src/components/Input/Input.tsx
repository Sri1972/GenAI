import React from 'react'
import { colors, usage, components, radius } from '../../tokens'

export interface InputProps {
  label?: string
  placeholder?: string
  value?: string
  defaultValue?: string
  type?: 'text' | 'email' | 'password' | 'number' | 'search'
  disabled?: boolean
  error?: string
  hint?: string
  prefix?: React.ReactNode
  suffix?: React.ReactNode
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
}

export function Input({
  label, placeholder, value, defaultValue, type = 'text',
  disabled = false, error, hint, prefix, suffix, onChange,
}: InputProps) {
  const wrapStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    fontFamily: 'Inter, sans-serif',
  }
  const labelStyle: React.CSSProperties = {
    fontSize: 13,
    fontWeight: 600,
    color: usage.primaryText,
  }
  const boxStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    height: components.inputHeight,
    border: `1.5px solid ${error ? colors.semantic.error : usage.border}`,
    borderRadius: radius.md,
    background: disabled ? colors.neutral.lightGray : colors.neutral.white,
    overflow: 'hidden',
    transition: 'border-color 0.15s',
  }
  const inputStyle: React.CSSProperties = {
    flex: 1,
    height: '100%',
    border: 'none',
    outline: 'none',
    padding: '0 12px',
    fontSize: 14,
    fontFamily: 'Inter, sans-serif',
    color: usage.primaryText,
    background: 'transparent',
    cursor: disabled ? 'not-allowed' : 'text',
  }
  const affixStyle: React.CSSProperties = {
    padding: '0 10px',
    color: usage.mutedText,
    fontSize: 14,
    display: 'flex',
    alignItems: 'center',
    userSelect: 'none',
  }
  const hintStyle: React.CSSProperties = {
    fontSize: 12,
    color: error ? colors.semantic.error : usage.mutedText,
  }

  return (
    <div style={wrapStyle}>
      {label && <label style={labelStyle}>{label}</label>}
      <div style={boxStyle}>
        {prefix && <span style={affixStyle}>{prefix}</span>}
        <input
          type={type}
          placeholder={placeholder}
          value={value}
          defaultValue={defaultValue}
          disabled={disabled}
          style={inputStyle}
          onChange={onChange}
        />
        {suffix && <span style={affixStyle}>{suffix}</span>}
      </div>
      {(error || hint) && <span style={hintStyle}>{error || hint}</span>}
    </div>
  )
}
