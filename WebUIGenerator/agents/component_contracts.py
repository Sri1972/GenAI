"""
Single source of truth for component prop contracts.
Injected into Pass 3 page-generation prompts so the LLM
uses the correct prop names, types, and data shapes.
"""

COMPONENT_CONTRACTS: dict[str, dict] = {

    "D3GroupedBar": {
        "filename": "D3GroupedBar.tsx",
        "interface": """\
interface GroupSeries { key: string; color: string }
interface Props {
  data: Record<string, any>[]   // FLAT records — one per group
  groupKey: string              // field name used as the group label
  series: GroupSeries[]         // one entry per bar series (NOT groups=)
  height?: number
  valueFormat?: (n: number) => string
}""",
        "example": """\
const rows = REGIONS.map(r => ({
  region: r,
  'Q1 2024': salesByRegionQ1[r],
  'Q2 2024': salesByRegionQ2[r],
}))
const series = QUARTERS.map((q, i) => ({
  key: q,
  color: ['#0064D2','#420E71','#059669','#D97706'][i % 4],
}))
<D3GroupedBar data={rows} groupKey="region" series={series} height={360} />""",
        "mistakes": [
            "NEVER use groups= — the prop is series=",
            "NEVER use groupKeys= — the prop is series= (array of {key,color})",
            "NEVER pass nested {label, values:[]} shape — data must be flat records with one key per series",
            "NEVER omit groupKey — it is required and must match a field in data",
        ],
    },

    "D3StackedArea": {
        "filename": "D3StackedArea.tsx",
        "interface": """\
interface StackSeries { key: string; color: string }
interface Props {
  data: Record<string, any>[]
  keys: StackSeries[]           // NOT series= — the prop is keys=
  xKey: string                  // REQUIRED — field name for x-axis labels
  height?: number
  yFormat?: (n: number) => string
}""",
        "example": """\
const data = QUARTERS.map(q => ({
  label: q,
  Americas: revenueByRegionQ[q]['Americas'],
  Europe: revenueByRegionQ[q]['Europe'],
}))
const keys = REGIONS.map(r => ({ key: r, color: REGION_COLORS[r] }))
<D3StackedArea data={data} xKey="label" keys={keys} height={360} yFormat={v => `$${v}M`} />""",
        "mistakes": [
            "NEVER omit xKey — it is required",
            "NEVER use series= — the prop is keys=",
        ],
    },

    "D3LineChart": {
        "filename": "D3LineChart.tsx",
        "interface": """\
interface LinePoint { x: string; y: number | null }  // x MUST be a string label
interface LineSeries {
  name: string
  color: string
  dashed?: boolean
  points: LinePoint[]
}
interface Props {
  series: LineSeries[]
  height?: number
  yFormat?: (n: number) => string
}""",
        "example": """\
const series = topMakes.map(make => ({
  name: make,
  color: MAKE_COLORS[make],
  points: QUARTERS.map(q => ({ x: q, y: unitsByMakeQuarter[make][q] })),
}))
<D3LineChart series={series} height={360} />""",
        "mistakes": [
            "NEVER use x: number — x must always be a string label (quarter name, month, etc.)",
            "NEVER use data= — the prop is series=",
            "NEVER use lines= or lineData= — the prop is series=",
        ],
    },

    "D3BarChart": {
        "filename": "D3BarChart.tsx",
        "interface": """\
interface BarDatum { label: string; value: number; color?: string }
interface Props {
  data: BarDatum[]
  height?: number
  horizontal?: boolean
  valueFormat?: (n: number) => string
}""",
        "example": """\
const data = REGIONS.map(r => ({
  label: r, value: revenueByRegion[r], color: REGION_COLORS[r],
}))
<D3BarChart data={data} horizontal={true} valueFormat={v => `$${v}M`} />""",
        "mistakes": [],
    },

    "D3DonutChart": {
        "filename": "D3DonutChart.tsx",
        "interface": """\
interface DonutDatum { label: string; value: number; color: string }
interface Props {
  data: DonutDatum[]
  centerLabel?: string
  height?: number
}""",
        "example": """\
<D3DonutChart data={makeShareData} centerLabel="Market Share" />""",
        "mistakes": [],
    },

    "Tabs": {
        "filename": "Tabs.tsx",
        "interface": """\
interface Props {
  tabs: (string | { id: string; label: string })[]
  active: number        // ZERO-BASED INDEX — NOT a string id
  onChange: (index: number) => void
}""",
        "example": """\
const TAB_IDS = ['volume', 'revenue', 'share', 'ev']
const [tab, setTab] = useState('volume')

<Tabs
  tabs={[
    { id: 'volume', label: 'Volume Trends' },
    { id: 'revenue', label: 'Revenue Mix' },
    { id: 'share', label: 'Market Share' },
    { id: 'ev', label: 'EV Adoption' },
  ]}
  active={TAB_IDS.indexOf(tab)}
  onChange={(i) => setTab(TAB_IDS[i])}
/>""",
        "mistakes": [
            "NEVER pass active={tab} where tab is a string — active must be a number (the index)",
            "NEVER pass onChange={setTab} when tab is a string — wrap it: onChange={(i) => setTab(TAB_IDS[i])}",
        ],
    },

    "UsaSalesMap": {
        "filename": "UsaSalesMap.tsx",
        "interface": """\
interface Props {
  stateSales: { state: string; make: string; units: number; abbr?: string }[]
  makeFilter?: string      // string like 'Toyota', or undefined for All — NEVER null, NEVER a function
  height?: number
  onStateClick?: (stateName: string) => void
  selectedState?: string
}""",
        "example": """\
<UsaSalesMap
  stateSales={filteredRows}
  makeFilter={make === 'All' ? undefined : make}
  selectedState={selectedState ?? undefined}
  onStateClick={(name) => setSelectedState(prev => prev === name ? null : name)}
/>""",
        "mistakes": [
            "NEVER import from '../components/SalesMap' or '../components/USSalesMap' — always UsaSalesMap",
            "NEVER pass makeFilter as a useCallback or function — it must be a string or undefined",
            "NEVER pass makeFilter={null} — use undefined",
        ],
    },

    "WorldSalesMap": {
        "filename": "WorldSalesMap.tsx",
        "interface": """\
interface Props {
  salesData: { countryCode: string; make: string; units: number }[]
  makeFilter?: string    // string or undefined — NEVER null
  height?: number
}""",
        "example": """\
<WorldSalesMap
  salesData={filtered}
  makeFilter={make === 'All' ? undefined : make}
/>""",
        "mistakes": [
            "NEVER pass makeFilter={null} — use undefined or omit the prop",
            "NEVER pass sales= or data= — the prop is salesData=",
        ],
    },

    "FilterDropdown": {
        "filename": "FilterDropdown.tsx",
        "interface": """\
type Option = string | { value: string; label: string }
interface Props {
  value: string
  options: Option[]          // accepts plain strings OR {value, label} objects
  onChange: (value: string) => void
  label?: string
}""",
        "mistakes": [],
    },

    "PersonaCard": {
        "filename": "PersonaCard.tsx",
        "interface": """\
interface Props {
  persona: Persona
  active: boolean    // NOT selected — the prop is active
  onClick: () => void
}""",
        "mistakes": [
            "NEVER use selected= — the prop name is active=",
        ],
    },

    "DataTable": {
        "filename": "DataTable.tsx",
        "interface": """\
interface Column<T> {
  key: string
  header: string
  sortable?: boolean
  align?: 'left' | 'right'
  render?: (row: T) => ReactNode
}
interface Props<T> {
  columns: Column<T>[]
  data?: T[]
  rows?: T[]                        // alias for data — either works
  rowKey?: ((row: T) => string) | string
  initialSort?: { key: string; dir: 'asc' | 'desc' }
}""",
        "mistakes": [],
    },

    "Pagination": {
        "filename": "Pagination.tsx",
        "interface": """\
interface Props {
  page: number
  pageCount: number      // NOT totalPages
  onChange: (p: number) => void   // NOT onPageChange
}""",
        "mistakes": [
            "NEVER use totalPages= — the prop is pageCount=",
            "NEVER use onPageChange= — the prop is onChange=",
        ],
    },
}


def build_component_api_section() -> str:
    """
    Build a markdown-formatted Component API Reference section to inject
    into Pass 3 page-generation prompts.
    """
    lines = [
        "## Component API Reference",
        "Use ONLY these prop names and types. Do not invent alternatives.",
        "Violating these contracts causes runtime crashes or blank charts.",
        "",
    ]
    for name, c in COMPONENT_CONTRACTS.items():
        filename = c["filename"].replace(".tsx", "")
        lines.append(f"### {name}  →  import from '../components/{filename}'")
        lines.append("```typescript")
        lines.append(c["interface"].strip())
        lines.append("```")
        if "example" in c:
            lines.append("**Correct usage:**")
            lines.append("```tsx")
            lines.append(c["example"].strip())
            lines.append("```")
        for mistake in c.get("mistakes", []):
            lines.append(f"❌ {mistake}")
        lines.append("")
    return "\n".join(lines)
