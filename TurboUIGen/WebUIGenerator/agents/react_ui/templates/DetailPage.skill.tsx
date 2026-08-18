// @ts-nocheck
/**
 * DetailPage.skill.tsx — Master-detail layout with searchable list + detail panel.
 *
 * Domain-agnostic — reads config from src/config/DetailPage.config.ts
 * Works for: product details, employee profiles, order details, case management, etc.
 */
import { useState, useEffect, useMemo } from 'react'
import { config } from '../config/DetailPage.config'

const _API = (import.meta as any).env?.VITE_API_BASE || ''

function fmtValue(value: any, format: string) {
  if (value == null) return '—'
  if (format === 'text' || format === 'badge') return String(value)
  const n = Number(value)
  if (isNaN(n)) return String(value)
  if (format === 'currency') {
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`
    return `$${n.toFixed(2)}`
  }
  if (format === 'percent') return `${n.toFixed(1)}%`
  if (format === 'date') return new Date(value).toLocaleDateString()
  if (format === 'number') return n.toLocaleString()
  return String(value)
}

function Spinner() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
      <div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

function FieldsSection({ section, item }: { section: any; item: any }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
      {(section.fields || []).map((f: any) => (
        <div key={f.key}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>{f.label}</div>
          <div style={{ fontSize: 14, fontWeight: 500, color: '#1F2937' }}>{fmtValue(item[f.key], f.format)}</div>
        </div>
      ))}
    </div>
  )
}

function TableSection({ section, item }: { section: any; item: any }) {
  const rows = item[section.dataField] || []
  const cols = section.columns || []
  if (!Array.isArray(rows) || rows.length === 0) return <div style={{ color: '#9CA3AF', fontSize: 13 }}>No data available.</div>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr>
            {cols.map((c: any) => (
              <th key={c.key} style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid #E5E7EB', fontWeight: 600, color: '#6B7280' }}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row: any, i: number) => (
            <tr key={i} style={{ borderBottom: '1px solid #F3F4F6' }}>
              {cols.map((c: any) => (
                <td key={c.key} style={{ padding: '8px 12px', color: '#374151' }}>{fmtValue(row[c.key], c.format || 'text')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TextSection({ section, item }: { section: any; item: any }) {
  const text = item[section.textField] || ''
  return <div style={{ fontSize: 14, color: '#374151', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{text}</div>
}

export function DetailPage() {
  const {
    tableName, pageTitle, pageSubtitle,
    listTitleField, listSubtitleField, listBadgeField, listBadgeColors = {},
    searchFields = [],
    detailTitleField, detailSubtitleField, detailSections = [],
    accentColor = '#0064D2',
  } = config as any

  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  useEffect(() => {
    if (!tableName) { setLoading(false); return }
    fetch(`${_API}/api/data/${tableName}?limit=1000`)
      .then(r => r.json())
      .then(j => { setData(j.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tableName])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return data
    return data.filter(row => {
      const hay = (searchFields as string[]).map(f => String(row[f] ?? '')).join(' ').toLowerCase()
      return hay.includes(q)
    })
  }, [data, search])

  const selectedItem = selectedIdx !== null ? filtered[selectedIdx] ?? null : null

  if (loading) return <Spinner />

  const s = {
    page: { display: 'flex', flexDirection: 'column' as const, height: '100%', background: '#F8FAFC' },
    header: { padding: '20px 24px', borderBottom: '1px solid #E5E7EB', background: '#fff' },
    h1: { fontSize: 22, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    subtitle: { fontSize: 13, color: '#6B7280', marginTop: 4 },
    body: { display: 'flex', flex: 1, overflow: 'hidden' },
    listPanel: { width: 320, minWidth: 280, borderRight: '1px solid #E5E7EB', display: 'flex', flexDirection: 'column' as const, background: '#fff' },
    detailPanel: { flex: 1, overflow: 'auto', padding: 28, background: '#F8FAFC' },
    searchBox: { padding: '12px 16px', borderBottom: '1px solid #F3F4F6' },
    input: { width: '100%', height: 36, padding: '0 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, outline: 'none', color: '#374151', boxSizing: 'border-box' as const },
    listScroll: { flex: 1, overflowY: 'auto' as const },
    listItem: (active: boolean) => ({
      padding: '14px 16px', cursor: 'pointer', borderBottom: '1px solid #F3F4F6',
      background: active ? `${accentColor}0D` : '#fff',
      borderLeft: active ? `3px solid ${accentColor}` : '3px solid transparent',
      transition: 'background 0.15s',
    }),
    listTitle: { fontSize: 14, fontWeight: 600, color: '#1F2937', margin: 0 },
    listSub: { fontSize: 12, color: '#6B7280', marginTop: 2 },
    badge: (color: string) => ({
      display: 'inline-block', padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 600,
      background: color || '#F3F4F6', color: '#fff', marginTop: 4,
    }),
    sectionTitle: { fontSize: 15, fontWeight: 700, color: '#374151', marginBottom: 12 },
    sectionCard: { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: 20, marginBottom: 20 },
    emptyState: { display: 'flex', flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9CA3AF' },
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <h1 style={s.h1}>{pageTitle}</h1>
        {pageSubtitle && <div style={s.subtitle}>{pageSubtitle}</div>}
      </div>

      {/* Body: list + detail */}
      <div style={s.body}>
        {/* Left panel — list */}
        <div style={s.listPanel}>
          <div style={s.searchBox}>
            <input
              style={s.input}
              placeholder="Search..."
              value={search}
              onChange={e => { setSearch(e.target.value); setSelectedIdx(null) }}
            />
          </div>
          <div style={s.listScroll}>
            {filtered.length === 0 && (
              <div style={{ padding: 24, textAlign: 'center', color: '#9CA3AF', fontSize: 13 }}>No items found.</div>
            )}
            {filtered.map((row, i) => {
              const title = String(row[listTitleField] ?? '—')
              const sub = listSubtitleField ? String(row[listSubtitleField] ?? '') : null
              const badgeVal = listBadgeField ? String(row[listBadgeField] ?? '') : null
              const badgeColor = badgeVal ? (listBadgeColors as any)[badgeVal] || '#6B7280' : null
              return (
                <div key={i} style={s.listItem(selectedIdx === i)} onClick={() => setSelectedIdx(i)}>
                  <div style={s.listTitle}>{title}</div>
                  {sub && <div style={s.listSub}>{sub}</div>}
                  {badgeVal && <span style={s.badge(badgeColor)}>{badgeVal}</span>}
                </div>
              )
            })}
          </div>
          <div style={{ padding: '10px 16px', borderTop: '1px solid #F3F4F6', fontSize: 12, color: '#9CA3AF' }}>
            {filtered.length} item{filtered.length !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Right panel — detail */}
        <div style={s.detailPanel}>
          {!selectedItem ? (
            <div style={s.emptyState}>
              <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="#D1D5DB" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              <div style={{ marginTop: 12, fontSize: 14 }}>Select an item to view details</div>
            </div>
          ) : (
            <div>
              {/* Detail header */}
              <div style={{ marginBottom: 24 }}>
                <h2 style={{ fontSize: 20, fontWeight: 700, color: '#0D1B2A', margin: 0 }}>{selectedItem[detailTitleField] ?? '—'}</h2>
                {detailSubtitleField && selectedItem[detailSubtitleField] && (
                  <div style={{ fontSize: 14, color: '#6B7280', marginTop: 4 }}>{selectedItem[detailSubtitleField]}</div>
                )}
              </div>

              {/* Sections */}
              {(detailSections as any[]).map((section: any, si: number) => (
                <div key={si} style={s.sectionCard}>
                  <div style={s.sectionTitle}>{section.title}</div>
                  {section.type === 'fields' && <FieldsSection section={section} item={selectedItem} />}
                  {section.type === 'table' && <TableSection section={section} item={selectedItem} />}
                  {section.type === 'text' && <TextSection section={section} item={selectedItem} />}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Responsive stacking */}
      <style>{`
        @media (max-width: 768px) {
          [style*="width: 320"] { width: 100% !important; border-right: none !important; border-bottom: 1px solid #E5E7EB; max-height: 40vh; }
          [style*="display: flex"][style*="overflow: hidden"] { flex-direction: column !important; }
        }
      `}</style>
    </div>
  )
}

export default DetailPage
