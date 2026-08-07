// @ts-nocheck
/**
 * KpiDashboard.skill.tsx — Generic KPI dashboard page.
 *
 * Domain-agnostic — reads config from src/config/KpiDashboard.config.ts
 * Works for: executive dashboards, analytics overviews, performance scorecards.
 * Layout: KPI cards → two-chart row → optional summary table.
 */
import { useState, useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'
import { config } from '../config/KpiDashboard.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

const BADGE_STYLES: Record<string, {bg:string;color:string}> = {
  default: { bg: '#F3F4F6', color: '#374151' },
  success: { bg: '#D1FAE5', color: '#065F46' },
  warning: { bg: '#FEF3C7', color: '#92400E' },
  error:   { bg: '#FEE2E2', color: '#991B1B' },
  info:    { bg: '#DBEAFE', color: '#1E40AF' },
  accent:  { bg: '#EDE9FE', color: '#5B21B6' },
}

// Smart number formatter — handles named aliases + valid d3 format strings
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
  try { return d3.format(fmt) } catch { return (v: any) => d3.format(',.0f')(Number(v) || 0) }
}

// Body-appended tooltip — never clipped by overflow or transforms
function makeTip() {
  return d3.select(document.body).append('div')
    .style('position', 'fixed').style('display', 'none')
    .style('background', 'rgba(15,23,42,0.88)').style('color', '#fff')
    .style('padding', '7px 11px').style('border-radius', '8px').style('font-size', '12px')
    .style('pointer-events', 'none').style('z-index', '99999').style('max-width', '220px')
    .style('box-shadow', '0 4px 12px rgba(0,0,0,0.25)').style('line-height', '1.5')
}

// ── Bar Chart ─────────────────────────────────────────────────────────────────
function BarChart({ chart }: { chart: any }) {
  const ref = useRef<SVGSVGElement>(null)
  const fmt = useMemo(() => safeFormat(chart?.valueFormat), [chart?.valueFormat])
  useEffect(() => {
    if (!ref.current) return
    const raw = chart?.data ?? []
    if (!raw.length) return
    // Aggregate duplicate labels (e.g. multiple rows per region)
    const aggMap = new Map<string, any>()
    raw.forEach((d: any) => {
      const key = String(d.label)
      if (aggMap.has(key)) aggMap.get(key).value += Number(d.value)
      else aggMap.set(key, { ...d, value: Number(d.value) })
    })
    const data = Array.from(aggMap.values())
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
    g.selectAll('.bar').data(data).join('rect')
      .attr('class', 'bar').attr('x', 0)
      .attr('y', (d: any) => y(d.label)!).attr('height', y.bandwidth())
      .attr('fill', (d: any) => d.color ?? '#0064D2').attr('rx', 4)
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
  }, [chart, fmt])
  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Donut Chart ───────────────────────────────────────────────────────────────
function DonutChart({ chart }: { chart: any }) {
  const ref = useRef<SVGSVGElement>(null)
  const fmt = useMemo(() => safeFormat(chart?.valueFormat), [chart?.valueFormat])
  useEffect(() => {
    if (!ref.current) return
    const data = chart?.data ?? []
    if (!data.length) return
    const tip = makeTip()
    const W = 340, H = 260, R = 90, RI = 50
    const svg = d3.select(ref.current).attr('width', W).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${W / 2 - 40},${H / 2})`)
    const pie  = d3.pie<any>().sort(null).value((d: any) => d.value)
    const arc  = d3.arc<any>().outerRadius(R).innerRadius(RI)
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
  }, [chart, fmt])
  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Line Chart ────────────────────────────────────────────────────────────────
function LineChart({ chart }: { chart: any }) {
  const ref = useRef<SVGSVGElement>(null)
  const fmt = useMemo(() => safeFormat(chart?.yFormat ?? chart?.valueFormat), [chart?.yFormat, chart?.valueFormat])
  useEffect(() => {
    if (!ref.current) return
    const xLabels = chart?.xLabels ?? []
    const series  = chart?.series  ?? []
    if (!xLabels.length || !series.length) return
    const tip = makeTip()
    const W = ref.current.clientWidth || 400, H = 260
    const m = { top: 20, right: 20, bottom: 40, left: 55 }
    const iW = W - m.left - m.right, iH = H - m.top - m.bottom
    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)
    const allVals = series.flatMap((s: any) => s.values ?? []).filter((v: any) => v != null && !isNaN(v))
    const x = d3.scalePoint().domain(xLabels).range([0, iW])
    const y = d3.scaleLinear().domain([0, d3.max(allVals) ?? 1]).nice().range([iH, 0])
    g.append('g').call(d3.axisLeft(y).ticks(4).tickSize(-iW).tickFormat(() => '')).select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9').attr('stroke-dasharray', '2,2')
    g.append('g').call(d3.axisLeft(y).ticks(4).tickFormat(fmt as any)).select('.domain').remove()
      .selectAll('text').attr('font-size', 10).attr('fill', '#9CA3AF')
    g.append('g').attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).tickValues(
        xLabels.filter((_: any, i: number) => i % Math.ceil(xLabels.length / 6) === 0)
      ))
      .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')
    const line = d3.line<number>()
      .defined((v: any) => v != null && !isNaN(v))
      .x((_: any, i: number) => x(xLabels[i])!)
      .y((v: number) => y(v))
      .curve(d3.curveMonotoneX)
    series.forEach((s: any) => {
      const vals = s.values ?? []
      g.append('path').datum(vals)
        .attr('fill', 'none').attr('stroke', s.color ?? '#0064D2').attr('stroke-width', 2).attr('d', line as any)
      g.selectAll(null).data(vals.filter((v: any) => v != null && !isNaN(v)))
        .join('circle')
        .attr('cx', (_: any, i: number) => {
          const realIdx = vals.indexOf(vals.filter((v: any) => v != null && !isNaN(v))[i])
          return x(xLabels[realIdx])!
        })
        .attr('cy', (v: any) => y(v)).attr('r', 3).attr('fill', s.color ?? '#0064D2')
    })
    // Hover overlay using getBoundingClientRect for accurate x-position
    svg.append('rect').attr('transform', `translate(${m.left},${m.top})`)
      .attr('width', iW).attr('height', iH).attr('fill', 'transparent')
      .on('mousemove', function(this: any, event: MouseEvent) {
        const svgRect = (ref.current as SVGSVGElement).getBoundingClientRect()
        const mx   = event.clientX - svgRect.left - m.left
        const step = iW / Math.max(xLabels.length - 1, 1)
        const idx  = Math.max(0, Math.min(xLabels.length - 1, Math.round(mx / step)))
        const lines = series.map((s: any) => {
          const v = s.values?.[idx]
          return v != null ? `${s.label}: <b>${fmt(v)}</b>` : null
        }).filter(Boolean)
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${xLabels[idx]}</b><br/>${lines.join('<br/>')}`)
      })
      .on('mouseleave', () => tip.style('display', 'none'))
    return () => { tip.remove() }
  }, [chart, fmt])
  return <svg ref={ref} style={{ width: '100%', height: 260, display: 'block' }} />
}

// ── Universal chart slot — picks renderer by type ─────────────────────────────
function ChartSlot({ chart }: { chart: any }) {
  const type = (chart?.type ?? '').toLowerCase()
  if (type === 'bar')   return <BarChart   chart={chart} />
  if (type === 'donut') return <DonutChart chart={chart} />
  if (type === 'line')  return <LineChart  chart={chart} />
  // If type is missing or unrecognised, guess from data shape
  if (chart?.data && !chart?.xLabels)  return <BarChart chart={{ ...chart, type: 'bar' }} />
  if (chart?.xLabels && chart?.series) return <LineChart chart={{ ...chart, type: 'line' }} />
  return <div style={{ padding: 20, color: '#9CA3AF', fontSize: 13 }}>No chart data</div>
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function KpiDashboardPage() {
  const { pageTitle, kpiCards, chart1, chart2, tableName, tableColumns } = config as any

  const [chart1Data, setChart1Data] = useState<any[] | null>(chart1?.data ?? null)
  const [chart2Data, setChart2Data] = useState<any[] | null>(chart2?.data ?? null)
  const [tableRows, setTableRows]   = useState<any[] | null>(null)

  useEffect(() => {
    if (chart1?.tableName && !chart1Data) {
      fetch(`${_API}/api/data/${chart1.tableName}?limit=200`)
        .then(r => r.json())
        .then(j => {
          const rows = j.data || []
          setChart1Data(rows.map((r: any) => ({ label: String(r[chart1.labelField] ?? ''), value: Number(r[chart1.valueField] ?? 0) })))
        })
        .catch(() => {})
    }
    if (chart2?.tableName && !chart2Data) {
      fetch(`${_API}/api/data/${chart2.tableName}?limit=200`)
        .then(r => r.json())
        .then(j => setChart2Data(j.data || []))
        .catch(() => {})
    }
    if (tableName) {
      fetch(`${_API}/api/data/${tableName}?limit=10`)
        .then(r => r.json())
        .then(j => setTableRows(j.data || []))
        .catch(() => {})
    }
  }, [])

  const c1 = chart1 ? { ...chart1, data: chart1Data ?? [] } : null
  const c2 = chart2 ? { ...chart2, data: chart2Data ?? [], xLabels: (chart2Data ?? []).map((r: any) => String(r[chart2.xField] ?? '')), series: (chart2.series ?? []).map((s: any) => ({ ...s, values: (chart2Data ?? []).map((r: any) => Number(r[s.field] ?? 0)) })) } : null

  const s = {
    page:     { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    card:     { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    heading:  { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    kpiRow:   { display: 'flex', gap: 16, flexWrap: 'wrap' as const },
    kpiCard:  { flex: '1 1 160px', background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '16px 20px' },
    kpiLbl:   { fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' as const, letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: 6 },
    kpiVal:   { fontSize: 28, fontWeight: 700, color: '#0D1B2A', margin: '6px 0 4px' },
    chartRow: { display: 'flex', gap: 16 },
  }

  return (
    <div style={s.page}>
      <div><h1 style={s.heading}>{pageTitle}</h1></div>

      {/* KPI Cards */}
      <div style={s.kpiRow}>
        {(kpiCards ?? []).map((k: any, i: number) => {
          const dir = k.direction === 'up' ? 'success' : k.direction === 'down' ? 'error' : 'default'
          const ds  = BADGE_STYLES[dir] ?? BADGE_STYLES.default
          return (
            <div key={i} style={s.kpiCard}>
              <div style={s.kpiLbl}>{k.icon && <span>{k.icon}</span>}{k.label}</div>
              <div style={s.kpiVal}>{k.value}</div>
              <span style={{ display: 'inline-flex', padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: ds.bg, color: ds.color }}>
                {k.direction === 'up' ? '▲' : k.direction === 'down' ? '▼' : '●'} {k.change}
              </span>
            </div>
          )
        })}
      </div>

      {/* Charts row */}
      <div style={s.chartRow}>
        {c1 && (
          <div style={{ ...s.card, flex: 1 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#374151' }}>{c1.title}</h3>
            <ChartSlot chart={c1} />
          </div>
        )}
        {c2 && (
          <div style={{ ...s.card, flex: 1 }}>
            <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#374151' }}>{c2.title}</h3>
            <ChartSlot chart={c2} />
          </div>
        )}
      </div>

      {/* Optional table */}
      {tableRows && tableColumns && tableRows.length > 0 && (
        <div style={s.card}>
          <h3 style={{ margin: '0 0 14px', fontSize: 14, fontWeight: 700, color: '#374151' }}>Summary</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {(tableColumns as any[]).map((c: any) => (
                  <th key={c.key} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', borderBottom: '2px solid #E5E7EB' }}>{c.header}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(tableRows as any[]).slice(0, 10).map((row: any, i: number) => (
                <tr key={i}>
                  {(tableColumns as any[]).map((c: any) => (
                    <td key={c.key} style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9' }}>
                      {String(row[c.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
