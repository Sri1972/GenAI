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
import { Card, KpiCard, DataTable } from 'mobility-global-ds'
import { config } from '../config/KpiDashboard.config'
import { fetchTableRows } from '../hooks/useApi'

// Map the config's 'up' | 'down' | other direction field to KpiCard's changeType prop
function toChangeType(direction: any): 'positive' | 'negative' | 'neutral' {
  return direction === 'up' ? 'positive' : direction === 'down' ? 'negative' : 'neutral'
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
    const W = ref.current.parentElement?.clientWidth || ref.current.clientWidth || 400
    const m = { top: 10, right: 16, bottom: 30, left: 130 }
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
      .attr('x', (d: any) => {
        const bw = x(d.value)
        return bw > iW * 0.75 ? bw - 8 : bw + 6
      })
      .attr('y', (d: any) => y(d.label)! + y.bandwidth() / 2 + 4)
      .attr('font-size', 11)
      .attr('fill', (d: any) => x(d.value) > iW * 0.75 ? '#fff' : '#6B7280')
      .attr('text-anchor', (d: any) => x(d.value) > iW * 0.75 ? 'end' : 'start')
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
    const W = ref.current.parentElement?.clientWidth || ref.current.clientWidth || 400, H = 280
    const m = { top: 20, right: 20, bottom: 60, left: 55 }
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
  return <svg ref={ref} style={{ width: '100%', height: 280, display: 'block' }} />
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
// Shapes a chart config + its fetched rows into whatever ChartSlot's renderer for
// that chart's `type` expects. Used for chart1/chart2/chart3 uniformly — previously
// chart1 always got the bar/donut {label,value} shape and chart2 always got the line
// {xLabels,series} shape regardless of each one's actual configured `type`, so a
// chart assigned to a slot other than the one its type was hardcoded for (e.g. a
// donut in chart3, or a line chart moved to chart1) would render with the wrong data
// shape and silently show nothing.
function deriveChartData(chart: any, rows: any[] | null) {
  if (!chart) return null
  const data = rows ?? []
  if (chart.type === 'line') {
    return {
      ...chart,
      data,
      xLabels: data.map((r: any) => String(r[chart.xField] ?? '')),
      series: (chart.series ?? []).map((s: any) => ({
        ...s,
        values: data.map((r: any) => { const v = r[s.field]; return v != null && v !== '' ? Number(v) : null }),
      })),
    }
  }
  // bar / donut: {label, value}[]
  return {
    ...chart,
    data: data.map((r: any) => ({ label: String(r[chart.labelField] ?? ''), value: Number(r[chart.valueField] ?? 0) })),
  }
}

export default function KpiDashboardPage() {
  const { pageTitle, kpiCards: staticKpis, kpiTableName, kpiMapping, chart1, chart2, chart3, tableName, tableColumns } = config as any

  const [kpiCards, setKpiCards] = useState<any[]>(staticKpis ?? [])
  const [chart1Rows, setChart1Rows] = useState<any[] | null>(chart1?.data ?? null)
  const [chart2Rows, setChart2Rows] = useState<any[] | null>(chart2?.data ?? null)
  const [chart3Rows, setChart3Rows] = useState<any[] | null>(chart3?.data ?? null)
  const [tableRows, setTableRows]   = useState<any[] | null>(null)

  useEffect(() => {
    // Fetch KPIs from API table if configured
    if (kpiTableName) {
      fetchTableRows(kpiTableName, { limit: 20 })
        .then(rows => {
          if (rows.length) {
            const m = kpiMapping || {}
            setKpiCards(rows.map((r: any) => ({
              label: r[m.label || 'metric'] || r.label || r.metric || '',
              value: r[m.value || 'value'] || '',
              change: r[m.change || 'change_pct'] != null
                ? `${Number(r[m.change || 'change_pct']) > 0 ? '+' : ''}${r[m.change || 'change_pct']}%`
                : '',
              direction: r[m.direction || 'direction'] || 'neutral',
              icon: '',
            })))
          }
        })
        .catch(() => {})
    }
    if (chart1?.tableName && !chart1Rows) {
      fetchTableRows(chart1.tableName, { limit: 200 }).then(setChart1Rows).catch(() => {})
    }
    if (chart2?.tableName && !chart2Rows) {
      fetchTableRows(chart2.tableName, { limit: 200 }).then(setChart2Rows).catch(() => {})
    }
    if (chart3?.tableName && !chart3Rows) {
      fetchTableRows(chart3.tableName, { limit: 200 }).then(setChart3Rows).catch(() => {})
    }
    if (tableName) {
      fetchTableRows(tableName, { limit: 10 }).then(setTableRows).catch(() => {})
    }
  }, [])

  const c1 = useMemo(() => deriveChartData(chart1, chart1Rows), [chart1, chart1Rows])
  const c2 = useMemo(() => deriveChartData(chart2, chart2Rows), [chart2, chart2Rows])
  const c3 = useMemo(() => deriveChartData(chart3, chart3Rows), [chart3, chart3Rows])

  const s = {
    page:     { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    heading:  { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    kpiRow:   { display: 'flex', gap: 12, flexWrap: 'wrap' as const },
    chartRow: { display: 'flex', gap: 16 },
  }

  // Map the config's tableColumns shape ({key, header, ...}) onto DataTable's Column shape,
  // preserving the original renderer's '—' fallback for null/empty values.
  const dtColumns = (tableColumns ?? []).map((c: any) => ({
    key: c.key,
    header: c.header,
    width: c.width,
    align: c.align,
    render: c.render ?? ((v: any) => (v != null && v !== '' ? String(v) : '—')),
  }))

  return (
    <div style={s.page}>
      <div><h1 style={s.heading}>{pageTitle}</h1></div>

      {/* KPI Cards */}
      <div style={s.kpiRow}>
        {(kpiCards ?? []).map((k: any, i: number) => (
          <KpiCard
            key={i}
            label={k.label}
            value={k.value}
            change={k.change}
            changeType={toChangeType(k.direction)}
            icon={k.icon || undefined}
          />
        ))}
      </div>

      {/* Charts row */}
      <div style={s.chartRow}>
        {c1 && (
          <Card title={c1.title} style={{ flex: 1 }}>
            <ChartSlot chart={c1} />
          </Card>
        )}
        {c2 && (
          <Card title={c2.title} style={{ flex: 1 }}>
            <ChartSlot chart={c2} />
          </Card>
        )}
      </div>

      {/* Full-width third chart (e.g. a trend line below the two side-by-side charts) */}
      {c3 && (
        <Card title={c3.title}>
          <ChartSlot chart={c3} />
        </Card>
      )}

      {/* Optional table */}
      {tableRows && tableColumns && tableRows.length > 0 && (
        <Card title="Summary">
          <DataTable columns={dtColumns} rows={(tableRows as any[]).slice(0, 10)} />
        </Card>
      )}
    </div>
  )
}
