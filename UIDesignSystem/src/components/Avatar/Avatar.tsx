import React from 'react'
import { colors, usage, radius } from '../../tokens'

export type AvatarSize   = 'xs' | 'sm' | 'md' | 'lg' | 'xl'
export type AvatarShape  = 'circle' | 'square'

export interface AvatarProps {
  name?: string
  src?: string
  size?: AvatarSize
  shape?: AvatarShape
  status?: 'online' | 'offline' | 'busy' | 'away'
}

const sizes: Record<AvatarSize, number> = { xs: 24, sm: 32, md: 40, lg: 48, xl: 64 }
const fontSizes: Record<AvatarSize, number> = { xs: 10, sm: 12, md: 14, lg: 16, xl: 22 }

const statusColors: Record<string, string> = {
  online:  colors.semantic.success,
  offline: usage.mutedText,
  busy:    colors.semantic.error,
  away:    colors.semantic.warning,
}

function initials(name: string) {
  return name.split(' ').slice(0, 2).map(n => n[0]).join('').toUpperCase()
}

// Deterministic color from name
function bgFromName(name: string) {
  const palette = [
    colors.primary.vitalBlue,
    colors.primary.forwardBlue,
    colors.accent.steadyLilac,
    '#0E7490',
    '#0F766E',
    '#1D4ED8',
  ]
  let hash = 0
  for (const c of name) hash = (hash * 31 + c.charCodeAt(0)) & 0xffffffff
  return palette[Math.abs(hash) % palette.length]
}

export function Avatar({ name = '', src, size = 'md', shape = 'circle', status }: AvatarProps) {
  const dim = sizes[size]
  const br = shape === 'circle' ? '50%' : radius.md

  return (
    <div style={{ position: 'relative', display: 'inline-flex', flexShrink: 0 }}>
      <div style={{
        width: dim, height: dim,
        borderRadius: br,
        overflow: 'hidden',
        background: src ? 'transparent' : bgFromName(name || '?'),
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: fontSizes[size],
        fontWeight: 700,
        color: '#fff',
        fontFamily: 'Inter, sans-serif',
        flexShrink: 0,
      }}>
        {src ? (
          <img src={src} alt={name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          initials(name) || '?'
        )}
      </div>
      {status && (
        <span style={{
          position: 'absolute',
          bottom: 0, right: 0,
          width: Math.max(8, dim * 0.25),
          height: Math.max(8, dim * 0.25),
          borderRadius: '50%',
          background: statusColors[status],
          border: `2px solid ${colors.neutral.white}`,
        }} />
      )}
    </div>
  )
}

export interface AvatarGroupProps {
  avatars: Pick<AvatarProps, 'name' | 'src'>[]
  size?: AvatarSize
  max?: number
}

export function AvatarGroup({ avatars, size = 'md', max = 4 }: AvatarGroupProps) {
  const visible = avatars.slice(0, max)
  const overflow = avatars.length - max
  const dim = sizes[size]

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      {visible.map((a, i) => (
        <div key={i} style={{ marginLeft: i === 0 ? 0 : -(dim * 0.3), zIndex: visible.length - i }}>
          <div style={{ border: `2px solid ${colors.neutral.white}`, borderRadius: '50%' }}>
            <Avatar {...a} size={size} shape="circle" />
          </div>
        </div>
      ))}
      {overflow > 0 && (
        <div style={{
          marginLeft: -(dim * 0.3),
          width: dim, height: dim,
          borderRadius: '50%',
          background: colors.neutral.lightGray,
          border: `2px solid ${colors.neutral.white}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: fontSizes[size] - 1,
          fontWeight: 700,
          color: usage.mutedText,
          fontFamily: 'Inter, sans-serif',
          zIndex: 0,
        }}>
          +{overflow}
        </div>
      )}
    </div>
  )
}
