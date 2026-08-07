// @ts-nocheck
/**
 * DataGrid.skill.tsx — Generic filterable / sortable / paginated data table.
 *
 * This file is domain-agnostic. It reads everything it needs from
 * src/config/DataGrid.config.ts which the LLM generates per project.
 *
 * Works for: sales records, player stats, orders, products, transactions, etc.
 * Valid Badge variants: default | success | warning | error | info | accent
 */
import { useState, useEffect, useMemo } from 'react'
import { config } from '../config/DataGrid.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

// ── Types inferred from config ────────────────────────────────────────────────

type SortDir = 'asc' | 'desc'
type ColumnType = 'text' | 'number' | 'currency' | 'percent' | 'badge' | 'progress' | 'date'

interface ColumnDef {
  key: string
  header: string
  type: ColumnType
  align?: 'left' | 'right'
  /** For type='badge': maps value string → valid variant */
  badgeColors?: Record<string, 'default' | 'success' | 'warning' | 'error' | 'info' | 'accent'>
  /** For type='currency': multiplier before formatting (e.g. 1/1_000_000 for $M) */
  divisor?: number
  /** For type='currency': suffix like 'M' or 'B' */
  suffix?: string
  /** For type='progress': max value (defaults to 100) */
  progressMax?: number
}

// ── Cell renderers ────────────────────────────────────────────────────────────

const BADGE_VALID = new Set(['default','success','warning','error','info','accent'])

function safeVariant(v: string | undefined): 'default'|'success'|'warning'|'error'|'info'|'accent' {
  if (v && BADGE_VALID.has(v)) return v as any
  return 'default'
}

const BADGE_STYLES: Record<string, {bg:string;color:string}> = {
  default: { bg: '#F3F4F6', color: '#374151' },
  success: { bg: '#D1FAE5', color: '#065F46' },
  warning: { bg: '#FEF3C7', color: '#92400E' },
  error:   { bg: '#FEE2E2', color: '#991B1B' },
  info:    { bg: '#DBEAFE', color: '#1E40AF' },
  accent:  { bg: '#EDE9FE', color: '#5B21B6' },
}

function Badge({ label, variant }: { label: string; variant?: string }) {
  const v = safeVariant(variant)
  const s = BADGE_STYLES[v]
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '2px 8px', borderRadius: 999,
      fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap',
      background: s.bg, color: s.color,
    }}>{label}</span>
  )
}

function ProgressBar({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 6, background: '#E5E7EB', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: '#0064D2', borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, color: '#6B7280', minWidth: 28, textAlign: 'right' }}>
        {value.toFixed(1)}
      </span>
    </div>
  )
}

function renderCell(value: any, col: ColumnDef): React.ReactNode {
  if (value == null || value === '') return <span style={{ color: '#9CA3AF' }}>—</span>

  switch (col.type) {
    case 'badge': {
      const variant = col.badgeColors?.[String(value)]
      return <Badge label={String(value)} variant={variant} />
    }
    case 'currency': {
      const divisor = col.divisor ?? 1
      const suffix = col.suffix ?? ''
      const v = (Number(value) / divisor)
      const fmt = v >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 1 }) : v.toFixed(1)
      return <span style={{ fontVariantNumeric: 'tabular-nums' }}>${fmt}{suffix}</span>
    }
    case 'percent': {
      const n = Number(value)
      const color = n >= 0 ? '#059669' : '#DC2626'
      const bg = n >= 0 ? '#D1FAE5' : '#FEE2E2'
      return (
        <span style={{
          display: 'inline-flex', padding: '2px 8px', borderRadius: 999,
          fontSize: 11, fontWeight: 600, background: bg, color,
        }}>
          {n >= 0 ? '+' : ''}{n.toFixed(1)}%
        </span>
      )
    }
    case 'number': {
      return <span style={{ fontVariantNumeric: 'tabular-nums' }}>{Number(value).toLocaleString()}</span>
    }
    case 'progress': {
      return <ProgressBar value={Number(value)} max={col.progressMax} />
    }
    default:
      return <span>{String(value)}</span>
  }
}

// ── CSV export ────────────────────────────────────────────────────────────────

function exportCSV(rows: any[], columns: ColumnDef[], filename: string) {
  const headers = columns.map(c => c.header).join(',')
  const lines = rows.map(row =>
    columns.map(c => {
      const v = row[c.key] ?? ''
      const s = String(v).replace(/"/g, '""')
      return /[,"\n]/.test(s) ? `"${s}"` : s
    }).join(',')
  )
  const csv = [headers, ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

// ── Component ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20

export default function DataGridPage() {
  const { dataExport, tableName, pageTitle, pageSubtitle, rowKey, searchFields,
          filters: filterDefs, columns, defaultSort, csvFilename } = config as any

  const [apiData, setApiData] = useState<any[] | null>(null)
  const [apiLoading, setApiLoading] = useState(!!tableName)

  useEffect(() => {
    if (!tableName) return
    fetch(`${_API}/api/data/${tableName}?limit=1000`)
      .then(r => r.json())
      .then(j => { setApiData(j.data || []); setApiLoading(false) })
      .catch(() => setApiLoading(false))
  }, [tableName])

  const allRows: any[] = apiData ?? dataExport ?? []

  const [search, setSearch] = useState('')
  const [filterValues, setFilterValues] = useState<Record<string, string>>(
    Object.fromEntries((filterDefs ?? []).map(f => [f.field, 'All']))
  )
  const [sortKey, setSortKey] = useState<string>(defaultSort?.key ?? columns[0]?.key ?? '')
  const [sortDir, setSortDir] = useState<SortDir>(defaultSort?.dir ?? 'desc')
  const [page, setPage] = useState(1)

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return allRows.filter(row => {
      // Global search
      if (q) {
        const hay = (searchFields ?? []).map(f => String(row[f] ?? '')).join(' ').toLowerCase()
        if (!hay.includes(q)) return false
      }
      // Dropdown filters
      for (const [field, val] of Object.entries(filterValues)) {
        if (val !== 'All' && String(row[field]) !== val) return false
      }
      return true
    })
  }, [allRows, search, filterValues])

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey]
      let cmp = 0
      if (typeof av === 'number' && typeof bv === 'number') cmp = av - bv
      else cmp = String(av ?? '').localeCompare(String(bv ?? ''))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [filtered, sortKey, sortDir])

  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const pageRows = sorted.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const handleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
    setPage(1)
  }

  const reset = () => {
    setSearch('')
    setFilterValues(Object.fromEntries((filterDefs ?? []).map(f => [f.field, 'All'])))
    setPage(1)
  }

  // ── Styles ──────────────────────────────────────────────────────────────────
  const s = {
    page:    { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 24, minHeight: '100%', background: '#F8FAFC' },
    card:    { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    heading: { fontSize: 28, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    sub:     { fontSize: 14, color: '#6B7280', marginTop: 4 },
    bar:     { display: 'flex', flexWrap: 'wrap' as const, gap: 10, alignItems: 'flex-end' },
    input:   { height: 40, padding: '0 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, minWidth: 220, outline: 'none', color: '#374151' },
    select:  { height: 40, padding: '0 10px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, background: '#fff', color: '#374151', cursor: 'pointer' },
    btnPri:  { height: 40, padding: '0 16px', borderRadius: 8, border: 'none', background: '#0064D2', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' },
    btnSec:  { height: 40, padding: '0 14px', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', color: '#374151', fontSize: 13, fontWeight: 500, cursor: 'pointer' },
    btnDis:  { opacity: 0.4, cursor: 'not-allowed' as const },
    table:   { width: '100%', borderCollapse: 'collapse' as const },
    th:      { padding: '10px 12px', textAlign: 'left' as const, fontSize: 11, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase' as const, letterSpacing: '0.05em', borderBottom: '2px solid #E5E7EB', cursor: 'pointer', userSelect: 'none' as const, whiteSpace: 'nowrap' as const },
    thR:     { padding: '10px 12px', textAlign: 'right' as const, fontSize: 11, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase' as const, letterSpacing: '0.05em', borderBottom: '2px solid #E5E7EB', cursor: 'pointer', userSelect: 'none' as const, whiteSpace: 'nowrap' as const },
    td:      { padding: '10px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', whiteSpace: 'nowrap' as const },
    tdR:     { padding: '10px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', whiteSpace: 'nowrap' as const, textAlign: 'right' as const },
  }

  const arrow = (key: string) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''

  if (apiLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  return (
    <div style={s.page}>
      {/* Header */}
      <div>
        <h1 style={s.heading}>{pageTitle}</h1>
        {pageSubtitle && <p style={s.sub}>{pageSubtitle}</p>}
      </div>

      {/* Filter bar */}
      <div style={s.card}>
        <div style={s.bar}>
          <input
            style={s.input}
            placeholder={`Search ${(searchFields ?? []).join(', ')}…`}
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
          />
          {(filterDefs ?? []).map(f => (
            <div key={f.field} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600 }}>{f.label}</span>
              <select
                style={s.select}
                value={filterValues[f.field] ?? 'All'}
                onChange={e => { setFilterValues(prev => ({ ...prev, [f.field]: e.target.value })); setPage(1) }}
              >
                <option value="All">All</option>
                {f.options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
          ))}
          <button style={s.btnSec} onClick={reset}>Reset</button>
          <span style={{ ...s.btnSec, background: '#EFF6FF', color: '#1D4ED8', border: '1px solid #BFDBFE', display: 'inline-flex', alignItems: 'center' }}>
            {sorted.length.toLocaleString()} rows
          </span>
          <div style={{ marginLeft: 'auto' }}>
            <button style={s.btnPri} onClick={() => exportCSV(sorted, columns, csvFilename ?? 'export.csv')}>
              Export CSV
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div style={s.card}>
        <div style={{ overflowX: 'auto' }}>
          <table style={s.table}>
            <thead>
              <tr>
                {columns.map(col => (
                  <th
                    key={col.key}
                    style={col.align === 'right' ? s.thR : s.th}
                    onClick={() => handleSort(col.key)}
                  >
                    {col.header}{arrow(col.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} style={{ ...s.td, textAlign: 'center', padding: 40, color: '#9CA3AF' }}>
                    No records match your filters.
                  </td>
                </tr>
              ) : pageRows.map((row, i) => (
                <tr key={row[rowKey] ?? i} style={{ background: i % 2 === 0 ? '#fff' : '#FAFAFA' }}>
                  {columns.map(col => (
                    <td key={col.key} style={col.align === 'right' ? s.tdR : s.td}>
                      {renderCell(row[col.key], col)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pageCount > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, paddingTop: 12, borderTop: '1px solid #F1F5F9' }}>
            <span style={{ fontSize: 12, color: '#9CA3AF' }}>
              Showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, sorted.length)} of {sorted.length}
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button
                style={{ ...s.btnSec, ...(safePage === 1 ? s.btnDis : {}) }}
                disabled={safePage === 1}
                onClick={() => setPage(p => p - 1)}
              >← Prev</button>
              <span style={{ height: 40, display: 'inline-flex', alignItems: 'center', padding: '0 12px', fontSize: 13, color: '#374151' }}>
                {safePage} / {pageCount}
              </span>
              <button
                style={{ ...s.btnSec, ...(safePage === pageCount ? s.btnDis : {}) }}
                disabled={safePage === pageCount}
                onClick={() => setPage(p => p + 1)}
              >Next →</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
export { DataGridPage as DataGrid }
