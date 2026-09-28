import React from 'react'
import { colors, usage, components } from '../../tokens'

export interface FooterProps {
  brand?: string
  links?: { label: string; href?: string }[]
  copyright?: string
  variant?: 'light' | 'dark'
}

export function Footer({ brand = 'Mobility Global', links = [], copyright, variant = 'light' }: FooterProps) {
  const isDark = variant === 'dark'
  const bg    = isDark ? colors.primary.vitalBlue : colors.neutral.white
  const text  = isDark ? 'rgba(255,255,255,0.72)' : usage.mutedText
  const border = isDark ? 'rgba(255,255,255,0.12)' : usage.border

  return (
    <footer style={{
      height: components.footerHeight,
      background: bg,
      borderTop: `1px solid ${border}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      fontFamily: 'Inter, sans-serif',
      fontSize: 13,
      color: text,
      gap: 16,
    }}>
      <span style={{ fontWeight: 600, color: isDark ? '#fff' : usage.primaryText }}>
        {brand}
      </span>
      {links.length > 0 && (
        <nav style={{ display: 'flex', gap: 20 }}>
          {links.map(link => (
            <a key={link.label} href={link.href ?? '#'}
              style={{ color: text, textDecoration: 'none', fontSize: 13 }}>
              {link.label}
            </a>
          ))}
        </nav>
      )}
      <span>{copyright ?? `© ${new Date().getFullYear()} ${brand}. All rights reserved.`}</span>
    </footer>
  )
}
