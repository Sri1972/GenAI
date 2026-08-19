// @ts-nocheck
/**
 * PptxExport.skill.tsx — Generic PowerPoint export panel.
 *
 * Domain-agnostic — reads config from src/config/PptxExport.config.ts
 * Uses pptxgenjs to create a real downloadable .pptx file.
 * Works for any app that needs slide export.
 */
import { useState, useEffect } from 'react'
import pptxgen from 'pptxgenjs'
import { config } from '../config/PptxExport.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

export default function PptxExportPage() {
  const { pageTitle, slides, themes, dataMap, dataTableNames, filenamePrefix } = config as any

  const [selectedTheme, setSelectedTheme] = useState(themes[0]?.id ?? '')
  const [reportTitle,   setReportTitle]   = useState(pageTitle ?? 'Report')
  const [author,        setAuthor]        = useState('')
  const [generating,    setGenerating]    = useState(false)
  const [done,          setDone]          = useState(false)
  const [apiDataMap, setApiDataMap]       = useState<Record<string, any[]>>({})
  const [loading, setLoading]             = useState(false)

  useEffect(() => {
    if (!dataTableNames) return
    const entries = Object.entries(dataTableNames as Record<string, string>).filter(([, t]) => t)
    if (!entries.length) return
    setLoading(true)
    Promise.all(entries.map(([key, table]) =>
      fetch(`${_API}/api/data/${table}?limit=5000`).then(r => r.json()).then(j => ({ key, data: j.data || [] }))
    )).then(results => {
      const map: Record<string, any[]> = {}
      for (const r of results) map[r.key] = r.data
      setApiDataMap(map)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  const theme = themes.find((t: any) => t.id === selectedTheme) ?? themes[0]
  const today = new Date().toISOString().slice(0, 10)

  const generate = async () => {
    if (!theme) return
    setGenerating(true)
    setDone(false)

    try {
      const pptx = new pptxgen()
      pptx.author    = author || 'TurboUIGen'
      pptx.subject   = reportTitle
      pptx.company   = author || 'Generated Report'

      // Cover slide
      const cover = pptx.addSlide()
      cover.background = { color: theme.bg.replace('#', '') }
      cover.addText(reportTitle, {
        x: 0.5, y: 1.5, w: 9, h: 1.5,
        fontSize: 36, bold: true,
        color: theme.textColor.replace('#', ''),
      })
      cover.addText(`${author ? `Prepared by ${author} · ` : ''}${today}`, {
        x: 0.5, y: 3.5, w: 9, h: 0.6,
        fontSize: 14,
        color: theme.accent.replace('#', ''),
      })

      // Content slides
      for (const slideDef of slides as any[]) {
        const slide = pptx.addSlide()
        slide.background = { color: theme.bg.replace('#', '') }

        // Title bar
        slide.addShape(pptx.ShapeType.rect, {
          x: 0, y: 0, w: 10, h: 0.9,
          fill: { color: theme.accent.replace('#', '') },
        })
        slide.addText(slideDef.title, {
          x: 0.3, y: 0.1, w: 9.4, h: 0.7,
          fontSize: 20, bold: true,
          color: 'FFFFFF',
        })

        const rows: any[] = apiDataMap[slideDef.dataKey] ?? (dataMap as any)?.[slideDef.dataKey] ?? []
        const bullets: string[] = rows.slice(0, 8).map(slideDef.bulletTemplate)

        if (bullets.length > 0) {
          slide.addText(
            bullets.map(b => ({ text: b, options: { bullet: true } })),
            {
              x: 0.5, y: 1.1, w: 9, h: 5.5,
              fontSize: 13,
              color: theme.textColor.replace('#', ''),
              lineSpacingMultiple: 1.3,
            }
          )
        } else {
          slide.addText('No data available for this slide.', {
            x: 0.5, y: 2.5, w: 9, h: 1,
            fontSize: 14, italic: true,
            color: '9CA3AF',
          })
        }

        // Slide description note
        if (slideDef.description) {
          slide.addText(slideDef.description, {
            x: 0.5, y: 6.8, w: 9, h: 0.5,
            fontSize: 10, italic: true,
            color: '9CA3AF',
          })
        }
      }

      await pptx.writeFile({ fileName: `${filenamePrefix ?? 'report'}-${today}.pptx` })
      setDone(true)
    } finally {
      setGenerating(false)
    }
  }

  const s = {
    page:    { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 24, background: '#F8FAFC', minHeight: '100%' },
    card:    { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    heading: { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    label:   { fontSize: 12, fontWeight: 600, color: '#374151', display: 'block', marginBottom: 6 },
    input:   { width: '100%', height: 40, padding: '0 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 14, outline: 'none', color: '#374151', boxSizing: 'border-box' as const },
    genBtn:  { height: 52, padding: '0 32px', borderRadius: 10, border: 'none', background: generating ? '#9CA3AF' : '#0064D2', color: '#fff', fontSize: 16, fontWeight: 700, cursor: generating ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 8 },
  }

  return (
    <div style={s.page}>
      <div>
        <h1 style={s.heading}>Export Report</h1>
        <p style={{ margin: '4px 0 0', fontSize: 14, color: '#6B7280' }}>Generate a PowerPoint presentation from your data</p>
      </div>

      {/* Theme selector */}
      <div style={s.card}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700, color: '#374151' }}>Choose a Theme</h3>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          {(themes as any[]).map((t: any) => (
            <div
              key={t.id}
              onClick={() => setSelectedTheme(t.id)}
              style={{
                width: 180, padding: 14, borderRadius: 10, cursor: 'pointer',
                border: `2px solid ${selectedTheme === t.id ? t.accent : '#E5E7EB'}`,
                background: selectedTheme === t.id ? `${t.accent}10` : '#fff',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                <div style={{ width: 20, height: 20, borderRadius: 4, background: t.bg, border: '1px solid #E5E7EB' }} />
                <div style={{ width: 20, height: 20, borderRadius: 4, background: t.accent }} />
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>{t.name}</div>
              {t.description && <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{t.description}</div>}
            </div>
          ))}
        </div>
      </div>

      {/* Slide list */}
      <div style={s.card}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700, color: '#374151' }}>Slides ({(slides as any[]).length + 1})</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 500, color: '#374151', borderBottom: '1px solid #F1F5F9' }}>1</td>
              <td style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', fontWeight: 600 }}>Cover Page</td>
              <td style={{ padding: '8px 12px', fontSize: 13, color: '#9CA3AF', borderBottom: '1px solid #F1F5F9' }}>Title + author + date</td>
            </tr>
            {(slides as any[]).map((sl: any, i: number) => (
              <tr key={sl.id}>
                <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 500, color: '#374151', borderBottom: '1px solid #F1F5F9' }}>{i + 2}</td>
                <td style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', fontWeight: 600 }}>{sl.title}</td>
                <td style={{ padding: '8px 12px', fontSize: 13, color: '#9CA3AF', borderBottom: '1px solid #F1F5F9' }}>{sl.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Customise */}
      <div style={s.card}>
        <h3 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 700, color: '#374151' }}>Customise</h3>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={s.label}>Report Title</label>
            <input style={s.input} value={reportTitle} onChange={e => setReportTitle(e.target.value)} />
          </div>
          <div style={{ flex: '1 1 200px' }}>
            <label style={s.label}>Author (optional)</label>
            <input style={s.input} value={author} onChange={e => setAuthor(e.target.value)} placeholder="Your name" />
          </div>
          <div style={{ flex: '0 1 140px' }}>
            <label style={s.label}>Date</label>
            <input style={{ ...s.input, background: '#F9FAFB', color: '#9CA3AF' }} value={today} readOnly />
          </div>
        </div>
      </div>

      {/* Generate */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <button style={s.genBtn} onClick={generate} disabled={generating}>
          {generating ? '⏳ Generating…' : '⬇ Generate & Download .pptx'}
        </button>
        {done && <span style={{ color: '#059669', fontWeight: 600, fontSize: 14 }}>✓ Downloaded!</span>}
      </div>
    </div>
  )
}
