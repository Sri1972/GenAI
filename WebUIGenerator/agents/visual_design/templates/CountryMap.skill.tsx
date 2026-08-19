// @ts-nocheck
/**
 * CountryMap.skill.tsx — Sub-national choropleth map for ANY country.
 *
 * Domain-agnostic — reads all config from src/config/CountryMap.config.ts
 * Works for: India states, UK regions, Germany Bundesländer, Brazil estados,
 * France régions, Canada provinces, Australia states, Japan prefectures, etc.
 *
 * The GeoJSON URL in config points to a public file with admin-1 boundaries.
 * The regionNameProp tells us which property in the GeoJSON holds the region name.
 * The regionField tells us which column in YOUR data to match against.
 */
import { useState, useEffect, useRef, useMemo } from 'react'
import React from 'react'
import * as d3 from 'd3'
import { config } from '../config/CountryMap.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

// ── Colour palettes ───────────────────────────────────────────────────────────
const COLOR_SCHEMES: Record<string, string[]> = {
  blue:   [...(d3.schemeBlues[9]   as readonly string[])],
  green:  [...(d3.schemeGreens[9]  as readonly string[])],
  orange: [...(d3.schemeOranges[9] as readonly string[])],
  purple: [...(d3.schemePurples[9] as readonly string[])],
  red:    [...(d3.schemeReds[9]    as readonly string[])],
}

function fmt(n: number, f = ',.1f') {
  try { return d3.format(f)(n) } catch { return String(n) }
}

// ── Region drilldown panel ────────────────────────────────────────────────────
function RegionDrilldown({
  feature, name, val, valueField, valueFmt, onClose,
}: {
  feature: any; name: string; val: number | null; valueField: string; valueFmt: string; onClose: () => void
}) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current || !feature) return
    const W = ref.current.clientWidth || 340
    const H = 200
    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', '#EFF6FF').attr('rx', 8)

    const proj = d3.geoMercator().fitExtent([[12, 12], [W - 12, H - 12]], feature)
    const path = d3.geoPath().projection(proj)
    svg.append('path')
      .datum(feature)
      .attr('d', path as any)
      .attr('fill', '#0064D2')
      .attr('fill-opacity', 0.18)
      .attr('stroke', '#0064D2')
      .attr('stroke-width', 2)
  }, [feature])

  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#0D1B2A' }}>{name}</div>
          {val != null && (
            <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2 }}>
              {valueField}: <span style={{ fontWeight: 700, color: '#0064D2' }}>{fmt(val, valueFmt)}</span>
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          style={{ fontSize: 12, color: '#6B7280', background: 'none', border: '1px solid #E5E7EB', borderRadius: 6, padding: '4px 12px', cursor: 'pointer' }}
        >
          ✕ Close
        </button>
      </div>
      <svg ref={ref} style={{ width: '100%', display: 'block', borderRadius: 6 }} />
    </div>
  )
}

export default function CountryMapPage() {
  const {
    dataExport,
    tableName,
    countryName,
    geoJsonUrl,
    regionNameProp,
    regionField,
    valueField,
    labelField,
    title,
    colorScheme = 'blue',
    filterField = null,
    valueFormat = ',.1f',
  } = config as any

  // ── API data fetch ──────────────────────────────────────────────────────────
  const [apiData, setApiData] = useState<any[] | null>(null)
  const [apiLoading, setApiLoading] = useState(!!tableName)

  useEffect(() => {
    if (!tableName) return
    fetch(`${_API}/api/data/${tableName}?limit=5000`)
      .then(r => r.json())
      .then(j => { setApiData(j.data || []); setApiLoading(false) })
      .catch(() => setApiLoading(false))
  }, [tableName])

  const allRows: any[] = apiData ?? dataExport ?? []

  // ── GeoJSON fetch ───────────────────────────────────────────────────────────
  const svgRef = useRef<SVGSVGElement>(null)
  const [geo, setGeo] = useState<any>(null)
  const [geoError, setGeoError] = useState(false)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; html: string } | null>(null)
  const [filter, setFilter] = useState('All')
  const [selectedRegion, setSelectedRegion] = useState<{ feature: any; name: string; val: number | null } | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(geoJsonUrl)
      .then(r => r.json())
      .then(data => {
        if (cancelled) return
        // Handle both TopoJSON and GeoJSON formats
        if (data.type === 'Topology') {
          // TopoJSON — convert first object to GeoJSON
          const topojson = require('topojson-client')
          const key = Object.keys(data.objects)[0]
          setGeo(topojson.feature(data, data.objects[key]))
        } else {
          setGeo(data)
        }
      })
      .catch(() => { if (!cancelled) setGeoError(true) })
    return () => { cancelled = true }
  }, [geoJsonUrl])

  // ── Filtered data ───────────────────────────────────────────────────────────
  const filteredData = useMemo<any[]>(() => {
    if (!filterField || filter === 'All') return allRows
    return allRows.filter((r: any) => String(r[filterField]) === filter)
  }, [filter, allRows])

  // ── Value lookup: normalised region name → total ────────────────────────────
  const valueByRegion = useMemo<Record<string, number>>(() => {
    const m: Record<string, number> = {}
    for (const row of filteredData) {
      const key = String(row[regionField] ?? '').toLowerCase().trim()
      const val = Number(row[valueField] ?? 0)
      if (key) m[key] = (m[key] ?? 0) + val
    }
    return m
  }, [filteredData])

  const filterOptions = useMemo<string[]>(() => {
    if (!filterField) return []
    const s = new Set<string>()
    for (const r of allRows) s.add(String(r[filterField]))
    return [...s].sort()
  }, [allRows])

  const values = Object.values(valueByRegion)
  const maxVal = values.length ? Math.max(...values) : 1
  const totalVal = values.reduce((a, b) => a + b, 0)
  const regionCount = Object.keys(valueByRegion).length

  const palette = COLOR_SCHEMES[colorScheme as string] ?? COLOR_SCHEMES.blue
  const colorScale = useMemo(
    () => d3.scaleQuantize<string>().domain([0, maxVal]).range(palette),
    [maxVal, palette]
  )

  // ── Name matching helper ────────────────────────────────────────────────────
  function getGeoRegionName(feature: any): string {
    const props = feature.properties ?? {}
    // Try the configured property first, then common fallbacks
    const candidates = [regionNameProp, 'NAME_1', 'name', 'NAME', 'admin', 'state', 'region', 'provincia', 'nom']
    for (const key of candidates) {
      if (props[key]) return props[key]
    }
    return ''
  }

  function matchValue(feature: any): number | null {
    const name = getGeoRegionName(feature).toLowerCase().trim()
    if (!name) return null
    // Exact match
    if (valueByRegion[name] != null) return valueByRegion[name]
    // Partial match (handles "Maharashtra" matching "maharashtra" in data)
    for (const [key, val] of Object.entries(valueByRegion)) {
      if (name.includes(key) || key.includes(name)) return val
    }
    return null
  }

  // ── Draw map ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!geo || !svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const W = svgRef.current.clientWidth || 900
    const H = svgRef.current.clientHeight || 500

    // Fit projection to the full extent of the GeoJSON
    const proj = d3.geoMercator().fitExtent([[20, 20], [W - 20, H - 20]], geo)
    const path = d3.geoPath().projection(proj)

    // Background
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', '#F0F5FF').attr('rx', 8)

    // Regions
    const features: any[] = geo.features ?? []
    svg.selectAll('path.region')
      .data(features)
      .join('path')
      .attr('class', 'region')
      .attr('d', path as any)
      .attr('fill', (d: any) => {
        const val = matchValue(d)
        return val != null ? colorScale(val) : '#D1D5DB'
      })
      .attr('stroke', (d: any) => {
        const name = getGeoRegionName(d)
        return selectedRegion?.name === name ? '#003F8A' : '#fff'
      })
      .attr('stroke-width', (d: any) => {
        const name = getGeoRegionName(d)
        return selectedRegion?.name === name ? 2.5 : 0.6
      })
      .style('cursor', 'pointer')
      .on('click', function(this: SVGPathElement, event: MouseEvent, d: any) {
        const name = getGeoRegionName(d)
        if (!name) return
        const val = matchValue(d)
        setSelectedRegion(prev =>
          prev?.name === name ? null : { feature: d, name, val }
        )
        setTooltip(null)
      })
      .on('mouseover', function(this: SVGPathElement, event: MouseEvent, d: any) {
        const name = getGeoRegionName(d)
        const isSelected = selectedRegion?.name === name
        if (!isSelected) d3.select(this).raise().attr('stroke', '#374151').attr('stroke-width', 1.5)
        const val = matchValue(d)
        const text = val != null ? fmt(val, valueFormat) : 'No data'
        setTooltip({ x: event.clientX, y: event.clientY - 10, html: `<b>${name}</b><br/>${valueField}: ${text}` })
      })
      .on('mousemove', function(this: SVGPathElement, event: MouseEvent) {
        setTooltip((t: any) => t ? { ...t, x: event.clientX, y: event.clientY - 10 } : t)
      })
      .on('mouseleave', function(this: SVGPathElement, event: MouseEvent, d: any) {
        const name = getGeoRegionName(d)
        const isSelected = selectedRegion?.name === name
        d3.select(this)
          .attr('stroke', isSelected ? '#003F8A' : '#fff')
          .attr('stroke-width', isSelected ? 2.5 : 0.6)
        setTooltip(null)
      })

    // Region labels for larger regions (skip tiny ones)
    const labelThreshold = (W * H) / 5000
    svg.selectAll('text.label')
      .data(features.filter((d: any) => {
        const bounds = path.bounds(d)
        const area = (bounds[1][0] - bounds[0][0]) * (bounds[1][1] - bounds[0][1])
        return area > labelThreshold
      }))
      .join('text')
      .attr('class', 'label')
      .attr('transform', (d: any) => {
        const [cx, cy] = path.centroid(d)
        return `translate(${cx},${cy})`
      })
      .attr('text-anchor', 'middle')
      .attr('font-size', 9)
      .attr('font-weight', 600)
      .attr('fill', '#374151')
      .attr('pointer-events', 'none')
      .text((d: any) => {
        const name = getGeoRegionName(d)
        return name.length > 12 ? name.slice(0, 10) + '…' : name
      })
  }, [geo, valueByRegion, colorScale, selectedRegion])

  // ── Top regions table ───────────────────────────────────────────────────────
  const topRegions = useMemo(() => {
    return Object.entries(valueByRegion)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, val]) => ({
        name: name.replace(/\b\w/g, c => c.toUpperCase()),
        val,
      }))
  }, [valueByRegion])

  // ── Styles ──────────────────────────────────────────────────────────────────
  const s = {
    page:    { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    card:    { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    heading: { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    sub:     { fontSize: 13, color: '#6B7280', marginTop: 4 },
    kpiRow:  { display: 'flex', gap: 16, flexWrap: 'wrap' as const },
    kpiCard: { flex: '1 1 120px', background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '14px 18px' },
    kpiLbl:  { fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' as const, letterSpacing: '0.05em' },
    kpiVal:  { fontSize: 22, fontWeight: 700, color: '#0D1B2A', marginTop: 4 },
  }

  if (apiLoading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
      <div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )

  return (
    <div style={s.page}>
      <div>
        <h1 style={s.heading}>{title}</h1>
        <p style={s.sub}>{countryName} — sub-national breakdown by {valueField}</p>
      </div>

      {filterField && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: '#6B7280' }}>Filter:</span>
          <select
            style={{ height: 36, padding: '0 10px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13 }}
            value={filter}
            onChange={(e: any) => setFilter(e.target.value)}
          >
            <option value="All">All</option>
            {filterOptions.map((o: string) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      )}

      <div style={s.kpiRow}>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Regions</div><div style={s.kpiVal}>{regionCount}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Total</div><div style={s.kpiVal}>{fmt(totalVal, valueFormat)}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Highest</div><div style={s.kpiVal}>{fmt(maxVal, valueFormat)}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Data Rows</div><div style={s.kpiVal}>{filteredData.length}</div></div>
      </div>

      <div style={s.card}>
        <div style={{ position: 'relative', borderRadius: 8 }}>
          <svg
            ref={svgRef}
            style={{ width: '100%', height: 500, display: 'block' }}
          />
          {!geo && !geoError && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF', background: '#F0F5FF', borderRadius: 8 }}>
              Loading {countryName} map…
            </div>
          )}
          {geoError && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center', color: '#9CA3AF', gap: 8 }}>
              <span style={{ fontSize: 32 }}>🗺</span>
              <span>Map could not load — showing data table only</span>
            </div>
          )}
          {tooltip && (
            <div style={{
              position: 'fixed', left: tooltip.x + 14, top: tooltip.y,
              background: 'rgba(15,23,42,0.92)', color: '#fff',
              padding: '8px 12px', borderRadius: 8, fontSize: 12,
              pointerEvents: 'none', zIndex: 99999, maxWidth: 220,
            }} dangerouslySetInnerHTML={{ __html: tooltip.html }} />
          )}
        </div>

        {/* Colour legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 14 }}>
          <span style={{ fontSize: 11, color: '#9CA3AF' }}>Low</span>
          <div style={{ display: 'flex', height: 12, borderRadius: 4, overflow: 'hidden', flex: 1, maxWidth: 220 }}>
            {palette.map((c: string, i: number) => <div key={i} style={{ flex: 1, background: c }} />)}
          </div>
          <span style={{ fontSize: 11, color: '#9CA3AF' }}>High</span>
          <span style={{ fontSize: 11, color: '#9CA3AF', marginLeft: 12 }}>
            No data: <span style={{ color: '#D1D5DB', fontWeight: 700 }}>■</span>
          </span>
        </div>
      </div>

      {selectedRegion && (
        <RegionDrilldown
          feature={selectedRegion.feature}
          name={selectedRegion.name}
          val={selectedRegion.val}
          valueField={valueField}
          valueFmt={valueFormat}
          onClose={() => setSelectedRegion(null)}
        />
      )}

      {topRegions.length > 0 && (
        <div style={s.card}>
          <h3 style={{ margin: '0 0 14px', fontSize: 14, fontWeight: 700, color: '#374151' }}>
            Top {topRegions.length} Regions — {valueField}
          </h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' as const }}>
            <thead>
              <tr>
                {['#', 'Region / State', valueField].map((h: string) => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: h === '#' ? 'center' as const : 'left' as const, fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' as const, borderBottom: '2px solid #E5E7EB' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {topRegions.map((row: { name: string; val: number }, i: number) => (
                <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#FAFAFA' }}>
                  <td style={{ padding: '8px 12px', textAlign: 'center' as const, fontSize: 13, color: '#9CA3AF', borderBottom: '1px solid #F1F5F9' }}>{i + 1}</td>
                  <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 500, color: '#374151', borderBottom: '1px solid #F1F5F9' }}>{row.name}</td>
                  <td style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.val, valueFormat)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export { CountryMapPage }
