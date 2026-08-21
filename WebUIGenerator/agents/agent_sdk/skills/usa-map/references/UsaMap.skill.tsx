// @ts-nocheck
/**
 * UsaMap.skill.tsx — Generic D3 USA state choropleth map.
 *
 * Domain-agnostic — reads config from src/config/UsaMap.config.ts
 * Uses us-atlas (static import — no fetch, works offline / behind proxies).
 * Works for: state sales, election data, demographics, any state-level metric.
 */
import { useState, useEffect, useRef, useMemo } from 'react'
import React from 'react'
import * as d3 from 'd3'
import * as topojson from 'topojson-client'
import usaTopo from 'us-atlas/states-10m.json'
import { config } from '../config/UsaMap.config'
import { ExportToolbar } from '../components/ExportToolbar'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

// Static FIPS → full state name lookup (us-atlas uses numeric FIPS ids)
const FIPS_TO_STATE: Record<string, string> = {
  '01':'Alabama','02':'Alaska','04':'Arizona','05':'Arkansas','06':'California',
  '08':'Colorado','09':'Connecticut','10':'Delaware','11':'District of Columbia',
  '12':'Florida','13':'Georgia','15':'Hawaii','16':'Idaho','17':'Illinois',
  '18':'Indiana','19':'Iowa','20':'Kansas','21':'Kentucky','22':'Louisiana',
  '23':'Maine','24':'Maryland','25':'Massachusetts','26':'Michigan',
  '27':'Minnesota','28':'Mississippi','29':'Missouri','30':'Montana',
  '31':'Nebraska','32':'Nevada','33':'New Hampshire','34':'New Jersey',
  '35':'New Mexico','36':'New York','37':'North Carolina','38':'North Dakota',
  '39':'Ohio','40':'Oklahoma','41':'Oregon','42':'Pennsylvania',
  '44':'Rhode Island','45':'South Carolina','46':'South Dakota','47':'Tennessee',
  '48':'Texas','49':'Utah','50':'Vermont','51':'Virginia','53':'Washington',
  '54':'West Virginia','55':'Wisconsin','56':'Wyoming',
}

const STATE_ABBR: Record<string, string> = {
  'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA',
  'Colorado':'CO','Connecticut':'CT','Delaware':'DE','Florida':'FL','Georgia':'GA',
  'Hawaii':'HI','Idaho':'ID','Illinois':'IL','Indiana':'IN','Iowa':'IA',
  'Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD',
  'Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS','Missouri':'MO',
  'Montana':'MT','Nebraska':'NE','Nevada':'NV','New Hampshire':'NH','New Jersey':'NJ',
  'New Mexico':'NM','New York':'NY','North Carolina':'NC','North Dakota':'ND','Ohio':'OH',
  'Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA','Rhode Island':'RI','South Carolina':'SC',
  'South Dakota':'SD','Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT',
  'Virginia':'VA','Washington':'WA','West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY',
  'District of Columbia':'DC',
}
const ABBR_STATE: Record<string, string> = Object.fromEntries(
  Object.entries(STATE_ABBR).map(([k, v]) => [v, k])
)

// Derive GeoJSON once from the static topojson bundle
const statesFeatures: any[] = (topojson.feature(
  usaTopo as any,
  (usaTopo as any).objects.states
) as any).features

const COLOR_SCHEMES: Record<string, readonly string[]> = {
  blue:   d3.schemeBlues[9],
  green:  d3.schemeGreens[9],
  orange: d3.schemeOranges[9],
  purple: d3.schemePurples[9],
}

function fmt(n: number) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return d3.format(',.0f')(n)
}

// ── State drilldown panel ─────────────────────────────────────────────────────
function StateDrilldown({
  stateName, stateFeature, val, valueField, onClose,
}: {
  stateName: string; stateFeature: any; val: number | null; valueField: string; onClose: () => void
}) {
  const ref = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!ref.current || !stateFeature) return
    const W = ref.current.clientWidth || 340
    const H = 220
    const svg = d3.select(ref.current).attr('height', H)
    svg.selectAll('*').remove()
    svg.append('rect').attr('width', W).attr('height', H).attr('fill', '#EFF6FF').attr('rx', 8)

    const proj = d3.geoAlbersUsa().fitExtent([[20, 20], [W - 20, H - 20]], stateFeature)
    const path = d3.geoPath().projection(proj)
    svg.append('path')
      .datum(stateFeature)
      .attr('d', path as any)
      .attr('fill', '#0064D2')
      .attr('fill-opacity', 0.18)
      .attr('stroke', '#0064D2')
      .attr('stroke-width', 2.5)
      .attr('rx', 2)
  }, [stateFeature])

  return (
    <div style={{ background: '#fff', borderRadius: 12, border: '2px solid #0064D2', padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 700, color: '#0D1B2A' }}>{stateName}</div>
          {val != null && (
            <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2 }}>
              {valueField}: <span style={{ fontWeight: 700, color: '#0064D2' }}>{fmt(val)}</span>
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

export default function UsaMapPage() {
  const {
    dataExport, tableName, stateField, valueField,
    title, colorScheme = 'blue', filterField = null,
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

  const svgRef = useRef<SVGSVGElement>(null)
  const [tooltip,         setTooltip]         = useState<{x:number;y:number;html:string}|null>(null)
  const [filter,          setFilter]          = useState('All')
  const [selectedState,   setSelectedState]   = useState<string | null>(null)
  const [selectedFeature, setSelectedFeature] = useState<any>(null)

  const filteredData = useMemo(() => {
    if (!filterField || filter === 'All') return allRows
    return allRows.filter((r: any) => String(r[filterField]) === filter)
  }, [filter, allRows])

  // Build value map: lower-case full name → value AND abbreviation → value
  const valueByState = useMemo(() => {
    const m: Record<string, number> = {}
    for (const row of filteredData) {
      const raw = String(row[stateField] ?? '')
      const val = Number(row[valueField] ?? 0)
      const isAbbr = raw.length === 2
      const full  = isAbbr ? (ABBR_STATE[raw.toUpperCase()] ?? raw) : raw
      const abbr  = isAbbr ? raw.toUpperCase() : (STATE_ABBR[raw] ?? raw)
      m[full.toLowerCase()] = (m[full.toLowerCase()] ?? 0) + val
      m[abbr] = (m[abbr] ?? 0) + val
    }
    return m
  }, [filteredData])

  const filterOptions = useMemo(() => {
    if (!filterField) return []
    return [...new Set(allRows.map((r: any) => String(r[filterField])))].sort()
  }, [allRows])

  const values  = Object.values(valueByState).filter(v => typeof v === 'number')
  const maxVal  = values.length ? Math.max(...values) : 1
  const topEntry = useMemo(() =>
    [...filteredData].sort((a: any, b: any) => Number(b[valueField]) - Number(a[valueField]))[0]
  , [filteredData])

  const palette    = COLOR_SCHEMES[colorScheme] ?? COLOR_SCHEMES.blue
  const colorScale = useMemo(
    () => d3.scaleQuantize<string>().domain([0, maxVal]).range([...palette] as string[]),
    [maxVal, palette]
  )

  // Draw map — statesFeatures is static, no fetch needed
  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    const W = svgRef.current.clientWidth || 900
    const H = 520
    const proj = d3.geoAlbersUsa().fitSize([W, H], { type: 'FeatureCollection', features: statesFeatures } as any)
    const path = d3.geoPath().projection(proj)

    svg.append('rect').attr('width', W).attr('height', H).attr('fill', '#EFF6FF')

    svg.selectAll('path')
      .data(statesFeatures)
      .join('path')
      .attr('d', path as any)
      .attr('fill', (d: any) => {
        const fipsId = String(d.id).padStart(2, '0')
        const name   = FIPS_TO_STATE[fipsId] ?? ''
        const isSelected = selectedState && name.toLowerCase() === selectedState.toLowerCase()
        const val    = valueByState[name.toLowerCase()] ?? valueByState[STATE_ABBR[name] ?? '']
        if (isSelected) return '#0064D2'
        return val != null ? colorScale(val) : '#D1D5DB'
      })
      .attr('stroke', (d: any) => {
        const name = FIPS_TO_STATE[String(d.id).padStart(2, '0')] ?? ''
        return selectedState && name.toLowerCase() === selectedState.toLowerCase() ? '#003F8A' : '#fff'
      })
      .attr('stroke-width', (d: any) => {
        const name = FIPS_TO_STATE[String(d.id).padStart(2, '0')] ?? ''
        return selectedState && name.toLowerCase() === selectedState.toLowerCase() ? 2.5 : 0.8
      })
      .style('cursor', 'pointer')
      .on('click', function(event: any, d: any) {
        const name = FIPS_TO_STATE[String(d.id).padStart(2, '0')] ?? ''
        if (!name) return
        const isDeselect = selectedState?.toLowerCase() === name.toLowerCase()
        setSelectedState(isDeselect ? null : name)
        setSelectedFeature(isDeselect ? null : d)
        setTooltip(null)
      })
      .on('mouseover', function(event: any, d: any) {
        const name = FIPS_TO_STATE[String(d.id).padStart(2, '0')] ?? ''
        const isSelected = selectedState && name.toLowerCase() === selectedState.toLowerCase()
        if (!isSelected) d3.select(this).attr('stroke-width', 2).attr('stroke', '#374151')
        const val  = valueByState[name.toLowerCase()] ?? valueByState[STATE_ABBR[name] ?? '']
        const text = val != null ? fmt(val) : 'No data'
        const rect = svgRef.current!.getBoundingClientRect()
        setTooltip({ x: event.clientX - rect.left, y: event.clientY - rect.top - 10,
                     html: `<b>${name}</b><br/>${valueField}: ${text}` })
      })
      .on('mousemove', function(event: any) {
        const rect = svgRef.current!.getBoundingClientRect()
        setTooltip((t: any) => t ? { ...t, x: event.clientX - rect.left, y: event.clientY - rect.top - 10 } : t)
      })
      .on('mouseleave', function(event: any, d: any) {
        const name = FIPS_TO_STATE[String(d.id).padStart(2, '0')] ?? ''
        const isSelected = selectedState && name.toLowerCase() === selectedState.toLowerCase()
        d3.select(this)
          .attr('stroke-width', isSelected ? 2.5 : 0.8)
          .attr('stroke', isSelected ? '#003F8A' : '#fff')
        setTooltip(null)
      })
  }, [valueByState, colorScale, selectedState])

  const top10 = useMemo(() =>
    Object.entries(valueByState)
      .filter(([k]) => k.length > 2)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([name, val]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), val }))
  , [valueByState])

  const totalVal = top10.reduce((s, r) => s + r.val, 0)

  const s = {
    page:    { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    card:    { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
    heading: { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    kpiRow:  { display: 'flex', gap: 16 },
    kpiCard: { flex: 1, background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '14px 18px' },
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
          <select style={{ height: 36, padding: '0 10px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13 }}
                  value={filter} onChange={e => setFilter(e.target.value)}>
            <option value="All">All</option>
            {filterOptions.map((o: string) => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      )}

      <div style={s.kpiRow}>
        <div style={s.kpiCard}><div style={s.kpiLbl}>States with Data</div><div style={s.kpiVal}>{top10.length}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Total {valueField}</div><div style={s.kpiVal}>{fmt(totalVal)}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Top State</div><div style={s.kpiVal}>{topEntry ? String(topEntry[stateField] ?? '—').slice(0, 20) : '—'}</div></div>
        <div style={s.kpiCard}><div style={s.kpiLbl}>Max Value</div><div style={s.kpiVal}>{fmt(maxVal)}</div></div>
      </div>

      <div style={s.card}>
        <div style={{ position: 'relative' }}>
          <svg ref={svgRef} style={{ width: '100%', height: 520, display: 'block' }} />
          {tooltip && (
            <div style={{ position: 'absolute', left: tooltip.x + 12, top: tooltip.y,
                          background: 'rgba(0,0,0,0.8)', color: '#fff', padding: '8px 12px',
                          borderRadius: 8, fontSize: 12, pointerEvents: 'none', zIndex: 10 }}
                 dangerouslySetInnerHTML={{ __html: tooltip.html }} />
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
          <span style={{ fontSize: 11, color: '#9CA3AF' }}>Low</span>
          <div style={{ display: 'flex', height: 12, borderRadius: 4, overflow: 'hidden', flex: 1, maxWidth: 200 }}>
            {[...palette].map((c: string, i: number) => <div key={i} style={{ flex: 1, background: c }} />)}
          </div>
          <span style={{ fontSize: 11, color: '#9CA3AF' }}>High</span>
        </div>
      </div>

      {selectedState && selectedFeature && (
        <StateDrilldown
          stateName={selectedState.charAt(0).toUpperCase() + selectedState.slice(1)}
          stateFeature={selectedFeature}
          val={valueByState[selectedState.toLowerCase()] ?? null}
          valueField={valueField}
          onClose={() => { setSelectedState(null); setSelectedFeature(null) }}
        />
      )}

      {top10.length > 0 && (
        <div style={s.card}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#374151' }}>
              {selectedState ? `${selectedState.charAt(0).toUpperCase() + selectedState.slice(1)} — Selected` : 'Top 10 States'}
            </h3>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {selectedState && (
                <button
                  onClick={() => setSelectedState(null)}
                  style={{ fontSize: 12, color: '#0064D2', background: 'none', border: '1px solid #0064D2', borderRadius: 6, padding: '3px 10px', cursor: 'pointer', fontWeight: 500 }}
                >
                  ✕ Clear selection
                </button>
              )}
              <ExportToolbar
                data={top10.map((r: any, i: number) => ({ '#': i + 1, State: r.name, [valueField]: r.val }))}
                columns={[{ key: '#', header: '#' }, { key: 'State', header: 'State' }, { key: valueField, header: valueField }]}
                title={(config as any).title ?? 'State Data'}
                filename="state-data"
              />
            </div>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['#', 'State', valueField].map((h: string) => (
                  <th key={h} style={{ padding: '8px 12px', textAlign: h === '#' ? 'center' : 'left',
                                       fontSize: 11, fontWeight: 700, color: '#9CA3AF',
                                       textTransform: 'uppercase', borderBottom: '2px solid #E5E7EB' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {top10
                .filter((row: any) => !selectedState || row.name.toLowerCase() === selectedState.toLowerCase())
                .map((row: any, i: number) => {
                  const isHighlighted = selectedState && row.name.toLowerCase() === selectedState.toLowerCase()
                  return (
                    <tr
                      key={row.name}
                      onClick={() => {
                        const isDeselect = selectedState?.toLowerCase() === row.name.toLowerCase()
                        setSelectedState(isDeselect ? null : row.name)
                        if (isDeselect) {
                          setSelectedFeature(null)
                        } else {
                          const feat = statesFeatures.find((f: any) => {
                            const n = FIPS_TO_STATE[String(f.id).padStart(2, '0')] ?? ''
                            return n.toLowerCase() === row.name.toLowerCase()
                          })
                          setSelectedFeature(feat ?? null)
                        }
                      }}
                      style={{ cursor: 'pointer', background: isHighlighted ? '#EFF6FF' : 'transparent', transition: 'background 0.15s' }}
                    >
                      <td style={{ padding: '8px 12px', textAlign: 'center', fontSize: 13, color: '#9CA3AF', borderBottom: '1px solid #F1F5F9' }}>{i + 1}</td>
                      <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: isHighlighted ? 700 : 500, color: isHighlighted ? '#0064D2' : '#374151', borderBottom: '1px solid #F1F5F9' }}>{row.name}</td>
                      <td style={{ padding: '8px 12px', fontSize: 13, color: isHighlighted ? '#0064D2' : '#374151', borderBottom: '1px solid #F1F5F9', fontVariantNumeric: 'tabular-nums' }}>{fmt(row.val)}</td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
