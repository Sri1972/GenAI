// @ts-nocheck
/**
 * ExportToolbar — Shared export utility component.
 * Renders "Excel ↓" and "PDF ↓" buttons that export any data array.
 * Auto-included in every generated app. Any page/skill can import and use it.
 *
 * Usage:
 *   import { ExportToolbar } from '../components/ExportToolbar'
 *   <ExportToolbar
 *     data={rows}
 *     columns={[{key:'name', header:'Name'}, {key:'revenue', header:'Revenue', format:'currency'}]}
 *     title="My Report"
 *     filename="my-report"
 *   />
 */
import { useState } from 'react'

interface Column {
  key: string
  header: string
  format?: 'text' | 'number' | 'currency' | 'percent' | 'date'
}

interface ExportToolbarProps {
  data: any[]
  columns: Column[]
  title?: string
  filename?: string
  accentColor?: string
}

function formatCell(value: any, format?: string): string {
  if (value == null) return ''
  if (format === 'currency' && typeof value === 'number') return `$${value.toLocaleString()}`
  if (format === 'percent' && typeof value === 'number') return `${value.toFixed(1)}%`
  if (format === 'number' && typeof value === 'number') return value.toLocaleString()
  return String(value)
}

export function ExportToolbar({ data, columns, title = 'Export', filename = 'export', accentColor = '#0064D2' }: ExportToolbarProps) {
  const [exporting, setExporting] = useState<string | null>(null)
  const today = new Date().toISOString().slice(0, 10)

  const exportExcel = async () => {
    setExporting('excel')
    try {
      const XLSX = await import('xlsx')
      const header = columns.map(c => c.header)
      const rows = data.map(row =>
        columns.map(c => {
          const raw = row[c.key]
          if (c.format === 'percent' && typeof raw === 'number') return raw / 100
          return raw ?? ''
        })
      )
      const ws = XLSX.utils.aoa_to_sheet([header, ...rows])
      ws['!cols'] = columns.map(c => ({ wch: Math.max(c.header.length + 2, 14) }))
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, title.slice(0, 31))
      XLSX.writeFile(wb, `${filename}-${today}.xlsx`)
    } catch (e) {
      console.error('Excel export failed:', e)
      alert('Excel export is not available. The xlsx package may not be installed.')
    } finally {
      setExporting(null)
    }
  }

  const exportPdf = async () => {
    setExporting('pdf')
    try {
      const { default: jsPDF } = await import('jspdf')
      const { default: autoTable } = await import('jspdf-autotable')

      // Estimate required width from content to decide orientation
      const avgCharWidth = 2.1 // mm per character at fontSize 8.5
      const cellPadding = 6    // mm horizontal padding per cell
      const margins = 28       // left + right margins
      const estWidth = columns.reduce((sum, col) => {
        const headerLen = col.header.length
        const maxDataLen = data.slice(0, 20).reduce((mx, row) => {
          const val = formatCell(row[col.key], col.format)
          return Math.max(mx, val.length)
        }, 0)
        return sum + Math.max(headerLen, maxDataLen) * avgCharWidth + cellPadding
      }, 0) + margins
      const orientation = estWidth > 182 ? 'landscape' : 'portrait'

      const doc = new jsPDF({ orientation, unit: 'mm', format: 'a4' })
      const pw = doc.internal.pageSize.getWidth()

      const rgb = [
        parseInt(accentColor.slice(1, 3), 16),
        parseInt(accentColor.slice(3, 5), 16),
        parseInt(accentColor.slice(5, 7), 16),
      ] as [number, number, number]
      doc.setFillColor(...rgb)
      doc.rect(0, 0, pw, 18, 'F')
      doc.setTextColor(255, 255, 255)
      doc.setFontSize(14)
      doc.setFont('helvetica', 'bold')
      doc.text(title, 14, 12)

      doc.setTextColor(200, 200, 200)
      doc.setFontSize(9)
      doc.text(today, pw - 14 - doc.getTextWidth(today), 12)

      autoTable(doc, {
        startY: 24,
        head: [columns.map(c => c.header)],
        body: data.map(row => columns.map(c => formatCell(row[c.key], c.format))),
        theme: 'striped',
        headStyles: { fillColor: rgb, textColor: [255, 255, 255], fontStyle: 'bold', fontSize: 9 },
        bodyStyles: { fontSize: 8.5, textColor: [50, 50, 50] },
        alternateRowStyles: { fillColor: [248, 250, 252] },
        margin: { left: 14, right: 14 },
      })

      doc.save(`${filename}-${today}.pdf`)
    } catch (e) {
      console.error('PDF export failed:', e)
      alert('PDF export is not available. The jspdf package may not be installed.')
    } finally {
      setExporting(null)
    }
  }

  const btnStyle = {
    fontSize: 12,
    color: '#374151',
    background: '#fff',
    border: '1px solid #D1D5DB',
    borderRadius: 6,
    padding: '4px 10px',
    cursor: 'pointer',
    fontWeight: 500,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    opacity: exporting ? 0.6 : 1,
  }

  return (
    <div style={{ display: 'flex', gap: 8 }}>
      <button onClick={exportExcel} disabled={!!exporting} style={btnStyle}>
        {exporting === 'excel' ? '…' : 'Excel ↓'}
      </button>
      <button onClick={exportPdf} disabled={!!exporting} style={btnStyle}>
        {exporting === 'pdf' ? '…' : 'PDF ↓'}
      </button>
    </div>
  )
}

export default ExportToolbar
