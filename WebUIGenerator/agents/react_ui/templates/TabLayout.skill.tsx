// @ts-nocheck
/**
 * TabLayout.skill.tsx — Tabbed page layout with composable sections.
 *
 * Domain-agnostic — reads config from src/config/TabLayout.config.ts
 * Each tab renders its sections[] array vertically. Supported section types:
 *   'chart' | 'table' | 'kpi-row' | 'cards' | 'text'
 */
import { useState, useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'
import { config } from '../config/TabLayout.config'

const _API = import.meta.env.VITE_API_BASE || ''

// ── Tooltip helper ───────────────────────────────────────────────────────────
function makeTip() {
  return d3.select(document.body).append('div')
    .style('position', 'fixed').style('display', 'none')
    .style('background', 'rgba(15,23,42,0.88)').style('color', '#fff')
    .style('padding', '7px 11px').style('border-radius', '8px').style('font-size', '12px')
    .style('pointer-events', 'none').style('z-index', '99999').style('max-width', '240px')
    .style('box-shadow', '0 4px 12px rgba(0,0,0,0.25)').style('line-height', '1.5')
}

// ── Number formatter ─────────────────────────────────────────────────────────
function safeFormat(fmt: any) {
  if (!fmt || typeof fmt !== 'string') return (v: any) => d3.format(',.0f')(Number(v) || 0)
  const lower = fmt.toLowerCase()
  if (lower === 'currency') return (v: any) => {
    const n = Number(v) || 0
    if (Math.abs(n) >= 1e9) return '$' + d3.format(',.1f')(n / 1e9) + 'B'
    if (Math.abs(n) >= 1e6) return '$' + d3.format(',.1f')(n / 1e6) + 'M'
    if (Math.abs(n) >= 1e3) return '$' + d3.format(',.1f')(n / 1e3) + 'K'
    return '$' + d3.format(',.0f')(n)
  }
  if (lower === 'compact' || lower === 'number') return (v: any) => {
    const n = Number(v) || 0
    if (Math.abs(n) >= 1e9) return d3.format(',.1f')(n / 1e9) + 'B'
    if (Math.abs(n) >= 1e6) return d3.format(',.1f')(n / 1e6) + 'M'
    if (Math.abs(n) >= 1e3) return d3.format(',.1f')(n / 1e3) + 'K'
    return d3.format(',.0f')(n)
  }
  if (lower === 'percent') return (v: any) => `${(Number(v) || 0).toFixed(1)}%`
  try { return d3.format(fmt) } catch { return (v: any) => d3.format(',.0f')(Number(v) || 0) }
}

// ── Bar Chart ────────────────────────────────────────────────────────────────
function BarChart({ section }: { section: any }) {
  const ref = useRef<SVGSVGElement>(null)
  const fmt = useMemo(() => safeFormat(section?.valueFormat), [section?.valueFormat])
  useEffect(() => {
    if (!ref.current) return
    const raw = section?.data ?? []
    if (!raw.length) return
    const labelField = section?.xField || section?.labelField || 'label'
    const valueField = section?.valueField || 'value'
    const data = raw.map((d: any) => ({ label: String(d[labelField] ?? ''), value: Number(d[valueField] ?? 0) }))
    const tip = makeTip()
    const H = Math.max(200, data.length * 36 + 60)
    const W = ref.current.clientWidth || 400
    const m = { top: 10, right: 60, bottom: 30, left: 130 }
    const iW = W - m.left - m.right, iH = H - m.top - m.bottom
    const svg = d3.select(ref.current)
    svg.selectAll('*').remove()
    svg.attr('height', H)
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)
    const maxV = d3.max(data, (d: any) => d.value) ?? 1
    const x = d3.scaleLinear().domain([0, maxV]).range([0, iW])
    const y = d3.scaleBand().domain(data.map((d: any) => d.label)).range([0, iH]).padding(0.25)
    g.append('g').call(d3.axisLeft(y).tickSize(0)).select('.domain').remove()
    g.append('g').attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).ticks(4).tickFormat(fmt as any))
      .selectAll('text').attr('font-size', 10).attr('fill', '#9CA3AF')
    const barColor = section?.color || (config as any).accentColor || '#0064D2'
    g.selectAll('.bar').data(data).join('rect')
      .attr('class', 'bar').attr('x', 0)
      .attr('y', (d: any) => y(d.label)!).attr('height', y.bandwidth())
      .attr('fill', barColor).attr('rx', 4)
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('fill-opacity', 0.8)
        tip.style('display', 'block')
          .style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${d.label}</b><br/>${fmt(d.value)}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 1); tip.style('display', 'none') })
      .transition().duration(400).attr('width', (d: any) => x(d.value))
    g.selectAll('.lbl').data(data).join('text')
      .attr('class', 'lbl')
      .attr('x', (d: any) => x(d.value) + 6)
      .attr('y', (d: any) => y(d.label)! + y.bandwidth() / 2 + 4)
      .attr('font-size', 11).attr('fill', '#6B7280')
      .text((d: any) => fmt(d.value))
    return () => { tip.remove() }
  }, [section, fmt])
  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Line Chart ───────────────────────────────────────────────────────────────
function LineChart({ section }: { section: any }) {
  const ref = useRef<SVGSVGElement>(null)
  const fmt = useMemo(() => safeFormat(section?.yFormat ?? section?.valueFormat), [section?.yFormat, section?.valueFormat])
  useEffect(() => {
    if (!ref.current) return
    const xField = section?.xField || 'x'
    const series = section?.series ?? []
    const data = section?.data ?? []
    if (!data.length || !series.length) return
    const xLabels = data.map((d: any) => String(d[xField] ?? ''))
    const tip = makeTip()
    const W = ref.current.clientWidth || 400, H = 260
    const m = { top: 20, right: 20, bottom: 40, left: 55 }
    const iW = W - m.left - m.right, iH = H - m.top - m.bottom
    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)
    const allVals = series.flatMap((s: any) => data.map((d: any) => Number(d[s.field] ?? 0)))
    const x = d3.scalePoint().domain(xLabels).range([0, iW])
    const y = d3.scaleLinear().domain([0, d3.max(allVals) ?? 1]).nice().range([iH, 0])
    g.append('g').call(d3.axisLeft(y).ticks(4).tickSize(-iW).tickFormat(() => '')).select('.domain').remove()
    g.selectAll('.tick line').attr('stroke', '#F1F5F9').attr('stroke-dasharray', '2,2')
    g.append('g').call(d3.axisLeft(y).ticks(4).tickFormat(fmt as any)).select('.domain').remove()
      .selectAll('text').attr('font-size', 10).attr('fill', '#9CA3AF')
    g.append('g').attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).tickValues(
        xLabels.filter((_: any, i: number) => i % Math.ceil(xLabels.length / 6) === 0)
      ))
      .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')
    const line = d3.line<any>()
      .x((_: any, i: number) => x(xLabels[i])!)
      .y((d: any) => y(d))
      .curve(d3.curveMonotoneX)
    series.forEach((s: any) => {
      const vals = data.map((d: any) => Number(d[s.field] ?? 0))
      const color = s.color || (config as any).accentColor || '#0064D2'
      g.append('path').datum(vals)
        .attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2).attr('d', line as any)
      g.selectAll(null).data(vals).join('circle')
        .attr('cx', (_: any, i: number) => x(xLabels[i])!)
        .attr('cy', (v: any) => y(v)).attr('r', 3).attr('fill', color)
    })
    // Hover overlay
    svg.append('rect').attr('transform', `translate(${m.left},${m.top})`)
      .attr('width', iW).attr('height', iH).attr('fill', 'transparent')
      .on('mousemove', function(this: any, event: MouseEvent) {
        const svgRect = (ref.current as SVGSVGElement).getBoundingClientRect()
        const mx = event.clientX - svgRect.left - m.left
        const step = iW / Math.max(xLabels.length - 1, 1)
        const idx = Math.max(0, Math.min(xLabels.length - 1, Math.round(mx / step)))
        const lines = series.map((s: any) => {
          const v = Number(data[idx]?.[s.field] ?? 0)
          return `${s.label}: <b>${fmt(v)}</b>`
        })
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${xLabels[idx]}</b><br/>${lines.join('<br/>')}`)
      })
      .on('mouseleave', () => tip.style('display', 'none'))
    return () => { tip.remove() }
  }, [section, fmt])
  return <svg ref={ref} style={{ width: '100%', height: 260, display: 'block' }} />
}

// ── Donut Chart ──────────────────────────────────────────────────────────────
function DonutChart({ section }: { section: any }) {
  const ref = useRef<SVGSVGElement>(null)
  const fmt = useMemo(() => safeFormat(section?.valueFormat), [section?.valueFormat])
  useEffect(() => {
    if (!ref.current) return
    const labelField = section?.labelField || 'label'
    const valueField = section?.valueField || 'value'
    const raw = section?.data ?? []
    if (!raw.length) return
    const data = raw.map((d: any) => ({ label: String(d[labelField] ?? ''), value: Number(d[valueField] ?? 0), color: d.color }))
    const tip = makeTip()
    const W = 340, H = 260, R = 90, RI = 50
    const svg = d3.select(ref.current).attr('width', W).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${W / 2 - 40},${H / 2})`)
    const pie = d3.pie<any>().sort(null).value((d: any) => d.value)
    const arc = d3.arc<any>().outerRadius(R).innerRadius(RI)
    const arcHover = d3.arc<any>().outerRadius(R + 6).innerRadius(RI)
    const colors = data.every((d: any) => d.color) ? data.map((d: any) => d.color) : d3.schemeTableau10
    g.selectAll('.arc').data(pie(data)).join('g').attr('class', 'arc')
      .append('path')
      .attr('fill', (_: any, i: number) => (colors as any)[i % (colors as any).length])
      .attr('stroke', '#fff').attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('d', arcHover(d) as string)
        tip.style('display', 'block')
          .style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${d.data.label}</b><br/>${fmt(d.data.value)}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any, _: any, d: any) { d3.select(this).attr('d', arc(d) as string); tip.style('display', 'none') })
      .transition().duration(500)
      .attrTween('d', function(d: any) {
        const interp = d3.interpolate({ startAngle: 0, endAngle: 0 }, d)
        return (t: number) => arc(interp(t))!
      })
    const legend = svg.append('g').attr('transform', `translate(${W / 2 + 60},${H / 2 - data.length * 10})`)
    data.forEach((d: any, i: number) => {
      const row = legend.append('g').attr('transform', `translate(0,${i * 20})`)
      row.append('rect').attr('width', 10).attr('height', 10)
        .attr('fill', (colors as any)[i % (colors as any).length]).attr('rx', 2)
      row.append('text').attr('x', 14).attr('y', 9).attr('font-size', 10).attr('fill', '#6B7280').text(d.label)
    })
    return () => { tip.remove() }
  }, [section, fmt])
  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Area Chart ───────────────────────────────────────────────────────────────
function AreaChart({ section }: { section: any }) {
  const ref = useRef<SVGSVGElement>(null)
  const fmt = useMemo(() => safeFormat(section?.yFormat ?? section?.valueFormat), [section?.yFormat, section?.valueFormat])
  useEffect(() => {
    if (!ref.current) return
    const xField = section?.xField || 'x'
    const series = section?.series ?? []
    const data = section?.data ?? []
    if (!data.length || !series.length) return
    const xLabels = data.map((d: any) => String(d[xField] ?? ''))
    const tip = makeTip()
    const W = ref.current.clientWidth || 400, H = 260
    const m = { top: 20, right: 20, bottom: 40, left: 55 }
    const iW = W - m.left - m.right, iH = H - m.top - m.bottom
    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)
    const allVals = series.flatMap((s: any) => data.map((d: any) => Number(d[s.field] ?? 0)))
    const x = d3.scalePoint().domain(xLabels).range([0, iW])
    const y = d3.scaleLinear().domain([0, d3.max(allVals) ?? 1]).nice().range([iH, 0])
    g.append('g').call(d3.axisLeft(y).ticks(4).tickSize(-iW).tickFormat(() => '')).select('.domain').remove()
    g.selectAll('.tick line').attr('stroke', '#F1F5F9').attr('stroke-dasharray', '2,2')
    g.append('g').call(d3.axisLeft(y).ticks(4).tickFormat(fmt as any)).select('.domain').remove()
      .selectAll('text').attr('font-size', 10).attr('fill', '#9CA3AF')
    g.append('g').attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).tickValues(
        xLabels.filter((_: any, i: number) => i % Math.ceil(xLabels.length / 6) === 0)
      ))
      .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')
    const area = d3.area<any>()
      .x((_: any, i: number) => x(xLabels[i])!)
      .y0(iH)
      .y1((d: any) => y(d))
      .curve(d3.curveMonotoneX)
    const line = d3.line<any>()
      .x((_: any, i: number) => x(xLabels[i])!)
      .y((d: any) => y(d))
      .curve(d3.curveMonotoneX)
    series.forEach((s: any) => {
      const vals = data.map((d: any) => Number(d[s.field] ?? 0))
      const color = s.color || (config as any).accentColor || '#0064D2'
      g.append('path').datum(vals)
        .attr('fill', color).attr('fill-opacity', 0.15).attr('d', area as any)
      g.append('path').datum(vals)
        .attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2).attr('d', line as any)
    })
    // Hover overlay
    svg.append('rect').attr('transform', `translate(${m.left},${m.top})`)
      .attr('width', iW).attr('height', iH).attr('fill', 'transparent')
      .on('mousemove', function(this: any, event: MouseEvent) {
        const svgRect = (ref.current as SVGSVGElement).getBoundingClientRect()
        const mx = event.clientX - svgRect.left - m.left
        const step = iW / Math.max(xLabels.length - 1, 1)
        const idx = Math.max(0, Math.min(xLabels.length - 1, Math.round(mx / step)))
        const lines = series.map((s: any) => {
          const v = Number(data[idx]?.[s.field] ?? 0)
          return `${s.label}: <b>${fmt(v)}</b>`
        })
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${xLabels[idx]}</b><br/>${lines.join('<br/>')}`)
      })
      .on('mouseleave', () => tip.style('display', 'none'))
    return () => { tip.remove() }
  }, [section, fmt])
  return <svg ref={ref} style={{ width: '100%', height: 260, display: 'block' }} />
}

// ── Chart Section Dispatcher ─────────────────────────────────────────────────
function ChartSection({ section }: { section: any }) {
  const type = (section?.chartType ?? '').toLowerCase()
  if (type === 'bar') return <BarChart section={section} />
  if (type === 'line') return <LineChart section={section} />
  if (type === 'donut' || type === 'pie') return <DonutChart section={section} />
  if (type === 'area') return <AreaChart section={section} />
  // Fallback: guess from data shape
  if (section?.series) return <LineChart section={section} />
  if (section?.data) return <BarChart section={section} />
  return <div style={{ padding: 20, color: '#9CA3AF', fontSize: 13 }}>No chart data</div>
}

// ── Table Section ────────────────────────────────────────────────────────────
function TableSection({ section }: { section: any }) {
  const columns = section?.columns ?? []
  const data = section?.data ?? []
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const sorted = useMemo(() => {
    if (!sortKey) return data
    return [...data].sort((a: any, b: any) => {
      const av = a[sortKey], bv = b[sortKey]
      const numA = Number(av), numB = Number(bv)
      if (!isNaN(numA) && !isNaN(numB)) return sortDir === 'asc' ? numA - numB : numB - numA
      return sortDir === 'asc' ? String(av ?? '').localeCompare(String(bv ?? '')) : String(bv ?? '').localeCompare(String(av ?? ''))
    })
  }, [data, sortKey, sortDir])

  const handleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {columns.map((c: any) => (
              <th
                key={c.key}
                onClick={() => handleSort(c.key)}
                style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.04em', borderBottom: '2px solid #E5E7EB', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}
              >
                {c.header} {sortKey === c.key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row: any, i: number) => (
            <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#F9FAFB' }}>
              {columns.map((c: any) => (
                <td key={c.key} style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9' }}>
                  {String(row[c.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!sorted.length && <div style={{ padding: 20, textAlign: 'center', color: '#9CA3AF', fontSize: 13 }}>No data</div>}
    </div>
  )
}

// ── KPI Row Section ──────────────────────────────────────────────────────────
function KpiRowSection({ section }: { section: any }) {
  const kpis = section?.kpis ?? []
  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
      {kpis.map((k: any, i: number) => {
        const isUp = k.direction === 'up'
        const isDown = k.direction === 'down'
        const changeColor = isUp ? '#059669' : isDown ? '#DC2626' : '#6B7280'
        const changeBg = isUp ? '#D1FAE5' : isDown ? '#FEE2E2' : '#F3F4F6'
        return (
          <div key={i} style={{ flex: '1 1 160px', background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '16px 20px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{k.label}</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#0D1B2A', margin: '6px 0 4px' }}>{k.value}</div>
            {k.change && (
              <span style={{ display: 'inline-flex', padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: changeBg, color: changeColor }}>
                {isUp ? '▲' : isDown ? '▼' : '●'} {k.change}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Text Section ─────────────────────────────────────────────────────────────
function TextSection({ section }: { section: any }) {
  return (
    <div style={{ fontSize: 14, lineHeight: 1.7, color: '#374151' }}>
      {section?.content ?? ''}
    </div>
  )
}

// ── Cards Section ────────────────────────────────────────────────────────────
function CardsSection({ section }: { section: any }) {
  const data = section?.data ?? []
  const nameField = section?.nameField || 'name'
  const metrics = section?.metrics ?? []
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
      {data.map((item: any, i: number) => (
        <div key={i} style={{ background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '16px 20px' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0D1B2A', marginBottom: 8 }}>{item[nameField] ?? '—'}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {metrics.map((m: any, j: number) => (
              <div key={j} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                <span style={{ color: '#6B7280' }}>{m.label}</span>
                <span style={{ fontWeight: 600, color: '#374151' }}>{item[m.field] ?? '—'}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
      {!data.length && <div style={{ padding: 20, color: '#9CA3AF', fontSize: 13 }}>No cards data</div>}
    </div>
  )
}

// ── Section Renderer ─────────────────────────────────────────────────────────
function SectionRenderer({ section }: { section: any }) {
  const type = (section?.type ?? '').toLowerCase()
  switch (type) {
    case 'chart': return <ChartSection section={section} />
    case 'table': return <TableSection section={section} />
    case 'kpi-row': return <KpiRowSection section={section} />
    case 'text': return <TextSection section={section} />
    case 'cards': return <CardsSection section={section} />
    default: return <div style={{ padding: 12, color: '#9CA3AF', fontSize: 13 }}>Unknown section type: {type}</div>
  }
}

// ── Main TabLayout Page ──────────────────────────────────────────────────────
export function TabLayoutPage() {
  const { pageTitle, pageSubtitle, accentColor, tabs } = config as any
  const [activeTab, setActiveTab] = useState(0)
  const accent = accentColor || '#0064D2'

  const currentTab = (tabs ?? [])[activeTab]
  const sections = currentTab?.sections ?? []

  const styles = {
    page: { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
    header: { marginBottom: 4 },
    title: { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    subtitle: { fontSize: 14, color: '#6B7280', margin: '4px 0 0' },
    tabBar: { display: 'flex', gap: 0, borderBottom: '2px solid #E5E7EB', marginBottom: 4 },
    tab: (active: boolean) => ({
      padding: '10px 20px',
      fontSize: 14,
      fontWeight: active ? 700 : 500,
      color: active ? accent : '#6B7280',
      cursor: 'pointer',
      borderBottom: active ? `3px solid ${accent}` : '3px solid transparent',
      marginBottom: -2,
      transition: 'all 0.2s ease',
      background: 'none',
      border: 'none',
      borderBottomStyle: 'solid' as const,
      userSelect: 'none' as const,
    }),
    sectionCard: { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    sectionTitle: { fontSize: 14, fontWeight: 700, color: '#374151', margin: '0 0 14px' },
  }

  return (
    <div style={styles.page}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>{pageTitle}</h1>
        {pageSubtitle && <p style={styles.subtitle}>{pageSubtitle}</p>}
      </div>

      {/* Tab Bar */}
      <div style={styles.tabBar}>
        {(tabs ?? []).map((tab: any, i: number) => (
          <button
            key={i}
            style={styles.tab(i === activeTab)}
            onClick={() => setActiveTab(i)}
          >
            {tab.title}
          </button>
        ))}
      </div>

      {/* Tab Content — sections rendered vertically */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        {sections.map((section: any, i: number) => (
          <div key={`${activeTab}-${i}`} style={styles.sectionCard}>
            {section.title && <h3 style={styles.sectionTitle}>{section.title}</h3>}
            <SectionRenderer section={section} />
          </div>
        ))}
        {!sections.length && (
          <div style={{ ...styles.sectionCard, textAlign: 'center', color: '#9CA3AF', fontSize: 14, padding: 40 }}>
            No content configured for this tab.
          </div>
        )}
      </div>
    </div>
  )
}

export default TabLayoutPage
