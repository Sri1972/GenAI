// @ts-nocheck
/**
 * DataChat.skill.tsx — AI-powered chat interface for any data context.
 *
 * Connects to a local FastAPI backend at /api/chat and /api/ingest/* endpoints.
 * Supports structured data, documents, custom contexts, and file uploads (Excel/PDF).
 * Renders responses as text, inline D3 charts, or sortable tables.
 * Domain-agnostic — reads config from src/config/DataChat.config.ts
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import * as d3 from 'd3'
import { config } from '../config/DataChat.config'

// ── Types ────────────────────────────────────────────────────────────────────
interface Message {
  role: 'user' | 'assistant'
  content: string
  type?: 'text' | 'chart' | 'table'
  data?: any
}

interface ChartData {
  type: 'bar' | 'line' | 'donut' | 'scatter'
  title?: string
  data: any[]
  xKey: string
  yKeys: string[]
  colors?: string[]
}

// ── Body-appended tooltip (same pattern as Charts.skill) ─────────────────────
function makeTip() {
  return d3.select(document.body).append('div')
    .style('position', 'fixed').style('display', 'none')
    .style('background', 'rgba(15,23,42,0.92)').style('color', '#fff')
    .style('padding', '8px 12px').style('border-radius', '8px').style('font-size', '12px')
    .style('pointer-events', 'none').style('z-index', '99999').style('max-width', '260px')
    .style('box-shadow', '0 4px 16px rgba(0,0,0,0.25)').style('line-height', '1.5')
    .style('white-space', 'nowrap')
}

// ── Markdown-lite renderer ───────────────────────────────────────────────────
function renderMarkdown(text: string) {
  const lines = text.split('\n')
  const elements: any[] = []
  let inCode = false, codeBlock: string[] = []

  lines.forEach((line, i) => {
    if (line.startsWith('```')) {
      if (inCode) {
        elements.push(<pre key={i} style={{ background: '#1E293B', color: '#E2E8F0', padding: 12, borderRadius: 8, fontSize: 12, overflowX: 'auto', margin: '8px 0' }}>{codeBlock.join('\n')}</pre>)
        codeBlock = []
      }
      inCode = !inCode
      return
    }
    if (inCode) { codeBlock.push(line); return }
    if (line.startsWith('- ') || line.startsWith('* ')) {
      elements.push(<div key={i} style={{ paddingLeft: 16, position: 'relative', margin: '2px 0' }}><span style={{ position: 'absolute', left: 4 }}>•</span>{formatInline(line.slice(2))}</div>)
    } else if (line.trim() === '') {
      elements.push(<div key={i} style={{ height: 8 }} />)
    } else {
      elements.push(<div key={i} style={{ margin: '2px 0' }}>{formatInline(line)}</div>)
    }
  })
  return <>{elements}</>
}

function formatInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) => p.startsWith('**') && p.endsWith('**')
    ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>)
}

// ── Chart Response Component ─────────────────────────────────────────────────
function ChartResponse({ chartData, accent }: { chartData: ChartData; accent: string }) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current || !chartData?.data?.length) return
    const tip = makeTip()
    const W = ref.current.clientWidth || 400, H = 240
    const m = { top: 20, right: 20, bottom: 36, left: 48 }
    const iW = W - m.left - m.right, iH = H - m.top - m.bottom
    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)
    const colors = chartData.colors ?? [accent, ...d3.schemeTableau10]
    const { type, data, xKey, yKeys } = chartData

    if (type === 'bar') {
      const x = d3.scaleBand().domain(data.map(d => String(d[xKey]))).range([0, iW]).padding(0.25)
      const y = d3.scaleLinear().domain([0, d3.max(data, d => Math.max(...yKeys.map(k => +d[k]))) * 1.1]).range([iH, 0])
      g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).tickSize(0)).select('.domain').remove()
      g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW)).select('.domain').remove()
      g.selectAll('.tick line').attr('stroke', '#E2E8F0')
      yKeys.forEach((key, ki) => {
        g.selectAll(`.bar-${ki}`).data(data).join('rect').attr('class', `bar-${ki}`)
          .attr('x', d => x(String(d[xKey]))! + (x.bandwidth() / yKeys.length) * ki)
          .attr('width', x.bandwidth() / yKeys.length).attr('y', d => y(+d[key]))
          .attr('height', d => iH - y(+d[key])).attr('fill', colors[ki % colors.length]).attr('rx', 3)
          .on('mouseenter', (e, d) => tip.style('display', 'block').html(`<b>${d[xKey]}</b><br/>${key}: ${d3.format(',.1f')(+d[key])}`))
          .on('mousemove', e => tip.style('left', e.clientX + 12 + 'px').style('top', e.clientY - 20 + 'px'))
          .on('mouseleave', () => tip.style('display', 'none'))
      })
    } else if (type === 'line') {
      const x = d3.scalePoint().domain(data.map(d => String(d[xKey]))).range([0, iW]).padding(0.3)
      const y = d3.scaleLinear().domain([0, d3.max(data, d => Math.max(...yKeys.map(k => +d[k]))) * 1.1]).range([iH, 0])
      g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).tickSize(0)).select('.domain').remove()
      g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW)).select('.domain').remove()
      g.selectAll('.tick line').attr('stroke', '#E2E8F0')
      yKeys.forEach((key, ki) => {
        const line = d3.line<any>().x(d => x(String(d[xKey]))!).y(d => y(+d[key])).curve(d3.curveMonotoneX)
        g.append('path').datum(data).attr('d', line).attr('fill', 'none').attr('stroke', colors[ki % colors.length]).attr('stroke-width', 2.5)
        g.selectAll(`.dot-${ki}`).data(data).join('circle').attr('class', `dot-${ki}`)
          .attr('cx', d => x(String(d[xKey]))!).attr('cy', d => y(+d[key])).attr('r', 4)
          .attr('fill', colors[ki % colors.length]).attr('stroke', '#fff').attr('stroke-width', 2)
          .on('mouseenter', (e, d) => tip.style('display', 'block').html(`<b>${d[xKey]}</b><br/>${key}: ${d3.format(',.1f')(+d[key])}`))
          .on('mousemove', e => tip.style('left', e.clientX + 12 + 'px').style('top', e.clientY - 20 + 'px'))
          .on('mouseleave', () => tip.style('display', 'none'))
      })
    } else if (type === 'donut') {
      const radius = Math.min(iW, iH) / 2
      const arc = d3.arc<any>().innerRadius(radius * 0.55).outerRadius(radius)
      const pie = d3.pie<any>().value(d => +d[yKeys[0]]).sort(null)
      const cg = g.append('g').attr('transform', `translate(${iW / 2},${iH / 2})`)
      cg.selectAll('path').data(pie(data)).join('path')
        .attr('d', arc).attr('fill', (_, i) => colors[i % colors.length]).attr('stroke', '#fff').attr('stroke-width', 2)
        .on('mouseenter', (e, d) => tip.style('display', 'block').html(`<b>${d.data[xKey]}</b><br/>${d3.format(',.1f')(d.data[yKeys[0]])}`))
        .on('mousemove', e => tip.style('left', e.clientX + 12 + 'px').style('top', e.clientY - 20 + 'px'))
        .on('mouseleave', () => tip.style('display', 'none'))
    } else if (type === 'scatter') {
      const x = d3.scaleLinear().domain(d3.extent(data, d => +d[xKey]) as [number, number]).nice().range([0, iW])
      const y = d3.scaleLinear().domain(d3.extent(data, d => +d[yKeys[0]]) as [number, number]).nice().range([iH, 0])
      g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).ticks(6)).select('.domain').remove()
      g.append('g').call(d3.axisLeft(y).ticks(6).tickSize(-iW)).select('.domain').remove()
      g.selectAll('.tick line').attr('stroke', '#E2E8F0')
      g.selectAll('circle').data(data).join('circle')
        .attr('cx', d => x(+d[xKey])).attr('cy', d => y(+d[yKeys[0]])).attr('r', 5)
        .attr('fill', colors[0]).attr('opacity', 0.7).attr('stroke', '#fff').attr('stroke-width', 1)
        .on('mouseenter', (e, d) => tip.style('display', 'block').html(`${xKey}: ${d3.format(',.1f')(+d[xKey])}<br/>${yKeys[0]}: ${d3.format(',.1f')(+d[yKeys[0]])}`))
        .on('mousemove', e => tip.style('left', e.clientX + 12 + 'px').style('top', e.clientY - 20 + 'px'))
        .on('mouseleave', () => tip.style('display', 'none'))
    }

    if (chartData.title) svg.append('text').attr('x', W / 2).attr('y', 14).attr('text-anchor', 'middle').attr('font-size', 13).attr('font-weight', 600).attr('fill', '#334155').text(chartData.title)
    return () => { tip.remove() }
  }, [chartData, accent])

  return <svg ref={ref} style={{ width: '100%', height: 240 }} />
}

// ── Table Response Component ─────────────────────────────────────────────────
function TableResponse({ rows }: { rows: any[] }) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortAsc, setSortAsc] = useState(true)
  if (!rows?.length) return null
  const cols = Object.keys(rows[0])
  const sorted = sortKey ? [...rows].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey]
    const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sortAsc ? cmp : -cmp
  }) : rows
  const display = sorted.slice(0, 20)
  const isNum = (v: any) => typeof v === 'number' || (!isNaN(v) && v !== '')

  return (
    <div style={{ overflowX: 'auto', maxHeight: 320, border: '1px solid #E2E8F0', borderRadius: 8, marginTop: 8 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>{cols.map(c => (
            <th key={c} onClick={() => { setSortKey(c); setSortAsc(sortKey === c ? !sortAsc : true) }}
              style={{ padding: '8px 10px', background: '#F8FAFC', borderBottom: '2px solid #E2E8F0', textAlign: 'left', cursor: 'pointer', whiteSpace: 'nowrap', fontWeight: 600, color: '#475569' }}>
              {c} {sortKey === c ? (sortAsc ? '↑' : '↓') : ''}
            </th>
          ))}</tr>
        </thead>
        <tbody>{display.map((row, ri) => (
          <tr key={ri} style={{ background: ri % 2 ? '#F8FAFC' : '#fff' }}>{cols.map(c => (
            <td key={c} style={{ padding: '6px 10px', borderBottom: '1px solid #F1F5F9', textAlign: isNum(row[c]) ? 'right' : 'left', whiteSpace: 'nowrap' }}>
              {isNum(row[c]) ? d3.format(',.2f')(+row[c]) : String(row[c] ?? '')}
            </td>
          ))}</tr>
        ))}</tbody>
      </table>
      {rows.length > 20 && <div style={{ padding: '6px 10px', fontSize: 11, color: '#94A3B8', textAlign: 'center' }}>Showing 20 of {rows.length} rows</div>}
    </div>
  )
}

// ── Upload Zone ──────────────────────────────────────────────────────────────
function UploadZone({ contextType, apiBaseUrl, onIngested }: { contextType: string; apiBaseUrl: string; onIngested: (ctx: any) => void }) {
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const accept = contextType === 'upload-excel' ? '.xlsx,.xls,.csv' : '.pdf'
  const label = contextType === 'upload-excel' ? 'Excel / CSV' : 'PDF'
  const endpoint = contextType === 'upload-excel' ? `${apiBaseUrl}/ingest/excel` : `${apiBaseUrl}/ingest/pdf`

  const upload = async (file: File) => {
    setProgress('Uploading...'); setError('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(endpoint, { method: 'POST', body: fd })
      if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`)
      setProgress('Parsing...')
      const data = await res.json()
      setProgress('Done')
      onIngested(data)
    } catch (e: any) { setError(e.message); setProgress('') }
  }

  const onDrop = (e: React.DragEvent) => { e.preventDefault(); setDragging(false); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]) }
  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => { if (e.target.files?.[0]) upload(e.target.files[0]) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, padding: 40 }}>
      <div onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{ width: '100%', maxWidth: 420, padding: '48px 32px', border: `2px dashed ${dragging ? '#3B82F6' : '#CBD5E1'}`, borderRadius: 16, textAlign: 'center', cursor: 'pointer', background: dragging ? '#EFF6FF' : '#FAFBFC', transition: 'all 0.2s' }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>+</div>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#334155' }}>Drop your {label} file here</div>
        <div style={{ fontSize: 13, color: '#64748B', marginTop: 6 }}>or click to browse</div>
        <input ref={inputRef} type="file" accept={accept} onChange={onPick} style={{ display: 'none' }} />
      </div>
      {progress && <div style={{ marginTop: 16, fontSize: 13, color: '#3B82F6', fontWeight: 500 }}>{progress}</div>}
      {error && <div style={{ marginTop: 16, fontSize: 13, color: '#EF4444' }}>{error}</div>}
    </div>
  )
}

// ── Typing Indicator ─────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div style={{ display: 'flex', gap: 4, padding: '12px 16px' }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{ width: 8, height: 8, borderRadius: '50%', background: '#94A3B8', animation: `dotPulse 1.2s ease-in-out ${i * 0.2}s infinite` }} />
      ))}
      <style>{`@keyframes dotPulse { 0%,80%,100% { opacity: 0.3; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1.1); } }`}</style>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────
export default function DataChatPage() {
  const { pageTitle, pageSubtitle, apiBaseUrl = '/api', accentColor, contextType, initialContext, suggestedPrompts, systemPromptOverride } = config

  const [messages, setMessages] = useState<Message[]>([])
  const [context, setContext] = useState<any>(initialContext)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [responseFormat, setResponseFormat] = useState<'auto' | 'text' | 'chart' | 'table'>('auto')
  const [ingested, setIngested] = useState(!contextType.startsWith('upload-'))
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  const contextLabel = contextType === 'upload-excel' ? 'Excel data' : contextType === 'upload-pdf' ? 'PDF loaded'
    : contextType === 'structured' ? 'Structured data' : contextType === 'document' ? 'Document' : 'Custom context'

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return
    const userMsg: Message = { role: 'user', content: text }
    const updated = [...messages, userMsg]
    setMessages(updated); setInput(''); setError(null); setLoading(true)

    try {
      const res = await fetch(`${apiBaseUrl}/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context, messages: updated, responseFormat }),
      })
      if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)
      const data = await res.json()
      const cleanText = (data.response || '').replace(/```(chart|table)\s*\n[\s\S]*?\n```/g, '').trim()
      const assistantMsg: Message = {
        role: 'assistant', content: cleanText || data.response || '',
        type: data.type ?? 'text', data: data.data ?? undefined,
      }
      setMessages(m => [...m, assistantMsg])
    } catch (e: any) {
      setError(e.message)
    } finally { setLoading(false) }
  }, [messages, context, responseFormat, loading, apiBaseUrl, systemPromptOverride])

  const retry = () => { if (messages.length) { const last = messages[messages.length - 1]; if (last.role === 'user') { setMessages(m => m.slice(0, -1)); sendMessage(last.content) } } }

  if (!ingested) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#F8FAFC' }}>
        <div style={{ padding: '16px 24px', borderBottom: '1px solid #E2E8F0', background: '#fff' }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#0F172A' }}>{pageTitle}</h1>
          {pageSubtitle && <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748B' }}>{pageSubtitle}</p>}
        </div>
        <UploadZone contextType={contextType} apiBaseUrl={apiBaseUrl} onIngested={(raw) => {
          let ctx: any
          if (contextType === 'upload-excel' && raw.sheets?.length) {
            const sheet = raw.sheets[0]
            ctx = { type: 'structured', schema: sheet.schema, sampleRows: sheet.sampleRows, metadata: { totalRows: sheet.totalRows, sheetName: sheet.name, sheetCount: raw.sheets.length } }
          } else if (contextType === 'upload-pdf') {
            ctx = { type: 'document', text: raw.text, metadata: raw.metadata }
          } else { ctx = { type: 'custom', text: JSON.stringify(raw).slice(0, 5000) } }
          setContext(ctx); setIngested(true)
        }} />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#F8FAFC', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
      {/* Top bar */}
      <div style={{ padding: '14px 24px', borderBottom: '1px solid #E2E8F0', background: '#fff', display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#0F172A' }}>{pageTitle}</h1>
          {pageSubtitle && <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748B' }}>{pageSubtitle}</p>}
        </div>
        <div style={{ padding: '4px 12px', borderRadius: 20, background: `${accentColor}18`, color: accentColor, fontSize: 12, fontWeight: 600 }}>
          Connected to: {contextLabel}
        </div>
      </div>

      {/* Chat area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 && suggestedPrompts?.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 40 }}>
            {suggestedPrompts.map((p, i) => (
              <button key={i} onClick={() => sendMessage(p)}
                style={{ padding: '8px 16px', borderRadius: 20, border: `1px solid ${accentColor}40`, background: '#fff', color: '#334155', fontSize: 13, cursor: 'pointer', transition: 'all 0.15s' }}
                onMouseEnter={e => { (e.target as any).style.background = `${accentColor}12` }}
                onMouseLeave={e => { (e.target as any).style.background = '#fff' }}>
                {p}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '100%' }}>
            <div style={{
              maxWidth: msg.type === 'chart' || msg.type === 'table' ? '90%' : '72%',
              padding: '10px 16px', borderRadius: 16,
              background: msg.role === 'user' ? accentColor : '#F1F5F9',
              color: msg.role === 'user' ? '#fff' : '#1E293B',
              fontSize: 14, lineHeight: 1.6,
              borderBottomRightRadius: msg.role === 'user' ? 4 : 16,
              borderBottomLeftRadius: msg.role === 'assistant' ? 4 : 16,
            }}>
              {msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}
              {msg.type === 'chart' && msg.data && <ChartResponse chartData={msg.data} accent={accentColor} />}
              {msg.type === 'table' && msg.data && <TableResponse rows={msg.data} />}
            </div>
          </div>
        ))}

        {loading && <div style={{ display: 'flex', justifyContent: 'flex-start' }}><div style={{ background: '#F1F5F9', borderRadius: 16, borderBottomLeftRadius: 4 }}><TypingDots /></div></div>}
        {error && (
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 12, padding: '10px 16px', fontSize: 13, color: '#DC2626', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span>{error}</span>
              <button onClick={retry} style={{ background: '#DC2626', color: '#fff', border: 'none', borderRadius: 6, padding: '4px 10px', fontSize: 12, cursor: 'pointer' }}>Retry</button>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div style={{ padding: '12px 24px 16px', borderTop: '1px solid #E2E8F0', background: '#fff' }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <select value={responseFormat} onChange={e => setResponseFormat(e.target.value as any)}
            style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid #E2E8F0', fontSize: 12, color: '#475569', background: '#F8FAFC', cursor: 'pointer' }}>
            <option value="auto">Auto</option>
            <option value="text">Text</option>
            <option value="chart">Chart</option>
            <option value="table">Table</option>
          </select>
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(input) } }}
            placeholder="Ask about your data..." disabled={loading}
            style={{ flex: 1, padding: '10px 16px', borderRadius: 12, border: '1px solid #E2E8F0', fontSize: 14, outline: 'none', transition: 'border 0.15s' }}
            onFocus={e => (e.target.style.borderColor = accentColor)} onBlur={e => (e.target.style.borderColor = '#E2E8F0')} />
          <button onClick={() => sendMessage(input)} disabled={loading || !input.trim()}
            style={{ padding: '10px 20px', borderRadius: 12, border: 'none', background: loading || !input.trim() ? '#CBD5E1' : accentColor, color: '#fff', fontWeight: 600, fontSize: 14, cursor: loading ? 'not-allowed' : 'pointer', transition: 'background 0.15s' }}>
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
