// @ts-nocheck
/**
 * ExcelExport.skill.tsx — Generic Excel / multi-CSV export page.
 *
 * Domain-agnostic — reads config from src/config/ExcelExport.config.ts
 * Uses SheetJS (xlsx) to create a real .xlsx file with multiple sheets.
 * Works for any app that needs spreadsheet export.
 */
import { useState, useEffect } from 'react'
import * as XLSX from 'xlsx'
import { config } from '../config/ExcelExport.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

export default function ExcelExportPage() {
  const { pageTitle, sheets, filename } = config as any

  const [generating, setGenerating] = useState(false)
  const [done,       setDone]       = useState(false)
  const [preview,    setPreview]    = useState<string | null>(sheets[0]?.name ?? null)
  const [sheetData, setSheetData]   = useState<Record<string, any[]>>({})
  const [loading, setLoading]       = useState(false)

  useEffect(() => {
    const toFetch = (sheets as any[]).filter((s: any) => s.tableName && !s.dataExport)
    if (!toFetch.length) return
    setLoading(true)
    Promise.all(toFetch.map((s: any) =>
      fetch(`${_API}/api/data/${s.tableName}?limit=5000`).then(r => r.json()).then(j => ({ name: s.name, data: j.data || [] }))
    )).then(results => {
      const map: Record<string, any[]> = {}
      for (const r of results) map[r.name] = r.data
      setSheetData(map)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const getRows = (sheet: any): any[] => sheetData[sheet.name] ?? sheet.dataExport ?? []

  const selectedSheet = sheets.find((s: any) => s.name === preview) ?? sheets[0]

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  const generate = () => {
    setGenerating(true)
    setDone(false)
    try {
      const wb = XLSX.utils.book_new()
      for (const sheet of sheets as any[]) {
        const rows = getRows(sheet)
        const cols = sheet.columns  as any[]
        // Header row
        const header = cols.map((c: any) => c.header)
        // Data rows — apply optional formatter
        const data = rows.map((r: any) =>
          cols.map((c: any) => {
            const raw = r[c.key]
            if (c.format === 'currency' && typeof raw === 'number') return raw  // keep numeric
            if (c.format === 'percent' && typeof raw === 'number') return raw / 100
            return raw ?? ''
          })
        )
        const ws = XLSX.utils.aoa_to_sheet([header, ...data])
        // Column widths
        ws['!cols'] = cols.map((c: any) => ({ wch: c.width ?? Math.max(c.header.length + 2, 12) }))
        XLSX.utils.book_append_sheet(wb, ws, sheet.name.slice(0, 31))
      }
      const today = new Date().toISOString().slice(0, 10)
      XLSX.writeFile(wb, `${filename ?? 'export'}-${today}.xlsx`)
      setDone(true)
    } finally {
      setGenerating(false)
    }
  }

  const exportSheetCSV = (sheet: any) => {
    const cols = sheet.columns as any[]
    const rows = getRows(sheet)
    const header = cols.map((c: any) => c.header).join(',')
    const lines  = rows.map((r: any) =>
      cols.map((c: any) => {
        const v = String(r[c.key] ?? '')
        return /[,"\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v
      }).join(',')
    )
    const csv  = [header, ...lines].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const a    = document.createElement('a')
    a.href     = URL.createObjectURL(blob)
    a.download = `${sheet.name}-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const s = {
    page:   { padding: 24, display: 'flex', flexDirection: 'column', gap: 24, background: '#F8FAFC', minHeight: '100%' },
    card:   { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    h1:     { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    tab:    (active: boolean) => ({
      padding: '8px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600,
      background: active ? '#0064D2' : '#fff',
      color:      active ? '#fff'    : '#374151',
      border:     active ? 'none'    : '1px solid #D1D5DB',
    }),
    th:     { padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', borderBottom: '2px solid #E5E7EB', whiteSpace: 'nowrap' },
    td:     { padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', whiteSpace: 'nowrap' },
    exlBtn: (disabled: boolean) => ({
      height: 48, padding: '0 28px', borderRadius: 10, border: 'none',
      background: disabled ? '#9CA3AF' : '#059669',
      color: '#fff', fontSize: 15, fontWeight: 700,
      cursor: disabled ? 'not-allowed' : 'pointer',
      display: 'flex', alignItems: 'center', gap: 8,
    }),
    csvBtn: { height: 36, padding: '0 14px', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', fontSize: 13, cursor: 'pointer', color: '#374151' },
  }

  return (
    <div style={s.page}>
      <div>
        <h1 style={s.h1}>{pageTitle ?? 'Export Data'}</h1>
        <p style={{ margin: '4px 0 0', fontSize: 14, color: '#6B7280' }}>
          Download as a multi-sheet Excel workbook or individual CSV files
        </p>
      </div>

      {/* Sheet overview cards */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {(sheets as any[]).map((sh: any) => (
          <div
            key={sh.name}
            style={{ flex: '1 1 180px', background: '#fff', borderRadius: 10, border: `2px solid ${preview === sh.name ? '#0064D2' : '#E5E7EB'}`, padding: '14px 18px', cursor: 'pointer', transition: 'all 0.15s' }}
            onClick={() => setPreview(sh.name)}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1B2A' }}>{sh.name}</div>
            <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>{getRows(sh).length.toLocaleString()} rows · {(sh.columns as any[]).length} cols</div>
            <div style={{ marginTop: 10 }}>
              <button style={s.csvBtn} onClick={e => { e.stopPropagation(); exportSheetCSV(sh) }}>CSV ↓</button>
            </div>
          </div>
        ))}
      </div>

      {/* Preview table */}
      {selectedSheet && (
        <div style={s.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#374151' }}>
              Preview — {selectedSheet.name}
              <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 400, color: '#9CA3AF' }}>first 10 rows</span>
            </h3>
            <div style={{ display: 'flex', gap: 6 }}>
              {(sheets as any[]).map((sh: any) => (
                <button key={sh.name} style={s.tab(preview === sh.name)} onClick={() => setPreview(sh.name)}>{sh.name}</button>
              ))}
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {(selectedSheet.columns as any[]).map((c: any) => (
                    <th key={c.key} style={s.th}>{c.header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {getRows(selectedSheet).slice(0, 10).map((row: any, i: number) => (
                  <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#FAFAFA' }}>
                    {(selectedSheet.columns as any[]).map((c: any) => (
                      <td key={c.key} style={s.td}>
                        {c.format === 'currency' && typeof row[c.key] === 'number'
                          ? `$${Number(row[c.key]).toLocaleString()}`
                          : c.format === 'percent' && typeof row[c.key] === 'number'
                          ? `${Number(row[c.key]).toFixed(1)}%`
                          : String(row[c.key] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Generate button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <button style={s.exlBtn(generating)} onClick={generate} disabled={generating}>
          {generating ? '⏳ Generating…' : '⬇ Download Excel (.xlsx)'}
        </button>
        {done && <span style={{ color: '#059669', fontWeight: 600, fontSize: 14 }}>✓ Downloaded!</span>}
      </div>
      <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>
        All {(sheets as any[]).reduce((s: number, sh: any) => s + getRows(sh).length, 0).toLocaleString()} rows across {(sheets as any[]).length} sheet{(sheets as any[]).length !== 1 ? 's' : ''} will be included in the workbook.
      </p>
    </div>
  )
}
