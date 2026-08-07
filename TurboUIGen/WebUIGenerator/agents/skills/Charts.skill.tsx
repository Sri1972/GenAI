// @ts-nocheck
/**
 * Charts.skill.tsx — Unified chart page skill.
 *
 * One skill file covers ALL chart types. Set config.chartType to select:
 *   'bar'          — horizontal or vertical bar chart
 *   'line'         — multi-line time-series chart
 *   'donut'/'pie'  — donut / pie chart with legend
 *   'area'         — stacked or layered area chart
 *   'grouped-bar'  — grouped bar chart (multiple series per group)
 *   'stacked-bar'  — stacked bar (series stacked vertically per group)
 *   'scatter'      — scatter plot (xField, yField, optional labelField)
 *   'bubble'       — bubble chart: sized circles (xField, yField, sizeField)
 *   'histogram'    — frequency distribution (valueField, optional bins count)
 *   'heatmap'      — matrix grid (xField, yField, valueField)
 *   'treemap'      — rectangular hierarchy (labelField, valueField, optional groupField)
 *   'radar'        — spider / radar (axes array, series with values array)
 *   'waterfall'    — waterfall / bridge chart (labelField, valueField)
 *   'multi'        — 2-column grid of mixed chart panels (charts array)
 *
 * Domain-agnostic — reads all config from src/config/Charts.config.ts
 */
import React, { useState, useEffect, useRef, useMemo } from 'react'
import * as d3 from 'd3'
import { config } from '../config/Charts.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n: number, f = ',.1f') {
  try { return d3.format(f)(n) } catch { return String(n) }
}

const AUTO_COLORS = [...(d3.schemeTableau10 as readonly string[])]

// Body-appended tooltip — created in each chart's useEffect, removed on cleanup.
// Appending to body means it is never clipped by any container, regardless of
// overflow, transform, or stacking context in the page layout.
function makeTip() {
  return d3.select(document.body).append('div')
    .style('position', 'fixed').style('display', 'none')
    .style('background', 'rgba(15,23,42,0.92)').style('color', '#fff')
    .style('padding', '8px 12px').style('border-radius', '8px').style('font-size', '12px')
    .style('pointer-events', 'none').style('z-index', '99999').style('max-width', '240px')
    .style('box-shadow', '0 4px 16px rgba(0,0,0,0.25)').style('line-height', '1.5')
    .style('white-space', 'nowrap')
}

function truncLabel(s: string, max = 14): string {
  return s.length > max ? s.slice(0, max - 1) + '…' : s
}

function pivotData(raw: any[], cfg: any): any[] {
  if (!raw.length) return raw
  const series = cfg.series as any[] | undefined
  if (!series?.length) return raw
  const xKey = cfg.xField || cfg.groupKey
  if (!xKey) return raw
  const firstRow = raw[0]
  const hasAllFields = series.every((s: any) => s.field in firstRow)
  if (hasAllFields) return raw
  const cols = Object.keys(firstRow)
  const fieldNames = series.map((s: any) => s.field as string)
  const slugify = (s: string) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  let pivotCol: string | null = null
  let metricCol: string | null = null
  for (const col of cols) {
    if (col === xKey || col === 'id') continue
    const colVals = [...new Set(raw.map(r => slugify(String(r[col]))))]
    for (const metric of cols) {
      if (metric === col || metric === xKey || metric === 'id') continue
      if (typeof firstRow[metric] !== 'number' && isNaN(Number(firstRow[metric]))) continue
      const expectedFields = colVals.map(v => `${v}_${metric}`)
      const matchCount = fieldNames.filter(f => expectedFields.includes(f)).length
      if (matchCount >= series.length * 0.4) { pivotCol = col; metricCol = metric; break }
    }
    if (pivotCol) break
  }
  if (!pivotCol || !metricCol) return raw
  const catValues = [...new Set(raw.map(r => String(r[pivotCol!])))]
  const aliasMap = new Map<string, string>()
  for (const cat of catValues) {
    const slug = slugify(cat)
    const canonical = `${slug}_${metricCol}`
    aliasMap.set(canonical, canonical)
    for (const f of fieldNames) {
      if (aliasMap.has(f)) continue
      const prefix = f.replace(new RegExp(`_${metricCol}$`), '')
      if (prefix && slug.startsWith(prefix)) aliasMap.set(f, canonical)
      else if (prefix && slug.includes(prefix)) aliasMap.set(f, canonical)
    }
  }
  const grouped = new Map<string, any>()
  for (const row of raw) {
    const key = String(row[xKey])
    if (!grouped.has(key)) grouped.set(key, { [xKey]: row[xKey] })
    const rec = grouped.get(key)!
    const catVal = slugify(String(row[pivotCol!]))
    const canonical = `${catVal}_${metricCol}`
    const numVal = Number(row[metricCol!] ?? 0)
    rec[canonical] = (rec[canonical] ?? 0) + numVal
    for (const [alias, target] of aliasMap) {
      if (target === canonical && alias !== canonical) rec[alias] = rec[canonical]
    }
  }
  return [...grouped.values()]
}

function aggregateSimple(rows: any[], cfg: any): any[] {
  if (!rows.length) return rows
  const type = (cfg.type ?? cfg.chartType ?? '').toLowerCase()
  const needsAgg = ['bar', 'donut', 'pie', 'treemap', 'waterfall'].includes(type)
  if (!needsAgg) return rows
  const labelField = cfg.labelField
  const valueField = cfg.valueField
  if (!labelField || !valueField) return rows
  if (new Set(rows.map(r => r[labelField])).size === rows.length) return rows
  const grouped = new Map<string, any>()
  for (const row of rows) {
    const key = String(row[labelField])
    if (!grouped.has(key)) grouped.set(key, { ...row, [valueField]: 0 })
    grouped.get(key)![valueField] += Number(row[valueField] ?? 0)
  }
  return [...grouped.values()].sort((a, b) => b[valueField] - a[valueField])
}

// ── Bar Chart ─────────────────────────────────────────────────────────────────
function BarChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const data   = (cfg.data ?? []) as any[]
    const horiz  = cfg.horizontal ?? false
    const valFmt = cfg.valueFormat ?? ',.0f'
    const maxV   = d3.max(data, (d: any) => Number(d[cfg.valueField])) ?? 1

    const W = ref.current.clientWidth || 500
    const H = horiz ? Math.max(180, data.length * 30 + 60) : 260
    const m = horiz
      ? { top: 8, right: 60, bottom: 28, left: 120 }
      : { top: 8, right: 16, bottom: 56, left: 50 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    if (horiz) {
      const x = d3.scaleLinear().domain([0, maxV * 1.08]).range([0, iW])
      const y = d3.scaleBand().domain(data.map((d: any) => String(d[cfg.labelField]))).range([0, iH]).padding(0.22)

      g.append('g').call(d3.axisLeft(y).tickSize(0).tickFormat((d: any) => truncLabel(String(d), 18))).select('.domain').remove()
        .selectAll('text').attr('font-size', 10).attr('fill', '#6B7280')
      g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).ticks(4).tickFormat(v => fmt(v as number, valFmt)))
        .select('.domain').remove()
      g.append('g').call(d3.axisBottom(x).ticks(4).tickSize(-iH).tickFormat(() => ''))
        .attr('transform', `translate(0,${iH})`).select('.domain').remove()
        .selectAll('.tick line').attr('stroke', '#F1F5F9')

      g.selectAll('rect.bar').data(data).join('rect').attr('class', 'bar')
        .attr('y', (d: any) => y(String(d[cfg.labelField]))!)
        .attr('height', y.bandwidth()).attr('x', 0).attr('rx', 3)
        .attr('fill', (d: any, i: number) => d[cfg.colorField ?? ''] ?? cfg.defaultColor ?? AUTO_COLORS[i % AUTO_COLORS.length])
        .style('cursor', 'pointer')
        .on('mouseover', function(this: any, event: any, d: any) {
          d3.select(this).attr('fill-opacity', 0.8)
          tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
            .html(`<b>${d[cfg.labelField]}</b><br/>${cfg.valueField}: ${fmt(Number(d[cfg.valueField]), valFmt)}`)
        })
        .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
        .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 1); tip.style('display', 'none') })
        .transition().duration(350)
        .attr('width', (d: any) => x(Number(d[cfg.valueField])))

      g.selectAll('text.val').data(data).join('text').attr('class', 'val')
        .attr('x', (d: any) => x(Number(d[cfg.valueField])) + 5)
        .attr('y', (d: any) => y(String(d[cfg.labelField]))! + y.bandwidth() / 2 + 4)
        .attr('font-size', 10).attr('fill', '#9CA3AF')
        .text((d: any) => fmt(Number(d[cfg.valueField]), valFmt))
    } else {
      const x = d3.scaleBand().domain(data.map((d: any) => String(d[cfg.labelField]))).range([0, iW]).padding(0.18)
      const y = d3.scaleLinear().domain([0, maxV * 1.08]).range([iH, 0])

      g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(v => fmt(v as number, valFmt))).select('.domain').remove()
        .selectAll('text').attr('font-size', 11).attr('fill', '#6B7280')
      g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).tickSize(0)
        .tickFormat((d: any) => truncLabel(String(d), 10)))
        .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')
      g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW).tickFormat(() => ''))
        .select('.domain').remove()
        .selectAll('.tick line').attr('stroke', '#F1F5F9')

      g.selectAll('rect.bar').data(data).join('rect').attr('class', 'bar')
        .attr('x', (d: any) => x(String(d[cfg.labelField]))!)
        .attr('width', x.bandwidth()).attr('rx', 3)
        .attr('fill', (d: any, i: number) => d[cfg.colorField ?? ''] ?? cfg.defaultColor ?? AUTO_COLORS[i % AUTO_COLORS.length])
        .style('cursor', 'pointer')
        .on('mouseover', function(this: any, event: any, d: any) {
          d3.select(this).attr('fill-opacity', 0.8)
          tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
            .html(`<b>${d[cfg.labelField]}</b><br/>${cfg.valueField}: ${fmt(Number(d[cfg.valueField]), valFmt)}`)
        })
        .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
        .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 1); tip.style('display', 'none') })
        .attr('y', iH).attr('height', 0)
        .transition().duration(350)
        .attr('y', (d: any) => y(Number(d[cfg.valueField])))
        .attr('height', (d: any) => iH - y(Number(d[cfg.valueField])))
    }
    return () => { tip.remove() }
  }, [cfg])

  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Stacked Bar Chart ─────────────────────────────────────────────────────────
function StackedBarChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const data   = (cfg.data ?? []) as any[]
    const series = (cfg.series ?? []) as any[]
    const groups = data.map((d: any) => String(d[cfg.groupKey ?? cfg.labelField]))
    const yFmt   = cfg.yFormat ?? cfg.valueFormat ?? ',.0f'

    const maxV = d3.max(data, (d: any) => series.reduce((s: number, sr: any) => s + Number(d[sr.field] ?? 0), 0)) ?? 1

    const W = ref.current.clientWidth || 500
    const H = 260
    const m = { top: 12, right: 16, bottom: 52, left: 50 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const x = d3.scaleBand().domain(groups).range([0, iW]).padding(0.22)
    const y = d3.scaleLinear().domain([0, maxV * 1.08]).range([iH, 0])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(v => fmt(v as number, yFmt))).select('.domain').remove()
      .selectAll('text').attr('font-size', 11).attr('fill', '#6B7280')
    g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).tickSize(0)
      .tickFormat((d: any) => truncLabel(String(d), 10)))
      .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')
    g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW).tickFormat(() => ''))
      .select('.domain').remove().selectAll('.tick line').attr('stroke', '#F1F5F9')

    data.forEach((row: any, di: number) => {
      let cumulative = 0
      series.forEach((s: any, si: number) => {
        const val = Number(row[s.field] ?? 0)
        g.append('rect')
          .attr('x', x(groups[di])!).attr('width', x.bandwidth()).attr('rx', si === 0 ? 3 : 0)
          .attr('fill', s.color ?? AUTO_COLORS[si % AUTO_COLORS.length])
          .attr('y', y(cumulative + val)).attr('height', Math.max(0, y(cumulative) - y(cumulative + val)))
          .style('cursor', 'pointer')
          .on('mouseover', function(this: any, event: any) {
            d3.select(this).attr('fill-opacity', 0.75)
            tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
              .html(`<b>${groups[di]}</b><br/>${s.label ?? s.field}: ${fmt(val, yFmt)}`)
          })
          .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
          .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 1); tip.style('display', 'none') })
        cumulative += val
      })
    })
    return () => { tip.remove() }
  }, [cfg])

  const series = (cfg.series ?? []) as any[]
  return (
    <div>
      <svg ref={ref} style={{ width: '100%', display: 'block' }} />
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
        {series.map((s: any, i: number) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 12, height: 12, borderRadius: 2, background: s.color ?? AUTO_COLORS[i % AUTO_COLORS.length] }} />
            <span style={{ fontSize: 11, color: '#6B7280' }}>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Line Chart ────────────────────────────────────────────────────────────────
function LineChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current) return
    const tip     = makeTip()
    const data    = (cfg.data ?? []) as any[]
    const series  = (cfg.series ?? []) as any[]
    const xLabels = data.map((r: any) => String(r[cfg.xField]))
    const yFmt    = cfg.yFormat ?? ',.1f'
    const allVals = series.flatMap((s: any) => data.map((r: any) => Number(r[s.field] ?? 0)))
    const maxV    = d3.max(allVals) ?? 1

    const W = ref.current.clientWidth || 500
    const H = 240
    const m = { top: 12, right: 16, bottom: 40, left: 50 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const x = d3.scalePoint().domain(xLabels).range([0, iW])
    const y = d3.scaleLinear().domain([0, maxV * 1.05]).nice().range([iH, 0])

    g.append('g').call(d3.axisLeft(y).ticks(4).tickSize(-iW).tickFormat(() => ''))
      .select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9').attr('stroke-dasharray', '2,2')
    g.append('g').call(d3.axisLeft(y).ticks(4).tickFormat(v => fmt(v as number, yFmt))).select('.domain').remove()
      .selectAll('text').attr('font-size', 10).attr('fill', '#9CA3AF')

    const every = Math.max(1, Math.ceil(xLabels.length / 7))
    g.append('g').attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).tickValues(xLabels.filter((_: string, i: number) => i % every === 0))
        .tickFormat((d: any) => truncLabel(String(d), 10)))
      .selectAll('text').attr('transform', 'rotate(-25)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')

    series.forEach((s: any, si: number) => {
      const color = s.color ?? AUTO_COLORS[si % AUTO_COLORS.length]
      const line  = d3.line<any>()
        .x((r: any) => x(String(r[cfg.xField]))!)
        .y((r: any) => y(Number(r[s.field] ?? 0)))
        .curve(d3.curveMonotoneX)
      g.append('path').datum(data).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2.5).attr('d', line as any)
      g.selectAll(null).data(data).join('circle')
        .attr('cx', (r: any) => x(String(r[cfg.xField]))!)
        .attr('cy', (r: any) => y(Number(r[s.field] ?? 0)))
        .attr('r', 3.5).attr('fill', '#fff').attr('stroke', color).attr('stroke-width', 2)
    })

    svg.append('rect').attr('transform', `translate(${m.left},${m.top})`)
      .attr('width', iW).attr('height', iH).attr('fill', 'transparent')
      .on('mousemove', function(this: any, event: MouseEvent) {
        const svgRect = (ref.current as SVGSVGElement).getBoundingClientRect()
        const mx  = event.clientX - svgRect.left - m.left
        const each = iW / Math.max(xLabels.length - 1, 1)
        const idx  = Math.max(0, Math.min(xLabels.length - 1, Math.round(mx / each)))
        const row  = data[idx]
        if (!row) return
        const lines = series.map((s: any) => `${s.label}: <b>${fmt(Number(row[s.field] ?? 0), yFmt)}</b>`)
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${row[cfg.xField]}</b><br/>${lines.join('<br/>')}`)
      })
      .on('mouseleave', () => tip.style('display', 'none'))
    return () => { tip.remove() }
  }, [cfg])

  const series = (cfg.series ?? []) as any[]
  return (
    <div>
      <svg ref={ref} style={{ width: '100%', display: 'block' }} />
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
        {series.map((s: any, i: number) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 14, height: 3, borderRadius: 2, background: s.color ?? AUTO_COLORS[i % AUTO_COLORS.length] }} />
            <span style={{ fontSize: 11, color: '#6B7280' }}>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Donut / Pie Chart ─────────────────────────────────────────────────────────
function DonutChart({ cfg }: { cfg: any }) {
  const ref   = useRef<SVGSVGElement>(null)
  const [hovered, setHovered] = useState<number | null>(null)
  const data  = useMemo(() => (cfg.data ?? []) as any[], [cfg])
  const total = data.reduce((s: number, r: any) => s + Number(r[cfg.valueField] ?? 0), 0)

  useEffect(() => {
    if (!ref.current || data.length === 0) return
    const W = 260, H = 220, R = 86, RI = 50
    const svg = d3.select(ref.current).attr('width', W).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${W / 2},${H / 2})`)

    const pie   = d3.pie<any>().sort(null).value((d: any) => Number(d[cfg.valueField] ?? 0))
    const arc   = d3.arc<any>().outerRadius(R).innerRadius(RI)
    const arcH  = d3.arc<any>().outerRadius(R + 7).innerRadius(RI)
    const colors = data.every((r: any) => r[cfg.colorField ?? ''])
      ? data.map((r: any) => String(r[cfg.colorField]))
      : AUTO_COLORS

    g.selectAll('.arc').data(pie(data)).join('g').attr('class', 'arc')
      .append('path')
      .attr('fill', (_: any, i: number) => colors[i % colors.length])
      .attr('stroke', '#fff').attr('stroke-width', 2).style('cursor', 'pointer')
      .on('mouseover', function(this: any, _: any, d: any) {
        d3.select(this).transition().duration(120).attr('d', arcH(d))
        setHovered(data.indexOf(d.data))
      })
      .on('mouseleave', function(this: any, _: any, d: any) {
        d3.select(this).transition().duration(120).attr('d', arc(d))
        setHovered(null)
      })
      .transition().duration(550)
      .attrTween('d', function(this: any, d: any) {
        const i = d3.interpolate({ startAngle: 0, endAngle: 0 }, d)
        return (t: number) => arc(i(t))!
      })

    g.append('text').attr('text-anchor', 'middle').attr('dy', '-0.4em')
      .attr('font-size', 11).attr('fill', '#9CA3AF').text(cfg.centerLabel ?? 'Total')
    g.append('text').attr('text-anchor', 'middle').attr('dy', '1.0em')
      .attr('font-size', 18).attr('font-weight', 700).attr('fill', '#0D1B2A')
      .text(fmt(total, cfg.valueFormat ?? ',.0f'))
  }, [data, total])

  const colors = data.every((r: any) => r[cfg.colorField ?? ''])
    ? data.map((r: any) => String(r[cfg.colorField]))
    : AUTO_COLORS

  return (
    <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
      <svg ref={ref} style={{ flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 140 }}>
        {data.map((r: any, i: number) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', background: hovered === i ? '#F8FAFC' : 'transparent', borderRadius: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', flexShrink: 0, background: colors[i % colors.length] }} />
            <span style={{ fontSize: 12, color: '#374151', flex: 1, fontWeight: hovered === i ? 600 : 400 }}>{r[cfg.labelField]}</span>
            <span style={{ fontSize: 12, color: '#6B7280', fontVariantNumeric: 'tabular-nums' }}>
              {total > 0 ? ((Number(r[cfg.valueField]) / total) * 100).toFixed(1) + '%' : '—'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Area Chart ────────────────────────────────────────────────────────────────
function AreaChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip     = makeTip()
    const data    = (cfg.data ?? []) as any[]
    const series  = (cfg.series ?? []) as any[]
    const xLabels = data.map((r: any) => String(r[cfg.xField]))
    const stacked = cfg.stacked ?? false
    const yFmt    = cfg.yFormat ?? ',.0f'

    const W = ref.current.clientWidth || 500
    const H = 240
    const m = { top: 12, right: 16, bottom: 40, left: 50 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const allVals = stacked
      ? data.map((r: any) => series.reduce((s: number, sr: any) => s + Number(r[sr.field] ?? 0), 0))
      : series.flatMap((s: any) => data.map((r: any) => Number(r[s.field] ?? 0)))
    const maxV = d3.max(allVals) ?? 1

    const x = d3.scalePoint().domain(xLabels).range([0, iW])
    const y = d3.scaleLinear().domain([0, maxV * 1.08]).nice().range([iH, 0])

    g.append('g').call(d3.axisLeft(y).ticks(4).tickSize(-iW).tickFormat(() => ''))
      .select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9').attr('stroke-dasharray', '2,2')
    g.append('g').call(d3.axisLeft(y).ticks(4).tickFormat(v => fmt(v as number, yFmt))).select('.domain').remove()
    const every = Math.max(1, Math.ceil(xLabels.length / 7))
    g.append('g').attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).tickValues(xLabels.filter((_: string, i: number) => i % every === 0))
        .tickFormat((d: any) => truncLabel(String(d), 10)))
      .selectAll('text').attr('transform', 'rotate(-25)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')

    let baseline = data.map(() => 0)
    series.forEach((s: any, si: number) => {
      const color = s.color ?? AUTO_COLORS[si % AUTO_COLORS.length]
      const vals  = data.map((r: any) => Number(r[s.field] ?? 0))
      const tops  = stacked ? vals.map((v: number, i: number) => baseline[i] + v) : vals
      const bots  = stacked ? [...baseline] : data.map(() => 0)
      const area  = d3.area<number>()
        .x((_: number, i: number) => x(xLabels[i])!)
        .y0((_: number, i: number) => y(bots[i]))
        .y1((v: number) => y(v))
        .curve(d3.curveMonotoneX)
      g.append('path').datum(tops).attr('fill', color).attr('fill-opacity', 0.25).attr('d', area as any)
      g.append('path').datum(tops).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2)
        .attr('d', d3.line<number>().x((_: number, i: number) => x(xLabels[i])!).y((v: number) => y(v)).curve(d3.curveMonotoneX) as any)
      if (stacked) baseline = tops
    })

    svg.append('rect').attr('transform', `translate(${m.left},${m.top})`)
      .attr('width', iW).attr('height', iH).attr('fill', 'transparent')
      .on('mousemove', function(this: any, event: MouseEvent) {
        const svgRect = (ref.current as SVGSVGElement).getBoundingClientRect()
        const mx  = event.clientX - svgRect.left - m.left
        const each = iW / Math.max(xLabels.length - 1, 1)
        const idx  = Math.max(0, Math.min(xLabels.length - 1, Math.round(mx / each)))
        const row  = data[idx]
        if (!row) return
        const lines = series.map((s: any) => `${s.label ?? s.field}: <b>${fmt(Number(row[s.field] ?? 0), yFmt)}</b>`)
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${row[cfg.xField]}</b><br/>${lines.join('<br/>')}`)
      })
      .on('mouseleave', () => tip.style('display', 'none'))
    return () => { tip.remove() }
  }, [cfg])

  const series = (cfg.series ?? []) as any[]
  return (
    <div>
      <svg ref={ref} style={{ width: '100%', display: 'block' }} />
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
        {series.map((s: any, i: number) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 14, height: 10, borderRadius: 2, background: s.color ?? AUTO_COLORS[i % AUTO_COLORS.length], opacity: 0.7 }} />
            <span style={{ fontSize: 11, color: '#6B7280' }}>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Grouped Bar Chart ─────────────────────────────────────────────────────────
function GroupedBarChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const data   = (cfg.data ?? []) as any[]
    const series = (cfg.series ?? []) as any[]
    const groups = data.map((d: any) => String(d[cfg.groupKey]))
    const yFmt   = cfg.yFormat ?? ',.0f'
    const allVals = series.flatMap((s: any) => data.map((r: any) => Number(r[s.field] ?? 0)))
    const maxV   = d3.max(allVals) ?? 1

    const W = ref.current.clientWidth || 500
    const H = 260
    const m = { top: 12, right: 16, bottom: 50, left: 50 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const x0 = d3.scaleBand().domain(groups).range([0, iW]).padding(0.2)
    const x1 = d3.scaleBand().domain(series.map((s: any) => s.field)).range([0, x0.bandwidth()]).padding(0.05)
    const y  = d3.scaleLinear().domain([0, maxV * 1.08]).range([iH, 0])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(v => fmt(v as number, yFmt))).select('.domain').remove()
      .selectAll('text').attr('font-size', 11).attr('fill', '#6B7280')
    g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x0).tickSize(0)
      .tickFormat((d: any) => truncLabel(String(d), 10)))
      .selectAll('text').attr('font-size', 10).attr('fill', '#9CA3AF').attr('transform', 'rotate(-25)').style('text-anchor', 'end')
    g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW).tickFormat(() => ''))
      .select('.domain').remove().selectAll('.tick line').attr('stroke', '#F1F5F9')

    const grp = g.selectAll('.grp').data(data).join('g').attr('class', 'grp')
      .attr('transform', (d: any) => `translate(${x0(String(d[cfg.groupKey]))},0)`)

    series.forEach((s: any, si: number) => {
      const color = s.color ?? AUTO_COLORS[si % AUTO_COLORS.length]
      grp.append('rect')
        .attr('x', x1(s.field)!).attr('width', x1.bandwidth()).attr('rx', 2)
        .attr('fill', color)
        .style('cursor', 'pointer')
        .on('mouseover', function(this: any, event: any, d: any) {
          d3.select(this).attr('fill-opacity', 0.75)
          tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
            .html(`<b>${d[cfg.groupKey]}</b><br/>${s.label ?? s.field}: ${fmt(Number(d[s.field] ?? 0), yFmt)}`)
        })
        .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
        .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 1); tip.style('display', 'none') })
        .attr('y', iH).attr('height', 0)
        .transition().duration(350)
        .attr('y', (d: any) => y(Number(d[s.field] ?? 0)))
        .attr('height', (d: any) => iH - y(Number(d[s.field] ?? 0)))
    })
    return () => { tip.remove() }
  }, [cfg])

  const series = (cfg.series ?? []) as any[]
  return (
    <div>
      <svg ref={ref} style={{ width: '100%', display: 'block' }} />
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
        {series.map((s: any, i: number) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 12, height: 12, borderRadius: 2, background: s.color ?? AUTO_COLORS[i % AUTO_COLORS.length] }} />
            <span style={{ fontSize: 11, color: '#6B7280' }}>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Scatter Plot ──────────────────────────────────────────────────────────────
function ScatterChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const data   = (cfg.data ?? []) as any[]
    const xFmt   = cfg.xFormat ?? ',.1f'
    const yFmt   = cfg.yFormat ?? ',.1f'
    const series = (cfg.series ?? [{ field: cfg.yField ?? '', label: cfg.yLabel ?? cfg.yField ?? '', color: cfg.defaultColor ?? AUTO_COLORS[0] }]) as any[]

    const W = ref.current.clientWidth || 500
    const H = 280
    const m = { top: 12, right: 20, bottom: 44, left: 56 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const allX = data.map((d: any) => Number(d[cfg.xField] ?? 0))
    const allY = series.flatMap((s: any) => data.map((d: any) => Number(d[s.field] ?? 0)))
    const xMin = d3.min(allX) ?? 0
    const xMax = d3.max(allX) ?? 1
    const yMax = d3.max(allY) ?? 1

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const x = d3.scaleLinear().domain([xMin - (xMax - xMin) * 0.05, xMax * 1.05]).range([0, iW])
    const y = d3.scaleLinear().domain([0, yMax * 1.08]).nice().range([iH, 0])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW).tickFormat(() => '')).select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9')
    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(v => fmt(v as number, yFmt))).select('.domain').remove()
    g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).ticks(6).tickFormat(v => fmt(v as number, xFmt)))
      .select('.domain').remove()

    if (cfg.xLabel) g.append('text').attr('x', iW / 2).attr('y', iH + 38).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', '#9CA3AF').text(cfg.xLabel)
    if (cfg.yLabel) g.append('text').attr('transform', 'rotate(-90)').attr('x', -iH / 2).attr('y', -42).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', '#9CA3AF').text(cfg.yLabel)

    series.forEach((s: any, si: number) => {
      const color = s.color ?? AUTO_COLORS[si % AUTO_COLORS.length]
      g.selectAll(null).data(data).join('circle')
        .attr('cx', (d: any) => x(Number(d[cfg.xField] ?? 0)))
        .attr('cy', (d: any) => y(Number(d[s.field] ?? 0)))
        .attr('r', 5).attr('fill', color).attr('fill-opacity', 0.7).attr('stroke', '#fff').attr('stroke-width', 1)
        .style('cursor', 'pointer')
        .on('mouseover', function(this: any, event: any, d: any) {
          d3.select(this).attr('r', 8).attr('fill-opacity', 1)
          const label = cfg.labelField ? d[cfg.labelField] : ''
          tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
            .html(`${label ? `<b>${label}</b><br/>` : ''}${cfg.xField}: ${fmt(Number(d[cfg.xField] ?? 0), xFmt)}<br/>${s.label || s.field}: ${fmt(Number(d[s.field] ?? 0), yFmt)}`)
        })
        .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
        .on('mouseleave', function(this: any) { d3.select(this).attr('r', 5).attr('fill-opacity', 0.7); tip.style('display', 'none') })
    })
    return () => { tip.remove() }
  }, [cfg])

  const series = (cfg.series ?? []) as any[]
  return (
    <div>
      <svg ref={ref} style={{ width: '100%', display: 'block' }} />
      {series.length > 1 && (
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 8 }}>
          {series.map((s: any, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: s.color ?? AUTO_COLORS[i % AUTO_COLORS.length] }} />
              <span style={{ fontSize: 11, color: '#6B7280' }}>{s.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Bubble Chart ──────────────────────────────────────────────────────────────
function BubbleChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip     = makeTip()
    const data    = (cfg.data ?? []) as any[]
    const xField  = cfg.xField  ?? 'x'
    const yField  = cfg.yField  ?? 'y'
    const szField = cfg.sizeField ?? 'size'
    const xFmt    = cfg.xFormat ?? ',.1f'
    const yFmt    = cfg.yFormat ?? ',.1f'
    const szFmt   = cfg.sizeFormat ?? ',.0f'

    const allX = data.map((d: any) => Number(d[xField] ?? 0))
    const allY = data.map((d: any) => Number(d[yField] ?? 0))
    const allZ = data.map((d: any) => Number(d[szField] ?? 0))

    const W = ref.current.clientWidth || 500
    const H = 300
    const m = { top: 20, right: 30, bottom: 46, left: 56 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const xExt = d3.extent(allX) as [number, number]
    const yExt = d3.extent(allY) as [number, number]
    const pad  = (v: number) => v * 0.1
    const x  = d3.scaleLinear().domain([xExt[0] - pad(xExt[1] - xExt[0]), xExt[1] + pad(xExt[1] - xExt[0])]).range([0, iW])
    const y  = d3.scaleLinear().domain([yExt[0] - pad(yExt[1] - yExt[0]), yExt[1] + pad(yExt[1] - yExt[0])]).range([iH, 0])
    const sz = d3.scaleSqrt().domain([0, d3.max(allZ) ?? 1]).range([4, 30])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW).tickFormat(() => '')).select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9')
    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(v => fmt(v as number, yFmt))).select('.domain').remove()
    g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).ticks(6).tickFormat(v => fmt(v as number, xFmt))).select('.domain').remove()

    if (cfg.xLabel) g.append('text').attr('x', iW / 2).attr('y', iH + 38).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', '#9CA3AF').text(cfg.xLabel)
    if (cfg.yLabel) g.append('text').attr('transform', 'rotate(-90)').attr('x', -iH / 2).attr('y', -42).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', '#9CA3AF').text(cfg.yLabel)

    const colorField = cfg.colorField ?? cfg.groupField
    const uniqueGroups = colorField ? [...new Set(data.map((d: any) => String(d[colorField] ?? '')))] : []
    const colorScale  = colorField
      ? d3.scaleOrdinal(AUTO_COLORS).domain(uniqueGroups)
      : () => cfg.defaultColor ?? AUTO_COLORS[0]

    g.selectAll('circle').data(data).join('circle')
      .attr('cx', (d: any) => x(Number(d[xField] ?? 0)))
      .attr('cy', (d: any) => y(Number(d[yField] ?? 0)))
      .attr('r',  (d: any) => sz(Number(d[szField] ?? 0)))
      .attr('fill', (d: any) => d[cfg.colorField ?? ''] ?? colorScale(String(d[colorField ?? ''] ?? '')))
      .attr('fill-opacity', 0.65).attr('stroke', '#fff').attr('stroke-width', 1.5)
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('fill-opacity', 1).attr('stroke-width', 2)
        const label = cfg.labelField ? `<b>${d[cfg.labelField]}</b><br/>` : ''
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`${label}${cfg.xLabel ?? xField}: ${fmt(Number(d[xField] ?? 0), xFmt)}<br/>${cfg.yLabel ?? yField}: ${fmt(Number(d[yField] ?? 0), yFmt)}<br/>${cfg.sizeLabel ?? szField}: ${fmt(Number(d[szField] ?? 0), szFmt)}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 0.65).attr('stroke-width', 1.5); tip.style('display', 'none') })
    return () => { tip.remove() }
  }, [cfg])

  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Histogram ─────────────────────────────────────────────────────────────────
function HistogramChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const data   = (cfg.data ?? []) as any[]
    const values = data.map((d: any) => Number(d[cfg.valueField] ?? 0)).filter(v => !isNaN(v))
    const bins   = cfg.bins ?? 20
    const yFmt   = cfg.yFormat ?? ',.0f'
    const color  = cfg.defaultColor ?? AUTO_COLORS[0]

    const W = ref.current.clientWidth || 500
    const H = 260
    const m = { top: 12, right: 16, bottom: 44, left: 50 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const x = d3.scaleLinear().domain(d3.extent(values) as [number,number]).nice().range([0, iW])
    const binner   = (d3.bin ?? (d3 as any).histogram)().domain(x.domain() as [number,number]).thresholds(x.ticks(bins))
    const binsData = binner(values)
    const maxCount  = d3.max(binsData, (b: any) => b.length) ?? 1
    const y = d3.scaleLinear().domain([0, maxCount * 1.08]).range([iH, 0])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW).tickFormat(() => '')).select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9')
    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(v => fmt(v as number, yFmt))).select('.domain').remove()
      .selectAll('text').attr('font-size', 11).attr('fill', '#6B7280')
    g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).ticks(8)).select('.domain').remove()
      .selectAll('text').attr('font-size', 11).attr('fill', '#6B7280')

    if (cfg.xLabel) g.append('text').attr('x', iW / 2).attr('y', iH + 38).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', '#9CA3AF').text(cfg.xLabel)

    g.selectAll('rect').data(binsData).join('rect')
      .attr('x', (d: any) => x(d.x0) + 1)
      .attr('width', (d: any) => Math.max(0, x(d.x1) - x(d.x0) - 2))
      .attr('y', iH).attr('height', 0).attr('rx', 3).attr('fill', color).attr('fill-opacity', 0.85)
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('fill-opacity', 1).attr('fill', AUTO_COLORS[1])
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${fmt(d.x0, cfg.valueFormat ?? ',.1f')} – ${fmt(d.x1, cfg.valueFormat ?? ',.1f')}</b><br/>Count: ${d.length}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 0.85).attr('fill', color); tip.style('display', 'none') })
      .transition().duration(400)
      .attr('y', (d: any) => y(d.length))
      .attr('height', (d: any) => iH - y(d.length))
    return () => { tip.remove() }
  }, [cfg])

  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Heatmap ───────────────────────────────────────────────────────────────────
function HeatmapChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const data   = (cfg.data ?? []) as any[]
    const xField = cfg.xField ?? 'x'
    const yField = cfg.yField ?? 'y'
    const vField = cfg.valueField ?? 'value'
    const vFmt   = cfg.valueFormat ?? ',.1f'

    const xDomain = [...new Set(data.map((d: any) => String(d[xField])))]
    const yDomain = [...new Set(data.map((d: any) => String(d[yField])))]
    const vals    = data.map((d: any) => Number(d[vField] ?? 0))
    const minV    = d3.min(vals) ?? 0
    const maxV    = d3.max(vals) ?? 1

    const W = ref.current.clientWidth || 500
    const cellH  = Math.min(40, Math.floor((W - 90) / Math.max(xDomain.length, 1) * 0.8))
    const H = cellH * yDomain.length + 60 + 20
    const m = { top: 20, right: 20, bottom: 44, left: 90 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const x = d3.scaleBand().domain(xDomain).range([0, iW]).padding(0.04)
    const y = d3.scaleBand().domain(yDomain).range([0, iH]).padding(0.04)
    const scheme = cfg.colorScheme === 'red' ? d3.interpolateReds
      : cfg.colorScheme === 'green' ? d3.interpolateGreens
      : cfg.colorScheme === 'purple' ? d3.interpolatePurples
      : d3.interpolateBlues
    const colorScale = d3.scaleSequential(scheme).domain([minV, maxV])

    g.append('g').call(d3.axisLeft(y).tickSize(0)).select('.domain').remove()
      .selectAll('text').attr('font-size', 10).attr('fill', '#6B7280')
    g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).tickSize(0))
      .select('.domain').remove()
      .selectAll('text').attr('font-size', 10).attr('fill', '#6B7280').attr('transform', 'rotate(-30)').style('text-anchor', 'end')

    g.selectAll('rect.cell').data(data).join('rect').attr('class', 'cell')
      .attr('x', (d: any) => x(String(d[xField]))!)
      .attr('y', (d: any) => y(String(d[yField]))!)
      .attr('width', x.bandwidth()).attr('height', y.bandwidth()).attr('rx', 3)
      .attr('fill', (d: any) => colorScale(Number(d[vField] ?? 0)))
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('stroke', '#374151').attr('stroke-width', 2)
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${d[xField]}</b> × <b>${d[yField]}</b><br/>${vField}: ${fmt(Number(d[vField] ?? 0), vFmt)}`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('stroke', 'none'); tip.style('display', 'none') })
    return () => { tip.remove() }
  }, [cfg])

  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Treemap ───────────────────────────────────────────────────────────────────
function TreemapChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip   = makeTip()
    const data  = (cfg.data ?? []) as any[]
    const lblF  = cfg.labelField ?? 'label'
    const valF  = cfg.valueField ?? 'value'
    const grpF  = cfg.groupField
    const vFmt  = cfg.valueFormat ?? ',.0f'
    const total = data.reduce((s: number, d: any) => s + Number(d[valF] ?? 0), 0)

    const W = ref.current.clientWidth || 500
    const H = 320

    const children = grpF
      ? [...new Set(data.map((d: any) => String(d[grpF])))].map(grp => ({
          name: grp,
          children: data.filter((d: any) => String(d[grpF]) === grp).map((d: any) => ({ name: String(d[lblF]), value: Number(d[valF] ?? 0) }))
        }))
      : data.map((d: any) => ({ name: String(d[lblF]), value: Number(d[valF] ?? 0) }))

    const root = d3.hierarchy({ name: 'root', children })
      .sum((d: any) => d.value ?? 0)
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))

    d3.treemap().size([W, H]).padding(2).paddingTop(grpF ? 18 : 2)(root)

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()

    const cell = svg.selectAll('g.leaf').data(root.leaves()).join('g').attr('class', 'leaf')
      .attr('transform', (d: any) => `translate(${d.x0},${d.y0})`)

    const colorScale = grpF
      ? d3.scaleOrdinal(AUTO_COLORS).domain([...new Set(data.map((d: any) => String(d[grpF])))])
      : d3.scaleOrdinal(AUTO_COLORS).domain(data.map((d: any) => String(d[lblF])))

    cell.append('rect')
      .attr('width', (d: any) => Math.max(0, d.x1 - d.x0))
      .attr('height', (d: any) => Math.max(0, d.y1 - d.y0))
      .attr('rx', 4)
      .attr('fill', (d: any) => colorScale(grpF ? String((d.parent?.data as any)?.name ?? '') : String((d.data as any)?.name ?? '')))
      .attr('fill-opacity', 0.85)
      .attr('stroke', '#fff').attr('stroke-width', 1)
      .style('cursor', 'pointer')
      .on('mouseover', function(this: any, event: any, d: any) {
        d3.select(this).attr('fill-opacity', 1).attr('stroke-width', 2).attr('stroke', '#374151')
        const pct = total > 0 ? ((d.value / total) * 100).toFixed(1) : '0'
        tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
          .html(`<b>${(d.data as any)?.name}</b><br/>${valF}: ${fmt(d.value ?? 0, vFmt)}<br/>${pct}% of total`)
      })
      .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
      .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 0.85).attr('stroke-width', 1).attr('stroke', '#fff'); tip.style('display', 'none') })

    cell.append('text')
      .attr('x', 6).attr('y', 16).attr('font-size', 11).attr('fill', '#fff').attr('font-weight', 600)
      .style('pointer-events', 'none')
      .text((d: any) => {
        const w = (d.x1 - d.x0)
        const name = String((d.data as any)?.name ?? '')
        return w < 40 ? '' : name.length > Math.floor(w / 7) ? name.slice(0, Math.floor(w / 7) - 1) + '…' : name
      })
    cell.append('text')
      .attr('x', 6).attr('y', 29).attr('font-size', 10).attr('fill', 'rgba(255,255,255,0.75)')
      .style('pointer-events', 'none')
      .text((d: any) => (d.x1 - d.x0) < 50 ? '' : fmt(d.value ?? 0, vFmt))

    // Group header labels
    if (grpF) {
      svg.selectAll('g.grp-label').data(root.children ?? []).join('g').attr('class', 'grp-label')
        .attr('transform', (d: any) => `translate(${d.x0},${d.y0})`)
        .append('text').attr('x', 4).attr('y', 13).attr('font-size', 11).attr('font-weight', 700)
        .attr('fill', '#374151').text((d: any) => String((d.data as any)?.name ?? ''))
    }
    return () => { tip.remove() }
  }, [cfg])

  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Radar / Spider Chart ──────────────────────────────────────────────────────
function RadarChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const axes   = (cfg.axes ?? []) as string[]
    const series = (cfg.series ?? []) as any[]
    if (!axes.length || !series.length) return

    const W = ref.current.clientWidth || 400
    const SIZE = Math.min(W, 340)
    const cx = SIZE / 2, cy = SIZE / 2
    const R  = SIZE / 2 - 36
    const N  = axes.length
    const maxV = cfg.maxValue ?? d3.max(series.flatMap((s: any) => (s.values ?? []) as number[])) ?? 1

    const svg = d3.select(ref.current).attr('width', SIZE).attr('height', SIZE)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${cx},${cy})`)

    const angle = (i: number) => (Math.PI * 2 * i) / N - Math.PI / 2
    const polar = (r: number, i: number) => [r * Math.cos(angle(i)), r * Math.sin(angle(i))] as [number, number]

    // Grid rings
    [0.25, 0.5, 0.75, 1].forEach(t => {
      const pts = axes.map((_: string, i: number) => polar(R * t, i))
      g.append('polygon').attr('points', pts.map(p => p.join(',')).join(' '))
        .attr('fill', 'none').attr('stroke', '#E5E7EB').attr('stroke-width', 1)
    })
    // Spokes
    axes.forEach((_: string, i: number) => {
      const [px, py] = polar(R, i)
      g.append('line').attr('x1', 0).attr('y1', 0).attr('x2', px).attr('y2', py)
        .attr('stroke', '#E5E7EB').attr('stroke-width', 1)
    })
    // Axis labels
    axes.forEach((a: string, i: number) => {
      const [px, py] = polar(R + 16, i)
      g.append('text').attr('x', px).attr('y', py).attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('font-size', 11).attr('fill', '#6B7280').text(truncLabel(a, 12))
    })
    // Series polygons + interactive dots
    series.forEach((s: any, si: number) => {
      const color  = s.color ?? AUTO_COLORS[si % AUTO_COLORS.length]
      const values = (s.values ?? []) as number[]
      const pts    = values.map((v: number, i: number) => polar(R * (v / maxV), i))
      g.append('polygon').attr('points', pts.map(p => p.join(',')).join(' '))
        .attr('fill', color).attr('fill-opacity', 0.15).attr('stroke', color).attr('stroke-width', 2)
      pts.forEach(([px, py]: [number, number], i: number) => {
        g.append('circle').attr('cx', px).attr('cy', py).attr('r', 4.5).attr('fill', color)
          .attr('stroke', '#fff').attr('stroke-width', 1.5).style('cursor', 'pointer')
          .on('mouseover', function(this: any, event: any) {
            d3.select(this).attr('r', 7)
            tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
              .html(`<b>${s.label ?? 'Series ' + (si + 1)}</b><br/>${axes[i]}: ${fmt(values[i], ',.1f')}`)
          })
          .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
          .on('mouseleave', function(this: any) { d3.select(this).attr('r', 4.5); tip.style('display', 'none') })
      })
    })
    return () => { tip.remove() }
  }, [cfg])

  const series = (cfg.series ?? []) as any[]
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <svg ref={ref} style={{ display: 'block' }} />
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {series.map((s: any, i: number) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ width: 14, height: 3, borderRadius: 2, background: s.color ?? AUTO_COLORS[i % AUTO_COLORS.length] }} />
            <span style={{ fontSize: 11, color: '#6B7280' }}>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Waterfall Chart ───────────────────────────────────────────────────────────
function WaterfallChart({ cfg }: { cfg: any }) {
  const ref = useRef<SVGSVGElement>(null)
  useEffect(() => {
    if (!ref.current) return
    const tip    = makeTip()
    const raw    = (cfg.data ?? []) as any[]
    const lblF   = cfg.labelField ?? 'label'
    const valF   = cfg.valueField ?? 'value'
    const vFmt   = cfg.valueFormat ?? ',.0f'
    const posClr = cfg.positiveColor ?? '#22C55E'
    const negClr = cfg.negativeColor ?? '#EF4444'
    const totClr = cfg.totalColor    ?? '#0064D2'

    // Build cumulative positions
    let cum = 0
    const bars = raw.map((d: any, i: number) => {
      const v    = Number(d[valF] ?? 0)
      const isTotal = d.isTotal === true || d.isTotal === 'true'
      const start  = isTotal ? 0 : cum
      const end    = isTotal ? v : cum + v
      if (!isTotal) cum += v
      return { label: String(d[lblF] ?? ''), value: v, start, end, isTotal, i }
    })

    const allEnds = bars.flatMap(b => [b.start, b.end])
    const minV    = Math.min(0, d3.min(allEnds) ?? 0)
    const maxV    = Math.max(0, d3.max(allEnds) ?? 1)

    const W = ref.current.clientWidth || 500
    const H = 260
    const m = { top: 20, right: 16, bottom: 56, left: 56 }
    const iW = W - m.left - m.right
    const iH = H - m.top  - m.bottom

    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)

    const x = d3.scaleBand().domain(bars.map(b => b.label)).range([0, iW]).padding(0.3)
    const y = d3.scaleLinear().domain([minV * 1.08, maxV * 1.08]).range([iH, 0])

    g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW).tickFormat(() => '')).select('.domain').remove()
      .selectAll('.tick line').attr('stroke', '#F1F5F9')
    g.append('g').call(d3.axisLeft(y).ticks(5).tickFormat(v => fmt(v as number, vFmt))).select('.domain').remove()
      .selectAll('text').attr('font-size', 11).attr('fill', '#6B7280')
    g.append('g').attr('transform', `translate(0,${iH})`).call(d3.axisBottom(x).tickSize(0)
      .tickFormat((d: any) => truncLabel(String(d), 10)))
      .selectAll('text').attr('transform', 'rotate(-30)').style('text-anchor', 'end').attr('font-size', 10).attr('fill', '#9CA3AF')
    g.append('line').attr('x1', 0).attr('x2', iW).attr('y1', y(0)).attr('y2', y(0))
      .attr('stroke', '#9CA3AF').attr('stroke-width', 1).attr('stroke-dasharray', '3,3')

    bars.forEach((b, i) => {
      const bx = x(b.label)!
      const bw = x.bandwidth()
      const top    = y(Math.max(b.start, b.end))
      const bottom = y(Math.min(b.start, b.end))
      const height = Math.max(2, bottom - top)
      const color  = b.isTotal ? totClr : b.value >= 0 ? posClr : negClr

      g.append('rect').attr('x', bx).attr('width', bw).attr('rx', 3)
        .attr('fill', color).style('cursor', 'pointer')
        .on('mouseover', function(this: any, event: any) {
          d3.select(this).attr('fill-opacity', 0.75)
          const typeLabel = b.isTotal ? 'Total' : b.value >= 0 ? 'Increase' : 'Decrease'
          tip.style('display', 'block').style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`)
            .html(`<b>${b.label}</b><br/>${typeLabel}: ${(b.value >= 0 ? '+' : '') + fmt(b.value, vFmt)}<br/>Running: ${fmt(b.end, vFmt)}`)
        })
        .on('mousemove', (event: any) => tip.style('left', `${event.clientX + 14}px`).style('top', `${event.clientY - 10}px`))
        .on('mouseleave', function(this: any) { d3.select(this).attr('fill-opacity', 1); tip.style('display', 'none') })
        .attr('y', top + height).attr('height', 0)
        .transition().duration(400).attr('y', top).attr('height', height)

      // Connector to next bar
      if (i < bars.length - 1 && !bars[i + 1].isTotal) {
        g.append('line')
          .attr('x1', bx + bw).attr('x2', x(bars[i + 1].label)!)
          .attr('y1', y(b.end)).attr('y2', y(b.end))
          .attr('stroke', '#D1D5DB').attr('stroke-width', 1).attr('stroke-dasharray', '3,3')
      }

      g.append('text')
        .attr('x', bx + bw / 2).attr('y', top - 4)
        .attr('text-anchor', 'middle').attr('font-size', 10).attr('fill', '#6B7280')
        .style('pointer-events', 'none')
        .text((b.value >= 0 ? '+' : '') + fmt(b.value, vFmt))
    })
    return () => { tip.remove() }
  }, [cfg])

  return <svg ref={ref} style={{ width: '100%', display: 'block' }} />
}

// ── Chart panel router ────────────────────────────────────────────────────────
function ChartPanelInner({ cfg }: { cfg: any }) {
  const type = (cfg.type ?? '').toLowerCase()
  switch (type) {
    case 'bar':          return <BarChart cfg={cfg} />
    case 'stacked-bar':  return <StackedBarChart cfg={cfg} />
    case 'line':         return <LineChart cfg={cfg} />
    case 'donut':
    case 'pie':          return <DonutChart cfg={cfg} />
    case 'area':         return <AreaChart cfg={cfg} />
    case 'grouped-bar':  return <GroupedBarChart cfg={cfg} />
    case 'scatter':      return <ScatterChart cfg={cfg} />
    case 'bubble':       return <BubbleChart cfg={cfg} />
    case 'histogram':    return <HistogramChart cfg={cfg} />
    case 'heatmap':      return <HeatmapChart cfg={cfg} />
    case 'treemap':      return <TreemapChart cfg={cfg} />
    case 'radar':        return <RadarChart cfg={cfg} />
    case 'waterfall':    return <WaterfallChart cfg={cfg} />
    default:             return <div style={{ color: '#9CA3AF', fontSize: 13 }}>Unknown chart type: {cfg.type}</div>
  }
}

function ChartPanel({ cfg }: { cfg: any }) {
  const [data, setData] = useState<any[] | null>(cfg.data ?? null)
  const [loading, setLoading] = useState(!cfg.data && !!cfg.tableName)

  useEffect(() => {
    if (cfg.data || !cfg.tableName) return
    fetch(`${_API}/api/data/${cfg.tableName}?limit=500`)
      .then(r => r.json())
      .then(j => { setData(j.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [cfg.tableName, cfg.data])

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><div style={{ width: 24, height: 24, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /></div>
  const rawData = data ?? cfg.data ?? []
  const pivoted = pivotData(rawData, cfg)
  const final = aggregateSimple(pivoted, cfg)
  return <ChartPanelInner cfg={{ ...cfg, data: final }} />
}

// ── Stats summary ─────────────────────────────────────────────────────────────
function StatBar({ cfg }: { cfg: any }) {
  const data   = (cfg.data ?? []) as any[]
  const valFld = cfg.valueField ?? cfg.series?.[0]?.field ?? cfg.yField
  if (!valFld) return null
  const vals  = data.map((r: any) => Number(r[valFld] ?? 0))
  const total = vals.reduce((a, b) => a + b, 0)
  const avg   = vals.length ? total / vals.length : 0
  const min   = vals.length ? Math.min(...vals) : 0
  const max   = vals.length ? Math.max(...vals) : 0
  const vFmt  = cfg.valueFormat ?? cfg.yFormat ?? ',.1f'

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
      {[{ l: 'Total', v: fmt(total, vFmt) }, { l: 'Avg', v: fmt(avg, vFmt) }, { l: 'Min', v: fmt(min, vFmt) }, { l: 'Max', v: fmt(max, vFmt) }].map(st => (
        <div key={st.l} style={{ flex: '1 1 80px', background: '#F8FAFC', borderRadius: 8, padding: '10px 14px', border: '1px solid #F1F5F9' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{st.l}</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#374151', marginTop: 2 }}>{st.v}</div>
        </div>
      ))}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ChartsPage() {
  const {
    chartType = 'bar',
    pageTitle,
    pageSubtitle,
    filterField,
    filterOptions = [],
    charts,        // for 'multi' mode
    layout,        // 'grid' (default) | 'tabs' — controls multi mode rendering
    tableName,     // API table name — when set, data is fetched from /api/data/{tableName}
    ...singleCfg   // all other fields passed directly to single-chart mode
  } = config as any

  const [filter,    setFilter]    = useState('All')
  const [activeTab, setActiveTab] = useState(0)
  const [apiData,   setApiData]   = useState<any[] | null>(null)
  const [loading,   setLoading]   = useState(!!tableName)

  useEffect(() => {
    if (!tableName) return
    fetch(`${_API}/api/data/${tableName}?limit=500`)
      .then(r => r.json())
      .then(j => { setApiData(j.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tableName])

  const singleData = useMemo(() => {
    const raw = (apiData ?? singleCfg.data ?? []) as any[]
    if (!filterField || filter === 'All') return raw
    return raw.filter((r: any) => String(r[filterField]) === filter)
  }, [filter, apiData, singleCfg.data, filterField])

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  const filteredCfg = { ...singleCfg, type: chartType, data: singleData }

  // Charts that don't need a stats bar (no single numeric valueField)
  const NO_STAT_BAR = new Set(['scatter', 'bubble', 'histogram', 'heatmap', 'treemap', 'radar', 'waterfall', 'grouped-bar', 'stacked-bar', 'multi'])

  const s = {
    page: { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    card: { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    h1:   { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 16 },
  }

  return (
    <div style={s.page}>
      <div>
        <h1 style={s.h1}>{pageTitle}</h1>
        {pageSubtitle && <p style={{ margin: '4px 0 0', fontSize: 14, color: '#6B7280' }}>{pageSubtitle}</p>}
      </div>

      {filterField && chartType !== 'multi' && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: '#6B7280' }}>Filter:</span>
          <select
            style={{ height: 36, padding: '0 10px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13 }}
            value={filter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setFilter(e.target.value)}
          >
            <option value="All">All</option>
            {(filterOptions as string[]).map((o: string) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      )}

      {chartType === 'multi' ? (
        layout === 'tabs' ? (
          /* ── Tabbed layout ──────────────────────────────────────────────── */
          <div style={s.card}>
            {/* Tab bar */}
            <div style={{ display: 'flex', gap: 4, borderBottom: '2px solid #E5E7EB', marginBottom: 20, flexWrap: 'wrap' }}>
              {((charts ?? []) as any[]).map((c: any, i: number) => (
                <button
                  key={i}
                  onClick={() => setActiveTab(i)}
                  style={{
                    padding: '8px 18px', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer',
                    borderRadius: '8px 8px 0 0', transition: 'all 0.15s',
                    background: activeTab === i ? '#fff' : 'transparent',
                    color: activeTab === i ? '#0064D2' : '#6B7280',
                    borderBottom: activeTab === i ? '2px solid #0064D2' : '2px solid transparent',
                    marginBottom: -2,
                  }}
                >
                  {c.title}
                </button>
              ))}
            </div>
            {/* Active panel */}
            {((charts ?? []) as any[])[activeTab] && (
              <ChartPanel cfg={((charts ?? []) as any[])[activeTab]} />
            )}
          </div>
        ) : (
          /* ── Grid layout (default) ──────────────────────────────────────── */
          <div style={s.grid}>
            {((charts ?? []) as any[]).map((c: any, i: number) => (
              <div key={i} style={s.card}>
                <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#374151' }}>{c.title}</h3>
                <ChartPanel cfg={c} />
              </div>
            ))}
          </div>
        )
      ) : (
        <>
          {!NO_STAT_BAR.has(chartType) && <StatBar cfg={filteredCfg} />}
          <div style={s.card}>
            <ChartPanel cfg={filteredCfg} />
          </div>
          {filteredCfg.data?.length > 0 && filteredCfg.labelField && filteredCfg.valueField && !NO_STAT_BAR.has(chartType) && (
            <div style={s.card}>
              <h3 style={{ margin: '0 0 14px', fontSize: 14, fontWeight: 700, color: '#374151' }}>Data</h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' as const }}>
                  <thead>
                    <tr>
                      {[filteredCfg.labelField, filteredCfg.valueField].map((h: string) => (
                        <th key={h} style={{ padding: '8px 12px', textAlign: 'left' as const, fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' as const, borderBottom: '2px solid #E5E7EB' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(filteredCfg.data as any[]).slice(0, 25).map((r: any, i: number) => (
                      <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#FAFAFA' }}>
                        <td style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', fontWeight: 500 }}>{r[filteredCfg.labelField]}</td>
                        <td style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', fontVariantNumeric: 'tabular-nums' }}>{fmt(Number(r[filteredCfg.valueField] ?? 0), filteredCfg.valueFormat ?? ',.1f')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
