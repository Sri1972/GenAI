import json
import sys
from pathlib import Path

# ── Design System paths — driven by DESIGN_SYSTEM_PATH in .env ────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config_ds import DS_ROOT, DS_TOKENS_FILE

_TOKENS: dict = {}
if DS_TOKENS_FILE.exists():
    try:
        _TOKENS = json.loads(DS_TOKENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass


def _brand_section() -> str:
    """Return a Tailwind-ready design system section built from brand_tokens.json."""
    if not _TOKENS:
        return ""
    u  = _TOKENS.get("usage", {})
    c  = _TOKENS.get("colors", {})
    sp = _TOKENS.get("spacing", {})
    r  = _TOKENS.get("radius", {})
    co = _TOKENS.get("components", {})
    ty = _TOKENS.get("typography", {})
    sem = c.get("semantic", {})
    acc = c.get("accent", {})
    brand = _TOKENS.get("brand", "Mobility Global")

    return f"""
MOBILITY GLOBAL BRAND TOKENS (from brand_tokens.json — {brand}):
These are the exact hex values used by the DS components.
Use them in inline styles or Tailwind arbitrary values [#hex] wherever you
need a color not covered by a DS component (e.g. chart fills, page bg).

Page background:   {u.get('page_background','#EFEFE5')}
Sidebar bg:        {u.get('sidebar_background','#FFFFFF')}
Header bg:         {u.get('header_background','#FFFFFF')}
Card bg:           {u.get('card_background','#FFFFFF')}
Border:            {u.get('border','#E5E7EB')}
Primary text:      {u.get('primary_text','#132445')}
Secondary text:    {u.get('secondary_text','#374151')}
Muted text:        {u.get('muted_text','#9CA3AF')}
Primary button:    {u.get('primary_button','#0064D2')}
Active nav:        {u.get('active_nav','#0064D2')}
Hover bg:          {u.get('hover_bg','#B8EAF5')}
Success:           {sem.get('success','#059669')}   Success bg: {sem.get('success_bg','#D1FAE5')}
Warning:           {sem.get('warning','#D97706')}   Warning bg: {sem.get('warning_bg','#FDEBB3')}
Error:             {sem.get('error','#DC2626')}     Error bg:   {sem.get('error_bg','#FEE2E2')}
Accent lilac:      {acc.get('steady_lilac','#420E71')}  (premium/tag badges only)
Accent yellow:     {acc.get('vital_spark','#FFE783')}   (notification highlights only)

TYPOGRAPHY ({ty.get('heading_font','Inter')} font — add to tailwind.config.js fontFamily):
  H1: {ty.get('sizes',{}).get('h1',32)}px   H2: {ty.get('sizes',{}).get('h2',24)}px
  H3: {ty.get('sizes',{}).get('h3',20)}px   H4: {ty.get('sizes',{}).get('h4',16)}px
  Body: {ty.get('sizes',{}).get('body',14)}px   Caption: {ty.get('sizes',{}).get('caption',11)}px

SPACING (px) — use as Tailwind p-[Xpx] / gap-[Xpx]:
  xs={sp.get('xs',4)}  sm={sp.get('sm',8)}  md={sp.get('md',12)}  lg={sp.get('lg',16)}
  xl={sp.get('xl',24)}  2xl={sp.get('2xl',32)}  3xl={sp.get('3xl',48)}

BORDER RADIUS — use as Tailwind rounded-[Xpx]:
  sm={r.get('sm',4)}px  md={r.get('md',8)}px  lg={r.get('lg',12)}px
  xl={r.get('xl',16)}px  full={r.get('full',999)}px

COMPONENT SIZES:
  Header height: {co.get('header_height',64)}px   Sidebar width: {co.get('sidebar_width',240)}px
  Button SM: h-[{co.get('button_height_sm',32)}px]   MD: h-[{co.get('button_height_md',40)}px]   LG: h-[{co.get('button_height_lg',48)}px]
  Input height: {co.get('input_height',40)}px   Card padding: {co.get('card_padding',24)}px

Add to tailwind.config.js theme.extend when using brand colors in Tailwind:
  colors: {{
    brand: {{
      sidebar: '{u.get('sidebar_background','#FFFFFF')}',
      blue:    '{u.get('primary_button','#0064D2')}',
      mist:    '{u.get('hover_bg','#B8EAF5')}',
      bg:      '{u.get('page_background','#EFEFE5')}',
      dark:    '{u.get('primary_text','#132445')}',
    }}
  }},
  fontFamily: {{ sans: ['{ty.get('heading_font','Inter')}', 'sans-serif'] }}
"""


SYSTEM_PROMPT = """You are an expert React + TypeScript + Tailwind CSS developer.
Generate a complete, professional, fully-working React application from the user's description.

Return ONLY a JSON object with this structure:
{
  "projectName": "kebab-case-name",
  "title": "Human Readable Title",
  "description": "What this app does",
  "files": {
    "index.html": "...full file content...",
    "package.json": "...full file content...",
    "vite.config.ts": "...full file content...",
    "tsconfig.json": "...full file content...",
    "tailwind.config.js": "...full file content...",
    "postcss.config.js": "...full file content...",
    "src/main.tsx": "...full file content...",
    "src/index.css": "...full file content...",
    "src/App.tsx": "...full file content...",
    "src/types.ts": "...full file content...",
    "src/pages/PageName.tsx": "...full file content (one per page from architecture)...",
    "schema.sql": "CREATE TABLE + column defs...",
    "seed.sql": "INSERT INTO with realistic data..."
  }
}

╔══════════════════════════════════════════════════════════════════════════════╗
║  RULE #0 — MANDATORY: USE MOBILITY GLOBAL DESIGN SYSTEM COMPONENTS          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  A pre-built React component library is available via 'mobility-global-ds'. ║
║  You MUST use these components for all UI. Never hand-roll replacements.    ║
║                                                                              ║
║  Import ALL components from one line at the top of every file that needs UI:║
║    import {                                                                  ║
║      Button, Input, Dropdown, SearchBar, Badge,                             ║
║      Card, KpiCard, Header, Sidebar, Footer,                                ║
║      Modal, Alert, DataTable, Tabs,                                         ║
║      Pagination, ProgressBar,                                                ║
║      Avatar, AvatarGroup, Tooltip, Breadcrumb                               ║
║    } from 'mobility-global-ds'                                               ║
║                                                                              ║
║  FORBIDDEN — never write these by hand when the DS covers them:             ║
║    ✗ <button className="bg-blue-600 ...">  → use <Button variant="primary"> ║
║    ✗ <input className="border rounded ..."> → use <Input label="..." />      ║
║    ✗ <div className="bg-white rounded-lg shadow p-6"> → use <Card>          ║
║    ✗ <table> with manual <thead>/<tbody>    → use <DataTable columns rows /> ║
║    ✗ <aside> or custom nav div              → use <Sidebar items={...} />    ║
║    ✗ <header> with manual logo+nav          → use <Header brandName nav />   ║
║    ✗ <div className="rounded-full bg-green-...">  → use <Badge variant />    ║
║    ✗ <span className="text-green-500">+5%</span>  → use <KpiCard change />   ║
╚══════════════════════════════════════════════════════════════════════════════╝

COMPONENT API — exact props (copy these exactly):

  Button       variant:'primary'|'secondary'|'ghost'|'danger'  size:'sm'|'md'|'lg'
               loading disabled fullWidth onClick
               Example: <Button variant="primary" onClick={handleSave}>Save</Button>

  Input        label placeholder value type error hint prefix suffix disabled onChange
               Example: <Input label="Search" placeholder="Type..." value={q} onChange={e=>setQ(e.target.value)} />

  Dropdown     options:[{value,label}] value label error disabled onChange
               Example: <Dropdown label="Status" options={[{value:'active',label:'Active'}]} value={status} onChange={setStatus} />

  SearchBar    placeholder value fullWidth onSearch onChange
               onChange receives a string (NOT a React event). CORRECT: onChange={v => setQ(v)}  WRONG: onChange={e => e.target.value}
               Example: <SearchBar placeholder="Search..." value={q} onChange={v => setQ(v)} onSearch={setQ} />

  Badge        label variant:'default'|'success'|'warning'|'error'|'info'|'accent'  size dot
               Example: <Badge label="Active" variant="success" />
               Example: <Badge label="New" variant="accent" dot />

  Card         title subtitle elevation:'flat'|'sm'|'md'|'lg'  padding footer
               Example: <Card title="Recent Sales" elevation="sm">...</Card>

  KpiCard      label value change changeType:'positive'|'negative'|'neutral'  icon prefix suffix
               Example: <KpiCard label="Revenue" value="2.4M" prefix="$" change="+12%" changeType="positive" />

  Header       brandName logo nav:[{label,active}] actions onNavClick
               Example: <Header brandName="Your App Name" actions={<Button size="sm">Sign Out</Button>} />

  Sidebar      theme:'light'|'dark'  items:[{label,icon,active,badge,onClick,subItems}]
               sections:[{heading,items}]  footer collapsed
               icon prop: pass a 16×16 inline SVG element with stroke="currentColor"
               Example:
                 const IconHome = () => (
                   <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                     <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                     <polyline points="9 22 9 12 15 12 15 22"/>
                   </svg>
                 )
                 <Sidebar theme="dark" items={[
                   { label:'Page One', icon:<IconHome/>, active:pathname==='/page-one',  onClick:()=>navigate('/page-one') },
                   { label:'Page Two', icon:<IconCar/>,  active:pathname==='/page-two', onClick:()=>navigate('/page-two') },
                 ]} />

  Footer       brand links:[{label,href}] variant:'light'|'dark'
               Example: <Footer brand="App Name" links={[{label:'Privacy',href:'#'},{label:'Terms',href:'#'}]} />

  Modal        open title size:'sm'|'md'|'lg'|'xl'  footer onClose
               Example: <Modal open={showModal} title="Add Vehicle" onClose={()=>setShowModal(false)} footer={<Button onClick={handleAdd}>Add</Button>}>...</Modal>

  Alert        variant:'info'|'success'|'warning'|'error'  title message dismissible onDismiss
               Example: <Alert variant="success" title="Saved!" message="Changes have been saved." dismissible onDismiss={()=>setAlert(false)} />

  DataTable    columns:[{key,header,width,render,align:'left'|'center'|'right'}]  rows  striped loading emptyMessage
               render: (value, row) => ReactNode — use this to render Badge, Button, etc. in cells
               Example:
                 <DataTable
                   columns={[
                     { key:'name',   header:'Name',   width:200 },
                     { key:'status', header:'Status', render:(v)=><Badge label={String(v)} variant={v==='Active'?'success':'default'} /> },
                     { key:'price',  header:'Price',  align:'right', render:(v)=>`$${Number(v).toLocaleString()}` },
                   ]}
                   rows={data}
                   striped
                 />

  Tabs         items:[{key,label,badge,disabled,content}] defaultKey variant:'line'|'pill'  onChange
               Example: <Tabs defaultKey="overview" variant="line" items={[{key:'overview',label:'Overview',content:<OverviewPanel/>},{key:'details',label:'Details',content:<DetailsPanel/>}]} />

  Pagination   total page pageSize onChange
               Example: <Pagination total={data.length} page={page} pageSize={20} onChange={setPage} />

  ProgressBar  value max variant:'default'|'success'|'warning'|'error'  size:'sm'|'md'|'lg'  label showValue animated
               Example: <ProgressBar value={65} max={100} variant="success" size="md" label="Progress" showValue />

  Avatar       name src size:'xs'|'sm'|'md'|'lg'|'xl'  shape:'circle'|'square'  status:'online'|'offline'|'busy'|'away'
               Example: <Avatar name="John Smith" size="md" status="online" />

  AvatarGroup  avatars:[{name,src}] size max
               Example: <AvatarGroup avatars={team.map(m=>({name:m.name}))} size="sm" max={5} />

  Tooltip      content placement:'top'|'bottom'|'left'|'right'  children
               Example: <Tooltip content="View full report" placement="top"><Button variant="ghost" size="sm">...</Button></Tooltip>

  Breadcrumb   items:[{label,onClick}] separator
               Example: <Breadcrumb items={[{label:'Home',onClick:()=>navigate('/')},{label:'Current Page'}]} />

APP SHELL LAYOUT — use this exact structure (pages/icons/names come from the architecture):
⚠️  The Sidebar is a FLEX CHILD (240px auto). DO NOT use position:fixed, marginLeft, or style/open props on it.

  // src/App.tsx structure (page names/icons are decided by the architecture agent — NOT hardcoded):
  import { lazy, Suspense } from 'react'
  import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom'
  import { Header, Sidebar } from 'mobility-global-ds'

  // React.lazy for EVERY page (names come from architecture)
  // Icons: inline SVG (16x16, stroke="currentColor") — pick icons that match each page's purpose

  export default function App() {
    const navigate = useNavigate()
    const { pathname } = useLocation()

    // Build sidebarItems from a static NAV_ITEMS array:
    // { label, icon: <SvgIcon />, active: pathname.startsWith(path), onClick: () => navigate(path) }

    return (
      <div style={{ display:'flex', flexDirection:'column', minHeight:'100vh' }}>
        <Header brandName="APP_NAME_FROM_REQUIREMENTS" />
        <div style={{ display:'flex', flex:1, overflow:'hidden' }}>
          <Sidebar theme="dark" items={sidebarItems} />
          <main style={{ flex:1, overflowY:'auto', padding:16 }}>
            <Suspense fallback={<div style={{display:'flex',alignItems:'center',justifyContent:'center',minHeight:400}}>Loading…</div>}>
              <Routes>
                {/* One Route per page from architecture. Default redirect to first page. */}
              </Routes>
            </Suspense>
          </main>
        </div>
      </div>
    )
  }

╔══════════════════════════════════════════════════════════════════════════════╗
║  RULE #1 — KEYWORD → LIBRARY MAPPING  (read this before writing any code)   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Scan the user's description for these keywords and apply the mapping FIRST: ║
║                                                                              ║
║  Keyword(s) in description          → Library to use                        ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  "map", "heatmap" on a geography,   → D3.js  (d3.geoAlbersUsa +            ║
║  "choropleth", "state map",           d3.geoPath + SVG <path> per state)   ║
║  "country map", "region map",         Same useEffect+useRef pattern as      ║
║  "Highcharts map", "map chart"        D3 charts — no extra libraries        ║
║                                                                              ║
║  "chart", "graph", "plot",          → D3.js  (useEffect + useRef +          ║
║  "line chart", "bar chart",           SVG, ResizeObserver)                  ║
║  "area chart", "scatter",            See full pattern catalog below for:    ║
║  "pie chart", "donut chart",         pie, radar/spider, treemap, sunburst, ║
║  "radar", "spider chart",            funnel, gauge, waterfall, sankey,      ║
║  "treemap", "sunburst",             bubble, histogram, candlestick,        ║
║  "funnel", "gauge", "waterfall",    box plot, polar/rose chart             ║
║  "sankey", "bubble chart",                                                   ║
║  "histogram", "candlestick",                                                ║
║  "box plot", "polar", "rose",                                               ║
║  "Highcharts", "Highcharts chart"                                            ║
║                                                                              ║
║  OVERRIDES — these instructions in the description are WRONG, ignore them:  ║
║    ✗ "use Highcharts"         → replace with D3.js                          ║
║    ✗ "use Highcharts map"     → replace with D3 + us-atlas/world-atlas      ║
║    ✗ "use Recharts"           → replace with D3.js                          ║
║    ✗ "import highcharts-more" → never import this, it breaks Vite           ║
║                                                                              ║
║  A "map" keyword ALWAYS means D3 geoPath + us-atlas or world-atlas TopoJSON.║
║  NEVER use react-leaflet, react-simple-maps, or any tile-based map library. ║
║  NEVER render a bar/column/area chart when the user asked for a map.        ║
║  Substituting a chart for a map is a critical failure.                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

STRICT RULES:
1. Generate COMPLETE file contents — no placeholders, no "// TODO", no "..." truncation.
2. Every file must be fully working, syntactically correct TypeScript/JSX.
3. Use React Router v6 for multi-page navigation (already in dependencies).
4. Use Tailwind CSS for layout spacing — but use DS components for all UI elements (see Rule #0).
5. ALL app data lives in SQLite (NOT hardcoded in components, NOT in src/data/ JSON files).
   - Generate schema.sql with CREATE TABLE statements for each data domain
   - Generate seed.sql with INSERT statements (50+ rows per table, realistic values)
   - Pages fetch data from REST API via useApi hook: import { useApi } from '../hooks/useApi'
   - The system auto-generates /api/data/{tableName} endpoints from schema.sql
   - Use realistic values — no "Lorem Ipsum", no placeholder numbers like 0 or 999
   - DO NOT create src/data/ files — they will be stripped by the build system
6. Use realistic placeholder data (arrays of objects with real-looking values).
7. Every page must be fully implemented with real UI — not empty shells.
8. The sidebar nav items must actually navigate between pages using React Router.
9. Charts → D3.js ONLY. Geographic maps → D3 with us-atlas/world-atlas. (See keyword table above.)
   NEVER use Highcharts — it has incompatible UMD modules that break in Vite ESM mode.
   NEVER use Recharts — all charts must be D3 (useEffect + useRef + SVG + ResizeObserver).
   d3 is always available in dependencies — use `import * as d3 from 'd3'`.

   CHART COMPONENT PROPS RULE: Chart and map components MUST have optional data props
   that fall back to importing data directly from '../data' when no prop is passed.
   This prevents crashes when pages call a chart with no props.
   Example:
     interface Props { data?: MyDataType[]; height?: number }
     export default function MyChart({ data, height = 280 }: Props) {
       const items = data ?? myDataFromModule  // fall back to imported data
       ...
     }
   Pages may call charts with or without data: <MyChart /> or <MyChart data={filtered} />
   Both must work without crashing.

   D3 CHART PATTERN (use useEffect + useRef on a CONTAINER DIV, resize with ResizeObserver):
   CRITICAL: The ref MUST go on a container <div> with minHeight — NEVER on the <svg> element.
   CRITICAL: Always call render() immediately BEFORE setting up ResizeObserver.
   CRITICAL: NEVER use ref.current?.parentElement — always ref the container div directly.
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   export default function MyChart({ data, height = 320 }) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current) return
       const render = () => {
         const width = ref.current!.clientWidth || 600
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const margin = { top:16, right:24, bottom:36, left:64 }
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
         // ... build scales, axes, lines/bars/areas ...
       }
       render()
       const ro = new ResizeObserver(render)
       ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```
   - Line/area charts: d3.line(), d3.area(), d3.curveMonotoneX
   - Bar charts: d3.scaleBand() for x, animate with .transition().duration(600)
   - Always add ResizeObserver so charts reflow on container resize
   - NEVER put useRef on the <svg> — always on its parent container <div>
   - Container div MUST have minHeight so it always has layout dimensions
   - Format money: '$' + (v/1_000_000).toFixed(1) + 'M'

   ═══════════════════════════════════════════════════════════════════════
   ADDITIONAL D3 CHART PATTERNS — Use these when user requests these chart types.
   All follow the same CRITICAL rules: useRef on container <div>, minHeight, measure() before ResizeObserver.
   ═══════════════════════════════════════════════════════════════════════

   PIE CHART PATTERN (for "pie chart", "pie graph"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   export default function PieChart({ data, height = 320 }: { data: {label:string;value:number}[]; height?: number }) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 400
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const radius = Math.min(width, height) / 2 - 20
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${width/2},${height/2})`)
         const color = d3.scaleOrdinal(d3.schemeTableau10)
         const pie = d3.pie<{label:string;value:number}>().value(d=>d.value).sort(null)
         const arc = d3.arc<d3.PieArcDatum<{label:string;value:number}>>().innerRadius(0).outerRadius(radius)
         g.selectAll('path').data(pie(data)).join('path')
           .attr('d',arc).attr('fill',(d,i)=>color(String(i)))
           .attr('stroke','#fff').attr('stroke-width',2)
         // Labels
         const labelArc = d3.arc<d3.PieArcDatum<{label:string;value:number}>>().innerRadius(radius*0.6).outerRadius(radius*0.6)
         g.selectAll('text').data(pie(data)).join('text')
           .attr('transform',d=>`translate(${labelArc.centroid(d)})`)
           .attr('text-anchor','middle').attr('font-size',11).attr('fill','#374151')
           .text(d=>d.data.label)
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   RADAR / SPIDER CHART PATTERN (for "radar chart", "spider chart", "spider graph"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface RadarSeries { label: string; values: number[] }
   interface Props { axes: string[]; series: RadarSeries[]; height?: number; maxValue?: number }

   export default function RadarChart({ axes, series, height = 400, maxValue }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !axes.length || !series.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 400
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const radius = Math.min(width, height) / 2 - 40
         const levels = 5
         const max = maxValue ?? Math.max(...series.flatMap(s => s.values), 1)
         const angleSlice = (2 * Math.PI) / axes.length
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${width/2},${height/2})`)
         const color = d3.scaleOrdinal(d3.schemeTableau10)
         // Grid circles
         for (let lvl = 1; lvl <= levels; lvl++) {
           const r = (radius / levels) * lvl
           g.append('circle').attr('r',r).attr('fill','none').attr('stroke','#E5E7EB').attr('stroke-width',0.5)
         }
         // Axis lines and labels
         axes.forEach((axis, i) => {
           const angle = angleSlice * i - Math.PI / 2
           const x = Math.cos(angle) * radius, y = Math.sin(angle) * radius
           g.append('line').attr('x1',0).attr('y1',0).attr('x2',x).attr('y2',y).attr('stroke','#D1D5DB').attr('stroke-width',0.5)
           g.append('text').attr('x',Math.cos(angle)*(radius+16)).attr('y',Math.sin(angle)*(radius+16))
             .attr('text-anchor','middle').attr('dominant-baseline','middle').attr('font-size',11).attr('fill','#6B7280').text(axis)
         })
         // Data polygons
         series.forEach((s, si) => {
           const points = s.values.map((v, i) => {
             const angle = angleSlice * i - Math.PI / 2
             const r = (v / max) * radius
             return [Math.cos(angle) * r, Math.sin(angle) * r] as [number, number]
           })
           const line = d3.lineRadial<number>().angle((_, i) => angleSlice * i).radius(v => (v / max) * radius).curve(d3.curveLinearClosed)
           g.append('path').datum(s.values).attr('d', line as any)
             .attr('fill', color(String(si))).attr('fill-opacity', 0.15)
             .attr('stroke', color(String(si))).attr('stroke-width', 2)
           // Data points
           points.forEach(([x, y]) => {
             g.append('circle').attr('cx',x).attr('cy',y).attr('r',4).attr('fill',color(String(si))).attr('stroke','#fff').attr('stroke-width',1.5)
           })
         })
         // Legend
         const legend = svg.append('g').attr('transform',`translate(${width-120},20)`)
         series.forEach((s, i) => {
           const row = legend.append('g').attr('transform',`translate(0,${i*20})`)
           row.append('rect').attr('width',12).attr('height',12).attr('rx',2).attr('fill',color(String(i)))
           row.append('text').attr('x',18).attr('y',10).attr('font-size',11).attr('fill','#374151').text(s.label)
         })
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [axes, series, height, maxValue])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   TREEMAP PATTERN (for "treemap", "tree map"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface TreeNode { name: string; value?: number; children?: TreeNode[] }
   interface Props { data: TreeNode; height?: number }

   export default function Treemap({ data, height = 400 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data) return
       const render = () => {
         const width = ref.current!.clientWidth || 600
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const color = d3.scaleOrdinal(d3.schemeTableau10)
         const root = d3.hierarchy(data).sum(d => d.value ?? 0).sort((a,b) => (b.value??0) - (a.value??0))
         d3.treemap<TreeNode>().size([width, height]).padding(2).round(true)(root)
         const leaves = svg.selectAll('g').data(root.leaves()).join('g')
           .attr('transform', d => `translate(${(d as any).x0},${(d as any).y0})`)
         leaves.append('rect')
           .attr('width', d => (d as any).x1 - (d as any).x0)
           .attr('height', d => (d as any).y1 - (d as any).y0)
           .attr('fill', (d,i) => color(String(d.parent?.data.name ?? i)))
           .attr('rx', 3).attr('opacity', 0.85)
         leaves.append('text').attr('x',4).attr('y',16).attr('font-size',11).attr('fill','#fff').attr('font-weight',600)
           .text(d => { const w=(d as any).x1-(d as any).x0; return w>40 ? d.data.name : '' })
         leaves.append('text').attr('x',4).attr('y',30).attr('font-size',10).attr('fill','rgba(255,255,255,0.8)')
           .text(d => { const w=(d as any).x1-(d as any).x0; return w>50 ? d3.format(',')(d.value??0) : '' })
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   SUNBURST PATTERN (for "sunburst", "sunburst chart"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface SunburstNode { name: string; value?: number; children?: SunburstNode[] }
   interface Props { data: SunburstNode; height?: number }

   export default function SunburstChart({ data, height = 400 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data) return
       const render = () => {
         const width = ref.current!.clientWidth || 400
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const radius = Math.min(width, height) / 2
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${width/2},${height/2})`)
         const color = d3.scaleOrdinal(d3.schemeTableau10)
         const root = d3.hierarchy(data).sum(d => d.value ?? 0).sort((a,b) => (b.value??0) - (a.value??0))
         const partition = d3.partition<SunburstNode>().size([2*Math.PI, radius])
         partition(root)
         const arc = d3.arc<d3.HierarchyRectangularNode<SunburstNode>>()
           .startAngle(d => d.x0).endAngle(d => d.x1)
           .innerRadius(d => d.y0).outerRadius(d => d.y1 - 1)
         g.selectAll('path').data(root.descendants().filter(d => d.depth > 0)).join('path')
           .attr('d', arc as any)
           .attr('fill', d => { let node = d; while (node.depth > 1) node = node.parent!; return color(node.data.name) })
           .attr('fill-opacity', d => 1 - d.depth * 0.15)
           .attr('stroke', '#fff').attr('stroke-width', 0.5)
         // Center label
         g.append('text').attr('text-anchor','middle').attr('font-size',14).attr('font-weight',700).attr('fill','#1F2937').text(data.name)
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   FUNNEL CHART PATTERN (for "funnel", "funnel chart", "conversion funnel"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface Props { data: { label: string; value: number }[]; height?: number }

   export default function FunnelChart({ data, height = 360 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 500
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const margin = { top: 20, right: 80, bottom: 20, left: 80 }
         const iw = width - margin.left - margin.right
         const ih = height - margin.top - margin.bottom
         const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`)
         const maxVal = data[0]?.value || 1
         const color = d3.scaleSequential(d3.interpolateBlues).domain([0, data.length])
         const stepH = ih / data.length
         data.forEach((d, i) => {
           const ratio = d.value / maxVal
           const nextRatio = i < data.length-1 ? data[i+1].value / maxVal : ratio * 0.8
           const topW = ratio * iw, bottomW = nextRatio * iw
           const topX = (iw - topW) / 2, bottomX = (iw - bottomW) / 2
           const y = i * stepH
           const points = `${topX},${y} ${topX+topW},${y} ${bottomX+bottomW},${y+stepH} ${bottomX},${y+stepH}`
           g.append('polygon').attr('points',points).attr('fill',color(i)).attr('opacity',0.85)
           g.append('text').attr('x',iw/2).attr('y',y+stepH/2+4)
             .attr('text-anchor','middle').attr('font-size',12).attr('font-weight',600).attr('fill','#fff')
             .text(`${d.label}: ${d3.format(',')(d.value)}`)
           // Conversion rate
           if (i > 0) {
             const rate = ((d.value / data[i-1].value) * 100).toFixed(1)
             g.append('text').attr('x',iw+10).attr('y',y+4).attr('font-size',10).attr('fill','#6B7280').text(`${rate}%`)
           }
         })
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   GAUGE / SPEEDOMETER CHART PATTERN (for "gauge", "speedometer", "meter"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface Props { value: number; min?: number; max?: number; label?: string; height?: number }

   export default function GaugeChart({ value, min = 0, max = 100, label = '', height = 240 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current) return
       const render = () => {
         const width = ref.current!.clientWidth || 300
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const cx = width/2, cy = height * 0.7
         const radius = Math.min(width/2, height*0.65) - 20
         const startAngle = -Math.PI * 0.75, endAngle = Math.PI * 0.75
         const angleRange = endAngle - startAngle
         const bg = d3.arc<any>().innerRadius(radius-16).outerRadius(radius).startAngle(startAngle).endAngle(endAngle)
         const g = svg.append('g').attr('transform',`translate(${cx},${cy})`)
         g.append('path').attr('d',bg({})!).attr('fill','#E5E7EB')
         // Colored arc segments (green → yellow → red)
         const segments = [{end:0.33,color:'#22C55E'},{end:0.66,color:'#EAB308'},{end:1,color:'#EF4444'}]
         let prev = 0
         segments.forEach(seg => {
           const segArc = d3.arc<any>().innerRadius(radius-16).outerRadius(radius)
             .startAngle(startAngle + prev * angleRange).endAngle(startAngle + seg.end * angleRange)
           g.append('path').attr('d',segArc({})!).attr('fill',seg.color).attr('opacity',0.3)
           prev = seg.end
         })
         // Value arc
         const pct = Math.max(0, Math.min(1, (value - min) / (max - min)))
         const valArc = d3.arc<any>().innerRadius(radius-16).outerRadius(radius).startAngle(startAngle).endAngle(startAngle + pct * angleRange)
         const valColor = pct < 0.33 ? '#22C55E' : pct < 0.66 ? '#EAB308' : '#EF4444'
         g.append('path').attr('d',valArc({})!).attr('fill',valColor)
         // Needle
         const needleAngle = startAngle + pct * angleRange
         const nx = Math.cos(needleAngle) * (radius - 30), ny = Math.sin(needleAngle) * (radius - 30)
         g.append('line').attr('x1',0).attr('y1',0).attr('x2',nx).attr('y2',ny).attr('stroke','#1F2937').attr('stroke-width',2.5).attr('stroke-linecap','round')
         g.append('circle').attr('r',6).attr('fill','#1F2937')
         // Value text
         g.append('text').attr('y',30).attr('text-anchor','middle').attr('font-size',24).attr('font-weight',700).attr('fill','#1F2937').text(d3.format(',')(value))
         if (label) g.append('text').attr('y',50).attr('text-anchor','middle').attr('font-size',12).attr('fill','#6B7280').text(label)
         // Min/max labels
         g.append('text').attr('x',-radius+10).attr('y',20).attr('font-size',10).attr('fill','#9CA3AF').text(String(min))
         g.append('text').attr('x',radius-10).attr('y',20).attr('text-anchor','end').attr('font-size',10).attr('fill','#9CA3AF').text(String(max))
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [value, min, max, label, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   WATERFALL CHART PATTERN (for "waterfall", "waterfall chart", "bridge chart"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface Props { data: { label: string; value: number; isTotal?: boolean }[]; height?: number }

   export default function WaterfallChart({ data, height = 360 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 600
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const margin = { top: 20, right: 20, bottom: 60, left: 60 }
         const iw = width - margin.left - margin.right
         const ih = height - margin.top - margin.bottom
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`)
         // Compute running totals
         let cumulative = 0
         const bars = data.map(d => {
           if (d.isTotal) { const bar = { ...d, start: 0, end: cumulative }; return bar }
           const start = cumulative; cumulative += d.value
           return { ...d, start, end: cumulative }
         })
         const allVals = bars.flatMap(b => [b.start, b.end])
         const yMin = Math.min(0, ...allVals), yMax = Math.max(0, ...allVals)
         const x = d3.scaleBand().domain(data.map(d=>d.label)).range([0,iw]).padding(0.3)
         const y = d3.scaleLinear().domain([yMin, yMax * 1.1]).range([ih, 0])
         g.append('g').attr('transform',`translate(0,${ih})`).call(d3.axisBottom(x)).selectAll('text').attr('transform','rotate(-30)').style('text-anchor','end').style('font-size','10px')
         g.append('g').call(d3.axisLeft(y).ticks(6).tickFormat(d3.format('.2s')))
         bars.forEach(b => {
           const bw = x.bandwidth()
           const yTop = y(Math.max(b.start, b.end)), yBot = y(Math.min(b.start, b.end))
           const barH = yBot - yTop
           const fill = b.isTotal ? '#6366F1' : b.value >= 0 ? '#22C55E' : '#EF4444'
           g.append('rect').attr('x',x(b.label)!).attr('y',yTop).attr('width',bw).attr('height',barH).attr('fill',fill).attr('rx',2)
           g.append('text').attr('x',x(b.label)!+bw/2).attr('y',yTop-4).attr('text-anchor','middle').attr('font-size',10).attr('fill','#374151').text(d3.format('.2s')(b.end))
         })
         // Connector lines
         bars.forEach((b, i) => {
           if (i < bars.length - 1 && !bars[i+1].isTotal) {
             g.append('line').attr('x1',x(b.label)!+x.bandwidth()).attr('x2',x(bars[i+1].label)!)
               .attr('y1',y(b.end)).attr('y2',y(b.end)).attr('stroke','#9CA3AF').attr('stroke-dasharray','2,2')
           }
         })
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   SANKEY DIAGRAM PATTERN (for "sankey", "flow diagram", "alluvial"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface SankeyNode { name: string }
   interface SankeyLink { source: number; target: number; value: number }
   interface Props { nodes: SankeyNode[]; links: SankeyLink[]; height?: number }

   export default function SankeyChart({ nodes, links, height = 400 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !nodes.length || !links.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 700
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const margin = { top: 10, right: 10, bottom: 10, left: 10 }
         const iw = width - margin.left - margin.right
         const ih = height - margin.top - margin.bottom
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`)
         const color = d3.scaleOrdinal(d3.schemeTableau10)
         // Simple sankey layout (no d3-sankey dependency)
         const nodeMap = new Map<number,{x:number;y:number;dy:number;value:number;name:string}>()
         // Assign columns by topological order
         const outgoing = new Map<number,number[]>(); const incoming = new Map<number,number[]>()
         links.forEach(l => { outgoing.set(l.source,[...(outgoing.get(l.source)||[]),l.target]); incoming.set(l.target,[...(incoming.get(l.target)||[]),l.source]) })
         const cols: number[][] = []; const visited = new Set<number>()
         const sources = nodes.map((_,i) => i).filter(i => !incoming.has(i) || incoming.get(i)!.length === 0)
         let frontier = sources.length ? sources : [0]
         while (frontier.length > 0) { cols.push(frontier); frontier.forEach(n => visited.add(n)); frontier = [...new Set(frontier.flatMap(n => outgoing.get(n) || []))].filter(n => !visited.has(n)) }
         const nodeW = 16, colW = iw / Math.max(cols.length, 1)
         cols.forEach((col, ci) => {
           const totalVal = col.reduce((s,ni) => s + links.filter(l=>l.source===ni||l.target===ni).reduce((a,l)=>Math.max(a,l.value),0), 0) || 1
           let yOff = 0
           col.forEach(ni => {
             const val = links.filter(l=>l.source===ni||l.target===ni).reduce((a,l)=>Math.max(a,l.value),0) || 1
             const dy = (val / totalVal) * ih * 0.8
             nodeMap.set(ni, { x: ci*colW, y: yOff, dy, value: val, name: nodes[ni].name })
             yOff += dy + 8
           })
         })
         // Draw links
         links.forEach(l => {
           const s = nodeMap.get(l.source), t = nodeMap.get(l.target)
           if (!s || !t) return
           const sy = s.y + s.dy/2, ty = t.y + t.dy/2
           const thickness = Math.max(2, (l.value / Math.max(...links.map(x=>x.value))) * 30)
           g.append('path')
             .attr('d', `M${s.x+nodeW},${sy} C${(s.x+nodeW+t.x)/2},${sy} ${(s.x+nodeW+t.x)/2},${ty} ${t.x},${ty}`)
             .attr('fill','none').attr('stroke',color(String(l.source))).attr('stroke-width',thickness).attr('opacity',0.4)
         })
         // Draw nodes
         nodeMap.forEach((n, i) => {
           g.append('rect').attr('x',n.x).attr('y',n.y).attr('width',nodeW).attr('height',n.dy).attr('fill',color(String(i))).attr('rx',3)
           g.append('text').attr('x',n.x + (cols.findIndex(c=>c.includes(i))===0 ? -4 : nodeW+4))
             .attr('y',n.y+n.dy/2).attr('dy','0.35em').attr('text-anchor',cols.findIndex(c=>c.includes(i))===0?'end':'start')
             .attr('font-size',11).attr('fill','#374151').text(n.name)
         })
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [nodes, links, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   BUBBLE CHART PATTERN (for "bubble chart", "bubble plot"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface BubblePoint { x: number; y: number; size: number; label: string; group?: string }
   interface Props { data: BubblePoint[]; height?: number; xLabel?: string; yLabel?: string }

   export default function BubbleChart({ data, height = 400, xLabel = 'X', yLabel = 'Y' }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 600
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const margin = { top: 20, right: 20, bottom: 50, left: 60 }
         const iw = width - margin.left - margin.right, ih = height - margin.top - margin.bottom
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`)
         const color = d3.scaleOrdinal(d3.schemeTableau10)
         const x = d3.scaleLinear().domain(d3.extent(data,d=>d.x) as [number,number]).nice().range([0,iw])
         const y = d3.scaleLinear().domain(d3.extent(data,d=>d.y) as [number,number]).nice().range([ih,0])
         const r = d3.scaleSqrt().domain([0, d3.max(data,d=>d.size)!]).range([4, 40])
         g.append('g').attr('transform',`translate(0,${ih})`).call(d3.axisBottom(x).ticks(6))
         g.append('g').call(d3.axisLeft(y).ticks(6))
         g.selectAll('circle').data(data).join('circle')
           .attr('cx',d=>x(d.x)).attr('cy',d=>y(d.y)).attr('r',d=>r(d.size))
           .attr('fill',d=>color(d.group??'')).attr('fill-opacity',0.6).attr('stroke',d=>color(d.group??'')).attr('stroke-width',1.5)
         // Axis labels
         svg.append('text').attr('x',width/2).attr('y',height-8).attr('text-anchor','middle').attr('font-size',12).attr('fill','#6B7280').text(xLabel)
         svg.append('text').attr('transform','rotate(-90)').attr('x',-height/2).attr('y',16).attr('text-anchor','middle').attr('font-size',12).attr('fill','#6B7280').text(yLabel)
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height, xLabel, yLabel])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   HISTOGRAM PATTERN (for "histogram", "distribution chart", "frequency chart"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface Props { data: number[]; bins?: number; height?: number; xLabel?: string }

   export default function Histogram({ data, bins = 20, height = 320, xLabel = 'Value' }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 600
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const margin = { top: 20, right: 20, bottom: 50, left: 50 }
         const iw = width - margin.left - margin.right, ih = height - margin.top - margin.bottom
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`)
         const x = d3.scaleLinear().domain(d3.extent(data) as [number,number]).nice().range([0,iw])
         const histogram = d3.bin().domain(x.domain() as [number,number]).thresholds(x.ticks(bins))
         const binsData = histogram(data)
         const y = d3.scaleLinear().domain([0, d3.max(binsData, d => d.length)!]).nice().range([ih, 0])
         g.append('g').attr('transform',`translate(0,${ih})`).call(d3.axisBottom(x).ticks(8))
         g.append('g').call(d3.axisLeft(y).ticks(6))
         g.selectAll('rect').data(binsData).join('rect')
           .attr('x', d => x(d.x0!)+1).attr('y', d => y(d.length))
           .attr('width', d => Math.max(0, x(d.x1!) - x(d.x0!) - 2))
           .attr('height', d => ih - y(d.length))
           .attr('fill', '#3B82F6').attr('rx', 1)
         svg.append('text').attr('x',width/2).attr('y',height-8).attr('text-anchor','middle').attr('font-size',12).attr('fill','#6B7280').text(xLabel)
         svg.append('text').attr('transform','rotate(-90)').attr('x',-height/2).attr('y',16).attr('text-anchor','middle').attr('font-size',12).attr('fill','#6B7280').text('Frequency')
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, bins, height, xLabel])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   CANDLESTICK CHART PATTERN (for "candlestick", "OHLC", "stock chart"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface Candle { date: string; open: number; high: number; low: number; close: number }
   interface Props { data: Candle[]; height?: number }

   export default function CandlestickChart({ data, height = 400 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 700
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const margin = { top: 20, right: 40, bottom: 50, left: 60 }
         const iw = width - margin.left - margin.right, ih = height - margin.top - margin.bottom
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`)
         const parseDate = d3.timeParse('%Y-%m-%d')
         const dates = data.map(d => parseDate(d.date) ?? new Date(d.date))
         const x = d3.scaleBand().domain(data.map(d=>d.date)).range([0,iw]).padding(0.3)
         const y = d3.scaleLinear().domain([d3.min(data,d=>d.low)!*0.99, d3.max(data,d=>d.high)!*1.01]).range([ih,0])
         g.append('g').attr('transform',`translate(0,${ih})`).call(d3.axisBottom(x).tickValues(x.domain().filter((_,i)=>i%Math.ceil(data.length/8)===0))).selectAll('text').attr('transform','rotate(-30)').style('text-anchor','end').style('font-size','10px')
         g.append('g').call(d3.axisLeft(y).ticks(8).tickFormat(d3.format(',.0f')))
         // Wicks
         g.selectAll('line.wick').data(data).join('line').attr('class','wick')
           .attr('x1',d=>x(d.date)!+x.bandwidth()/2).attr('x2',d=>x(d.date)!+x.bandwidth()/2)
           .attr('y1',d=>y(d.high)).attr('y2',d=>y(d.low))
           .attr('stroke',d=>d.close>=d.open?'#22C55E':'#EF4444').attr('stroke-width',1)
         // Bodies
         g.selectAll('rect.body').data(data).join('rect').attr('class','body')
           .attr('x',d=>x(d.date)!).attr('y',d=>y(Math.max(d.open,d.close)))
           .attr('width',x.bandwidth())
           .attr('height',d=>Math.max(1,Math.abs(y(d.open)-y(d.close))))
           .attr('fill',d=>d.close>=d.open?'#22C55E':'#EF4444').attr('rx',1)
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   BOX PLOT / WHISKER PATTERN (for "box plot", "whisker", "box and whisker"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface BoxData { label: string; values: number[] }
   interface Props { data: BoxData[]; height?: number }

   export default function BoxPlot({ data, height = 360 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 600
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const margin = { top: 20, right: 20, bottom: 50, left: 50 }
         const iw = width - margin.left - margin.right, ih = height - margin.top - margin.bottom
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${margin.left},${margin.top})`)
         const stats = data.map(d => {
           const sorted = [...d.values].sort(d3.ascending)
           const q1 = d3.quantile(sorted, 0.25)!, med = d3.quantile(sorted, 0.5)!, q3 = d3.quantile(sorted, 0.75)!
           const iqr = q3 - q1
           const min = Math.max(sorted[0], q1 - 1.5*iqr), max = Math.min(sorted[sorted.length-1], q3 + 1.5*iqr)
           const outliers = sorted.filter(v => v < min || v > max)
           return { label: d.label, q1, med, q3, min, max, outliers }
         })
         const allVals = data.flatMap(d => d.values)
         const x = d3.scaleBand().domain(data.map(d=>d.label)).range([0,iw]).padding(0.4)
         const y = d3.scaleLinear().domain(d3.extent(allVals) as [number,number]).nice().range([ih,0])
         g.append('g').attr('transform',`translate(0,${ih})`).call(d3.axisBottom(x))
         g.append('g').call(d3.axisLeft(y).ticks(8))
         stats.forEach(s => {
           const cx = x(s.label)! + x.bandwidth()/2, bw = x.bandwidth()
           // Whiskers
           g.append('line').attr('x1',cx).attr('x2',cx).attr('y1',y(s.min)).attr('y2',y(s.q1)).attr('stroke','#6B7280')
           g.append('line').attr('x1',cx).attr('x2',cx).attr('y1',y(s.q3)).attr('y2',y(s.max)).attr('stroke','#6B7280')
           g.append('line').attr('x1',cx-bw*0.3).attr('x2',cx+bw*0.3).attr('y1',y(s.min)).attr('y2',y(s.min)).attr('stroke','#6B7280')
           g.append('line').attr('x1',cx-bw*0.3).attr('x2',cx+bw*0.3).attr('y1',y(s.max)).attr('y2',y(s.max)).attr('stroke','#6B7280')
           // Box
           g.append('rect').attr('x',x(s.label)!).attr('y',y(s.q3)).attr('width',bw).attr('height',y(s.q1)-y(s.q3)).attr('fill','#DBEAFE').attr('stroke','#3B82F6').attr('stroke-width',1.5).attr('rx',3)
           // Median
           g.append('line').attr('x1',x(s.label)!).attr('x2',x(s.label)!+bw).attr('y1',y(s.med)).attr('y2',y(s.med)).attr('stroke','#1D4ED8').attr('stroke-width',2)
           // Outliers
           s.outliers.forEach(o => { g.append('circle').attr('cx',cx).attr('cy',y(o)).attr('r',3).attr('fill','#EF4444').attr('stroke','none') })
         })
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   POLAR / ROSE CHART PATTERN (for "polar chart", "rose chart", "coxcomb", "wind rose"):
   ```tsx
   import { useEffect, useRef } from 'react'
   import * as d3 from 'd3'

   interface Props { data: { label: string; value: number }[]; height?: number }

   export default function PolarChart({ data, height = 400 }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     useEffect(() => {
       if (!ref.current || !data.length) return
       const render = () => {
         const width = ref.current!.clientWidth || 400
         if (width === 0) return
         d3.select(ref.current).select('svg').remove()
         const radius = Math.min(width, height) / 2 - 30
         const svg = d3.select(ref.current).append('svg').attr('width',width).attr('height',height)
         const g = svg.append('g').attr('transform',`translate(${width/2},${height/2})`)
         const color = d3.scaleOrdinal(d3.schemeTableau10)
         const maxVal = d3.max(data, d => d.value) || 1
         const angleStep = (2 * Math.PI) / data.length
         const rScale = d3.scaleLinear().domain([0, maxVal]).range([0, radius])
         // Grid circles
         for (let lvl = 1; lvl <= 4; lvl++) {
           g.append('circle').attr('r', radius*lvl/4).attr('fill','none').attr('stroke','#E5E7EB').attr('stroke-width',0.5)
         }
         // Petals
         const arc = d3.arc<any>()
         data.forEach((d, i) => {
           const startAngle = i * angleStep - Math.PI/2
           const endAngle = startAngle + angleStep
           const petal = arc({ innerRadius: 0, outerRadius: rScale(d.value), startAngle, endAngle })
           g.append('path').attr('d', petal).attr('fill', color(String(i))).attr('fill-opacity', 0.7).attr('stroke', color(String(i))).attr('stroke-width', 1)
           // Label
           const labelAngle = startAngle + angleStep/2
           const lx = Math.cos(labelAngle) * (radius + 16), ly = Math.sin(labelAngle) * (radius + 16)
           g.append('text').attr('x',lx).attr('y',ly).attr('text-anchor','middle').attr('dominant-baseline','middle').attr('font-size',10).attr('fill','#6B7280').text(d.label)
         })
       }
       render()
       const ro = new ResizeObserver(render); ro.observe(ref.current)
       return () => ro.disconnect()
     }, [data, height])
     return <div ref={ref} style={{ width:'100%', minHeight: height }} />
   }
   ```

   D3 CHOROPLETH MAP PATTERN (for ANY "map" keyword — use REAL us-atlas TopoJSON for atlas-quality shapes):
   Use us-atlas + topojson-client to get detailed state/county boundaries. No hand-written GeoJSON.
   CRITICAL: Do NOT generate a src/data/usStatesGeo.json — use us-atlas package directly.

   FIPS lookup (put at top of component file):
   ```tsx
   const FIPS_TO_ABBR: Record<string,string> = {
     '01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT',
     '10':'DE','11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL',
     '18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD',
     '25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE',
     '32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND',
     '39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD',
     '47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV',
     '55':'WI','56':'WY',
   }
   ```

   SalesMap component — COPY THIS CODE EXACTLY, do not simplify or replace any section:
   ```tsx
   // src/components/SalesMap.tsx
   import { useEffect, useRef, useState, useMemo } from 'react'
   import * as d3 from 'd3'
   import * as topojson from 'topojson-client'
   import type { Topology, GeometryCollection } from 'topojson-specification'
   import type { GeoPermissibleObjects } from 'd3'
   import usaTopo from 'us-atlas/states-10m.json'
   import countiesTopo from 'us-atlas/counties-10m.json'

   // FIPS_TO_ABBR as above

   // Synthetic city/ZIP data — used for the cards shown below the state drill-down map
   // IMPORTANT: these cards appear BELOW the SVG map, not instead of it
   const STATE_CITIES: Record<string, { name:string; zip:string; volume:number }[]> = {
     CA:[{name:'Los Angeles',zip:'90001',volume:4200},{name:'San Francisco',zip:'94102',volume:3100},{name:'San Diego',zip:'92101',volume:2400},{name:'San Jose',zip:'95101',volume:1900},{name:'Sacramento',zip:'95814',volume:1500}],
     TX:[{name:'Houston',zip:'77001',volume:3800},{name:'Dallas',zip:'75201',volume:3200},{name:'Austin',zip:'78701',volume:2600},{name:'San Antonio',zip:'78201',volume:2100},{name:'Fort Worth',zip:'76101',volume:1700}],
     NY:[{name:'Manhattan',zip:'10001',volume:4480},{name:'Brooklyn',zip:'11201',volume:3260},{name:'Queens',zip:'11375',volume:2840},{name:'Buffalo',zip:'14202',volume:1780},{name:'Rochester',zip:'14604',volume:1620},{name:'Albany',zip:'12207',volume:1340}],
     FL:[{name:'Miami',zip:'33101',volume:3100},{name:'Orlando',zip:'32801',volume:2500},{name:'Tampa',zip:'33601',volume:2200},{name:'Jacksonville',zip:'32099',volume:1800},{name:'Fort Lauderdale',zip:'33301',volume:1400}],
     IL:[{name:'Chicago',zip:'60601',volume:3600},{name:'Aurora',zip:'60505',volume:1100},{name:'Naperville',zip:'60540',volume:950},{name:'Rockford',zip:'61101',volume:820}],
     WA:[{name:'Seattle',zip:'98101',volume:2900},{name:'Spokane',zip:'99201',volume:1200},{name:'Tacoma',zip:'98401',volume:1050}],
     GA:[{name:'Atlanta',zip:'30301',volume:2400},{name:'Augusta',zip:'30901',volume:780},{name:'Savannah',zip:'31401',volume:650}],
     OH:[{name:'Columbus',zip:'43085',volume:1700},{name:'Cleveland',zip:'44101',volume:1400},{name:'Cincinnati',zip:'45201',volume:1200}],
     MI:[{name:'Detroit',zip:'48201',volume:2100},{name:'Grand Rapids',zip:'49501',volume:1100},{name:'Ann Arbor',zip:'48103',volume:850}],
     AZ:[{name:'Phoenix',zip:'85001',volume:2600},{name:'Tucson',zip:'85701',volume:1300},{name:'Scottsdale',zip:'85251',volume:1050}],
     CO:[{name:'Denver',zip:'80201',volume:2100},{name:'Colorado Springs',zip:'80901',volume:980},{name:'Aurora',zip:'80010',volume:760}],
     NC:[{name:'Charlotte',zip:'28201',volume:2000},{name:'Raleigh',zip:'27601',volume:1600},{name:'Greensboro',zip:'27401',volume:900}],
   }
   function getCities(abbr: string, totalVol: number) {
     if (STATE_CITIES[abbr]) return STATE_CITIES[abbr]
     const fracs = [0.34, 0.27, 0.21, 0.18]
     const names = ['Metro Area', 'City Center', 'North District', 'South District']
     return fracs.map((f, i) => ({ name: names[i], zip: `${abbr}${String(i+1).padStart(3,'0')}`, volume: Math.round(totalVol * f) }))
   }

   // CANONICAL PROP CONTRACT — pages MUST pass these exact props:
   //   <SalesMap stateSales={filteredRows} makeFilter={makeFilter} />
   // stateSales rows have: { state: string, stateCode: 'us-ca', abbr?: 'CA', make: string, units: number }
   // The component normalises 'us-ca' → 'CA' internally — pages must NOT pre-aggregate.
   interface StateSaleRow { state: string; stateCode?: string; abbr?: string; make: string; units: number }
   interface Props { stateSales: StateSaleRow[]; makeFilter: string; height?: number }

   export default function SalesMap({ stateSales, makeFilter, height = 480 }: Props) {
     const usaRef = useRef<SVGSVGElement>(null)
     const stateRef = useRef<SVGSVGElement>(null)
     const [drillState, setDrillState] = useState<{ fips:string; abbr:string; name:string }|null>(null)
     const [tooltip, setTooltip] = useState<{ x:number; y:number; text:string }|null>(null)

     const stateVolumes = useMemo(() => {
       const map: Record<string,number> = {}
       stateSales.forEach(s => {
         if (makeFilter !== 'all' && s.make !== makeFilter) return
         // normalise stateCode 'us-ca' → 'CA', or use abbr field directly
         const abbr = (s.abbr ?? s.stateCode?.replace(/^us-/i,'') ?? '').toUpperCase()
         map[abbr] = (map[abbr] || 0) + (s.units ?? 0)
       })
       return map
     }, [stateSales, makeFilter])

     // USA choropleth — renders when drillState is null
     useEffect(() => {
       if (!usaRef.current || drillState) return
       const svg = d3.select(usaRef.current)
       svg.selectAll('*').remove()
       const w = usaRef.current.clientWidth || 800
       const topo = usaTopo as unknown as Topology
       const statesGeo = topojson.feature(topo, topo.objects.states as GeometryCollection)
       const mesh = topojson.mesh(topo, topo.objects.states as GeometryCollection, (a,b) => a !== b)
       const projection = d3.geoAlbersUsa().fitSize([w, height], statesGeo as GeoPermissibleObjects)
       const path = d3.geoPath().projection(projection)
       const maxVol = Math.max(1, ...Object.values(stateVolumes))
       const color = d3.scaleSequential(d3.interpolateBlues).domain([0, maxVol])
       svg.selectAll<SVGPathElement,unknown>('path.state')
         .data((statesGeo as GeoJSON.FeatureCollection).features)
         .enter().append('path').attr('class','state')
         .attr('d', d => path(d as GeoPermissibleObjects) ?? '')
         .attr('fill', (d:any) => { const abbr=FIPS_TO_ABBR[String(d.id).padStart(2,'0')]??''; const v=stateVolumes[abbr]??0; return v>0?color(v):'#E5E7EB' })
         .attr('stroke','none').style('cursor','pointer')
         .on('mouseover', function(event,d:any) { d3.select(this).attr('opacity',0.75); const abbr=FIPS_TO_ABBR[String(d.id).padStart(2,'0')]??''; setTooltip({x:event.offsetX,y:event.offsetY,text:`${d.properties?.name??abbr}: ${(stateVolumes[abbr]??0).toLocaleString()} units`}) })
         .on('mouseout', function(){ d3.select(this).attr('opacity',1); setTooltip(null) })
         .on('click', (_,d:any) => { const fips=String(d.id).padStart(2,'0'); setDrillState({fips, abbr:FIPS_TO_ABBR[fips]??'', name:d.properties?.name??''}) })
       svg.append('path').datum(mesh).attr('d',path as any).attr('fill','none').attr('stroke','#fff').attr('stroke-width',0.7).style('pointer-events','none')
       // Gradient legend
       const maxV=Math.max(1,...Object.values(stateVolumes)), lw=200, lh=10, lx=w/2-lw/2, ly=height-44
       const defs=svg.append('defs'); const grad=defs.append('linearGradient').attr('id','smGrad').attr('x1','0').attr('x2','1')
       grad.append('stop').attr('offset','0%').attr('stop-color',color(0)); grad.append('stop').attr('offset','100%').attr('stop-color',color(maxV))
       svg.append('rect').attr('x',lx).attr('y',ly).attr('width',lw).attr('height',lh).attr('rx',3).attr('fill','url(#smGrad)')
       svg.append('g').attr('transform',`translate(${lx},${ly+lh+2})`).call(d3.axisBottom(d3.scaleLinear().domain([0,maxV]).range([0,lw])).ticks(4).tickFormat(v=>d3.format('.2s')(Number(v)))).call(s=>s.select('.domain').remove()).call(s=>s.selectAll('text').style('font-size','10px').attr('fill','#6B7280'))
     }, [stateVolumes, height, drillState])

     // State drill-down — renders the state SVG map with county lines when drillState is set
     useEffect(() => {
       if (!stateRef.current || !drillState) return
       const svg = d3.select(stateRef.current)
       svg.selectAll('*').remove()
       const w = stateRef.current.clientWidth || 800
       const topo = countiesTopo as unknown as Topology
       const countiesGeo = topojson.feature(topo, topo.objects.counties as GeometryCollection) as GeoJSON.FeatureCollection
       const statesGeo = topojson.feature(topo, topo.objects.states as GeometryCollection) as GeoJSON.FeatureCollection
       const stateFeat = statesGeo.features.find((f:any) => String(f.id).padStart(2,'0') === drillState.fips)
       if (!stateFeat) return
       const projection = d3.geoAlbersUsa().fitSize([w, height], stateFeat as GeoPermissibleObjects)
       const path = d3.geoPath().projection(projection)
       svg.append('path').datum(stateFeat).attr('d',d=>path(d as GeoPermissibleObjects)??'').attr('fill','#60A5FA').attr('stroke','none')
       const stateCounties = countiesGeo.features.filter((f:any)=>String(f.id).padStart(5,'0').startsWith(drillState.fips))
       svg.selectAll('path.county').data(stateCounties).enter().append('path').attr('class','county')
         .attr('d',d=>path(d as GeoPermissibleObjects)??'').attr('fill','#60A5FA').attr('stroke','#fff').attr('stroke-width',0.6)
     }, [drillState, height])

     // City cards data — shown BELOW the state SVG map, not instead of it
     const drillCities = useMemo(() => {
       if (!drillState) return []
       return getCities(drillState.abbr, stateVolumes[drillState.abbr] ?? 5000)
     }, [drillState, stateVolumes])

     return (
       <div style={{ display:'flex', flexDirection:'column', gap:0 }}>
         {/* Breadcrumb / back button */}
         <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:12 }}>
           {drillState ? (
             <>
               <button onClick={()=>setDrillState(null)} style={{padding:'4px 12px',borderRadius:6,border:'1px solid #E5E7EB',background:'#fff',cursor:'pointer',fontSize:12,fontWeight:500}}>← Back to USA</button>
               <span style={{padding:'3px 10px',borderRadius:999,background:'#420E71',color:'#fff',fontSize:11,fontWeight:600}}>{drillState.name} · ZIP View</span>
               <span style={{fontSize:12,color:'#6B7280'}}>{(stateVolumes[drillState.abbr]??0).toLocaleString()} units</span>
             </>
           ) : (
             <span style={{padding:'3px 10px',borderRadius:999,background:'#DBEAFE',color:'#1D4ED8',fontSize:11,fontWeight:600}}>North America · State View</span>
           )}
         </div>
         {/* SVG map — always shown, switches between USA view and state+county view */}
         <div style={{position:'relative',background:'#F8FAFC',borderRadius:8,border:'1px solid #E5E7EB',overflow:'hidden'}}>
           {!drillState && <svg ref={usaRef} width="100%" height={height} />}
           {drillState  && <svg ref={stateRef} width="100%" height={height} />}
           {tooltip && <div style={{position:'absolute',left:tooltip.x+12,top:tooltip.y-8,background:'#132445',color:'#fff',padding:'4px 10px',borderRadius:6,fontSize:12,pointerEvents:'none',whiteSpace:'nowrap'}}>{tooltip.text}</div>}
         </div>
         {/* City/ZIP cards — rendered BELOW the state SVG map after drill-down */}
         {drillState && drillCities.length > 0 && (
           <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))',gap:12,marginTop:16}}>
             {drillCities.map(city => {
               const maxV = Math.max(1, ...drillCities.map(c=>c.volume))
               const pct = Math.round((city.volume/maxV)*100)
               return (
                 <div key={city.zip} style={{background:'#fff',border:'1px solid #E5E7EB',borderRadius:8,padding:'12px 14px'}}>
                   <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
                     <span style={{fontSize:13,fontWeight:700,color:'#132445'}}>{city.name}</span>
                     <span style={{fontSize:11,color:'#9CA3AF'}}>{city.zip}</span>
                   </div>
                   <div style={{fontSize:12,color:'#374151',marginBottom:8}}>{city.volume.toLocaleString()} units</div>
                   <div style={{height:4,background:'#FFEDD5',borderRadius:999}}>
                     <div style={{width:`${pct}%`,height:4,background:'#F97316',borderRadius:999}} />
                   </div>
                 </div>
               )
             })}
           </div>
         )}
       </div>
     )
   }
   ```

   UsStateMap component — use this INSTEAD of SalesMap when the page manages its own drill-down panel
   (i.e. when the page wants to render its own state detail UI, not inline inside the map component).
   Props: stateSales, makeFilter, height, onStateClick, focusState.
   When focusState is set, the map ZOOMS into that one state (D3 fitSize on the state feature).
   COPY THIS CODE EXACTLY:
   ```tsx
   // src/components/UsStateMap.tsx
   import { useEffect, useMemo, useRef, useState } from 'react'
   import * as d3 from 'd3'
   import { feature } from 'topojson-client'
   import usaTopo from 'us-atlas/states-10m.json'

   interface StateSaleRow { state: string; stateCode?: string; abbr?: string; make: string; units: number }
   interface Props {
     stateSales: StateSaleRow[]
     makeFilter: string
     height?: number
     onStateClick?: (stateName: string) => void
     focusState?: string
   }

   const nameToAbbr: Record<string, string> = {
     Alabama:'AL',Alaska:'AK',Arizona:'AZ',Arkansas:'AR',California:'CA',Colorado:'CO',
     Connecticut:'CT',Delaware:'DE',Florida:'FL',Georgia:'GA',Hawaii:'HI',Idaho:'ID',
     Illinois:'IL',Indiana:'IN',Iowa:'IA',Kansas:'KS',Kentucky:'KY',Louisiana:'LA',
     Maine:'ME',Maryland:'MD',Massachusetts:'MA',Michigan:'MI',Minnesota:'MN',
     Mississippi:'MS',Missouri:'MO',Montana:'MT',Nebraska:'NE',Nevada:'NV',
     'New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY',
     'North Carolina':'NC','North Dakota':'ND',Ohio:'OH',Oklahoma:'OK',Oregon:'OR',
     Pennsylvania:'PA','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD',
     Tennessee:'TN',Texas:'TX',Utah:'UT',Vermont:'VT',Virginia:'VA',Washington:'WA',
     'West Virginia':'WV',Wisconsin:'WI',Wyoming:'WY','District of Columbia':'DC',
   }

   export default function UsStateMap({ stateSales, makeFilter, height = 460, onStateClick, focusState }: Props) {
     const ref = useRef<HTMLDivElement>(null)
     const svgRef = useRef<SVGSVGElement>(null)
     const [width, setWidth] = useState(0)
     const [tip, setTip] = useState<{ x:number; y:number; name:string; units:number }|null>(null)

     useEffect(() => {
       if (!ref.current) return
       const measure = () => {
         const w = ref.current!.clientWidth
         if (w > 0) setWidth(w)
       }
       measure()
       const ro = new ResizeObserver(() => measure())
       ro.observe(ref.current)
       return () => ro.disconnect()
     }, [])

     const byAbbr = useMemo(() => {
       const m = new Map<string,number>()
       stateSales
         .filter(r => makeFilter === 'All' || r.make === makeFilter)
         .forEach(r => {
           const a = r.abbr || (r.stateCode?.replace(/^us-/i,'') || '').toUpperCase()
           if (a) m.set(a, (m.get(a) || 0) + r.units)
         })
       return m
     }, [stateSales, makeFilter])

     useEffect(() => {
       if (!width || !svgRef.current) return
       const svg = d3.select(svgRef.current)
       svg.selectAll('*').remove()
       const fc: any = feature(usaTopo as any, (usaTopo as any).objects.states)
       const states = fc.features
       const projection = d3.geoAlbersUsa().fitSize([width, height], fc)
       const path = d3.geoPath(projection)

       if (focusState) {
         // Zoom into the selected state
         const sf = states.find((d: any) => d.properties.name === focusState)
         if (!sf) return
         const [[bx0,by0],[bx1,by1]] = path.bounds(sf)
         const scale = 0.82 * Math.min(width / (bx1-bx0||1), height / (by1-by0||1))
         const tx = width/2 - scale*((bx0+bx1)/2)
         const ty = height/2 - scale*((by0+by1)/2)
         const g = svg.append('g').attr('transform',`translate(${tx},${ty}) scale(${scale})`)
         g.selectAll('path').data(states).join('path')
           .attr('d', path as any)
           .attr('fill', (d:any) => d.properties.name === focusState ? '#0064D2' : '#E5E7EB')
           .attr('stroke','#FFFFFF').attr('stroke-width', 0.8/scale)
           .attr('opacity', (d:any) => d.properties.name === focusState ? 1 : 0.4)
         const [cx,cy] = path.centroid(sf)
         const abbr = nameToAbbr[focusState]
         const units = abbr ? byAbbr.get(abbr) || 0 : 0
         if (abbr) {
           g.append('text').attr('x',cx).attr('y',cy-6/scale).attr('text-anchor','middle')
             .attr('font-size',Math.max(10,22/scale)).attr('font-weight','bold').attr('fill','#FFFFFF')
             .attr('pointer-events','none').text(abbr)
           g.append('text').attr('x',cx).attr('y',cy+18/scale).attr('text-anchor','middle')
             .attr('font-size',Math.max(7,14/scale)).attr('fill','#B8EAF5')
             .attr('pointer-events','none').text(units>0?`${units.toLocaleString()} units`:'')
         }
       } else {
         // Full US heatmap
         const max = d3.max(Array.from(byAbbr.values())) || 1
         const color = d3.scaleSequential<string>().domain([0,max]).interpolator(d3.interpolateBlues)
         svg.append('g').selectAll('path').data(states).join('path')
           .attr('d', path as any)
           .attr('fill', (d:any) => { const a=nameToAbbr[d.properties.name]; const v=a?byAbbr.get(a):undefined; return v?color(v):'#E5E7EB' })
           .attr('stroke','#FFFFFF').attr('stroke-width',0.7).style('cursor','pointer')
           .on('mousemove', function(event:any, d:any) {
             const a=nameToAbbr[d.properties.name]; const v=a?byAbbr.get(a)||0:0
             const [mx,my]=d3.pointer(event,ref.current)
             setTip({x:mx,y:my,name:d.properties.name,units:v})
             d3.select(this).attr('stroke','#0064D2').attr('stroke-width',1.8)
           })
           .on('click', (_:any,d:any) => { if(onStateClick) onStateClick(d.properties.name) })
           .on('mouseleave', function() { setTip(null); d3.select(this).attr('stroke','#FFFFFF').attr('stroke-width',0.7) })
       }
     }, [width, height, byAbbr, onStateClick, focusState])

     return (
       <div ref={ref} className="relative w-full" style={{height}}>
         <svg ref={svgRef} width={width} height={height} />
         {!focusState && tip && (
           <div className="absolute z-10 pointer-events-none bg-[#0D1B2A] text-white text-[11px] rounded-[8px] px-[10px] py-[6px] shadow-lg"
             style={{left:tip.x+12,top:tip.y+12}}>
             <div className="font-semibold">{tip.name}</div>
             <div>{tip.units.toLocaleString()} units</div>
           </div>
         )}
       </div>
     )
   }
   export { UsStateMap }
   ```

   CANONICAL PROP CONTRACT for UsStateMap — pages MUST follow this pattern:
   ```tsx
   // Full heatmap — clicking a state sets selectedState
   <UsStateMap stateSales={filteredRows} makeFilter="All" height={470}
     onStateClick={(name) => setSelectedState(prev => prev === name ? null : name)} />

   // Drill-down panel — renders zoomed map of the selected state
   {selectedState && (
     <div ref={drillRef}>
       <UsStateMap stateSales={allRows} makeFilter="All" height={300} focusState={selectedState} />
       {/* data cards below */}
     </div>
   )}
   ```
   useEffect to scroll drill-down into view:
   ```tsx
   const drillRef = useRef<HTMLDivElement>(null)
   useEffect(() => {
     if (selectedState && drillRef.current)
       drillRef.current.scrollIntoView({ behavior:'smooth', block:'start' })
   }, [selectedState])
   ```

   ══════════════════════════════════════════════════════
   CRITICAL — MAP DATA IMPORT RULES (violations = blank maps, always caught in QA)
   ══════════════════════════════════════════════════════
   ✅ CORRECT — static top-level import (Vite bundles at build time, always works):
      import usaTopo from 'us-atlas/states-10m.json'
      import countiesTopo from 'us-atlas/counties-10m.json'
      import worldTopo from 'world-atlas/countries-110m.json'
      Then inside the component: const topo = usaTopo as unknown as Topology

   ✗ FORBIDDEN — will produce blank maps, never use these patterns:
      import('us-atlas/states-10m.json').then(...)   ← dynamic import — BANNED
      d3.json('https://cdn.jsdelivr.net/...')         ← fetch — BANNED
      fetch('https://...')                            ← fetch — BANNED
      useState(null) + useEffect fetch               ← async load — BANNED
   ══════════════════════════════════════════════════════

   DO NOT generate usStatesGeo.json. Import real map data from 'us-atlas/states-10m.json'
   and 'us-atlas/counties-10m.json' which are bundled in node_modules (no fetch needed).
   The state FIPS id is a number in the TopoJSON — String(d.id).padStart(2,'0') gives the 2-digit string.

   WORLD MAP PATTERN — COPY THIS CODE EXACTLY (for "world map", "global map", "country map", "international"):
   Use world-atlas + topojson-client. Projection: d3.geoNaturalEarth1(). IDs are ISO 3166-1 numeric strings.
   MANDATORY: Use static import `import worldTopo from 'world-atlas/countries-110m.json'` — NEVER fetch or dynamic import().
   MANDATORY: Include .on('click') handler that sets a selectedCountry state — highlight the selected path with
   a distinct stroke colour and show the selection as a badge in the filter toolbar with a "Clear" button.
   When a country is selected, show a DETAIL TABLE below the summary table with all rows for that country
   (columns: Make, Model, Units, Revenue, Quarter, YTD Growth). Use a useMemo that filters the raw data
   by selectedCountry.name. Include a totals footer row. Hide this detail table when no country is selected.

   ```tsx
   // src/components/WorldSalesMap.tsx
   import { useEffect, useRef, useState, useMemo } from 'react'
   import * as d3 from 'd3'
   import * as topojson from 'topojson-client'
   import type { Topology, GeometryCollection } from 'topojson-specification'
   import type { GeoPermissibleObjects } from 'd3'
   import worldTopo from 'world-atlas/countries-110m.json'

   // ISO 3166-1 numeric → alpha-2. Include all entries — do NOT truncate this table.
   const ISO_NUM_TO_A2: Record<string,string> = {
     '4':'AF','8':'AL','12':'DZ','24':'AO','32':'AR','36':'AU','40':'AT','31':'AZ',
     '50':'BD','56':'BE','64':'BT','68':'BO','70':'BA','72':'BW','76':'BR','100':'BG',
     '104':'MM','108':'BI','116':'KH','120':'CM','124':'CA','140':'CF','148':'TD',
     '152':'CL','156':'CN','170':'CO','178':'CG','180':'CD','188':'CR','191':'HR',
     '192':'CU','196':'CY','203':'CZ','208':'DK','214':'DO','218':'EC','818':'EG',
     '231':'ET','246':'FI','250':'FR','266':'GA','268':'GE','276':'DE','288':'GH',
     '300':'GR','320':'GT','324':'GN','332':'HT','340':'HN','348':'HU','356':'IN',
     '360':'ID','364':'IR','368':'IQ','372':'IE','376':'IL','380':'IT','388':'JM',
     '392':'JP','400':'JO','398':'KZ','404':'KE','408':'KP','410':'KR','414':'KW',
     '418':'LA','422':'LB','430':'LR','434':'LY','440':'LT','442':'LU','450':'MG',
     '454':'MW','458':'MY','466':'ML','484':'MX','496':'MN','504':'MA','508':'MZ',
     '516':'NA','524':'NP','528':'NL','554':'NZ','558':'NI','562':'NE','566':'NG',
     '578':'NO','586':'PK','591':'PA','598':'PG','600':'PY','604':'PE','608':'PH',
     '616':'PL','620':'PT','642':'RO','643':'RU','646':'RW','682':'SA','686':'SN',
     '694':'SL','706':'SO','710':'ZA','724':'ES','144':'LK','736':'SD','752':'SE',
     '756':'CH','760':'SY','762':'TJ','764':'TH','800':'UG','804':'UA','784':'AE',
     '826':'GB','840':'US','858':'UY','860':'UZ','862':'VE','704':'VN','887':'YE',
     '894':'ZM','716':'ZW','792':'TR','222':'SV','226':'GQ','232':'ER','233':'EE',
     '204':'BJ','096':'BN','084':'BZ','044':'BS','051':'AM','242':'FJ','854':'BF',
   }

   // City data per country for drill-down cards (shown BELOW the country SVG map)
   const COUNTRY_CITIES: Record<string,{name:string;region:string;volume:number}[]> = {
     US:[{name:'New York',region:'NY',volume:4480},{name:'Los Angeles',region:'CA',volume:3800},{name:'Chicago',region:'IL',volume:2900},{name:'Houston',region:'TX',volume:2600},{name:'Phoenix',region:'AZ',volume:1900}],
     GB:[{name:'London',region:'England',volume:3200},{name:'Manchester',region:'England',volume:1400},{name:'Birmingham',region:'England',volume:1100},{name:'Edinburgh',region:'Scotland',volume:820}],
     DE:[{name:'Berlin',region:'Berlin',volume:2400},{name:'Munich',region:'Bavaria',volume:2100},{name:'Hamburg',region:'Hamburg',volume:1600},{name:'Frankfurt',region:'Hesse',volume:1400}],
     FR:[{name:'Paris',region:'Île-de-France',volume:2800},{name:'Lyon',region:'Auvergne-Rhône',volume:1200},{name:'Marseille',region:'PACA',volume:980},{name:'Toulouse',region:'Occitanie',volume:760}],
     JP:[{name:'Tokyo',region:'Kantō',volume:3600},{name:'Osaka',region:'Kansai',volume:2100},{name:'Nagoya',region:'Chūbu',volume:1400},{name:'Fukuoka',region:'Kyushu',volume:890}],
     CN:[{name:'Shanghai',region:'Shanghai',volume:5200},{name:'Beijing',region:'Beijing',volume:4800},{name:'Shenzhen',region:'Guangdong',volume:3900},{name:'Guangzhou',region:'Guangdong',volume:3400}],
     IN:[{name:'Mumbai',region:'Maharashtra',volume:3100},{name:'Delhi',region:'Delhi',volume:2800},{name:'Bangalore',region:'Karnataka',volume:2400},{name:'Chennai',region:'Tamil Nadu',volume:1600}],
     BR:[{name:'São Paulo',region:'São Paulo',volume:2900},{name:'Rio de Janeiro',region:'RJ',volume:2100},{name:'Brasília',region:'DF',volume:1200},{name:'Salvador',region:'Bahia',volume:880}],
     CA:[{name:'Toronto',region:'Ontario',volume:2200},{name:'Vancouver',region:'BC',volume:1600},{name:'Montreal',region:'Quebec',volume:1400},{name:'Calgary',region:'Alberta',volume:960}],
     AU:[{name:'Sydney',region:'NSW',volume:1800},{name:'Melbourne',region:'VIC',volume:1600},{name:'Brisbane',region:'QLD',volume:1100},{name:'Perth',region:'WA',volume:820}],
     ZA:[{name:'Johannesburg',region:'Gauteng',volume:1200},{name:'Cape Town',region:'WC',volume:980},{name:'Durban',region:'KZN',volume:720}],
     MX:[{name:'Mexico City',region:'CDMX',volume:2400},{name:'Guadalajara',region:'Jalisco',volume:1100},{name:'Monterrey',region:'NL',volume:980}],
     KR:[{name:'Seoul',region:'Seoul',volume:2100},{name:'Busan',region:'Busan',volume:1100},{name:'Incheon',region:'Incheon',volume:780}],
     RU:[{name:'Moscow',region:'Moscow',volume:2800},{name:'St. Petersburg',region:'SPb',volume:1400},{name:'Novosibirsk',region:'Novosibirsk',volume:680}],
     AE:[{name:'Dubai',region:'Dubai',volume:2100},{name:'Abu Dhabi',region:'AD',volume:1400},{name:'Sharjah',region:'Sharjah',volume:640}],
     SA:[{name:'Riyadh',region:'Riyadh',volume:1600},{name:'Jeddah',region:'Makkah',volume:1100},{name:'Dammam',region:'Eastern',volume:780}],
     ES:[{name:'Madrid',region:'Madrid',volume:1600},{name:'Barcelona',region:'Catalonia',volume:1400},{name:'Valencia',region:'Valencia',volume:760}],
     IT:[{name:'Milan',region:'Lombardy',volume:1800},{name:'Rome',region:'Lazio',volume:1400},{name:'Turin',region:'Piedmont',volume:820}],
     NL:[{name:'Amsterdam',region:'N. Holland',volume:1200},{name:'Rotterdam',region:'S. Holland',volume:980},{name:'The Hague',region:'S. Holland',volume:640}],
   }
   function getCountryCities(a2: string, totalVol: number) {
     if (COUNTRY_CITIES[a2]) return COUNTRY_CITIES[a2]
     const fracs = [0.38, 0.28, 0.20, 0.14]
     const names = ['Capital', 'City 2', 'City 3', 'City 4']
     return fracs.map((f, i) => ({ name: names[i], region: a2, volume: Math.round(totalVol * f) }))
   }

   // CANONICAL PROP CONTRACT — pages MUST pass these exact props:
   //   <WorldSalesMap salesData={filteredRows} makeFilter={makeFilter} />
   // salesData rows have: { countryCode: 'US', make: string, units: number }
   // The component aggregates internally — pages must NOT pre-aggregate.
   interface SalesRow { countryCode?: string; code?: string; make: string; units: number }
   interface Props { salesData: SalesRow[]; makeFilter?: string; height?: number }

   export default function WorldSalesMap({ salesData, makeFilter='all', height=500 }: Props) {
     const containerRef = useRef<HTMLDivElement>(null)
     const worldRef = useRef<SVGSVGElement>(null)
     const countryRef = useRef<SVGSVGElement>(null)
     const [drillCountry, setDrillCountry] = useState<{isoNum:string;alpha2:string;name:string}|null>(null)
     const [tooltip, setTooltip] = useState<{x:number;y:number;text:string}|null>(null)
     const [containerWidth, setContainerWidth] = useState(0)

     // CRITICAL: measure container width immediately, then observe for resize
     useEffect(() => {
       const el = containerRef.current
       if (!el) return
       const measure = () => { const w = el.clientWidth; if (w > 0) setContainerWidth(w) }
       measure()
       const ro = new ResizeObserver(() => measure())
       ro.observe(el)
       return () => ro.disconnect()
     }, [])

     const countryVolumes = useMemo(() => {
       const map: Record<string,number> = {}
       salesData.forEach(s => {
         if (makeFilter !== 'all' && s.make !== makeFilter) return
         const a2 = (s.countryCode ?? s.code ?? '').toUpperCase()
         if (a2.length === 2) map[a2] = (map[a2]||0) + (s.units ?? 0)
       })
       return map
     }, [salesData, makeFilter])

     // World choropleth — renders when drillCountry is null
     useEffect(() => {
       if (!worldRef.current || drillCountry || !containerWidth) return
       const svg = d3.select(worldRef.current); svg.selectAll('*').remove()
       const w = containerWidth
       const topo = worldTopo as unknown as Topology
       const geo = topojson.feature(topo, topo.objects.countries as GeometryCollection)
       const mesh = topojson.mesh(topo, topo.objects.countries as GeometryCollection, (a,b) => a!==b)
       const proj = d3.geoNaturalEarth1().fitSize([w, height], geo as GeoPermissibleObjects)
       const path = d3.geoPath().projection(proj)
       const maxVol = Math.max(1, ...Object.values(countryVolumes))
       const color = d3.scaleSequential(d3.interpolateBlues).domain([0, maxVol])
       svg.append('rect').attr('width',w).attr('height',height).attr('fill','#EFF6FF')
       svg.selectAll<SVGPathElement,unknown>('path.c').data((geo as GeoJSON.FeatureCollection).features).enter()
         .append('path').attr('class','c').attr('d',d=>path(d as GeoPermissibleObjects)??'')
         .attr('fill',(d:any)=>{ const a2=ISO_NUM_TO_A2[String(d.id)]??''; const v=countryVolumes[a2]??0; return v>0?color(v):'#D1D5DB' })
         .attr('stroke','none').style('cursor','pointer')
         .on('mouseover',function(ev,d:any){ d3.select(this).attr('opacity',0.75); const a2=ISO_NUM_TO_A2[String(d.id)]??''; const v=countryVolumes[a2]??0; setTooltip({x:ev.offsetX,y:ev.offsetY,text:`${d.properties?.name??a2}: ${v>0?v.toLocaleString()+' units':'No data'}`}) })
         .on('mouseout',function(){ d3.select(this).attr('opacity',1); setTooltip(null) })
         .on('click',(_,d:any)=>{ const isoNum=String(d.id); const alpha2=ISO_NUM_TO_A2[isoNum]??''; setDrillCountry({isoNum,alpha2,name:d.properties?.name??alpha2}) })
       svg.append('path').datum(mesh).attr('d',path as any).attr('fill','none').attr('stroke','#fff').attr('stroke-width',0.5).style('pointer-events','none')
       // Legend
       const lw=200, lh=10, lx=w/2-lw/2, ly=height-44
       const defs=svg.append('defs'); const grad=defs.append('linearGradient').attr('id','wmGrad').attr('x1','0').attr('x2','1')
       grad.append('stop').attr('offset','0%').attr('stop-color',color(0)); grad.append('stop').attr('offset','100%').attr('stop-color',color(maxVol))
       svg.append('rect').attr('x',lx).attr('y',ly).attr('width',lw).attr('height',lh).attr('rx',3).attr('fill','url(#wmGrad)')
       svg.append('g').attr('transform',`translate(${lx},${ly+lh+2})`).call(d3.axisBottom(d3.scaleLinear().domain([0,maxVol]).range([0,lw])).ticks(4).tickFormat(v=>d3.format('.2s')(Number(v)))).call(s=>s.select('.domain').remove()).call(s=>s.selectAll('text').style('font-size','10px').attr('fill','#6B7280'))
       svg.append('text').attr('x',lx-4).attr('y',ly+lh-1).attr('text-anchor','end').attr('fill','#9CA3AF').style('font-size','10px').text('Fewer')
       svg.append('text').attr('x',lx+lw+4).attr('y',ly+lh-1).attr('text-anchor','start').attr('fill','#9CA3AF').style('font-size','10px').text('More')
     }, [countryVolumes, height, drillCountry, containerWidth])

     // Country drill-down — zoomed Mercator view of single country
     useEffect(() => {
       if (!countryRef.current || !drillCountry || !containerWidth) return
       const svg = d3.select(countryRef.current); svg.selectAll('*').remove()
       const w = containerWidth
       const topo = worldTopo as unknown as Topology
       const geo = topojson.feature(topo, topo.objects.countries as GeometryCollection) as GeoJSON.FeatureCollection
       const feat = geo.features.find((f:any) => String(f.id) === drillCountry.isoNum)
       if (!feat) return
       const proj = d3.geoMercator().fitSize([w, height-40], feat as GeoPermissibleObjects)
       const path = d3.geoPath().projection(proj)
       svg.append('rect').attr('width',w).attr('height',height).attr('fill','#EFF6FF')
       svg.append('path').datum(feat).attr('d',d=>path(d as GeoPermissibleObjects)??'').attr('fill','#3B82F6').attr('stroke','#1D4ED8').attr('stroke-width',1)
       // City bubbles placed around the country centroid
       const cities = getCountryCities(drillCountry.alpha2, countryVolumes[drillCountry.alpha2]??5000)
       const maxCityVol = Math.max(1,...cities.map(c=>c.volume))
       const [cx,cy] = path.centroid(feat as GeoPermissibleObjects)
       if (cx && cy) {
         cities.forEach(({name,volume},i) => {
           const angle = cities.length===1 ? -Math.PI/2 : (2*Math.PI*i/cities.length)-Math.PI/2
           const spread = Math.min(w,height-40)*0.18
           const bx=cx+Math.cos(angle)*spread, by=cy+Math.sin(angle)*spread*0.7
           const r = 6+(volume/maxCityVol)*18
           svg.append('circle').attr('cx',bx).attr('cy',by).attr('r',r).attr('fill','#F97316').attr('fill-opacity',0.85).attr('stroke','#fff').attr('stroke-width',1.5)
           svg.append('text').attr('x',bx).attr('y',r>10?by+3:by-r-3).attr('text-anchor','middle').attr('fill',r>10?'#fff':'#374151').style('font-size','9px').style('font-weight','700').style('pointer-events','none').text(name.length>8?name.slice(0,7)+'…':name)
         })
       }
     }, [drillCountry, countryVolumes, height, containerWidth])

     // City cards data for below-map display
     const drillCities = useMemo(() => {
       if (!drillCountry) return []
       return getCountryCities(drillCountry.alpha2, countryVolumes[drillCountry.alpha2]??5000)
     }, [drillCountry, countryVolumes])

     return (
       <div ref={containerRef} style={{display:'flex',flexDirection:'column',gap:0,minHeight:height}}>
         {/* Breadcrumb */}
         <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:12}}>
           {drillCountry ? (
             <>
               <button onClick={()=>setDrillCountry(null)} style={{padding:'4px 12px',borderRadius:6,border:'1px solid #E5E7EB',background:'#fff',cursor:'pointer',fontSize:12,fontWeight:500}}>← Back to World</button>
               <span style={{padding:'3px 10px',borderRadius:999,background:'#420E71',color:'#fff',fontSize:11,fontWeight:600}}>{drillCountry.name} · City View</span>
               <span style={{fontSize:12,color:'#6B7280'}}>{(countryVolumes[drillCountry.alpha2]??0).toLocaleString()} units</span>
             </>
           ) : (
             <span style={{padding:'3px 10px',borderRadius:999,background:'#DBEAFE',color:'#1D4ED8',fontSize:11,fontWeight:600}}>Global · Country View</span>
           )}
         </div>
         {/* SVG map — always shown, switches between world view and country zoom */}
         <div style={{position:'relative',background:'#EFF6FF',borderRadius:8,border:'1px solid #E5E7EB',overflow:'hidden'}}>
           {!drillCountry && <svg ref={worldRef} width="100%" height={height} />}
           {drillCountry  && <svg ref={countryRef} width="100%" height={height} />}
           {tooltip && <div style={{position:'absolute',left:tooltip.x+12,top:tooltip.y-8,background:'#132445',color:'#fff',padding:'4px 10px',borderRadius:6,fontSize:12,pointerEvents:'none',whiteSpace:'nowrap'}}>{tooltip.text}</div>}
         </div>
         {/* City cards — rendered BELOW the country SVG map after drill-down */}
         {drillCountry && drillCities.length>0 && (
           <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))',gap:12,marginTop:16}}>
             {drillCities.map((city,i) => {
               const maxV=Math.max(1,...drillCities.map(c=>c.volume))
               const pct=Math.round((city.volume/maxV)*100)
               return (
                 <div key={i} style={{background:'#fff',border:'1px solid #E5E7EB',borderRadius:8,padding:'12px 14px'}}>
                   <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
                     <span style={{fontSize:13,fontWeight:700,color:'#132445'}}>{city.name}</span>
                     <span style={{fontSize:11,color:'#9CA3AF'}}>{city.region}</span>
                   </div>
                   <div style={{fontSize:12,color:'#374151',marginBottom:8}}>{city.volume.toLocaleString()} units</div>
                   <div style={{height:4,background:'#FED7AA',borderRadius:999}}>
                     <div style={{width:`${pct}%`,height:4,background:'#F97316',borderRadius:999}} />
                   </div>
                 </div>
               )
             })}
           </div>
         )}
       </div>
     )
   }
   ```

   SCOPE RULES — which map to use:
   - "USA/US/North America/state map" → SalesMap (us-atlas + counties)
   - "world/global/country/international map" → WorldSalesMap (world-atlas)
   - "map" with no geographic qualifier and data has country codes → WorldSalesMap
   - "map" with state/province data for a single country → SalesMap (or WorldSalesMap drill-down)
   Both can coexist on the same page if the data is hierarchical (world → country → state).

   Data key conventions:
   - SalesMap: stateCode='us-ca' or abbr='CA' (US state 2-letter) — uses 'units' field
   - WorldSalesMap: countryCode='US' (ISO alpha-2 country code) — uses 'units' field
   Both components aggregate internally — NEVER pre-aggregate before passing to a map.

╔══════════════════════════════════════════════════════════════════════════════╗
║  RULE #2 — MAP AND CHART PROP CONTRACTS (violations = blank maps/charts)    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  These are the EXACT props to use when calling map and chart components     ║
║  from pages. Do NOT invent alternative prop names.                           ║
║                                                                              ║
║  SalesMap (US choropleth):                                                   ║
║    <SalesMap stateSales={filteredStateSalesArray} makeFilter={makeFilter} /> ║
║    ✗ NEVER: data=, rows=, salesData=, mapData=, stateData=                  ║
║    ✗ NEVER pass a pre-aggregated Record<string,number> — pass raw rows       ║
║                                                                              ║
║  WorldSalesMap (world choropleth):                                           ║
║    <WorldSalesMap salesData={filteredGlobalSalesArray} makeFilter={make} />  ║
║    ✗ NEVER: data=, sales=, countryVolume=, onSelectCountry=                 ║
║    ✗ NEVER pass a pre-aggregated Record<string,number> — pass raw rows       ║
║                                                                              ║
║  D3BarChart:                                                                 ║
║    <D3BarChart data={barData} horizontal valueFormat={...} />               ║
║    data must be BarDatum[]: { label: string, value: number, color?: string } ║
║                                                                              ║
║  D3LineChart:                                                                ║
║    <D3LineChart series={seriesArray} height={360} />                        ║
║    series must be LineSeries[]: { name, color, points: {x,y}[] }            ║
║                                                                              ║
║  D3DonutChart:                                                               ║
║    <D3DonutChart data={donutData} centerLabel="Total" />                    ║
║    data must be DonutDatum[]: { label: string, value: number, color: string }║
╚══════════════════════════════════════════════════════════════════════════════╝

10. Keep all imports correct — only import what you use.
11. The app must run with zero errors after npm install.

ALWAYS include these exact files:
- index.html
- package.json  (include: react, react-dom, react-router-dom, lucide-react, d3, us-atlas, world-atlas, topojson-client; devDependencies: @types/d3, @types/topojson-specification, @types/geojson)
- vite.config.ts
- tsconfig.json
- tailwind.config.js
- postcss.config.js
- src/main.tsx
- src/index.css  (just @tailwind directives)
- src/App.tsx    (React Router + DS Header/Sidebar/Footer shell)
- src/types.ts   (shared TypeScript types)
- Plus all page and component files needed

package.json devDependencies must include:
  typescript, @types/react, @types/react-dom,
  vite, @vitejs/plugin-react,
  tailwindcss, postcss, autoprefixer

IMPORTANT: Always include d3, us-atlas, world-atlas, topojson-client in dependencies even if
the app description doesn't explicitly mention maps or charts — they are lightweight and
required for any chart or map component. Missing them causes runtime import errors.

Standard boilerplate to use exactly:

index.html:
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>APP_TITLE</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>

vite.config.ts:
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
export default defineConfig({ plugins: [react()], resolve: { alias: { 'mobility-global-ds': path.resolve(__dirname, '../UIDesignSystem/src/index.ts') }, dedupe: ['react','react-dom'] } })

tsconfig.json (COPY EXACTLY — do NOT add "references", do NOT add "tsconfig.node.json"):
{
  "compilerOptions": {
    "target": "ES2020","useDefineForClassFields": true,"lib": ["ES2020","DOM","DOM.Iterable"],
    "module": "ESNext","skipLibCheck": true,"moduleResolution": "bundler",
    "allowImportingTsExtensions": true,"resolveJsonModule": true,"isolatedModules": true,
    "noEmit": true,"jsx": "react-jsx","strict": true,"noUnusedLocals": false,
    "noUnusedParameters": false,"noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
IMPORTANT: Never generate tsconfig.node.json. Never add "references" to tsconfig.json. The above is the complete and final tsconfig.json — nothing else.

tailwind.config.js:
/** @type {import('tailwindcss').Config} */
export default { content: ['./index.html','./src/**/*.{js,ts,jsx,tsx}'], theme: { extend: {} }, plugins: [] }

postcss.config.js:
export default { plugins: { tailwindcss: {}, autoprefixer: {} } }

src/index.css:
@tailwind base;
@tailwind components;
@tailwind utilities;

src/main.tsx (COPY EXACTLY — the basename is REQUIRED because the app is served under /app/<projectName>/):
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

const BASE = import.meta.env.BASE_URL.replace(/\\/$/, '') || ''

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter basename={BASE} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)

IMPORTANT: The 'mobility-global-ds' alias is pre-configured in vite.config.ts by the build system.
NEVER add "mobility-global-ds" to package.json (not in dependencies, not in devDependencies).
It is NOT an npm package — it is resolved via the vite alias at build time. Adding it causes npm E404 errors.
""" + _brand_section()


# ── Multi-pass generation prompts ─────────────────────────────────────────────
# Used when single-shot generation would exceed model output limits (~64k tokens).
#
# Pass 1 — INFRASTRUCTURE: config files, types.ts, all data JSON, App.tsx shell,
#           utils. No components, no pages. Budget: ~20k tokens.
#
# Pass 2 — SHARED COMPONENTS: reusable chart/map/table components (SalesMap,
#           WorldSalesMap, D3BarChart, etc.) used by multiple pages.
#           Budget: ~25k tokens.
#
# Pass 3 — PAGES (one LLM call per page): each page individually, using the
#           infrastructure and shared components as context. Budget: ~10k per page.
#
# The "pages" and "components" lists in the Pass 1 response drive Passes 2 & 3.

PASS1_SYSTEM_PROMPT = """You are an expert React + TypeScript + Tailwind CSS developer.

You are generating a large app in multiple passes. This is PASS 1 (INFRASTRUCTURE).

Generate ONLY infrastructure files. Do NOT generate any page or component .tsx files.
Return ONLY a JSON object with this exact structure:
{
  "projectName": "kebab-case-name",
  "title": "Human Readable Title",
  "description": "What this app does",
  "pages": ["PageOne", "PageTwo", "PageThree", ...],
  "sharedComponents": [],
  "files": {
    "index.html": "...",
    "package.json": "...",
    "vite.config.ts": "...",
    "tsconfig.json": "...",
    "tailwind.config.js": "...",
    "postcss.config.js": "...",
    "src/main.tsx": "...",
    "src/index.css": "...",
    "src/App.tsx": "...",
    "src/types.ts": "...",
    "src/utils/formatters.ts": "...",
    "src/utils/csvExport.ts": "...",
    "schema.sql": "...",
    "seed.sql": "..."
  }
}

CRITICAL RULES for PASS 1:
1. Include ALL config files, schema.sql, seed.sql, ALL utility files, types.ts, and App.tsx.
2. src/App.tsx: use React.lazy + Suspense for every page import. Include all routes.
   The BrowserRouter is in src/main.tsx — App.tsx must NOT wrap with BrowserRouter again.
   Example (use actual page names from requirements):
     const MyPage = lazy(() => import('./pages/MyPage'))
     <Route path="/my-page" element={<Suspense fallback={<div>Loading…</div>}><MyPage /></Suspense>} />
3. "pages" array: every page name exactly as it will be in src/pages/<Name>.tsx
4. "sharedComponents" array: ONLY list components that are genuinely custom and reused across
   multiple pages (e.g. a bespoke KPI widget). Do NOT list maps or charts here — those are
   handled by the skill system (see SKILL SYSTEM below). Leave this array empty if unsure.
5. Do NOT include any src/pages/*.tsx or src/components/*.tsx files — those come in later passes.
6. src/types.ts: define ALL TypeScript interfaces used by all pages and components.
7. Generate COMPLETE file contents — no placeholders, no "// TODO", no "..." truncation.

=== DATABASE + API-FIRST ARCHITECTURE ===

This app uses a SQLite database + auto-generated REST API instead of static JSON files.
DO NOT generate src/data/*.json or src/data/index.ts. Instead generate:

8. **schema.sql**: CREATE TABLE statements for all app data. Rules:
   - Use standard SQLite types: TEXT, INTEGER, REAL, BLOB
   - Include meaningful column names matching the app's domain
   - Add appropriate PRIMARY KEY (use INTEGER PRIMARY KEY AUTOINCREMENT for id columns)
   - Each logical data domain = one table (e.g. sales, inventory, customers, kpis)
   - Minimum 3 tables per app, each with 5+ columns of realistic domain data

9. **seed.sql**: INSERT statements to populate all tables with realistic data. Rules:
   - Minimum 50 rows per table (more for primary data tables)
   - Use realistic values — no placeholder numbers like 0, 999 or "Lorem ipsum"
   - Data must be consistent across tables (e.g. if sales references customers, those customers must exist)
   - Use multi-value INSERT syntax: INSERT INTO table VALUES (...), (...), (...);

10. **src/hooks/useApi.ts**: This file is AUTO-INJECTED by the system. Do NOT generate it.
    Pages will import from '../hooks/useApi' to fetch data. The hook provides:
    - useApi<T>(tableName, {limit, offset, sort, order, filter}) → {data, total, loading, error, hasMore, refetch, fetchMore}
    - apiAggregate(tableName, {groupBy, metric, column, filter}) → grouped/scalar results
    - apiMetadata() → table catalog

11. **src/types.ts**: Define interfaces matching your schema.sql tables. Each table gets a
    corresponding TypeScript interface (e.g. CREATE TABLE sales → interface Sale { ... }).

12. Pages fetch data via the useApi hook — NOT from static imports. Example:
    ```
    import { useApi } from '../hooks/useApi'
    function MyPage() {
      const { data: rows, loading } = useApi<MyRow[]>('table_name', { sort: 'column', order: 'desc' })
      if (loading) return <Spinner />
      return <div>...</div>
    }
    ```

13. For skill pages (charts, grids, maps), the config must reference table names and column names
    that match the schema.sql definition. The skill system will use useApi internally.

14. package.json dependencies MUST always include:
   react, react-dom, react-router-dom, lucide-react, d3, us-atlas, world-atlas, topojson-client
   devDependencies MUST always include:
   typescript, @types/react, @types/react-dom, @types/d3, @types/topojson-specification, @types/geojson,
   vite, @vitejs/plugin-react, tailwindcss, postcss, autoprefixer
   NEVER use Highcharts, highcharts-react-official, or highcharts-more — they break Vite ESM.
   Do NOT add "references" to tsconfig.json. Do NOT generate tsconfig.node.json.
15. MAP DATA — static imports only (dynamic import/fetch = blank maps):
   CORRECT:  import usaTopo from 'us-atlas/states-10m.json'
   CORRECT:  import worldTopo from 'world-atlas/countries-110m.json'
   FORBIDDEN: import('us-atlas/...').then(...)  ← NEVER
   FORBIDDEN: d3.json('https://...')             ← NEVER
   FORBIDDEN: fetch('https://...')               ← NEVER

PAGE NAMING — name pages based on what they DO per the requirements:
- Name pages descriptively based on the app's domain (e.g. "Portfolio", "Timesheets", "DocumentViewer")
- Do NOT name pages after generic UI patterns (avoid "DataGrid", "KpiDashboard", "ChartPage")
- The LLM generates each page from scratch based on requirements — there are no templates

IMPORTANT — API-FIRST DATA:
- All pages get their data from the REST API via useApi hook.
- Use TABLE NAMES and COLUMN NAMES from schema.sql.
- Example: useApi<Row[]>('sales') fetches from /api/data/sales. Column names are snake_case.
- The system auto-generates REST endpoints for every table in schema.sql.
- DO NOT generate src/data/*.json or src/data/index.ts — all data lives in SQLite.
""" + _brand_section()


PASS2_SYSTEM_PROMPT = """You are an expert React + TypeScript + Tailwind CSS developer.

You are generating a large app in multiple passes. This is PASS 2 (SHARED COMPONENTS).

You will receive:
- The original app description
- The infrastructure already built: types.ts, schema.sql, App.tsx, utils

Generate ONLY the shared/reusable components listed — do NOT generate pages.
Return ONLY a JSON object:
{
  "files": {
    "src/components/SalesMap.tsx": "...full file content...",
    "src/components/D3BarChart.tsx": "...full file content...",
    ...
  }
}

CRITICAL RULES for PASS 2:
1. Generate ALL components listed in the "sharedComponents" array from Pass 1.
2. Each component must import types from '../types'. For data, use the useApi hook:
   import { useApi, apiAggregate } from '../hooks/useApi'
   Components receive data as props (fetched by the parent page) or fetch directly via useApi.
3. Charts use the D3 useEffect+useRef+ResizeObserver pattern. Maps use us-atlas/world-atlas.
   CRITICAL: useRef on container <div> with minHeight, call measure() before ResizeObserver, NEVER use parentElement.
4. Generate COMPLETE file contents — no placeholders, no "// TODO", no stubs.
5. Do NOT re-generate config, data, types, or App.tsx — only src/components/*.tsx files.
6. MAP IMPORTS — use static top-level imports ONLY:
   CORRECT:  import usaTopo from 'us-atlas/states-10m.json'
   CORRECT:  import worldTopo from 'world-atlas/countries-110m.json'
   FORBIDDEN: import('us-atlas/...').then(...)   ← causes blank maps, never do this
   FORBIDDEN: d3.json(url) / fetch(url)          ← causes blank maps, never do this
7. useMemo all data arrays used as useEffect deps — prevents infinite render loops and
   chart/map blinking on hover state changes.
8. CANONICAL COMPONENT PROP CONTRACTS (copy these exactly — pages will call with these props):
   SalesMap:      props = { stateSales: StateSaleRow[], makeFilter: string, height?: number }
                  StateSaleRow = { state: string, stateCode?: string, abbr?: string, make: string, units: number }
                  Component aggregates units internally. Pages pass raw rows, NOT pre-aggregated data.
   WorldSalesMap: props = { salesData: SalesRow[], makeFilter?: string, height?: number }
                  SalesRow = { countryCode?: string, code?: string, make: string, units: number }
                  Component aggregates internally. Pages pass raw rows, NOT pre-aggregated data.
   D3BarChart:    props = { data: BarDatum[], height?: number, horizontal?: boolean, valueFormat?: fn, defaultColor?: string }
                  BarDatum = { label: string, value: number, color?: string }
   D3LineChart:   props = { series: LineSeries[], height?: number, band?: BandPoint[], yFormat?: fn }
                  LineSeries = { name: string, color: string, dashed?: boolean, points: {x:string,y:number|null}[] }
   D3DonutChart:  props = { data: DonutDatum[], height?: number, centerLabel?: string, valueFormat?: fn }
                  DonutDatum = { label: string, value: number, color: string }
   All D3 charts MUST have interactive hover tooltips rendered in a React state div (not D3 text).
""" + _brand_section()


PASS3_SYSTEM_PROMPT = """You are an expert React + TypeScript + Tailwind CSS developer.

You are generating a large app in multiple passes. This is PASS 3 (ONE PAGE).

You will receive:
- The original app description
- Types, data shape, and shared component signatures from previous passes
- The specific page name to generate

Generate ONLY the requested single page. Return ONLY a JSON object:
{
  "files": {
    "src/pages/PageName.tsx": "...full file content..."
  }
}

CRITICAL RULES for PASS 3:
1. Import types from '../types', DS from 'mobility-global-ds'.
   For DATA: import { useApi, apiAggregate } from '../hooks/useApi' and fetch from the REST API.
   Use table names from schema.sql. Example:
     const { data: sales, loading } = useApi<Sale>('sales', { sort: 'revenue', order: 'desc', limit: 50 })
   ⚠️ ABSOLUTE BAN: NEVER import from '../data' or '../../data' — those modules DO NOT EXIST.
   The src/data/ directory is NOT part of this project. Any import from it will crash the build.
   All data comes ONLY from the REST API via useApi / apiAggregate / fetch('/api/data/...').
   ⚠️ API BASE URL: When using direct fetch() calls (not useApi), you MUST prefix with the Vite base path:
      const BASE_URL = (import.meta as any).env?.BASE_URL?.replace(/\\/$/, '') || ''
      fetch(`${BASE_URL}/api/chat`, {...})   // CORRECT
      fetch('/api/chat', {...})              // WRONG — breaks when app is served under /app/name/
   For config files: use `tableName: 'table_name'` (from schema.sql) — NEVER `dataExport: someVariable`.
2. COMPONENT IMPORTS: Only import from '../components/Name' if that component is listed
   in the sharedComponents context provided below. If no shared components were generated,
   you MUST inline all chart/visualization code directly in the page file using D3
   useEffect+useRef+ResizeObserver. NEVER import a component that doesn't exist.
3. Generate a COMPLETE, fully working page — no placeholders, no "// TODO", no stubs.
4. Match the design and color theme from the description.
5. If this page has D3 charts, use the useEffect+useRef+ResizeObserver pattern.
   CRITICAL: useRef MUST be on a container <div> (NOT the <svg>). Container MUST have minHeight.
   CRITICAL: Call measure() IMMEDIATELY before setting up ResizeObserver — never rely on RO alone.
   CRITICAL: NEVER use ref.current?.parentElement — ref the container div directly.
   ALL D3 charts MUST have interactive hover tooltips using React state:
   - const [tooltip, setTooltip] = useState<{x:number;y:number;text:string}|null>(null)
   - On mouseover: setTooltip({x: event.offsetX, y: event.offsetY, text: "label: value"})
   - On mouseout: setTooltip(null)
   - Render: {tooltip && <div style={{position:'absolute',left:tooltip.x+12,top:tooltip.y-8,background:'#1E293B',color:'#fff',padding:'4px 10px',borderRadius:6,fontSize:12,pointerEvents:'none',whiteSpace:'nowrap'}}>{tooltip.text}</div>}
   - The chart container must have position:'relative' for tooltip positioning to work.
6. Return ONLY this page's file — nothing else.
7. useMemo all data arrays passed as useEffect deps to prevent blink/infinite loops.
8. MANDATORY PROP CONTRACTS — The user prompt will include a full Component API Reference
   section listing exact interfaces, examples, and anti-patterns for every component.
   You MUST follow them exactly. Wrong props = runtime crash.
   Key rules repeated here for emphasis:
   - D3GroupedBar: use series= NOT groups=, data must be flat records, groupKey is required
   - D3StackedArea: xKey is REQUIRED, use keys= NOT series=
   - D3LineChart: points[].x must be string, NEVER number
   - Tabs: active= must be a number index, NEVER a string tab id
   - PersonaCard: use active= NOT selected=
   - Pagination: use pageCount= NOT totalPages=, onChange= NOT onPageChange=
9. Show a loading spinner while data is being fetched. Handle the error state gracefully.
   Pattern: if (loading) return <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>
10. Config files (src/config/*.config.ts): MUST use `tableName: 'xxx'` for data binding.
    NEVER use `dataExport: variableName` — those variables don't exist. Set `dataExport: null`.
11. AI CHAT PAGES (DataAdvisor, AiAdvisor, Concierge, Assistant, etc.):
    These pages call /api/chat for LLM-powered responses. Required patterns:
    a) BASE_URL: const BASE_URL = (import.meta as any).env?.BASE_URL?.replace(/\\/$/, '') || ''
       Always fetch with `${BASE_URL}/api/chat` — NEVER bare '/api/chat'.
    b) REQUEST BODY FORMAT — the /api/chat endpoint expects this EXACT shape:
       { "messages": [{"role": "user", "content": "..."}, ...], "context": {...optional...} }
       The 'messages' field is a REQUIRED array of {role, content} objects (OpenAI chat format).
       Do NOT send {message: string} or {prompt: string} — it MUST be {messages: [{role, content}]}.
       Maintain a conversation history array and send the full array on each request.
       Prepend the persona's systemContext to the FIRST user message content, not as a separate field.
    c) AbortController: wrap fetch with 180s timeout to prevent browser killing slow LLM calls.
    c2) Retry on 502/503/504: wrap the fetch in a retry loop (max 2 retries, 3s delay). These errors are transient gateway timeouts. Only retry on these status codes, not on 4xx client errors.
    d) Response types: the API returns {type: 'text'|'chart'|'table'|'map', response, data}.
       - 'chart': render D3 inline (bar/line/donut/scatter). data={type,title,data,xKey,yKeys}
       - 'map': render D3+topojson choropleth. data={mapType:'world'|'usa',title,data:[{id,value,label}],colorScheme}
         World-atlas uses NUMERIC IDs — include NUMERIC_TO_ISO2 lookup:
         {"840":"US","276":"DE","392":"JP","156":"CN","826":"GB","250":"FR","380":"IT","724":"ES",
          "036":"AU","124":"CA","076":"BR","356":"IN","410":"KR","682":"SA","784":"AE","710":"ZA",
          "643":"RU","484":"MX","764":"TH","360":"ID","702":"SG","458":"MY","578":"NO","752":"SE",
          "208":"DK","756":"CH","056":"BE","528":"NL","040":"AT","616":"PL","203":"CZ","792":"TR",
          "818":"EG","566":"NG","404":"KE","032":"AR","152":"CL","170":"CO","604":"PE","862":"VE",
          "608":"PH","704":"VN","158":"TW","344":"HK","554":"NZ","372":"IE","620":"PT","246":"FI",
          "300":"GR","348":"HU","642":"RO","804":"UA","586":"PK","050":"BD","144":"LK"}
       - 'table': render data table below text.
       - 'text': render markdown text only.
    e) Caching: maintain Map<string, result> keyed by `${personaId}::${question}`. Skip API on cache hit.
    f) Context: on mount fetch sample rows from each table to pass as sampleRows in the chat context.
    g) Persona system: prepend persona's systemContext as role framing in the user message content.
""" + _brand_section()
