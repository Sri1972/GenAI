// @ts-nocheck
/**
 * PdfExport.skill.tsx — Generic multi-section PDF export page.
 *
 * Domain-agnostic — reads config from src/config/PdfExport.config.ts
 * Uses jsPDF + jspdf-autotable for real, searchable PDF output.
 * Works for any app that needs printable reports with tables.
 */
import { useState, useEffect } from 'react'
import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'
import { config } from '../config/PdfExport.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ]
}

export default function PdfExportPage() {
  const {
    pageTitle, reportTitle, subtitle, author,
    filenamePrefix, sections, theme = 'striped',
    accentColor = '#0064D2',
  } = config as any

  const [generating, setGenerating] = useState(false)
  const [done,       setDone]       = useState(false)
  const [preview,    setPreview]    = useState<string | null>((sections as any[])[0]?.title ?? null)
  const [sectionData, setSectionData] = useState<Record<string, any[]>>({})
  const [loading, setLoading]         = useState(false)

  useEffect(() => {
    const toFetch = (sections as any[]).filter((s: any) => s.tableName && !s.dataExport)
    if (!toFetch.length) return
    setLoading(true)
    Promise.all(toFetch.map((s: any) =>
      fetch(`${_API}/api/data/${s.tableName}?limit=5000`).then(r => r.json()).then(j => ({ title: s.title, data: j.data || [] }))
    )).then(results => {
      const map: Record<string, any[]> = {}
      for (const r of results) map[r.title] = r.data
      setSectionData(map)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const getRows = (sec: any): any[] => sectionData[sec.title] ?? sec.dataExport ?? []

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  const selectedSection = (sections as any[]).find((s: any) => s.title === preview) ?? (sections as any[])[0]
  const accent = hexToRgb(accentColor)
  const today  = new Date().toISOString().slice(0, 10)

  const generate = () => {
    setGenerating(true)
    setDone(false)
    try {
      const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
      const PW = doc.internal.pageSize.getWidth()

      // ── Cover page ───────────────────────────────────────────────────────────
      doc.setFillColor(...accent)
      doc.rect(0, 0, PW, 55, 'F')

      doc.setTextColor(255, 255, 255)
      doc.setFontSize(26)
      doc.setFont('helvetica', 'bold')
      doc.text(reportTitle ?? pageTitle ?? 'Report', 14, 30)

      if (subtitle) {
        doc.setFontSize(13)
        doc.setFont('helvetica', 'normal')
        doc.text(subtitle, 14, 42)
      }

      doc.setTextColor(180, 180, 180)
      doc.setFontSize(9)
      doc.text(`${author ? `${author}  ·  ` : ''}${today}`, 14, 51)

      // Table of contents hint
      doc.setTextColor(60, 60, 60)
      doc.setFontSize(11)
      doc.setFont('helvetica', 'bold')
      doc.text('Contents', 14, 72)
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(10);
      (sections as any[]).forEach((sec: any, i: number) => {
        doc.text(`${i + 1}.  ${sec.title}`, 18, 82 + i * 8)
        if (sec.description) {
          doc.setTextColor(140, 140, 140)
          doc.setFontSize(8.5)
          doc.text(sec.description, 28, 87 + i * 8)
          doc.setTextColor(60, 60, 60)
          doc.setFontSize(10)
        }
      })

      // ── Data sections ────────────────────────────────────────────────────────
      for (const sec of sections as any[]) {
        doc.addPage()

        // Section header bar
        doc.setFillColor(...accent)
        doc.rect(0, 0, PW, 18, 'F')
        doc.setTextColor(255, 255, 255)
        doc.setFontSize(14)
        doc.setFont('helvetica', 'bold')
        doc.text(sec.title, 14, 12)

        if (sec.description) {
          doc.setTextColor(80, 80, 80)
          doc.setFontSize(9)
          doc.setFont('helvetica', 'italic')
          doc.text(sec.description, 14, 26)
        }

        const startY = sec.description ? 32 : 24
        const cols   = sec.columns as any[]
        const rows   = getRows(sec)

        autoTable(doc, {
          startY,
          head: [cols.map((c: any) => c.header)],
          body: rows.map((r: any) =>
            cols.map((c: any) => {
              const raw = r[c.key]
              if (c.format === 'currency' && typeof raw === 'number') return `$${Number(raw).toLocaleString()}`
              if (c.format === 'percent'  && typeof raw === 'number') return `${Number(raw).toFixed(1)}%`
              return raw ?? ''
            })
          ),
          theme: theme as any,
          headStyles: { fillColor: accent, textColor: [255, 255, 255], fontStyle: 'bold', fontSize: 9 },
          bodyStyles: { fontSize: 8.5, textColor: [50, 50, 50] },
          alternateRowStyles: theme === 'striped' ? { fillColor: [248, 250, 252] } : {},
          columnStyles: Object.fromEntries(
            cols.map((c: any, i: number) => [i, { cellWidth: c.pdfWidth ?? 'auto' }])
          ),
          margin: { left: 14, right: 14 },
          didDrawPage: (data: any) => {
            // Footer on each page
            const pageCount = (doc.internal as any).getNumberOfPages()
            doc.setFontSize(8)
            doc.setTextColor(160, 160, 160)
            doc.text(
              `${reportTitle ?? ''} — Page ${data.pageNumber}`,
              14,
              doc.internal.pageSize.getHeight() - 8
            )
          },
        })
      }

      doc.save(`${filenamePrefix ?? 'report'}-${today}.pdf`)
      setDone(true)
    } finally {
      setGenerating(false)
    }
  }

  const s = {
    page:   { padding: 24, display: 'flex', flexDirection: 'column', gap: 24, background: '#F8FAFC', minHeight: '100%' },
    card:   { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    h1:     { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    tab:    (active: boolean) => ({
      padding: '8px 16px', borderRadius: 8, cursor: 'pointer', fontSize: 13, fontWeight: 600,
      background: active ? accentColor : '#fff',
      color:      active ? '#fff'      : '#374151',
      border:     active ? 'none'      : '1px solid #D1D5DB',
    }),
    th:     { padding: '9px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', borderBottom: '2px solid #E5E7EB', whiteSpace: 'nowrap' },
    td:     { padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', whiteSpace: 'nowrap' },
    pdfBtn: (disabled: boolean) => ({
      height: 48, padding: '0 28px', borderRadius: 10, border: 'none',
      background: disabled ? '#9CA3AF' : '#DC2626',
      color: '#fff', fontSize: 15, fontWeight: 700,
      cursor: disabled ? 'not-allowed' : 'pointer',
      display: 'flex', alignItems: 'center', gap: 8,
    }),
  }

  const totalRows = (sections as any[]).reduce((n: number, s: any) => n + getRows(s).length, 0)

  return (
    <div style={s.page}>
      <div>
        <h1 style={s.h1}>{pageTitle ?? 'Export PDF Report'}</h1>
        <p style={{ margin: '4px 0 0', fontSize: 14, color: '#6B7280' }}>
          Generate a structured PDF report with cover page and data tables
        </p>
      </div>

      {/* Section summary cards */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {(sections as any[]).map((sec: any) => (
          <div
            key={sec.title}
            style={{ flex: '1 1 180px', background: '#fff', borderRadius: 10, border: `2px solid ${preview === sec.title ? accentColor : '#E5E7EB'}`, padding: '14px 18px', cursor: 'pointer', transition: 'all 0.15s' }}
            onClick={() => setPreview(sec.title)}
          >
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1B2A' }}>{sec.title}</div>
            {sec.description && <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{sec.description}</div>}
            <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 6 }}>
              {(getRows(sec)).length.toLocaleString()} rows · {(sec.columns as any[]).length} cols
            </div>
          </div>
        ))}
      </div>

      {/* Preview table */}
      {selectedSection && (
        <div style={s.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#374151' }}>
              Preview — {selectedSection.title}
              <span style={{ marginLeft: 8, fontSize: 12, fontWeight: 400, color: '#9CA3AF' }}>first 10 rows</span>
            </h3>
            <div style={{ display: 'flex', gap: 6 }}>
              {(sections as any[]).map((sec: any) => (
                <button key={sec.title} style={s.tab(preview === sec.title)} onClick={() => setPreview(sec.title)}>
                  {sec.title}
                </button>
              ))}
            </div>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {(selectedSection.columns as any[]).map((c: any) => (
                    <th key={c.key} style={s.th}>{c.header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {getRows(selectedSection).slice(0, 10).map((row: any, i: number) => (
                  <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#FAFAFA' }}>
                    {(selectedSection.columns as any[]).map((c: any) => (
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

      {/* PDF options summary */}
      <div style={s.card}>
        <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#374151' }}>Report Settings</h3>
        <div style={{ display: 'flex', gap: 32, flexWrap: 'wrap' }}>
          <div><span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700 }}>Title</span><div style={{ fontSize: 14, color: '#374151', marginTop: 4 }}>{reportTitle ?? pageTitle}</div></div>
          {subtitle && <div><span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700 }}>Subtitle</span><div style={{ fontSize: 14, color: '#374151', marginTop: 4 }}>{subtitle}</div></div>}
          {author && <div><span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700 }}>Author</span><div style={{ fontSize: 14, color: '#374151', marginTop: 4 }}>{author}</div></div>}
          <div><span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700 }}>Sections</span><div style={{ fontSize: 14, color: '#374151', marginTop: 4 }}>{(sections as any[]).length} + cover page</div></div>
          <div><span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700 }}>Total Rows</span><div style={{ fontSize: 14, color: '#374151', marginTop: 4 }}>{totalRows.toLocaleString()}</div></div>
          <div><span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700 }}>Table Style</span><div style={{ fontSize: 14, color: '#374151', marginTop: 4, textTransform: 'capitalize' }}>{theme}</div></div>
          <div>
            <span style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 700 }}>Accent Colour</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <div style={{ width: 18, height: 18, borderRadius: 4, background: accentColor, border: '1px solid #E5E7EB' }} />
              <span style={{ fontSize: 14, color: '#374151' }}>{accentColor}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Download button */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <button style={s.pdfBtn(generating)} onClick={generate} disabled={generating}>
          {generating ? '⏳ Generating…' : '⬇ Download PDF'}
        </button>
        {done && <span style={{ color: '#059669', fontWeight: 600, fontSize: 14 }}>✓ Downloaded!</span>}
      </div>
      <p style={{ fontSize: 12, color: '#9CA3AF', margin: 0 }}>
        Output: A4 portrait · {(sections as any[]).length + 1} page{(sections as any[]).length !== 0 ? 's' : ''} minimum · searchable text
      </p>
    </div>
  )
}
