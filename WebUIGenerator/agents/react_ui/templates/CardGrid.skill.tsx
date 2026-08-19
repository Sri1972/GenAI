// @ts-nocheck
/**
 * CardGrid.skill.tsx — Generic searchable / filterable card grid.
 *
 * Domain-agnostic — reads config from src/config/CardGrid.config.ts
 * Works for: player profiles, product catalog, dealer directory, team roster, etc.
 */
import { useState, useEffect, useMemo } from 'react'
import { config } from '../config/CardGrid.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

const BADGE_STYLES: Record<string, {bg:string;color:string}> = {
  default: { bg: '#F3F4F6', color: '#374151' },
  success: { bg: '#D1FAE5', color: '#065F46' },
  warning: { bg: '#FEF3C7', color: '#92400E' },
  error:   { bg: '#FEE2E2', color: '#991B1B' },
  info:    { bg: '#DBEAFE', color: '#1E40AF' },
  accent:  { bg: '#EDE9FE', color: '#5B21B6' },
}
const VALID_VARIANTS = new Set(Object.keys(BADGE_STYLES))
function safeVariant(v?: string) { return (v && VALID_VARIANTS.has(v) ? v : 'default') as keyof typeof BADGE_STYLES }

function fmtMetric(value: any, format: string) {
  if (value == null) return '—'
  const n = Number(value)
  if (isNaN(n)) return String(value)
  if (format === 'currency') {
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`
    return `$${n.toFixed(0)}`
  }
  if (format === 'percent') return `${n.toFixed(1)}%`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return n.toLocaleString()
}

function Initials({ name, size = 60 }: { name: string; size?: number }) {
  const init = name.split(/\s+/).map(w => w[0] ?? '').join('').slice(0, 2).toUpperCase()
  const hue  = Math.abs(name.split('').reduce((h, c) => (h << 5) - h + c.charCodeAt(0), 0)) % 360
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: `hsl(${hue},55%,50%)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#fff', fontWeight: 700, fontSize: size * 0.38, flexShrink: 0,
    }}>{init}</div>
  )
}

export default function CardGridPage() {
  const {
    dataExport, tableName, pageTitle, nameField, subtitleField, imageField,
    badgeField, badgeColors = {}, metrics = [], filters = [], searchFields = [],
  } = config as any

  const [apiData, setApiData] = useState<any[] | null>(null)
  const [apiLoading, setApiLoading] = useState(!!tableName)

  useEffect(() => {
    if (!tableName) return
    fetch(`${_API}/api/data/${tableName}?limit=500`)
      .then(r => r.json())
      .then(j => { setApiData(j.data || []); setApiLoading(false) })
      .catch(() => setApiLoading(false))
  }, [tableName])

  const allRows: any[] = apiData ?? dataExport ?? []

  const [search, setSearch]       = useState('')
  const [filterVals, setFilterVals] = useState<Record<string, string>>(
    Object.fromEntries((filters as any[]).map((f: any) => [f.field, 'All']))
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return allRows.filter(row => {
      if (q) {
        const hay = (searchFields as string[]).map(f => String(row[f] ?? '')).join(' ').toLowerCase()
        if (!hay.includes(q)) return false
      }
      for (const [field, val] of Object.entries(filterVals)) {
        if (val !== 'All' && String(row[field]) !== val) return false
      }
      return true
    })
  }, [search, filterVals])

  const s = {
    page:   { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    card:   { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    h1:     { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    bar:    { display: 'flex', gap: 10, flexWrap: 'wrap' as const, alignItems: 'flex-end' },
    input:  { height: 40, padding: '0 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, minWidth: 220, outline: 'none', color: '#374151' },
    sel:    { height: 40, padding: '0 10px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, background: '#fff', color: '#374151' },
    grid:   { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 },
    item:   { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: 20, display: 'flex', flexDirection: 'column' as const, gap: 10, transition: 'box-shadow 0.15s, transform 0.15s', cursor: 'default' },
  }

  if (apiLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  return (
    <div style={s.page}>
      <div><h1 style={s.h1}>{pageTitle}</h1></div>

      {/* Filter bar */}
      <div style={s.card}>
        <div style={s.bar}>
          <input
            style={s.input}
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {(filters as any[]).map((f: any) => (
            <div key={f.field} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600 }}>{f.label}</span>
              <select style={s.sel} value={filterVals[f.field] ?? 'All'} onChange={e => setFilterVals(p => ({ ...p, [f.field]: e.target.value }))}>
                <option value="All">All</option>
                {f.options.map((o: string) => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          ))}
          <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 12px', height: 40, borderRadius: 8, background: '#EFF6FF', color: '#1D4ED8', fontSize: 13, fontWeight: 600, border: '1px solid #BFDBFE' }}>
            {filtered.length} items
          </span>
        </div>
      </div>

      {/* Grid */}
      <div style={s.grid}>
        {filtered.map((row: any, i: number) => {
          const name    = String(row[nameField] ?? '—')
          const sub     = subtitleField ? String(row[subtitleField] ?? '') : null
          const imgSrc  = imageField ? String(row[imageField] ?? '') : null
          const badgeV  = badgeField ? String(row[badgeField] ?? '') : null
          const variant = badgeV ? safeVariant((badgeColors as any)[badgeV]) : 'default'
          const bs      = BADGE_STYLES[variant]

          return (
            <div
              key={i}
              style={s.item}
              onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = '0 8px 24px rgba(0,0,0,0.10)'; (e.currentTarget as HTMLDivElement).style.transform = 'translateY(-2px)' }}
              onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = ''; (e.currentTarget as HTMLDivElement).style.transform = '' }}
            >
              {/* Avatar / image */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {imgSrc ? (
                  <img src={imgSrc} alt={name} style={{ width: 56, height: 56, borderRadius: '50%', objectFit: 'cover', border: '2px solid #E5E7EB' }}
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
                ) : (
                  <Initials name={name} size={56} />
                )}
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1B2A', lineHeight: 1.2 }}>{name}</div>
                  {sub && <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>{sub}</div>}
                </div>
              </div>

              {/* Badge */}
              {badgeV && (
                <span style={{ display: 'inline-flex', padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: bs.bg, color: bs.color, alignSelf: 'flex-start' }}>{badgeV}</span>
              )}

              {/* Metrics */}
              {(metrics as any[]).length > 0 && (
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', borderTop: '1px solid #F1F5F9', paddingTop: 10 }}>
                  {(metrics as any[]).map((m: any) => (
                    <div key={m.field} style={{ flex: '1 1 60px' }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{m.label}</div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: '#374151', marginTop: 2 }}>{fmtMetric(row[m.field], m.format)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {filtered.length === 0 && (
        <div style={{ textAlign: 'center', padding: 60, color: '#9CA3AF', fontSize: 14 }}>No items match your filters.</div>
      )}
    </div>
  )
}
