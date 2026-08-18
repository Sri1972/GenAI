// @ts-nocheck
/**
 * SettingsForm.skill.tsx — Generic multi-section settings / preferences form.
 *
 * Domain-agnostic — reads all config from src/config/SettingsForm.config.ts
 * Works for: user settings, app preferences, profile editing, configuration panels.
 * Features: section grouping, text/email/number/select/toggle/textarea fields,
 *   unsaved-changes detection, save/reset, per-section success toast.
 */
import React, { useState, useMemo } from 'react'
import { config } from '../config/SettingsForm.config'

// ── Helpers ───────────────────────────────────────────────────────────────────
function deepClone<T>(v: T): T { return JSON.parse(JSON.stringify(v)) }

function initValues(sections: any[]): Record<string, any> {
  const vals: Record<string, any> = {}
  for (const sec of sections) {
    for (const field of sec.fields ?? []) {
      vals[field.key] = field.defaultValue ?? (field.type === 'toggle' ? false : '')
    }
  }
  return vals
}

// ── Field renderers ────────────────────────────────────────────────────────────
function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      style={{
        position: 'relative', display: 'inline-flex', alignItems: 'center',
        width: 44, height: 24, borderRadius: 999, border: 'none', cursor: 'pointer',
        background: checked ? '#0064D2' : '#D1D5DB', transition: 'background 0.2s',
        flexShrink: 0,
      }}
    >
      <span style={{
        position: 'absolute', left: checked ? 22 : 2, width: 20, height: 20,
        borderRadius: '50%', background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        transition: 'left 0.2s',
      }} />
    </button>
  )
}

function FieldRow({ field, value, onChange, error }: { field: any; value: any; onChange: (v: any) => void; error?: string }) {
  const base: React.CSSProperties = {
    height: 40, padding: '0 12px', borderRadius: 8, fontSize: 14, outline: 'none',
    border: `1px solid ${error ? '#EF4444' : '#D1D5DB'}`, background: '#fff',
    color: '#0D1B2A', width: '100%', boxSizing: 'border-box',
    transition: 'border-color 0.15s',
  }

  if (field.type === 'toggle') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0' }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#0D1B2A' }}>{field.label}</div>
          {field.hint && <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>{field.hint}</div>}
        </div>
        <Toggle checked={!!value} onChange={onChange} />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: '#374151', letterSpacing: '0.03em' }}>
        {field.label}{field.required && <span style={{ color: '#EF4444', marginLeft: 2 }}>*</span>}
      </label>
      {field.type === 'select' ? (
        <select value={value} onChange={e => onChange(e.target.value)} style={base}>
          <option value="">— Select —</option>
          {(field.options ?? []).map((o: any) => (
            <option key={typeof o === 'string' ? o : o.value} value={typeof o === 'string' ? o : o.value}>
              {typeof o === 'string' ? o : o.label}
            </option>
          ))}
        </select>
      ) : field.type === 'textarea' ? (
        <textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          rows={field.rows ?? 3}
          placeholder={field.placeholder ?? ''}
          style={{ ...base, height: 'auto', padding: '10px 12px', resize: 'vertical' }}
        />
      ) : (
        <input
          type={field.type ?? 'text'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={field.placeholder ?? ''}
          min={field.min}
          max={field.max}
          style={base}
        />
      )}
      {field.hint && !error && <span style={{ fontSize: 11, color: '#9CA3AF' }}>{field.hint}</span>}
      {error && <span style={{ fontSize: 11, color: '#EF4444' }}>{error}</span>}
    </div>
  )
}

// ── Section card ───────────────────────────────────────────────────────────────
function SectionCard({
  section, values, errors, onChange, onSave, saved,
}: {
  section: any; values: Record<string, any>; errors: Record<string, string>;
  onChange: (key: string, v: any) => void; onSave: () => void; saved: boolean;
}) {
  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', overflow: 'hidden' }}>
      {/* Section header */}
      <div style={{ padding: '16px 24px', borderBottom: '1px solid #F1F5F9', display: 'flex', alignItems: 'center', gap: 12 }}>
        {section.icon && <span style={{ fontSize: 20 }}>{section.icon}</span>}
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1B2A' }}>{section.title}</div>
          {section.description && <div style={{ fontSize: 12, color: '#6B7280', marginTop: 1 }}>{section.description}</div>}
        </div>
        {saved && (
          <span style={{ marginLeft: 'auto', fontSize: 12, fontWeight: 600, color: '#059669', background: '#D1FAE5', padding: '3px 10px', borderRadius: 999 }}>
            ✓ Saved
          </span>
        )}
      </div>

      {/* Fields */}
      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Toggle fields inline, others in grid */}
        {(section.fields ?? []).filter((f: any) => f.type === 'toggle').map((field: any) => (
          <FieldRow key={field.key} field={field} value={values[field.key]} onChange={v => onChange(field.key, v)} error={errors[field.key]} />
        ))}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
          {(section.fields ?? []).filter((f: any) => f.type !== 'toggle').map((field: any) => (
            <FieldRow key={field.key} field={field} value={values[field.key]} onChange={v => onChange(field.key, v)} error={errors[field.key]} />
          ))}
        </div>
      </div>

      {/* Section footer with save */}
      <div style={{ padding: '12px 24px', borderTop: '1px solid #F1F5F9', display: 'flex', justifyContent: 'flex-end', background: '#FAFAFA' }}>
        <button
          type="button"
          onClick={onSave}
          style={{
            height: 36, padding: '0 20px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: '#0064D2', color: '#fff', fontSize: 13, fontWeight: 600,
            transition: 'opacity 0.15s',
          }}
          onMouseOver={e => (e.currentTarget.style.opacity = '0.88')}
          onMouseOut={e => (e.currentTarget.style.opacity = '1')}
        >
          Save {section.title}
        </button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function SettingsFormPage() {
  const { pageTitle, pageSubtitle, sections } = config as any

  const original  = useMemo(() => initValues(sections ?? []), [])
  const [values,  setValues]  = useState<Record<string, any>>(deepClone(original))
  const [errors,  setErrors]  = useState<Record<string, string>>({})
  const [savedSet, setSavedSet] = useState<Set<string>>(new Set())

  const isDirty = JSON.stringify(values) !== JSON.stringify(original)

  function handleChange(key: string, value: any) {
    setValues(prev => ({ ...prev, [key]: value }))
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n })
  }

  function validateSection(section: any): Record<string, string> {
    const errs: Record<string, string> = {}
    for (const field of section.fields ?? []) {
      if (field.required && !values[field.key]) {
        errs[field.key] = `${field.label} is required`
      }
      if (field.type === 'email' && values[field.key] && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values[field.key])) {
        errs[field.key] = 'Enter a valid email address'
      }
    }
    return errs
  }

  function handleSave(section: any) {
    const errs = validateSection(section)
    if (Object.keys(errs).length) {
      setErrors(prev => ({ ...prev, ...errs }))
      return
    }
    setSavedSet(prev => new Set([...prev, section.title]))
    setTimeout(() => setSavedSet(prev => { const n = new Set(prev); n.delete(section.title); return n }), 2500)
  }

  function handleReset() {
    setValues(deepClone(original))
    setErrors({})
  }

  const s = {
    page: { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    h1:   { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={s.h1}>{pageTitle ?? 'Settings'}</h1>
          {pageSubtitle && <p style={{ margin: '4px 0 0', fontSize: 14, color: '#6B7280' }}>{pageSubtitle}</p>}
        </div>
        {isDirty && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 12, color: '#D97706', fontWeight: 500 }}>● Unsaved changes</span>
            <button
              type="button"
              onClick={handleReset}
              style={{ height: 34, padding: '0 14px', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', fontSize: 13, cursor: 'pointer', color: '#374151' }}
            >
              Discard
            </button>
          </div>
        )}
      </div>

      {/* Sections */}
      {(sections ?? []).map((section: any) => (
        <SectionCard
          key={section.title}
          section={section}
          values={values}
          errors={errors}
          onChange={handleChange}
          onSave={() => handleSave(section)}
          saved={savedSet.has(section.title)}
        />
      ))}
    </div>
  )
}
