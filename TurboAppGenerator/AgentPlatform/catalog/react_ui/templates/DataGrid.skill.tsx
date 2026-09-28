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
import { ExportToolbar } from '../components/ExportToolbar'
import { Card, SearchBar, Dropdown, Button, Badge, ProgressBar, DataTable, Pagination } from 'mobility-global-ds'
import { fetchTableRows } from '../hooks/useApi'

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

function renderCell(value: any, col: ColumnDef): React.ReactNode {
  if (value == null || value === '') return <span style={{ color: '#9CA3AF' }}>—</span>

  switch (col.type) {
    case 'badge': {
      const variant = safeVariant(col.badgeColors?.[String(value)])
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
      const v = Number(value)
      const max = col.progressMax ?? 100
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ flex: 1, minWidth: 60 }}>
            <ProgressBar value={v} max={max} />
          </div>
          <span style={{ fontSize: 11, color: '#6B7280', minWidth: 28, textAlign: 'right' }}>
            {v.toFixed(1)}
          </span>
        </div>
      )
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
    fetchTableRows(tableName, { limit: 1000 })
      .then(rows => { setApiData(rows); setApiLoading(false) })
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

  // ── Styles (page-level chrome only; generic UI now comes from mobility-global-ds) ──
  const s = {
    page:    { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 24, minHeight: '100%', background: '#F8FAFC' },
    heading: { fontSize: 28, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    sub:     { fontSize: 14, color: '#6B7280', marginTop: 4 },
    bar:     { display: 'flex', flexWrap: 'wrap' as const, gap: 10, alignItems: 'flex-end' },
  }

  const arrow = (key: string) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''

  if (apiLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  const dataTableColumns = columns.map((col: ColumnDef) => ({
    key: col.key,
    header: (
      <span style={{ cursor: 'pointer', userSelect: 'none' }} onClick={() => handleSort(col.key)}>
        {col.header}{arrow(col.key)}
      </span>
    ),
    align: col.align === 'right' ? 'right' : 'left',
    render: (value: any) => renderCell(value, col),
  }))

  return (
    <div style={s.page}>
      {/* Header */}
      <div>
        <h1 style={s.heading}>{pageTitle}</h1>
        {pageSubtitle && <p style={s.sub}>{pageSubtitle}</p>}
      </div>

      {/* Filter bar */}
      <Card>
        <div style={s.bar}>
          <SearchBar
            placeholder={`Search ${(searchFields ?? []).join(', ')}…`}
            value={search}
            onChange={(val) => { setSearch(val); setPage(1) }}
          />
          {(filterDefs ?? []).map(f => (
            <Dropdown
              key={f.field}
              label={f.label}
              options={[{ value: 'All', label: 'All' }, ...f.options.map(o => ({ value: o, label: o }))]}
              value={filterValues[f.field] ?? 'All'}
              onChange={(val) => { setFilterValues(prev => ({ ...prev, [f.field]: val })); setPage(1) }}
            />
          ))}
          <Button variant="secondary" onClick={reset}>Reset</Button>
          <Badge label={`${sorted.length.toLocaleString()} rows`} variant="info" />
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            <Button variant="secondary" onClick={() => exportCSV(sorted, columns, csvFilename ?? 'export.csv')}>
              CSV
            </Button>
            <ExportToolbar
              data={sorted}
              columns={columns.map((c: any) => ({ key: c.key, header: c.header, format: c.type }))}
              title={pageTitle ?? 'Data'}
              filename={csvFilename?.replace('.csv', '') ?? 'export'}
            />
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card>
        <DataTable
          columns={dataTableColumns}
          rows={pageRows}
          emptyMessage="No records match your filters."
        />

        {/* Pagination */}
        {pageCount > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, paddingTop: 12, borderTop: '1px solid #F1F5F9' }}>
            <span style={{ fontSize: 12, color: '#9CA3AF' }}>
              Showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, sorted.length)} of {sorted.length}
            </span>
            <Pagination total={sorted.length} page={safePage} pageSize={PAGE_SIZE} onChange={setPage} />
          </div>
        )}
      </Card>
    </div>
  )
}
export { DataGridPage as DataGrid }
