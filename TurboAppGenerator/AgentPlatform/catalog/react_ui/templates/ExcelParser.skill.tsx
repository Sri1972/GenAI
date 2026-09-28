// @ts-nocheck
/**
 * ExcelParser.skill.tsx — Client-side Excel analytics page.
 *
 * Accepts any .xlsx/.xls file upload, parses all worksheets using SheetJS,
 * auto-detects column types, selects appropriate chart types, and renders
 * interactive D3 charts + a sortable data table for each sheet.
 *
 * Domain-agnostic — works with ANY Excel file. No server required.
 * Reads accent/colors from src/config/ExcelParser.config.ts
 */
import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import * as d3 from 'd3'
import * as XLSX from 'xlsx'
import { config } from '../config/ExcelParser.config'

// ── Types ────────────────────────────────────────────────────────────────────
interface ColumnMeta {
  name: string
  type: 'numeric' | 'date' | 'categorical' | 'text' | 'percentage'
  uniqueCount: number
  nullCount: number
  stats?: { min: number; max: number; mean: number; median: number; sum: number }
  topValues?: { value: string; count: number }[]
}

interface ChartConfig {
  type: 'bar' | 'horizontal-bar' | 'line' | 'multi-line' | 'scatter' | 'donut' | 'histogram' | 'grouped-bar' | 'stacked-area'
  title: string
  subtitle: string
  xKey: string
  yKeys: string[]
  data: Record<string, any>[]
}

interface SheetData {
  name: string
  rows: Record<string, any>[]
  columns: ColumnMeta[]
  charts: ChartConfig[]
}

// ── Constants ────────────────────────────────────────────────────────────────
const COLORS = config.chartColors?.length === 10
  ? config.chartColors
  : ['#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#3B82F6', '#EF4444', '#8B5CF6', '#06B6D4', '#84CC16']
const ACCENT = config.accentColor || '#4F46E5'
const MAX_CHART_ROWS = config.maxChartRows || 5000

// ── Utility: Column Type Detection ───────────────────────────────────────────
function classifyColumns(rows: Record<string, any>[]): ColumnMeta[] {
  if (!rows.length) return []
  const keys = Object.keys(rows[0])
  return keys.map(name => {
    const values = rows.map(r => r[name]).filter(v => v != null && v !== '')
    const total = values.length
    if (!total) return { name, type: 'text' as const, uniqueCount: 0, nullCount: rows.length - total }

    const isPercentHeader = /percent|%|pct|ratio/i.test(name)
    const numericValues = values.filter(v => !isNaN(Number(v)))
    const numericRatio = numericValues.length / total

    if (numericRatio > 0.85) {
      const nums = numericValues.map(Number)
      const sorted = [...nums].sort((a, b) => a - b)
      const mid = Math.floor(sorted.length / 2)
      const stats = {
        min: sorted[0],
        max: sorted[sorted.length - 1],
        mean: nums.reduce((s, n) => s + n, 0) / nums.length,
        median: sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2,
        sum: nums.reduce((s, n) => s + n, 0),
      }
      const type = (isPercentHeader || (stats.min >= 0 && stats.max <= 100 && name.toLowerCase().includes('%')))
        ? 'percentage' as const : 'numeric' as const
      return { name, type, uniqueCount: new Set(nums).size, nullCount: rows.length - total, stats }
    }

    // Date detection
    const dateValues = values.filter(v => {
      if (typeof v === 'number' && v > 25000 && v < 60000) return true // Excel serial
      const d = new Date(v)
      return !isNaN(d.getTime()) && String(v).length > 4
    })
    if (dateValues.length / total > 0.7) {
      return { name, type: 'date' as const, uniqueCount: new Set(values.map(String)).size, nullCount: rows.length - total }
    }

    // Categorical vs text
    const unique = new Set(values.map(String))
    const type = unique.size <= 20 ? 'categorical' as const : 'text' as const
    const topValues = type === 'categorical'
      ? [...unique].map(v => ({ value: v, count: values.filter(x => String(x) === v).length }))
          .sort((a, b) => b.count - a.count).slice(0, 10)
      : undefined
    return { name, type, uniqueCount: unique.size, nullCount: rows.length - total, topValues }
  })
}

// ── Utility: Chart Selection ─────────────────────────────────────────────────
function selectCharts(columns: ColumnMeta[], rows: Record<string, any>[]): ChartConfig[] {
  if (rows.length < 3) return []
  const charts: ChartConfig[] = []
  const usedTypes = new Set<string>()
  const numerics = columns.filter(c => c.type === 'numeric' || c.type === 'percentage')
  const categoricals = columns.filter(c => c.type === 'categorical')
  const dates = columns.filter(c => c.type === 'date')
  const chartData = rows.slice(0, MAX_CHART_ROWS)

  // 1. Categorical + Numeric → Bar or Horizontal Bar
  if (categoricals.length && numerics.length) {
    const cat = categoricals[0]
    const num = numerics[0]
    const aggData = aggregateByCategory(chartData, cat.name, num.name)
    const isHorizontal = cat.uniqueCount > 8 || aggData.some(d => String(d[cat.name]).length > 15)
    const type = isHorizontal ? 'horizontal-bar' : 'bar'
    charts.push({
      type, title: `${num.name} by ${cat.name}`,
      subtitle: `${isHorizontal ? 'Horizontal bar' : 'Bar'} chart showing ${num.name} across ${cat.uniqueCount} categories`,
      xKey: cat.name, yKeys: [num.name], data: aggData,
    })
    usedTypes.add(type)
  }

  // 2. Date + Numeric → Line Chart
  if (dates.length && numerics.length && !usedTypes.has('line')) {
    const dt = dates[0]
    const num = numerics[0]
    const sorted = [...chartData].sort((a, b) => new Date(a[dt.name]).getTime() - new Date(b[dt.name]).getTime())
    charts.push({
      type: 'line', title: `${num.name} over Time`,
      subtitle: `Trend of ${num.name} across ${dt.name}`,
      xKey: dt.name, yKeys: [num.name], data: sorted,
    })
    usedTypes.add('line')
  }

  // 3. Date + Multiple Numerics → Multi-line
  if (dates.length && numerics.length > 1 && !usedTypes.has('multi-line')) {
    const dt = dates[0]
    const nums = numerics.slice(0, 4)
    const sorted = [...chartData].sort((a, b) => new Date(a[dt.name]).getTime() - new Date(b[dt.name]).getTime())
    charts.push({
      type: 'multi-line', title: `Trends: ${nums.map(n => n.name).join(', ')}`,
      subtitle: `Multiple metrics over ${dt.name}`,
      xKey: dt.name, yKeys: nums.map(n => n.name), data: sorted,
    })
    usedTypes.add('multi-line')
  }

  // 4. Categorical (< 8 unique) + Numeric → Donut
  if (categoricals.length && numerics.length && !usedTypes.has('donut')) {
    const cat = categoricals.find(c => c.uniqueCount <= 8 && c.uniqueCount >= 2) ?? categoricals[0]
    if (cat.uniqueCount <= 8) {
      const num = numerics[Math.min(1, numerics.length - 1)]
      const aggData = aggregateByCategory(chartData, cat.name, num.name)
      charts.push({
        type: 'donut', title: `${num.name} Distribution by ${cat.name}`,
        subtitle: `Proportional breakdown across ${cat.uniqueCount} categories`,
        xKey: cat.name, yKeys: [num.name], data: aggData,
      })
      usedTypes.add('donut')
    }
  }

  // 5. Two Numerics → Scatter
  if (numerics.length >= 2 && !usedTypes.has('scatter')) {
    const [nx, ny] = numerics
    charts.push({
      type: 'scatter', title: `${nx.name} vs ${ny.name}`,
      subtitle: `Relationship between ${nx.name} and ${ny.name}`,
      xKey: nx.name, yKeys: [ny.name], data: chartData,
    })
    usedTypes.add('scatter')
  }

  // 6. Numeric → Histogram
  if (numerics.length && !usedTypes.has('histogram') && charts.length < 5) {
    const num = numerics[numerics.length > 2 ? 2 : 0]
    charts.push({
      type: 'histogram', title: `Distribution of ${num.name}`,
      subtitle: `Frequency distribution across value ranges`,
      xKey: num.name, yKeys: [num.name], data: chartData,
    })
    usedTypes.add('histogram')
  }

  // 7. Categorical + Multiple Numerics → Grouped Bar
  if (categoricals.length && numerics.length > 1 && !usedTypes.has('grouped-bar') && charts.length < 6) {
    const cat = categoricals[0]
    const nums = numerics.slice(0, 3)
    const aggData = aggregateByCategory(chartData, cat.name, nums[0].name)
    for (const n of nums.slice(1)) {
      const agg2 = aggregateByCategory(chartData, cat.name, n.name)
      aggData.forEach((d, i) => { d[n.name] = agg2[i]?.[n.name] ?? 0 })
    }
    charts.push({
      type: 'grouped-bar', title: `Comparison: ${nums.map(n => n.name).join(', ')}`,
      subtitle: `Grouped by ${cat.name}`,
      xKey: cat.name, yKeys: nums.map(n => n.name), data: aggData.slice(0, 12),
    })
    usedTypes.add('grouped-bar')
  }

  return charts.slice(0, 6)
}

function aggregateByCategory(rows: Record<string, any>[], catKey: string, numKey: string): Record<string, any>[] {
  const map = new Map<string, { sum: number; count: number }>()
  for (const r of rows) {
    const cat = String(r[catKey] ?? '')
    const val = Number(r[numKey])
    if (!cat || isNaN(val)) continue
    const cur = map.get(cat) ?? { sum: 0, count: 0 }
    cur.sum += val; cur.count++
    map.set(cat, cur)
  }
  return [...map.entries()]
    .map(([k, v]) => ({ [catKey]: k, [numKey]: Math.round(v.sum * 100) / 100 }))
    .sort((a, b) => (b[numKey] as number) - (a[numKey] as number))
}

// ── Utility: Parse Excel ─────────────────────────────────────────────────────
function parseExcel(buffer: ArrayBuffer): SheetData[] {
  const wb = XLSX.read(buffer, { type: 'array', cellDates: true })
  return wb.SheetNames.map(name => {
    const ws = wb.Sheets[name]
    const rows: Record<string, any>[] = XLSX.utils.sheet_to_json(ws, { defval: '' })
    const columns = classifyColumns(rows)
    const charts = selectCharts(columns, rows)
    return { name, rows, columns, charts }
  })
}

// ── Tooltip (body-appended, never clipped) ───────────────────────────────────
function makeTip() {
  return d3.select(document.body).append('div')
    .style('position', 'fixed').style('display', 'none')
    .style('background', 'rgba(15,23,42,0.92)').style('color', '#fff')
    .style('padding', '8px 12px').style('border-radius', '8px').style('font-size', '12px')
    .style('pointer-events', 'none').style('z-index', '99999').style('max-width', '240px')
    .style('box-shadow', '0 4px 16px rgba(0,0,0,0.25)').style('line-height', '1.5')
    .style('white-space', 'nowrap')
}

function fmtNum(n: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(n)
}

function truncLabel(s: string, max = 14): string {
  return s.length > max ? s.slice(0, max - 1) + '…' : s
}

// ── Chart Components ─────────────────────────────────────────────────────────
function ChartCard({ chart }: { chart: ChartConfig }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !chart.data?.length) return
    const el = ref.current
    d3.select(el).select('svg').remove()
    const W = el.clientWidth || 400
    const H = 280
    const margin = { top: 16, right: 20, bottom: 52, left: 60 }
    const w = W - margin.left - margin.right
    const h = H - margin.top - margin.bottom
    const svg = d3.select(el).append('svg').attr('width', W).attr('height', H)
    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    const tip = makeTip()

    switch (chart.type) {
      case 'bar': renderBar(g, chart, w, h, false, tip); break
      case 'horizontal-bar': renderBar(g, chart, w, h, true, tip); break
      case 'line': renderLine(g, chart, w, h, tip); break
      case 'multi-line': renderLine(g, chart, w, h, tip); break
      case 'donut': renderDonut(svg, chart, W, H, tip); break
      case 'scatter': renderScatter(g, chart, w, h, tip); break
      case 'histogram': renderHistogram(g, chart, w, h, tip); break
      case 'grouped-bar': renderGroupedBar(g, chart, w, h, tip); break
      case 'stacked-area': renderLine(g, chart, w, h, tip); break
      default: renderBar(g, chart, w, h, false, tip)
    }

    return () => { tip.remove() }
  }, [chart])

  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: 16, minHeight: 340 }}>
      <div style={{ marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#1F2937' }}>{chart.title}</div>
        <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>{chart.subtitle}</div>
      </div>
      <div ref={ref} style={{ width: '100%', height: 280 }} />
    </div>
  )
}

function renderBar(g: any, chart: ChartConfig, w: number, h: number, horiz: boolean, tip: any) {
  const data = chart.data.slice(0, 15)
  const valKey = chart.yKeys[0]
  const catKey = chart.xKey
  const maxV = d3.max(data, (d: any) => Number(d[valKey])) ?? 1

  if (horiz) {
    const y = d3.scaleBand().domain(data.map(d => truncLabel(String(d[catKey]), 20))).range([0, h]).padding(0.25)
    const x = d3.scaleLinear().domain([0, maxV * 1.1]).range([0, w])
    g.append('g').call(d3.axisLeft(y).tickSize(0)).select('.domain').remove()
      .selectAll('text').style('font-size', '11px').style('fill', '#374151')
    g.append('g').call(d3.axisBottom(x).ticks(4).tickSize(-h).tickFormat(() => ''))
      .attr('transform', `translate(0,${h})`).select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9')
    g.selectAll('rect.bar').data(data).join('rect').attr('class', 'bar')
      .attr('y', (d: any) => y(truncLabel(String(d[catKey]), 20))!).attr('height', y.bandwidth())
      .attr('x', 0).attr('rx', 4)
      .attr('fill', (_: any, i: number) => COLORS[i % COLORS.length])
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('opacity', 0.75)
        tip.style('display', 'block').html(`<b>${d[catKey]}</b><br/>${valKey}: ${fmtNum(Number(d[valKey]))}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('opacity', 1); tip.style('display', 'none') })
      .transition().duration(500).attr('width', (d: any) => x(Number(d[valKey])))
    g.selectAll('text.val').data(data).join('text').attr('class', 'val')
      .attr('x', (d: any) => x(Number(d[valKey])) + 5)
      .attr('y', (d: any) => y(truncLabel(String(d[catKey]), 20))! + y.bandwidth() / 2 + 4)
      .style('font-size', '10px').style('fill', '#6B7280').text((d: any) => fmtNum(Number(d[valKey])))
  } else {
    const x = d3.scaleBand().domain(data.map(d => String(d[catKey]))).range([0, w]).padding(0.25)
    const y = d3.scaleLinear().domain([0, maxV * 1.1]).range([h, 0])
    g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-w).tickFormat(() => ''))
      .select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9')
    g.append('g').call(d3.axisLeft(y).ticks(5)).select('.domain').remove()
      .selectAll('text').style('font-size', '11px').style('fill', '#6B7280')
    g.append('g').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x).tickSize(0)
      .tickFormat((d: any) => truncLabel(String(d), 10))).select('.domain').remove()
      .selectAll('text').style('font-size', '10px').attr('transform', 'rotate(-30)').style('text-anchor', 'end').style('fill', '#6B7280')
    g.selectAll('rect.bar').data(data).join('rect').attr('class', 'bar')
      .attr('x', (d: any) => x(String(d[catKey]))!).attr('width', x.bandwidth())
      .attr('y', h).attr('rx', 4)
      .attr('fill', (_: any, i: number) => COLORS[i % COLORS.length])
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('opacity', 0.75)
        tip.style('display', 'block').html(`<b>${d[catKey]}</b><br/>${valKey}: ${fmtNum(Number(d[valKey]))}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('opacity', 1); tip.style('display', 'none') })
      .transition().duration(500).attr('y', (d: any) => y(Number(d[valKey]))).attr('height', (d: any) => h - y(Number(d[valKey])))
  }
}

function renderLine(g: any, chart: ChartConfig, w: number, h: number, tip: any) {
  const data = chart.data.slice(0, 50)
  const xLabels = data.map(d => String(d[chart.xKey]))
  const step = Math.max(1, Math.floor(xLabels.length / 10))
  const x = d3.scalePoint().domain(xLabels).range([0, w])
  const allVals = chart.yKeys.flatMap(k => data.map(d => Number(d[k])).filter(v => !isNaN(v)))
  const y = d3.scaleLinear().domain([Math.min(0, d3.min(allVals) ?? 0), (d3.max(allVals) ?? 1) * 1.1]).range([h, 0])

  g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-w).tickFormat(() => ''))
    .select('.domain').remove().selectAll('.tick line').attr('stroke', '#F1F5F9')
  g.append('g').call(d3.axisLeft(y).ticks(5)).select('.domain').remove()
    .selectAll('text').style('font-size', '11px').style('fill', '#6B7280')
  g.append('g').attr('transform', `translate(0,${h})`)
    .call(d3.axisBottom(x).tickSize(0).tickValues(xLabels.filter((_, i) => i % step === 0))
      .tickFormat((d: any) => truncLabel(String(d), 8)))
    .select('.domain').remove()
    .selectAll('text').style('font-size', '10px').style('fill', '#6B7280').attr('transform', 'rotate(-25)').style('text-anchor', 'end')

  chart.yKeys.forEach((key, si) => {
    const lineGen = d3.line<any>().defined(d => !isNaN(Number(d[key]))).x((_, i) => x(xLabels[i])!).y(d => y(Number(d[key]) || 0)).curve(d3.curveMonotoneX)
    g.append('path').datum(data).attr('fill', 'none').attr('stroke', COLORS[si % COLORS.length])
      .attr('stroke-width', 2.5).attr('d', lineGen)
    g.selectAll(`.dot-s${si}`).data(data).join('circle').attr('class', `dot-s${si}`)
      .attr('cx', (_: any, i: number) => x(xLabels[i])!).attr('cy', (d: any) => y(Number(d[key]) || 0))
      .attr('r', 3.5).attr('fill', COLORS[si % COLORS.length]).attr('stroke', '#fff').attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('r', 6)
        tip.style('display', 'block').html(`<b>${d[chart.xKey]}</b><br/>${key}: ${fmtNum(Number(d[key]))}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('r', 3.5); tip.style('display', 'none') })
  })

  if (chart.yKeys.length > 1) {
    const leg = g.append('g').attr('transform', `translate(0,${h + 34})`)
    chart.yKeys.forEach((key, i) => {
      const xOff = i * Math.min(120, w / chart.yKeys.length)
      leg.append('rect').attr('x', xOff).attr('width', 12).attr('height', 3).attr('rx', 1.5).attr('fill', COLORS[i % COLORS.length])
      leg.append('text').attr('x', xOff + 16).attr('y', 4).style('font-size', '10px').style('fill', '#6B7280').text(truncLabel(key, 12))
    })
  }
}

function renderDonut(svg: any, chart: ChartConfig, W: number, H: number, tip: any) {
  const data = chart.data.slice(0, 8)
  const valKey = chart.yKeys[0]
  const catKey = chart.xKey
  const total = d3.sum(data, (d: any) => Number(d[valKey]))
  const radius = Math.min(W, H) / 2 - 40
  const g = svg.append('g').attr('transform', `translate(${W / 2},${H / 2 - 10})`)

  const pie = d3.pie<any>().value(d => Number(d[valKey])).sort(null).padAngle(0.02)
  const arc = d3.arc<any>().innerRadius(radius * 0.55).outerRadius(radius)
  const arcHover = d3.arc<any>().innerRadius(radius * 0.55).outerRadius(radius + 6)
  const arcs = pie(data)

  g.selectAll('path').data(arcs).join('path')
    .attr('d', arc).attr('fill', (_: any, i: number) => COLORS[i % COLORS.length])
    .attr('stroke', '#fff').attr('stroke-width', 2).style('cursor', 'pointer')
    .on('mouseover', function(this: any, event: any, d: any) {
      d3.select(this).transition().duration(150).attr('d', arcHover)
      const pct = total > 0 ? ((Number(d.data[valKey]) / total) * 100).toFixed(1) : '0'
      tip.style('display', 'block').html(`<b>${d.data[catKey]}</b><br/>${valKey}: ${fmtNum(Number(d.data[valKey]))}<br/>${pct}% of total`)
    })
    .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
    .on('mouseleave', function(this: any) { d3.select(this).transition().duration(150).attr('d', arc); tip.style('display', 'none') })

  // Center label
  g.append('text').attr('text-anchor', 'middle').attr('dy', '-0.2em').style('font-size', '18px').style('font-weight', '800').style('fill', '#1F2937').text(fmtNum(total))
  g.append('text').attr('text-anchor', 'middle').attr('dy', '1.2em').style('font-size', '11px').style('fill', '#9CA3AF').text('Total')

  // Legend below
  const cols = Math.min(data.length, 4)
  const legW = cols * 90
  const leg = svg.append('g').attr('transform', `translate(${(W - legW) / 2},${H - 20})`)
  data.forEach((d: any, i: number) => {
    const col = i % cols
    const row = Math.floor(i / cols)
    const xOff = col * 90
    const yOff = row * 16
    leg.append('rect').attr('x', xOff).attr('y', yOff).attr('width', 8).attr('height', 8).attr('rx', 2).attr('fill', COLORS[i % COLORS.length])
    leg.append('text').attr('x', xOff + 12).attr('y', yOff + 8).style('font-size', '10px').style('fill', '#6B7280').text(truncLabel(String(d[catKey]), 10))
  })
}

function renderScatter(g: any, chart: ChartConfig, w: number, h: number, tip: any) {
  const data = chart.data.slice(0, 200)
  const xKey = chart.xKey
  const yKey = chart.yKeys[0]
  const xVals = data.map(d => Number(d[xKey])).filter(v => !isNaN(v))
  const yVals = data.map(d => Number(d[yKey])).filter(v => !isNaN(v))

  const x = d3.scaleLinear().domain(d3.extent(xVals) as [number, number]).range([0, w]).nice()
  const y = d3.scaleLinear().domain(d3.extent(yVals) as [number, number]).range([h, 0]).nice()

  g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-w).tickFormat(() => ''))
    .select('.domain').remove().selectAll('.tick line').attr('stroke', '#F1F5F9')
  g.append('g').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x).ticks(5)).select('.domain').remove()
    .selectAll('text').style('font-size', '11px').style('fill', '#6B7280')
  g.append('g').call(d3.axisLeft(y).ticks(5)).select('.domain').remove()
    .selectAll('text').style('font-size', '11px').style('fill', '#6B7280')

  // Axis labels
  g.append('text').attr('x', w / 2).attr('y', h + 32).attr('text-anchor', 'middle').style('font-size', '11px').style('fill', '#9CA3AF').text(xKey)
  g.append('text').attr('transform', 'rotate(-90)').attr('x', -h / 2).attr('y', -44).attr('text-anchor', 'middle').style('font-size', '11px').style('fill', '#9CA3AF').text(yKey)

  g.selectAll('circle').data(data).join('circle')
    .attr('cx', (d: any) => x(Number(d[xKey]) || 0)).attr('cy', (d: any) => y(Number(d[yKey]) || 0))
    .attr('r', 5).attr('fill', COLORS[0]).attr('opacity', 0.65).attr('stroke', COLORS[0]).attr('stroke-width', 1)
    .style('cursor', 'pointer')
    .on('mouseover', function(this: any, event: any, d: any) {
      d3.select(this).attr('r', 8).attr('opacity', 1)
      tip.style('display', 'block').html(`<b>${xKey}</b>: ${fmtNum(Number(d[xKey]))}<br/><b>${yKey}</b>: ${fmtNum(Number(d[yKey]))}`)
    })
    .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
    .on('mouseleave', function(this: any) { d3.select(this).attr('r', 5).attr('opacity', 0.65); tip.style('display', 'none') })
}

function renderHistogram(g: any, chart: ChartConfig, w: number, h: number, tip: any) {
  const valKey = chart.yKeys[0]
  const values = chart.data.map(d => Number(d[valKey])).filter(v => !isNaN(v))
  const x = d3.scaleLinear().domain(d3.extent(values) as [number, number]).range([0, w]).nice()
  const bins = d3.bin().domain(x.domain() as [number, number]).thresholds(15)(values)
  const y = d3.scaleLinear().domain([0, d3.max(bins, b => b.length) ?? 1]).range([h, 0])

  g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-w).tickFormat(() => ''))
    .select('.domain').remove().selectAll('.tick line').attr('stroke', '#F1F5F9')
  g.append('g').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x).ticks(6)).select('.domain').remove()
    .selectAll('text').style('font-size', '11px').style('fill', '#6B7280')
  g.append('g').call(d3.axisLeft(y).ticks(5)).select('.domain').remove()
    .selectAll('text').style('font-size', '11px').style('fill', '#6B7280')

  g.selectAll('rect').data(bins).join('rect')
    .attr('x', (d: any) => x(d.x0) + 1).attr('width', (d: any) => Math.max(0, x(d.x1) - x(d.x0) - 2))
    .attr('y', h).attr('rx', 3).attr('fill', COLORS[0]).attr('opacity', 0.85)
    .style('cursor', 'pointer')
    .on('mouseover', function(this: any, event: any, d: any) {
      d3.select(this).attr('opacity', 1).attr('fill', COLORS[1])
      tip.style('display', 'block').html(`<b>${fmtNum(d.x0)} – ${fmtNum(d.x1)}</b><br/>Count: ${d.length}`)
    })
    .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
    .on('mouseleave', function(this: any) { d3.select(this).attr('opacity', 0.85).attr('fill', COLORS[0]); tip.style('display', 'none') })
    .transition().duration(500).attr('y', (d: any) => y(d.length)).attr('height', (d: any) => h - y(d.length))
}

function renderGroupedBar(g: any, chart: ChartConfig, w: number, h: number, tip: any) {
  const data = chart.data.slice(0, 10)
  const catKey = chart.xKey
  const keys = chart.yKeys
  const x0 = d3.scaleBand().domain(data.map(d => String(d[catKey]))).range([0, w]).padding(0.2)
  const x1 = d3.scaleBand().domain(keys).range([0, x0.bandwidth()]).padding(0.08)
  const maxV = d3.max(data, (d: any) => d3.max(keys, k => Number(d[k]))) ?? 1
  const y = d3.scaleLinear().domain([0, maxV * 1.1]).range([h, 0])

  g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-w).tickFormat(() => ''))
    .select('.domain').remove().selectAll('.tick line').attr('stroke', '#F1F5F9')
  g.append('g').attr('transform', `translate(0,${h})`).call(d3.axisBottom(x0).tickSize(0)
    .tickFormat((d: any) => truncLabel(String(d), 10))).select('.domain').remove()
    .selectAll('text').style('font-size', '10px').attr('transform', 'rotate(-25)').style('text-anchor', 'end').style('fill', '#6B7280')
  g.append('g').call(d3.axisLeft(y).ticks(5)).select('.domain').remove()
    .selectAll('text').style('font-size', '11px').style('fill', '#6B7280')

  const groups = g.selectAll('.grp').data(data).join('g').attr('class', 'grp')
    .attr('transform', (d: any) => `translate(${x0(String(d[catKey]))},0)`)
  groups.selectAll('rect').data((d: any) => keys.map(k => ({ key: k, val: Number(d[k]) || 0, cat: d[catKey] })))
    .join('rect')
    .attr('x', (d: any) => x1(d.key)!).attr('width', x1.bandwidth())
    .attr('y', h).attr('rx', 3)
    .attr('fill', (d: any) => COLORS[keys.indexOf(d.key) % COLORS.length])
    .style('cursor', 'pointer')
    .on('mouseover', function(this: any, event: any, d: any) {
      d3.select(this).attr('opacity', 0.75)
      tip.style('display', 'block').html(`<b>${d.cat}</b><br/>${d.key}: ${fmtNum(d.val)}`)
    })
    .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
    .on('mouseleave', function(this: any) { d3.select(this).attr('opacity', 1); tip.style('display', 'none') })
    .transition().duration(500).attr('y', (d: any) => y(d.val)).attr('height', (d: any) => h - y(d.val))

  // Legend
  const leg = g.append('g').attr('transform', `translate(0,${h + 34})`)
  keys.forEach((key, i) => {
    const xOff = i * Math.min(110, w / keys.length)
    leg.append('rect').attr('x', xOff).attr('width', 10).attr('height', 3).attr('rx', 1.5).attr('fill', COLORS[i % COLORS.length])
    leg.append('text').attr('x', xOff + 14).attr('y', 4).style('font-size', '10px').style('fill', '#6B7280').text(truncLabel(key, 12))
  })
}

// ── Data Table ───────────────────────────────────────────────────────────────
function DataTable({ rows, columns }: { rows: Record<string, any>[]; columns: ColumnMeta[] }) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [expanded, setExpanded] = useState(false)
  const displayCols = columns.filter(c => c.type !== 'text' || c.uniqueCount < 50).slice(0, 12)
  const displayRows = useMemo(() => {
    let r = rows.slice(0, 100)
    if (sortKey) {
      r = [...r].sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey]
        const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
        return sortDir === 'asc' ? cmp : -cmp
      })
    }
    return r
  }, [rows, sortKey, sortDir])

  const toggleSort = (key: string) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('asc') }
  }

  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: 16, marginTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, cursor: 'pointer' }}
           onClick={() => setExpanded(!expanded)}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#1F2937' }}>
          Raw Data <span style={{ fontWeight: 400, color: '#9CA3AF', fontSize: 12 }}>({rows.length.toLocaleString()} rows)</span>
        </div>
        <span style={{ color: '#6B7280', fontSize: 18 }}>{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div style={{ overflowX: 'auto', maxHeight: 400 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                {displayCols.map(c => (
                  <th key={c.name} onClick={() => toggleSort(c.name)}
                      style={{ padding: '8px 10px', textAlign: c.type === 'numeric' ? 'right' : 'left', fontWeight: 700, color: '#6B7280', borderBottom: '2px solid #E5E7EB', cursor: 'pointer', whiteSpace: 'nowrap', background: '#F9FAFB', position: 'sticky', top: 0 }}>
                    {c.name} {sortKey === c.name ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {displayRows.map((row, i) => (
                <tr key={i} style={{ background: i % 2 ? '#F9FAFB' : '#fff' }}>
                  {displayCols.map(c => (
                    <td key={c.name} style={{ padding: '6px 10px', textAlign: c.type === 'numeric' ? 'right' : 'left', borderBottom: '1px solid #F1F5F9', whiteSpace: 'nowrap' }}>
                      {c.type === 'numeric' && typeof row[c.name] === 'number' ? Number(row[c.name]).toLocaleString() : String(row[c.name] ?? '')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 100 && <div style={{ padding: 8, textAlign: 'center', fontSize: 11, color: '#9CA3AF' }}>Showing 100 of {rows.length.toLocaleString()} rows</div>}
        </div>
      )}
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────
export default function ExcelParserPage() {
  const [sheets, setSheets] = useState<SheetData[] | null>(null)
  const [activeTab, setActiveTab] = useState(0)
  const [fileName, setFileName] = useState('')
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState('')
  const dropRef = useRef<HTMLDivElement>(null)

  const handleFile = useCallback((file: File) => {
    if (!file) return
    setError('')
    setParsing(true)
    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const data = parseExcel(e.target!.result as ArrayBuffer)
        setSheets(data)
        setActiveTab(0)
      } catch (err: any) {
        setError(err.message || 'Failed to parse file')
        setSheets(null)
      } finally {
        setParsing(false)
      }
    }
    reader.readAsArrayBuffer(file)
  }, [])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && /\.(xlsx?|xls)$/i.test(file.name)) handleFile(file)
    else setError('Please upload an .xlsx or .xls file')
  }, [handleFile])

  const onFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }, [handleFile])

  const activeSheet = sheets?.[activeTab]
  const totalRows = sheets?.reduce((s, sh) => s + sh.rows.length, 0) ?? 0

  // ── Upload State ───────────────────────────────────────────────────────────
  if (!sheets) {
    return (
      <div style={{ padding: 32, minHeight: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#F9FAFB' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: '#1F2937', margin: 0 }}>{config.pageTitle || 'Excel Insights'}</h1>
          <p style={{ color: '#6B7280', marginTop: 8 }}>{config.pageSubtitle || 'Upload any Excel file to get instant analytics'}</p>
        </div>
        <div ref={dropRef} onDrop={onDrop} onDragOver={e => e.preventDefault()}
             style={{ width: '100%', maxWidth: 500, border: `2px dashed ${ACCENT}`, borderRadius: 16, padding: '60px 40px', textAlign: 'center', cursor: 'pointer', background: '#fff', transition: 'all 0.2s' }}
             onClick={() => document.getElementById('excel-file-input')?.click()}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>{parsing ? '⏳' : '\u{1F4C2}'}</div>
          {parsing
            ? <div style={{ fontSize: 16, color: ACCENT, fontWeight: 600 }}>Analyzing sheets...</div>
            : <>
                <div style={{ fontSize: 16, fontWeight: 600, color: '#1F2937' }}>Drop your Excel file here</div>
                <div style={{ fontSize: 13, color: '#9CA3AF', marginTop: 6 }}>or click to browse &middot; .xlsx, .xls &middot; Up to 50MB</div>
              </>
          }
          <input id="excel-file-input" type="file" accept=".xlsx,.xls" style={{ display: 'none' }} onChange={onFileInput} />
        </div>
        {error && <div style={{ marginTop: 16, color: '#EF4444', fontWeight: 600, fontSize: 14 }}>{error}</div>}
      </div>
    )
  }

  // ── Analysis State ─────────────────────────────────────────────────────────
  return (
    <div style={{ padding: 24, minHeight: '100%', background: '#F9FAFB' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: '#1F2937', margin: 0 }}>{fileName}</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6B7280' }}>
            {sheets.length} sheet{sheets.length !== 1 ? 's' : ''} &middot; {totalRows.toLocaleString()} total rows
          </p>
        </div>
        <button onClick={() => { setSheets(null); setFileName(''); setError('') }}
                style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 600, color: '#374151' }}>
          Upload New File
        </button>
      </div>

      {/* Stats Bar */}
      {activeSheet && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Rows', value: activeSheet.rows.length.toLocaleString() },
            { label: 'Columns', value: activeSheet.columns.length },
            { label: 'Numeric', value: activeSheet.columns.filter(c => c.type === 'numeric' || c.type === 'percentage').length },
            { label: 'Categorical', value: activeSheet.columns.filter(c => c.type === 'categorical').length },
          ].map(kpi => (
            <div key={kpi.label} style={{ background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '14px 18px' }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#1F2937' }}>{kpi.value}</div>
              <div style={{ fontSize: 11, color: '#9CA3AF', marginTop: 2 }}>{kpi.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '2px solid #E5E7EB', marginBottom: 20, overflowX: 'auto' }}>
        {sheets.map((sh, i) => (
          <button key={sh.name} onClick={() => setActiveTab(i)}
                  style={{ padding: '10px 18px', border: 'none', borderBottom: `3px solid ${i === activeTab ? ACCENT : 'transparent'}`, background: 'none', cursor: 'pointer', fontSize: 13, fontWeight: i === activeTab ? 700 : 400, color: i === activeTab ? '#1F2937' : '#6B7280', whiteSpace: 'nowrap', transition: 'all 0.15s' }}>
            {sh.name} <span style={{ fontSize: 11, color: '#9CA3AF', marginLeft: 4 }}>{sh.rows.length}</span>
          </button>
        ))}
      </div>

      {/* Charts Grid */}
      {activeSheet && activeSheet.charts.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 16, marginBottom: 16 }}>
          {activeSheet.charts.map((chart, i) => <ChartCard key={i} chart={chart} />)}
        </div>
      )}

      {activeSheet && activeSheet.charts.length === 0 && (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '40px 20px', textAlign: 'center', color: '#9CA3AF', marginBottom: 16 }}>
          Not enough structured data in this sheet to generate charts.
        </div>
      )}

      {/* Data Table */}
      {activeSheet && <DataTable rows={activeSheet.rows} columns={activeSheet.columns} />}
    </div>
  )
}
