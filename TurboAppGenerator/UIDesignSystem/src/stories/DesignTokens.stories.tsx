import type { Meta, StoryObj } from '@storybook/react'
import React from 'react'
import { colors, spacing, radius, shadow, typography } from '../tokens'

function Swatch({ name, hex }: { name: string; hex: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, width: 80 }}>
      <div style={{
        width: 64, height: 64,
        borderRadius: 12,
        background: hex,
        boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
        border: '1px solid rgba(0,0,0,0.06)',
      }} />
      <div style={{ fontSize: 11, fontWeight: 600, color: '#374151', textAlign: 'center' }}>{name}</div>
      <div style={{ fontSize: 10, color: '#9CA3AF', fontFamily: 'monospace' }}>{hex}</div>
    </div>
  )
}

function TokenSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 40 }}>
      <h2 style={{ fontSize: 18, fontWeight: 700, color: '#132445', marginBottom: 16, fontFamily: 'Inter,sans-serif' }}>
        {title}
      </h2>
      {children}
    </div>
  )
}

function TokensPage() {
  return (
    <div style={{ fontFamily: 'Inter, sans-serif', padding: 32, background: '#EFEFE5', minHeight: '100vh' }}>
      <h1 style={{ fontSize: 28, fontWeight: 800, color: '#132445', marginBottom: 8 }}>Mobility Global Design Tokens</h1>
      <p style={{ fontSize: 14, color: '#374151', marginBottom: 40 }}>
        Single source of truth — <code style={{ background: '#fff', padding: '2px 6px', borderRadius: 4 }}>UIDesignSystem/brand_tokens.json</code>
      </p>

      <TokenSection title="Primary Colors">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <Swatch name="Vital Blue"    hex={colors.primary.vitalBlue}   />
          <Swatch name="Forward Blue"  hex={colors.primary.forwardBlue} />
          <Swatch name="Morning Mist"  hex={colors.primary.morningMist} />
        </div>
      </TokenSection>

      <TokenSection title="Neutral Colors">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <Swatch name="White"       hex={colors.neutral.white}      />
          <Swatch name="Quiet Light" hex={colors.neutral.quietLight} />
          <Swatch name="Light Gray"  hex={colors.neutral.lightGray}  />
          <Swatch name="Mid Gray"    hex={colors.neutral.midGray}    />
          <Swatch name="Dark Gray"   hex={colors.neutral.darkGray}   />
          <Swatch name="Black"       hex={colors.neutral.black}      />
        </div>
      </TokenSection>

      <TokenSection title="Accent Colors">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <Swatch name="Steady Lilac"   hex={colors.accent.steadyLilac}   />
          <Swatch name="Soft Lilac"     hex={colors.accent.softLilac}     />
          <Swatch name="Vital Spark"    hex={colors.accent.vitalSpark}    />
          <Swatch name="Clarity Yellow" hex={colors.accent.clarityYellow} />
        </div>
      </TokenSection>

      <TokenSection title="Semantic Colors">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <Swatch name="Success"    hex={colors.semantic.success}   />
          <Swatch name="Success Bg" hex={colors.semantic.successBg} />
          <Swatch name="Warning"    hex={colors.semantic.warning}   />
          <Swatch name="Warning Bg" hex={colors.semantic.warningBg} />
          <Swatch name="Error"      hex={colors.semantic.error}     />
          <Swatch name="Error Bg"   hex={colors.semantic.errorBg}   />
          <Swatch name="Info"       hex={colors.semantic.info}      />
          <Swatch name="Info Bg"    hex={colors.semantic.infoBg}    />
        </div>
      </TokenSection>

      <TokenSection title="Spacing">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {Object.entries(spacing).map(([name, value]) => (
            <div key={name} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <div style={{ width: value, height: value, background: '#0064D2', borderRadius: 2 }} />
              <div style={{ fontSize: 11, fontWeight: 600, color: '#374151' }}>{name}</div>
              <div style={{ fontSize: 10, color: '#9CA3AF', fontFamily: 'monospace' }}>{value}px</div>
            </div>
          ))}
        </div>
      </TokenSection>

      <TokenSection title="Border Radius">
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
          {Object.entries(radius).map(([name, value]) => (
            <div key={name} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 48, height: 48, background: '#132445', borderRadius: Math.min(value, 24) }} />
              <div style={{ fontSize: 11, fontWeight: 600, color: '#374151' }}>{name}</div>
              <div style={{ fontSize: 10, color: '#9CA3AF', fontFamily: 'monospace' }}>{value}px</div>
            </div>
          ))}
        </div>
      </TokenSection>

      <TokenSection title="Shadows">
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {Object.entries(shadow).map(([name, value]) => (
            <div key={name} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 80, height: 80, background: '#fff', borderRadius: 12, boxShadow: value }} />
              <div style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>shadow.{name}</div>
            </div>
          ))}
        </div>
      </TokenSection>

      <TokenSection title="Typography">
        <div style={{ background: '#fff', borderRadius: 12, padding: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#132445' }}>H1 — 32px / 800</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#132445' }}>H2 — 24px / 700</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#132445' }}>H3 — 20px / 700</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#132445' }}>H4 — 16px / 600</div>
          <div style={{ fontSize: 16, color: '#374151' }}>Body Large — 16px</div>
          <div style={{ fontSize: 14, color: '#374151' }}>Body — 14px (primary)</div>
          <div style={{ fontSize: 13, color: '#374151' }}>Body Small — 13px</div>
          <div style={{ fontSize: 11, color: '#9CA3AF' }}>Caption — 11px</div>
        </div>
      </TokenSection>
    </div>
  )
}

const meta: Meta = {
  title: 'Foundation/Design Tokens',
  component: TokensPage,
  parameters: {
    layout: 'fullscreen',
    backgrounds: { default: 'page' },
  },
}
export default meta

export const Tokens: StoryObj = {
  render: () => <TokensPage />,
}
