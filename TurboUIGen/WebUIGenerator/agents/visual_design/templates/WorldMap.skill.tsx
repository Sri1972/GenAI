// @ts-nocheck
/**
 * WorldMap.skill.tsx — Generic D3 world/regional choropleth map.
 *
 * Domain-agnostic — reads all config from src/config/WorldMap.config.ts
 * Works for: global sales, population, climate data, elections, any country-level metric.
 *
 * Region support — set config.region to zoom to any area:
 *   'world' | 'europe' | 'asia' | 'north-america' | 'south-america' | 'americas'
 *   | 'africa' | 'middle-east' | 'southeast-asia' | 'oceania'
 */
import { useState, useEffect, useRef, useMemo } from 'react'
import React from 'react'
import * as d3 from 'd3'
import { config } from '../config/WorldMap.config'
import { ExportToolbar } from '../components/ExportToolbar'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

// ── Colour palettes ───────────────────────────────────────────────────────────
const COLOR_SCHEMES: Record<string, string[]> = {
  blue:   [...(d3.schemeBlues[9]   as readonly string[])],
  green:  [...(d3.schemeGreens[9]  as readonly string[])],
  orange: [...(d3.schemeOranges[9] as readonly string[])],
  purple: [...(d3.schemePurples[9] as readonly string[])],
  red:    [...(d3.schemeReds[9]    as readonly string[])],
}

// ── Region bounding boxes [west, south, east, north] ─────────────────────────
const REGION_BOUNDS: Record<string, [number, number, number, number]> = {
  'world':          [-180, -85,  180,  85],
  'europe':         [ -25,  34,   45,  72],
  'asia':           [  24,  -5,  150,  75],
  'north-america':  [-170,   7,  -52,  85],
  'south-america':  [ -85, -60,  -30,  15],
  'americas':       [-170, -60,  -30,  85],
  'africa':         [ -20, -40,   55,  40],
  'middle-east':    [  25,  12,   65,  43],
  'southeast-asia': [  92, -12,  142,  30],
  'oceania':        [ 110, -50,  180,  10],
}

function fmt(n: number, f = ',.1f') {
  try { return d3.format(f)(n) } catch { return String(n) }
}

const GEO_URL = 'https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson'

// GeoJSON name → normalised lowercase data name
// Covers holtzy/D3-graph-gallery GeoJSON (short names like 'usa', 'england')
// AND standard long-form GeoJSON names as fallbacks
const GEO_NAME_MAP: Record<string, string> = {
  // Holtzy GeoJSON actual names (what the map file really contains)
  'usa':                              'united states',
  'england':                          'united kingdom',
  'republic of serbia':               'serbia',
  'democratic republic of the congo': 'dr congo',
  'republic of the congo':            'congo',
  'united republic of tanzania':      'tanzania',
  'the bahamas':                      'bahamas',
  'east timor':                       'timor-leste',
  'swaziland':                        'eswatini',
  // Standard/alternative GeoJSON long-form names
  'united states of america':         'united states',
  'great britain':                    'united kingdom',
  'britain':                          'united kingdom',
  'russian federation':               'russia',
  'korea, republic of':               'south korea',
  'republic of korea':                'south korea',
  "democratic people's republic of korea": 'north korea',
  'iran, islamic republic of':        'iran',
  'syrian arab republic':             'syria',
  'viet nam':                         'vietnam',
  "côte d'ivoire":                    'ivory coast',
  'taiwan, province of china':        'taiwan',
  'bolivia, plurinational state of':  'bolivia',
  'venezuela, bolivarian republic of':'venezuela',
}

// ── Country drilldown panel ───────────────────────────────────────────────────
function CountryDrilldown({
  feature, name, val, valueField, valueFmt, onClose,
}: {
  feature: any; name: string; val: number | null; valueField: string; valueFmt: string; onClose: () => void
}) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current || !feature) return
    const W = ref.current.clientWidth || 340
    const H = 220
    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', '#EFF6FF').attr('rx', 8)

    const proj = d3.geoMercator().fitExtent([[16, 16], [W - 16, H - 16]], feature)
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

export default function WorldMapPage() {
  const {
    dataExport,
    tableName,
    countryCodeField,
    valueField,
    labelField,
    title,
    colorScheme = 'blue',
    filterField = null,
    region = 'world',
  } = config as any

  const [apiData, setApiData] = useState<any[] | null>(null)
  const [apiLoading, setApiLoading] = useState(!!tableName)

  useEffect(() => {
    if (!tableName) return
    fetch(`${_API}/api/data/${tableName}?limit=1000`)
      .then(r => r.json())
      .then(j => { setApiData(j.data || []); setApiLoading(false) })
      .catch(() => setApiLoading(false))
  }, [tableName])

  const allRows: any[] = apiData ?? dataExport ?? []

  const svgRef  = useRef<SVGSVGElement>(null)
  const [geo,      setGeo]      = useState<any>(null)
  const [geoError, setGeoError] = useState(false)
  const [tooltip,  setTooltip]  = useState<{ x: number; y: number; html: string } | null>(null)
  const [filter,   setFilter]   = useState('All')
  const [selectedCountry, setSelectedCountry] = useState<{ feature: any; name: string; val: number | null } | null>(null)

  // Filtered rows
  const filteredData = useMemo<any[]>(() => {
    if (!filterField || filter === 'All') return allRows
    return allRows.filter((r: any) => String(r[filterField]) === filter)
  }, [filter, allRows])

  // value lookup: ISO-2 code → total, country name (lower) → total
  const valueByCode = useMemo<Record<string, number>>(() => {
    const m: Record<string, number> = {}
    for (const row of filteredData) {
      const code  = String(row[countryCodeField] ?? '').toUpperCase()
      const lname = String(row[labelField]       ?? '').toLowerCase()
      const val   = Number(row[valueField]        ?? 0)
      if (code)  m[code]  = (m[code]  ?? 0) + val
      if (lname) m[lname] = (m[lname] ?? 0) + val
    }
    return m
  }, [filteredData])

  const filterOptions = useMemo<string[]>(() => {
    if (!filterField) return []
    const s = new Set<string>()
    for (const r of allRows) s.add(String(r[filterField]))
    return [...s].sort()
  }, [allRows])

  const values   = Object.values(valueByCode)
  const maxVal   = values.length ? Math.max(...values) : 1
  const totalVal = values.reduce((a, b) => a + b, 0)
  const topEntry: any = filteredData.length
    ? [...filteredData].sort((a, b) => Number(b[valueField]) - Number(a[valueField]))[0]
    : null

  const palette    = COLOR_SCHEMES[colorScheme as string] ?? COLOR_SCHEMES.blue
  const colorScale = useMemo(
    () => d3.scaleQuantize<string>().domain([0, maxVal]).range(palette),
    [maxVal, palette]
  )

  // Fetch GeoJSON once
  useEffect(() => {
    let cancelled = false
    fetch(GEO_URL)
      .then(r => r.json())
      .then(data => { if (!cancelled) setGeo(data) })
      .catch(() => { if (!cancelled) setGeoError(true) })
    return () => { cancelled = true }
  }, [])

  // Draw / redraw map whenever data or geo changes
  useEffect(() => {
    if (!geo || !svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const W = svgRef.current.clientWidth  || 900
    const H = svgRef.current.clientHeight || 460

    const regionKey  = String(region ?? 'world')
    const isWorld    = regionKey === 'world'
    let proj: d3.GeoProjection

    if (isWorld) {
      proj = d3.geoNaturalEarth1().scale(148).translate([W / 2, H / 2])
    } else {
      const bounds = REGION_BOUNDS[regionKey] ?? REGION_BOUNDS['world']
      const [west, south, east, north] = bounds
      // Inline bounding polygon — avoids needing @types/geojson
      const boundsPoly = {
        type: 'Feature' as const,
        geometry: {
          type: 'Polygon' as const,
          coordinates: [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
        },
        properties: {},
      }
      proj = d3.geoMercator().fitExtent([[20, 20], [W - 20, H - 20]], boundsPoly as any)
    }

    const path = d3.geoPath().projection(proj)

    // Ocean background
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', '#E8F0FE').attr('rx', 8)

    // Graticule
    svg.append('path')
      .datum(d3.geoGraticule().step([10, 10])())
      .attr('d', path as any)
      .attr('fill', 'none')
      .attr('stroke', '#C7D6F5')
      .attr('stroke-width', 0.3)

    // Countries
    const features: any[] = (geo as any).features ?? []
    svg.selectAll('path.country')
      .data(features)
      .join('path')
      .attr('class', 'country')
      .attr('d', path as any)
      .attr('fill', (d: any) => {
        const props    = d.properties ?? {}
        const geoName  = (props.name ?? props.NAME ?? props.admin ?? '').toLowerCase()
        const normName = GEO_NAME_MAP[geoName] ?? geoName
        const raw      = valueByCode[normName] ?? valueByCode[geoName]
        return raw != null ? colorScale(raw as number) : '#D1D5DB'
      })
      .attr('stroke', (d: any) => {
        const props = d.properties ?? {}
        const name  = props.name ?? props.NAME ?? props.admin ?? ''
        return selectedCountry?.name === name ? '#003F8A' : '#fff'
      })
      .attr('stroke-width', (d: any) => {
        const props = d.properties ?? {}
        const name  = props.name ?? props.NAME ?? props.admin ?? ''
        return selectedCountry?.name === name ? 2.5 : 0.5
      })
      .style('cursor', 'pointer')
      .on('click', function(this: SVGPathElement, event: MouseEvent, d: any) {
        const props    = d.properties ?? {}
        const name     = props.name ?? props.NAME ?? props.admin ?? ''
        const geoName  = name.toLowerCase()
        const normName = GEO_NAME_MAP[geoName] ?? geoName
        const raw      = valueByCode[normName] ?? valueByCode[geoName]
        if (!name) return
        setSelectedCountry(prev =>
          prev?.name === name ? null : { feature: d, name, val: raw != null ? raw as number : null }
        )
        setTooltip(null)
      })
      .on('mouseover', function(this: SVGPathElement, event: MouseEvent, d: any) {
        const props      = d.properties ?? {}
        const name       = props.name ?? props.NAME ?? props.admin ?? ''
        const isSelected = selectedCountry?.name === name
        if (!isSelected) d3.select(this).raise().attr('stroke', '#374151').attr('stroke-width', 1.5)
        const geoName  = name.toLowerCase()
        const normName = GEO_NAME_MAP[geoName] ?? geoName
        const raw      = valueByCode[normName] ?? valueByCode[geoName]
        const text     = raw != null ? fmt(raw as number) : 'No data'
        setTooltip({ x: event.clientX, y: event.clientY - 10, html: `<b>${name}</b><br/>${valueField}: ${text}` })
      })
      .on('mousemove', function(this: SVGPathElement, event: MouseEvent) {
        setTooltip((t: any) => t ? { ...t, x: event.clientX, y: event.clientY - 10 } : t)
      })
      .on('mouseleave', function(this: SVGPathElement, event: MouseEvent, d: any) {
        const props = d.properties ?? {}
        const name  = props.name ?? props.NAME ?? props.admin ?? ''
        const isSelected = selectedCountry?.name === name
        d3.select(this)
          .attr('stroke', isSelected ? '#003F8A' : '#fff')
          .attr('stroke-width', isSelected ? 2.5 : 0.5)
        setTooltip(null)
      })
  }, [geo, valueByCode, colorScale, region, selectedCountry])

  // Top entries table
  const top10 = useMemo(() => {
    // valueByCode has two kinds of keys: numeric codes ("840") and lowercase names ("united states").
    // Keep only the name entries (non-numeric, length > 2), title-case them, sort by value.
    return Object.entries(valueByCode)
      .filter(([k]) => isNaN(Number(k)) && k === k.toLowerCase())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, val]) => ({
        name: name.replace(/\b\w/g, c => c.toUpperCase()),
        val,
      }))
  }, [valueByCode])

  const isWorldRegion = !region || region === 'world'

  // ── Styles ────────────────────────────────────────────────────────────────
  const s = {
    page:    { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    card:    { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    heading: { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    kpiRow:  { display: 'flex', gap: 16, flexWrap: 'wrap' as const },
    kpiCard: { flex: '1 1 120px', background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '14px 18px' },
    kpiLbl:  { fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' as const, letterSpacing: '0.05em' },
    kpiVal:  { fontSize: 22, fontWeight: 700, color: '#0D1B2A', marginTop: 4 },
  }

  if (apiLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  return (
    <div style={s.page}>
      <div><h1 style={s.heading}>{title}</h1></div>

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
        <div style={s.kpiCard}><div style={s.kpiLbl}>Entries</div><div style={s.kpiVal}>{filteredData.length}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Total</div><div style={s.kpiVal}>{fmt(totalVal)}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Top</div><div style={s.kpiVal}>{topEntry ? String(topEntry[labelField] ?? topEntry[countryCodeField] ?? '—').slice(0, 18) : '—'}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Max</div><div style={s.kpiVal}>{fmt(maxVal)}</div></div>
      </div>

      <div style={s.card}>
        <div style={{ position: 'relative', borderRadius: 8 }}>
          <svg
            ref={svgRef}
            style={{ width: '100%', height: isWorldRegion ? 460 : 420, display: 'block' }}
          />
          {!geo && !geoError && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9CA3AF', background: '#EFF6FF' }}>
              Loading map…
            </div>
          )}
          {geoError && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center', color: '#9CA3AF', gap: 8 }}>
              <span style={{ fontSize: 32 }}>🗺</span>
              <span>Map could not load — data table below</span>
            </div>
          )}
          {tooltip && (
            <div style={{
              position: 'fixed', left: tooltip.x + 14, top: tooltip.y,
              background: 'rgba(15,23,42,0.9)', color: '#fff',
              padding: '8px 12px', borderRadius: 8, fontSize: 12,
              pointerEvents: 'none', zIndex: 99999, maxWidth: 220,
            }} dangerouslySetInnerHTML={{ __html: tooltip.html }} />
          )}
        </div>

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

      {selectedCountry && (
        <CountryDrilldown
          feature={selectedCountry.feature}
          name={selectedCountry.name}
          val={selectedCountry.val}
          valueField={valueField}
          valueFmt={(config as any).valueFormat ?? ',.1f'}
          onClose={() => setSelectedCountry(null)}
        />
      )}

      {top10.length > 0 && (
        <div style={s.card}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#374151' }}>
              Top {top10.length} — {valueField}
            </h3>
            <ExportToolbar
              data={top10.map((r: any, i: number) => ({ '#': i + 1, 'Country / Region': r.name, [valueField]: r.val }))}
              columns={[{ key: '#', header: '#' }, { key: 'Country / Region', header: 'Country / Region' }, { key: valueField, header: valueField }]}
              title={(config as any).title ?? 'Map Data'}
              filename="map-data"
            />
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' as const }}>
            <thead>
              <tr>
                {['#', 'Country / Region', valueField].map((h: string) => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: h === '#' ? 'center' as const : 'left' as const, fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase' as const, borderBottom: '2px solid #E5E7EB' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {top10.map((row: { name: string; val: number }, i: number) => (
                <tr key={i} style={{ background: i % 2 === 0 ? '#fff' : '#FAFAFA' }}>
                  <td style={{ padding: '8px 12px', textAlign: 'center' as const, fontSize: 13, color: '#9CA3AF', borderBottom: '1px solid #F1F5F9' }}>{i + 1}</td>
                  <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 500, color: '#374151', borderBottom: '1px solid #F1F5F9' }}>{row.name}</td>
                  <td style={{ padding: '8px 12px', fontSize: 13, color: '#374151', borderBottom: '1px solid #F1F5F9', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.val, (config as any).valueFormat ?? ',.0f')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
