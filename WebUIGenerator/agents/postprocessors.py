"""
Post-processors that fix systematic LLM generation errors.
Imported by uigen_agent.py and server.py.

Each function takes `files: dict` (mapping relative path → file content string)
and returns the patched `files` dict.  They are pure transformations — no disk I/O.

`run_all_postprocessors(files, project_dir=None)` runs them all in the correct order.
"""

import json
import os
import re
from pathlib import Path


# ── Path constants (mirrors the logic in uigen_agent.py) ──────────────────────

def _needs_clean_paths() -> bool:
    """Return True if any project path contains characters that break Vite @fs/ URLs."""
    try:
        from agents.prompts import DS_ROOT
        from config import WEB_APPS_DIR
        _legacy_shared_nm = WEB_APPS_DIR.parent / "shared-node-modules"
        bad_chars = set("&")
        probe = [str(_legacy_shared_nm), str(DS_ROOT)]
        return any(c in p for p in probe for c in bad_chars)
    except Exception:
        return False


def _clean_junction_base() -> Path:
    override = os.environ.get("TURBOUI_JUNCTION_DIR", "").strip()
    if override:
        return Path(override)
    return Path.home() / ".turboui-junctions"


_NEEDS_JUNCTIONS = _needs_clean_paths()
_JUNCTION_BASE   = _clean_junction_base() if _NEEDS_JUNCTIONS else None


def _get_ds_root() -> Path:
    try:
        from agents.prompts import DS_ROOT
        return DS_ROOT
    except Exception:
        return Path(".")


def _get_shared_nm_dir() -> Path:
    try:
        from config import WEB_APPS_DIR
        _legacy = WEB_APPS_DIR.parent / "shared-node-modules"
    except Exception:
        _legacy = Path.home() / ".turboui-junctions" / "shared-nm"
    if _NEEDS_JUNCTIONS and _JUNCTION_BASE:
        return _JUNCTION_BASE / "shared-nm"
    return _legacy


_DS_CLEAN_JUNCTION  = ((_JUNCTION_BASE / "mgds").as_posix()
                       if (_NEEDS_JUNCTIONS and _JUNCTION_BASE)
                       else _get_ds_root().as_posix())
_SHARED_NM_JUNCTION = (_get_shared_nm_dir() / "node_modules").as_posix()


# ── _HC_REPLACEMENTS (used by _patch_highcharts_more) ─────────────────────────

_HC_REPLACEMENTS = {
    "arearange":       "area",
    "areasplinerange": "area",
    "columnrange":     "column",
    "errorbar":        "column",
    "gauge":           "column",
    "solidgauge":      "column",
    "waterfall":       "column",
    "bubble":          "scatter",
    "polygon":         "line",
    "boxplot":         "column",
}


# ── _CANONICAL_US_STATE_MAP (used by _patch_map_components) ───────────────────

_CANONICAL_US_STATE_MAP = """\
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
  const [tip, setTip] = useState<{ x: number; y: number; name: string; units: number } | null>(null)

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
    const m = new Map<string, number>()
    stateSales
      .filter((r) => makeFilter === 'All' || r.make === makeFilter)
      .forEach((r) => {
        const a = r.abbr || (r.stateCode?.replace(/^us-/i, '') || '').toUpperCase()
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
      const sf = states.find((d: any) => d.properties.name === focusState)
      if (!sf) return
      const [[bx0, by0], [bx1, by1]] = path.bounds(sf)
      const scale = 0.82 * Math.min(width / (bx1 - bx0 || 1), height / (by1 - by0 || 1))
      const tx = width / 2 - scale * ((bx0 + bx1) / 2)
      const ty = height / 2 - scale * ((by0 + by1) / 2)
      const g = svg.append('g').attr('transform', `translate(${tx},${ty}) scale(${scale})`)
      g.selectAll('path').data(states).join('path')
        .attr('d', path as any)
        .attr('fill', (d: any) => d.properties.name === focusState ? '#0064D2' : '#E5E7EB')
        .attr('stroke', '#FFFFFF').attr('stroke-width', 0.8 / scale)
        .attr('opacity', (d: any) => d.properties.name === focusState ? 1 : 0.4)
      const [cx, cy] = path.centroid(sf)
      const abbr = nameToAbbr[focusState]
      const units = abbr ? byAbbr.get(abbr) || 0 : 0
      if (abbr) {
        g.append('text').attr('x', cx).attr('y', cy - 6 / scale).attr('text-anchor', 'middle')
          .attr('font-size', Math.max(10, 22 / scale)).attr('font-weight', 'bold').attr('fill', '#FFFFFF')
          .attr('pointer-events', 'none').text(abbr)
        g.append('text').attr('x', cx).attr('y', cy + 18 / scale).attr('text-anchor', 'middle')
          .attr('font-size', Math.max(7, 14 / scale)).attr('fill', '#B8EAF5')
          .attr('pointer-events', 'none').text(units > 0 ? `${units.toLocaleString()} units` : '')
      }
    } else {
      const max = d3.max(Array.from(byAbbr.values())) || 1
      const color = d3.scaleSequential<string>().domain([0, max]).interpolator(d3.interpolateBlues)
      svg.append('g').selectAll('path').data(states).join('path')
        .attr('d', path as any)
        .attr('fill', (d: any) => { const a = nameToAbbr[d.properties.name]; const v = a ? byAbbr.get(a) : undefined; return v ? color(v) : '#E5E7EB' })
        .attr('stroke', '#FFFFFF').attr('stroke-width', 0.7).style('cursor', 'pointer')
        .on('mousemove', function (event: any, d: any) {
          const a = nameToAbbr[d.properties.name]; const v = a ? byAbbr.get(a) || 0 : 0
          const [mx, my] = d3.pointer(event, ref.current)
          setTip({ x: mx, y: my, name: d.properties.name, units: v })
          d3.select(this).attr('stroke', '#0064D2').attr('stroke-width', 1.8)
        })
        .on('click', (_: any, d: any) => { if (onStateClick) onStateClick(d.properties.name) })
        .on('mouseleave', function () { setTip(null); d3.select(this).attr('stroke', '#FFFFFF').attr('stroke-width', 0.7) })
    }
  }, [width, height, byAbbr, onStateClick, focusState])

  return (
    <div ref={ref} className="relative w-full" style={{ height, minHeight: height }}>
      <svg ref={svgRef} width={width} height={height} />
      {!focusState && tip && (
        <div className="absolute z-10 pointer-events-none bg-[#0D1B2A] text-white text-[11px] rounded-[8px] px-[10px] py-[6px] shadow-lg"
          style={{ left: tip.x + 12, top: tip.y + 12 }}>
          <div className="font-semibold">{tip.name}</div>
          <div>{tip.units.toLocaleString()} units</div>
        </div>
      )}
    </div>
  )
}
export { UsStateMap }
"""


# ── Post-processor functions ───────────────────────────────────────────────────

def _patch_vite_for_ds(files: dict, project_dir=None) -> dict:
    """
    Rewrite vite.config.ts to resolve 'mobility-global-ds' via a clean path junction
    (C:/TurboUI/mgds) that has no spaces or special characters.  This prevents Vite from
    generating @fs/ URLs containing '&' from 'S&P Global', which break the proxy.

    Also pins react/react-dom to the shared-nm clean junction so that MGDS (which has
    its own node_modules/react from Storybook) never loads a second React copy.

    Sub-path aliases (react/jsx-dev-runtime, react/jsx-runtime) MUST be listed before
    the bare 'react' alias — Vite object aliases do prefix substitution in key order,
    so listing 'react' first would rewrite 'react/jsx-dev-runtime' to a broken path.
    """
    ds_index = _DS_CLEAN_JUNCTION + "/src/index.ts"
    shared_react = _SHARED_NM_JUNCTION + "/react"
    shared_rdom = _SHARED_NM_JUNCTION + "/react-dom"
    snm = _SHARED_NM_JUNCTION

    # Export package aliases — only include if the files actually exist on disk
    export_aliases = ""
    _xlsx_path = Path(snm.replace("/", os.sep)) / "xlsx" / "xlsx.mjs"
    _jspdf_path = Path(snm.replace("/", os.sep)) / "jspdf" / "dist" / "jspdf.es.min.js"
    _autotable_path = Path(snm.replace("/", os.sep)) / "jspdf-autotable" / "dist" / "jspdf.plugin.autotable.js"
    if _xlsx_path.exists():
        export_aliases += "      'xlsx': '" + snm + "/xlsx/xlsx.mjs',\n"
    if _jspdf_path.exists():
        export_aliases += "      'jspdf': '" + snm + "/jspdf/dist/jspdf.es.min.js',\n"
    if _autotable_path.exists():
        export_aliases += "      'jspdf-autotable': '" + snm + "/jspdf-autotable/dist/jspdf.plugin.autotable.js',\n"

    alias_block = (
        "    alias: {\n"
        "      'mobility-global-ds': '" + ds_index + "',\n"
        "      'react/jsx-dev-runtime': '" + shared_react + "/jsx-dev-runtime.js',\n"
        "      'react/jsx-runtime': '" + shared_react + "/jsx-runtime.js',\n"
        "      'react': '" + shared_react + "/index.js',\n"
        "      'react-dom/client': '" + shared_rdom + "/client.js',\n"
        "      'react-dom': '" + shared_rdom + "/index.js',\n"
        + export_aliases +
        "    },\n"
    )

    vite_template = (
        "import { defineConfig } from 'vite'\n"
        "import react from '@vitejs/plugin-react'\n"
        "export default defineConfig({\n"
        "  plugins: [react()],\n"
        "  resolve: {\n"
        + alias_block +
        "    dedupe: ['react', 'react-dom'],\n"
        "    preserveSymlinks: true,\n"
        "  },\n"
        "  optimizeDeps: {\n"
        "    include: ['react', 'react-dom', 'react-router-dom', 'd3', 'topojson-client'],\n"
        "    force: true,\n"
        "  },\n"
        "})\n"
    )
    files["vite.config.ts"] = vite_template
    return files


def _fix_chart_container(files: dict) -> dict:
    """
    If the LLM generates a ChartContainer wrapper component whose children prop is
    typed as a render function `(dims) => ReactNode`, patch it to also accept plain
    ReactNode children.  Pages almost always pass regular JSX children, not a
    render prop, so the strict function-only type causes a runtime crash:
      TypeError: children is not a function

    The fix rewrites the children type union and the render call so both patterns work.
    """
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "ChartContainer" not in path and "ChartWrapper" not in path and "ChartCard" not in path:
            continue
        if "children is not a function" in content:
            continue  # already patched message

        changed = False

        # Fix 1: widen the children type from render-prop-only to union
        new_content = re.sub(
            r'children\s*:\s*\(\s*\w[^)]*\)\s*=>\s*ReactNode',
            'children: ReactNode | ((dims: { width: number; height: number }) => ReactNode)',
            content
        )
        if new_content != content:
            content = new_content
            changed = True

        # Fix 2: replace the direct children() call with a typeof guard
        new_content = re.sub(
            r'\{width\s*>\s*0\s*&&\s*children\s*\(\s*\{[^}]*\}\s*\)\s*\}',
            '{typeof children === \'function\' ? (width > 0 ? children({ width, height }) : null) : children}',
            content
        )
        if new_content != content:
            content = new_content
            changed = True
        else:
            new_content = re.sub(
                r'\bchildren\s*\(\s*\{[^}]*width[^}]*\}\s*\)',
                'typeof children === \'function\' ? children({ width, height }) : children',
                content
            )
            if new_content != content:
                content = new_content
                changed = True

        if changed:
            files[path] = content
            print(f"[_fix_chart_container] patched {path}", flush=True)

    return files


def _fix_self_wrapping_charts(files: dict) -> dict:
    """
    Detect chart components that self-wrap in ChartContainer (render-prop pattern)
    and fix pages that double-wrap them.
    """
    # Identify self-wrapping components
    self_wrappers: set[str] = set()
    comp_to_path: dict[str, str] = {}

    for path, content in files.items():
        if not path.endswith(".tsx") or "pages/" in path:
            continue
        if "ChartContainer" not in content:
            continue
        if not re.search(r"import\s+\w+\s+from\s+['\"].*ChartContainer['\"]", content):
            continue
        if not re.search(r"return\s*\(?\s*\n?\s*<ChartContainer", content):
            continue
        m = re.search(r"export\s+default\s+function\s+(\w+)", content)
        if m:
            comp_name = m.group(1)
            self_wrappers.add(comp_name)
            comp_to_path[comp_name] = path

    if not self_wrappers:
        return files

    print(f"[_fix_self_wrapping_charts] self-wrapping components: {self_wrappers}", flush=True)

    for path, content in list(files.items()):
        if "pages/" not in path or not path.endswith(".tsx"):
            continue
        changed = False

        for comp in self_wrappers:
            pattern = re.compile(
                r'<ChartContainer\b([^>]*)>\s*\n\s*(<' + re.escape(comp) + r'\b[^/]*/?>)\s*\n\s*</ChartContainer>',
                re.DOTALL
            )
            def _replace_wrapper(m: re.Match) -> str:
                wrapper_attrs = m.group(1)
                comp_tag = m.group(2)
                title_m = re.search(r'title=\{?["\']([^"\'}\n]+)["\']?\}?', wrapper_attrs)
                sub_m   = re.search(r'subtitle=\{?["\']([^"\'}\n]+)["\']?\}?', wrapper_attrs)
                extra = ''
                if title_m and 'title=' not in comp_tag:
                    extra += f' title="{title_m.group(1)}"'
                if sub_m and 'subtitle=' not in comp_tag:
                    extra += f' subtitle="{sub_m.group(1)}"'
                if extra:
                    comp_tag = re.sub(r'(\s*/>|>)$', extra + r'\1', comp_tag.rstrip())
                return comp_tag
            new_content = pattern.sub(_replace_wrapper, content)
            if new_content != content:
                content = new_content
                changed = True

        for comp, comp_path in comp_to_path.items():
            comp_content = files.get(comp_path, "")
            if "ForecastPoint" in comp_content or "priorYear" in comp_content or "forecast" in comp_content.lower():
                pat = re.compile(r'(<' + re.escape(comp) + r'\b[^>]*?)\bseries\s*=\s*\{[^}]*\}', re.DOTALL)
                new_content = pat.sub(lambda m: re.sub(r'\bseries\s*=\s*\{[^}]*\}', 'data={forecast}', m.group(0)), content)
                if new_content != content:
                    content = new_content
                    changed = True
                    if "forecast" not in content.split("from '../data'")[0] if "from '../data'" in content else True:
                        content = re.sub(
                            r"(import\s*\{[^}]*)(from\s*'../data')",
                            lambda m: m.group(1).rstrip().rstrip(',') + ', forecast }' + m.group(2)
                            if 'forecast' not in m.group(1) else m.group(0),
                            content
                        )

        if changed:
            files[path] = content
            print(f"[_fix_self_wrapping_charts] patched {path}", flush=True)

    return files


def _fix_badge_variants(files: dict) -> dict:
    """
    The mobility-global-ds Badge accepts only: default | success | warning | error | info | accent.
    The LLM regularly invents 'neutral', 'danger', 'primary', 'secondary', 'blue', 'green',
    'red', 'gray', 'purple', 'teal', 'amber' — all of which crash at runtime with
    "Cannot destructure property 'bg' of variantMap[variant]".

    Button valid variants: primary | secondary | ghost | danger  (these are fine, skip Button).
    """
    _BADGE_VALID = {"default", "success", "warning", "error", "info", "accent"}

    _BADGE_REMAP = {
        "neutral":   "default",
        "danger":    "error",
        "primary":   "accent",
        "secondary": "default",
        "blue":      "info",
        "green":     "success",
        "red":       "error",
        "gray":      "default",
        "grey":      "default",
        "purple":    "accent",
        "teal":      "info",
        "amber":     "warning",
        "orange":    "warning",
        "dark":      "default",
        "light":     "default",
    }

    for path, content in list(files.items()):
        if not path.endswith(".tsx") and not path.endswith(".ts"):
            continue
        if "Badge" not in content:
            continue

        patched = content

        def _fix_literal(m: re.Match) -> str:
            v = m.group(1)
            if v in _BADGE_VALID:
                return m.group(0)
            replacement = _BADGE_REMAP.get(v, "default")
            return f'variant="{replacement}"'

        patched = re.sub(r'variant="([^"]+)"', _fix_literal, patched)

        def _fix_type_union(m: re.Match) -> str:
            v = m.group(1)
            if v in _BADGE_VALID:
                return m.group(0)
            replacement = _BADGE_REMAP.get(v, "default")
            return f"'{replacement}'"

        # Only rewrite quoted words that are known bad Badge variants — never
        # touch arbitrary string literals like 'react', 'left', 'auto', etc.
        _bad_variants_pattern = "|".join(re.escape(k) for k in _BADGE_REMAP)
        patched = re.sub(rf"'({_bad_variants_pattern})'", _fix_type_union, patched)

        for wrong, right in _BADGE_REMAP.items():
            patched = patched.replace(f"|| '{wrong}'", f"|| '{right}'")

        if patched != content:
            files[path] = patched
            print(f"[_fix_badge_variants] fixed Badge variants in {path}", flush=True)

    return files


def _fix_prop_contracts(files: dict) -> dict:
    """
    Fix systematic prop-name mismatches between map/chart components and the pages
    that call them.  The LLM frequently invents alternate prop names even when the
    system prompt specifies the canonical API.
    """
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        changed = False

        # ── WorldSalesMap page call fixes ──────────────────────────────────────
        for wrong_prop in ("sales", "globalSales", "data", "salesRows", "rows"):
            pat = re.compile(
                r'(<WorldSalesMap\b[^>]*?)\b' + re.escape(wrong_prop) + r'\s*=\s*\{([^}]*)\}',
                re.DOTALL
            )
            new = pat.sub(lambda m: m.group(1) + 'salesData={' + m.group(2) + '}', content)
            if new != content:
                content = new
                changed = True

        content_new = re.sub(r'\bcountryVolume\s*=\s*\{[^}]*\}', '', content)
        if content_new != content:
            content = content_new
            changed = True

        content_new = re.sub(r'\bonSelectCountry\s*=\s*\{[^}]*\}', '', content)
        if content_new != content:
            content = content_new
            changed = True

        # ── SalesMap / UsaSalesMap / USSalesMap page call fixes ───────────────
        for map_tag in ("SalesMap", "UsaSalesMap", "USSalesMap", "UsStateMap", "UsStateSalesMap"):
            for wrong_prop in ("data", "stateSalesData", "sales", "salesRows", "rows", "mapData"):
                pat = re.compile(
                    r'(<' + re.escape(map_tag) + r'\b[^>]*?)\b' + re.escape(wrong_prop) + r'\s*=\s*\{([^}]*)\}',
                    re.DOTALL
                )
                new = pat.sub(lambda m: m.group(1) + 'stateSales={' + m.group(2) + '}', content)
                if new != content:
                    content = new
                    changed = True

        # ── makeFilter: remove if it's a function (callback), not a string ────
        for map_tag in ("SalesMap", "UsaSalesMap", "USSalesMap", "UsStateMap", "USSalesMap"):
            def _remove_fn_makefilter(m: re.Match) -> str:
                full_tag = m.group(0)
                prop_m = re.search(r'\bmakeFilter=\{(\w+)\}', full_tag)
                if not prop_m:
                    return full_tag
                identifier = prop_m.group(1)
                if re.search(r'const\s+' + re.escape(identifier) + r'\s*=\s*useCallback', content):
                    return full_tag.replace(f'makeFilter={{{identifier}}}', '')
                return full_tag
            new = re.sub(
                r'<' + re.escape(map_tag) + r'\b[^>]*/?>',
                _remove_fn_makefilter,
                content,
                flags=re.DOTALL
            )
            if new != content:
                content = new
                changed = True

        # ── GroupedBarChart: groups= → data=
        for wrong_prop in ("groups", "barData", "chartData", "items"):
            pat = re.compile(
                r'(<GroupedBarChart\b[^>]*?)\b' + re.escape(wrong_prop) + r'\s*=\s*\{([^}]*)\}',
                re.DOTALL
            )
            new = pat.sub(lambda m: m.group(1) + 'data={' + m.group(2) + '}', content)
            if new != content:
                content = new
                changed = True

        # ── D3LineChart: series prop fix ───────────────────────────────────────
        for wrong_prop in ("data", "lines", "lineData"):
            pat = re.compile(
                r'(<D3LineChart\b[^>]*?)\b' + re.escape(wrong_prop) + r'\s*=\s*\{([^}]*)\}',
                re.DOTALL
            )
            new = pat.sub(lambda m: m.group(1) + 'series={' + m.group(2) + '}', content)
            if new != content:
                content = new
                changed = True

        # ── UsStateMap: ensure onStateClick + focusState drill-down wiring ───
        if 'UsStateMap' in content and 'onStateClick' not in content:
            if 'const [selectedState' not in content:
                content = re.sub(
                    r'(const \[\w+,\s*set\w+\]\s*=\s*useState[^;]+;)',
                    r'\1\n  const [selectedState, setSelectedState] = React.useState<string | null>(null)',
                    content, count=1
                )
                if 'React.useState' in content and 'import React' not in content and "from 'react'" in content:
                    content = re.sub(
                        r"(import \{[^}]+)\}\s*from\s*'react'",
                        lambda m: m.group(0).replace('}', ', useState }').replace('useState , useState', 'useState'),
                        content, count=1
                    )
                    content = content.replace('React.useState<string | null>', 'useState<string | null>')
                changed = True
            content = re.sub(
                r'(<UsStateMap\b)(?![^>]*onStateClick)([^/]*/?>)',
                lambda m: m.group(1) + '\n          onStateClick={(name) => setSelectedState(prev => prev === name ? null : name)}' + m.group(2),
                content
            )
            changed = True

        if changed:
            files[path] = content
            print(f"[_fix_prop_contracts] patched {path}", flush=True)

    return files


def _patch_map_components(files: dict) -> dict:
    """
    Fix two systematic bugs that appear when the LLM generates map components:

    1. react-simple-maps WorldSalesMap: geo.properties.ADM0_A3 does not exist in
       world-atlas@2 — the only reliable key is geo.id (ISO 3166-1 numeric string).
    2. UsaSalesMap stateCode normalisation.
    3. react-simple-maps import removal.
    """
    # ── Fix 3: strip non-existent / hallucinated packages from package.json ──
    _STRIP_PACKAGES = [
        "react-simple-maps", "@types/react-simple-maps",
        "@types/us-atlas", "@types/world-atlas",
        "@types/topojson", "@types/topojson-specification",
        "@types/geojson-vt",
        "mobility-global-ds", "@mobility-global/ds",
    ]
    for path in ("package.json",):
        if path in files:
            for pkg in _STRIP_PACKAGES:
                files[path] = re.sub(
                    r',?\s*"' + re.escape(pkg) + r'"\s*:\s*"[^"]*"', '', files[path]
                )

    # ── Fix 1 & 2: patch map TSX files ───────────────────────────────────────
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        changed = False

        if "react-simple-maps" in content:
            content = re.sub(
                r"import\s+\{[^}]*\}\s+from\s+'react-simple-maps'[^\n]*\n", "", content
            )
            content = re.sub(
                r'import\s+\{[^}]*\}\s+from\s+"react-simple-maps"[^\n]*\n', "", content
            )
            changed = True

        if "ADM0_A3" in content or "ISO2_TO_ISO3" in content:
            content = content.replace(
                "geo.properties?.['ADM0_A3'] ?? geo.id ?? ''",
                "String(geo.id)"
            )
            content = content.replace(
                "geo.properties?.ADM0_A3 ?? geo.id ?? ''",
                "String(geo.id)"
            )
            content = re.sub(
                r"Object\.entries\(ISO2_TO_ISO3\)\.find\(\(\[,\s*v\]\)\s*=>\s*v\s*===\s*iso3\)\?\.\[0\]",
                "NUMERIC_TO_ISO2[String(geo.id).padStart(3,'0')]",
                content
            )
            if "NUMERIC_TO_ISO2" not in content and "ISO2_TO_ISO3" in content:
                numeric_table = (
                    "const NUMERIC_TO_ISO2: Record<string,string> = {\n"
                    "  '840':'US','124':'CA','484':'MX','076':'BR','032':'AR','152':'CL',\n"
                    "  '276':'DE','826':'GB','250':'FR','380':'IT','724':'ES','578':'NO',\n"
                    "  '752':'SE','528':'NL','616':'PL','392':'JP','410':'KR','156':'CN',\n"
                    "  '356':'IN','036':'AU','360':'ID','764':'TH','702':'SG','458':'MY',\n"
                    "  '704':'VN','158':'TW','710':'ZA','566':'NG','818':'EG','784':'AE',\n"
                    "  '682':'SA','376':'IL','792':'TR','643':'RU','804':'UA','076':'BR',\n"
                    "}\n"
                )
                content = re.sub(
                    r"(const ISO2_TO_ISO3[^\n]*\{[^}]*\}[^\n]*\n)",
                    numeric_table,
                    content,
                    count=1,
                    flags=re.DOTALL
                )
            changed = True

        _is_usa_map = "UsaSalesMap" in path or ("SalesMap" in path and "World" not in path)
        _normdata_used = "normData" in content
        _normdata_defined = bool(re.search(r"const normData\s*=", content))
        _needs_norm_inject = _is_usa_map and _normdata_used and not _normdata_defined
        _needs_data_replace = (
            _is_usa_map and not _normdata_used
            and ("us-" in content or "stateCode" in content)
        )
        if _needs_norm_inject or _needs_data_replace:
            _NORM_MEMO = (
                "const normData = useMemo(() => {\n"
                "    const out: Record<string,number> = {}\n"
                "    Object.entries(data).forEach(([k,v]) => {\n"
                "      const key = k.startsWith('us-') ? k.slice(3).toUpperCase() : k.toUpperCase()\n"
                "      out[key] = (out[key] || 0) + v\n"
                "    })\n"
                "    return out\n"
                "  }, [data])\n  "
            )
            if _needs_norm_inject and not _normdata_defined:
                injected = re.sub(
                    r"(const (?:maxUnits|colorScale)\s*=\s*useMemo)",
                    _NORM_MEMO + r"\1",
                    content,
                    count=1,
                )
                if injected != content:
                    content = injected
                    changed = True
            if _needs_data_replace:
                content = re.sub(
                    r"(const maxUnits = useMemo\(\(\) => Math\.max\(\.\.\.Object\.values\(data\))",
                    _NORM_MEMO + "const maxUnits = useMemo(() => Math.max(...Object.values(normData)",
                    content,
                    count=1,
                )
                content = content.replace("data[abbr]", "normData[abbr]")
                content = content.replace("(data[", "(normData[")
                changed = True

        # ── Fix 4: UsStateMap — inject focusState zoom if missing ───────────────
        if "UsStateMap" in path and "focusState" not in content:
            files[path] = _CANONICAL_US_STATE_MAP
            print(f"[_patch_map_components] replaced {path} with canonical UsStateMap (focusState added)", flush=True)
            continue

        if changed:
            files[path] = content
            print(f"[_patch_map_components] patched {path}", flush=True)

    # ── Fix 5: Normalize all USA map imports to match the actual component file ─
    _usa_map_variants = ("UsaSalesMap", "USSalesMap", "UsStateMap", "USStateMap", "UsStateSalesMap", "SalesMap")
    _USA_MAP_DETECT = ("UsaSalesMap", "USSalesMap", "UsStateMap", "USStateMap", "UsStateSalesMap")
    _actual_usa_map = None
    for _fp in files:
        _fname = _fp.split("/")[-1].replace(".tsx", "")
        if (_fname in _USA_MAP_DETECT or any(_v in _fname for _v in _USA_MAP_DETECT)) and "World" not in _fname:
            _actual_usa_map = _fname
            break
    _canonical = _actual_usa_map or "UsaSalesMap"

    for path, content in list(files.items()):
        if not path.endswith(".tsx") or _canonical in path:
            continue
        patched = content
        for wrong in _usa_map_variants:
            if wrong == _canonical:
                continue
            for quote in ("'", '"'):
                patched = patched.replace(
                    f"from {quote}../components/{wrong}{quote}",
                    f"from '../components/{_canonical}'",
                )
                patched = patched.replace(
                    f"from {quote}./components/{wrong}{quote}",
                    f"from './components/{_canonical}'",
                )
            patched = re.sub(
                rf"\bimport {wrong} from",
                f"import {_canonical} from",
                patched,
            )
            patched = patched.replace(f"<{wrong} ", f"<{_canonical} ")
            patched = patched.replace(f"<{wrong}/", f"<{_canonical}/")
            patched = patched.replace(f"<{wrong}>", f"<{_canonical}>")
            patched = patched.replace(f"</{wrong}>", f"</{_canonical}>")
        if patched != content:
            files[path] = patched
            print(f"[_patch_map_components] normalized USA map import in {path} → {_canonical}", flush=True)

    return files


def _patch_dynamic_imports(files: dict) -> dict:
    """
    Convert dynamic map data imports (import() / fetch / d3.json) to static top-level
    imports.  The LLM frequently ignores the 'FORBIDDEN' rule and uses async loading
    patterns that cause blank maps in Vite dev mode.
    """
    _ATLAS = [
        ("us-atlas/states-10m",       "import usaStatesTopo from 'us-atlas/states-10m.json'",       "usaStatesTopo"),
        ("us-atlas/counties-10m",     "import usaCountiesTopo from 'us-atlas/counties-10m.json'",   "usaCountiesTopo"),
        ("world-atlas/countries-110m","import worldTopo from 'world-atlas/countries-110m.json'",     "worldTopo"),
        ("world-atlas/countries-50m", "import worldTopo from 'world-atlas/countries-50m.json'",      "worldTopo"),
        ("us-atlas@3/states-10m",     "import usaStatesTopo from 'us-atlas/states-10m.json'",        "usaStatesTopo"),
        ("us-atlas@3/counties-10m",   "import usaCountiesTopo from 'us-atlas/counties-10m.json'",   "usaCountiesTopo"),
        ("world-atlas@2/countries-110m","import worldTopo from 'world-atlas/countries-110m.json'",   "worldTopo"),
    ]

    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        changed = False

        for fragment, static_import, var_name in _ATLAS:
            if fragment not in content:
                continue

            has_dyn_import = bool(re.search(
                r"import\s*\(['\"][^'\"]*" + re.escape(fragment) + r"[^'\"]*['\"]", content
            ))
            has_fetch = bool(re.search(
                r"(?:fetch|d3\.json)\s*\(['\"]https?://[^'\"]*" + re.escape(fragment.split('/')[-1]) + r"[^'\"]*['\"]", content
            ))

            if not (has_dyn_import or has_fetch):
                continue

            if static_import.split("'")[1] not in content:
                last_import_end = 0
                for m in re.finditer(r"^import\s+.*?;?\s*$", content, re.MULTILINE):
                    last_import_end = m.end()
                if last_import_end:
                    content = content[:last_import_end] + "\n" + static_import + content[last_import_end:]
                else:
                    content = static_import + "\n" + content
                changed = True

            setter_match = re.search(
                r"(set\w+)\s*\(\s*(?:m\.default\s*\?\?\s*m|j|data|topo|result)\s*\)",
                content
            )
            if not setter_match:
                setter_match = re.search(r"\b(set(?:Topo|GeoData|TopoData|Data|States|World)\w*)\s*\(", content)

            if setter_match:
                setter = setter_match.group(1)
                replaced = re.sub(
                    r"useEffect\s*\(\s*\(\s*\)\s*=>\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*,\s*\[\s*\]\s*\)",
                    lambda m: (
                        f"useEffect(() => {{ {setter}({var_name} as any) }}, [])"
                        if any(frag in m.group(0) for frag in [fragment, fragment.split('/')[-1]])
                        else m.group(0)
                    ),
                    content,
                    flags=re.DOTALL
                )
                if replaced != content:
                    content = replaced
                    changed = True

        if changed:
            files[path] = content
            print(f"[_patch_dynamic_imports] patched {path}", flush=True)

    return files


def _patch_index_html(files: dict) -> dict:
    """
    Fix absolute-path hrefs/srcs in index.html that break when served under a sub-path.
    """
    html = files.get("index.html", "")
    if not html:
        return files
    html = re.sub(r'(href|src)="/vite\.svg"', r'\1="./vite.svg"', html)
    files["index.html"] = html
    return files


def _patch_highcharts_more(files: dict) -> dict:
    """
    1. Strip any highcharts-more / highcharts/modules/* imports (they break in Vite ESM).
    2. Replace banned series types with safe base equivalents.
    3. Strip ALL Highcharts imports entirely — the LLM should have used D3 instead.
    """
    for path, content in list(files.items()):
        if not (path.endswith(".tsx") or path.endswith(".ts")):
            continue
        if "highcharts" not in content.lower():
            continue

        changed = False

        new_lines = []
        for line in content.splitlines(keepends=True):
            if re.match(r"\s*import\s+.*['\"]highcharts", line, re.IGNORECASE):
                changed = True
                continue
            new_lines.append(line)
        content = "".join(new_lines)

        for banned, replacement in _HC_REPLACEMENTS.items():
            pattern = rf"(type\s*:\s*['\"]){banned}(['\"])"
            new_content = re.sub(pattern, rf"\g<1>{replacement}\g<2>", content)
            if new_content != content:
                changed = True
                content = new_content
                if banned in ("arearange", "areasplinerange"):
                    content = re.sub(
                        r"(data\s*:\s*\w+\.map\([^)]+\s*=>\s*)\[([^,\[\]]+),\s*([^\[\]]+)\](\s*\))",
                        r"\g<1>\g<3>\g<4>",
                        content
                    )

        if changed:
            files[path] = content

    pj_key = "package.json"
    if pj_key in files:
        try:
            pj = json.loads(files[pj_key])
            for section in ("dependencies", "devDependencies"):
                pkg = pj.get(section, {})
                removed = [k for k in list(pkg.keys()) if "highcharts" in k.lower()]
                for k in removed:
                    del pkg[k]
            files[pj_key] = json.dumps(pj, indent=2)
        except Exception:
            pass

    return files


def _ensure_tsconfig_vite_types(files: dict) -> dict:
    """Ensure tsconfig.json includes vite/client types so import.meta.env resolves."""
    if "tsconfig.json" not in files:
        return files
    try:
        cfg = json.loads(files["tsconfig.json"])
        opts = cfg.setdefault("compilerOptions", {})
        types = opts.setdefault("types", [])
        if "vite/client" not in types:
            types.append("vite/client")
            files["tsconfig.json"] = json.dumps(cfg, indent=2)
            print("[_ensure_tsconfig_vite_types] added vite/client to tsconfig.json", flush=True)
    except Exception:
        pass
    return files


# ── Post-processor: warn on unfilled template placeholders ────────────────────

def _warn_unfilled_placeholders(files: dict) -> dict:
    """
    Scan every generated .ts / .tsx file for any remaining {{PLACEHOLDER}} tokens.
    These are template markers the LLM was supposed to replace but didn't — leaving
    them in produces broken TypeScript that silently compiles but crashes at runtime.

    We print a clear warning for each hit so the failure is visible in the build log.
    We do NOT try to auto-fix here because the right values are domain-specific; the
    retry logic in _gen_page handles the primary prevention.  This is a last-resort
    diagnostic so the user (and log) can see exactly what was missed.
    """
    _PLACEHOLDER_RE = re.compile(r'\{\{[A-Z][A-Z0-9_]*\}\}')

    for path, content in files.items():
        if not (path.endswith(".ts") or path.endswith(".tsx")):
            continue
        hits = _PLACEHOLDER_RE.findall(content)
        if hits:
            unique = sorted(set(hits))
            print(
                f"[_warn_unfilled_placeholders] WARNING: {path} still contains "
                f"unfilled placeholder(s): {unique}",
                flush=True,
            )

    return files


def _strip_data_imports(files: dict) -> dict:
    """Remove stale src/data/ files and import statements when API-first mode is active.
    If schema.sql is present (at root or in api/), the app uses the REST API — not static JSON imports.

    Also patches dangling variable references left behind after stripping the import:
    - `dataExport: varName` → `dataExport: null`
    - Injects `tableName` derived from schema.sql table names when possible.
    """
    if "schema.sql" not in files and "api/schema.sql" not in files:
        return files

    # Remove any src/data/ files the LLM generated despite instructions
    stale_keys = [k for k in files if k.startswith("src/data/")]
    for k in stale_keys:
        del files[k]
        print(f"[_strip_data_imports] Removed stale file: {k}", flush=True)

    # Extract table names from schema.sql for inferring tableName
    _table_names = []
    schema_content = files.get("api/schema.sql", "") or files.get("schema.sql", "")
    if schema_content:
        _table_names = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", schema_content, re.IGNORECASE)

    # Regex to capture named imports from '../data' or '../../data'
    import_re = re.compile(
        r"^import\s+\{([^}]+)\}\s+from\s+['\"]\.\.(?:/\.\.)?/data(?:/[^'\"]*)?['\"];?\s*$",
        re.MULTILINE,
    )
    # Fallback for default imports: import foo from '../data/...'
    import_default_re = re.compile(
        r"^import\s+(\w+)\s+from\s+['\"]\.\.(?:/\.\.)?/data(?:/[^'\"]*)?['\"];?\s*$",
        re.MULTILINE,
    )

    for path, content in list(files.items()):
        if not (path.endswith(".ts") or path.endswith(".tsx")):
            continue
        if "from '../data" not in content and "from '../../data" not in content and 'from "../data' not in content:
            continue

        # Collect all imported variable names from data imports
        imported_vars = set()
        for m in import_re.finditer(content):
            names = [n.strip().split(" as ")[-1].strip() for n in m.group(1).split(",")]
            imported_vars.update(n for n in names if n)
        for m in import_default_re.finditer(content):
            imported_vars.add(m.group(1).strip())

        # Strip the import lines
        new_content = import_re.sub("// data fetched via useApi hook", content)
        new_content = import_default_re.sub("// data fetched via useApi hook", new_content)

        # Replace dangling references to stripped variables
        if imported_vars:
            for var in imported_vars:
                # Pattern: `dataExport: varName` or `dataExport: varName,`
                new_content = re.sub(
                    rf'\bdataExport\s*:\s*{re.escape(var)}\b',
                    'dataExport: null',
                    new_content,
                )
                # Pattern: standalone usage like `data={varName}` or `= varName`
                # Only null-out if the var is used as a standalone identifier (not inside strings)
                new_content = re.sub(
                    rf'(?<![\'"\w.]){re.escape(var)}(?![\'"\w])',
                    'null',
                    new_content,
                )

            # Inject tableName if not already present and we have table names from schema
            if 'tableName' not in new_content and _table_names:
                # Try to infer the best table from the file name
                page_name = path.split("/")[-1].replace(".config.ts", "").replace(".tsx", "").lower()
                best_table = _table_names[0]  # default to first table
                for t in _table_names:
                    if t.lower() in page_name or page_name in t.lower():
                        best_table = t
                        break
                # Insert tableName after dataExport: null
                new_content = new_content.replace(
                    "dataExport: null",
                    f"dataExport: null,\n  tableName: '{best_table}'",
                    1,
                )

        if new_content != content:
            files[path] = new_content
            print(f"[_strip_data_imports] Patched data import + dangling refs in: {path}", flush=True)

    return files


# ── Public orchestration function ─────────────────────────────────────────────

def _inject_api_proxy(files: dict, project_name: str = "", port: int = 0, api_port: int = 0) -> dict:
    """If app_server.py or api_server.py is bundled (or schema.sql present), inject the
    full server block (port + proxy with base-path rewrite) into vite.config.ts.

    When project_name and port are supplied (called from generate_project), the server
    block includes port, host, and the base-path-aware rewrite rule so the proxy chain
    works through the main FastAPI server at localhost:3000.

    api_port is the unique port assigned to this project's API server.
    """
    has_api = (
        "api/app_server.py" in files or "app_server.py" in files
        or "api_server.py" in files
        or "api/schema.sql" in files or "schema.sql" in files
        or "backend/.backend_type" in files or "backend/pom.xml" in files
    )
    if not has_api:
        return files
    vite_key = "vite.config.ts"
    if vite_key not in files:
        return files
    content = files[vite_key]
    if "'/api'" in content or '"/api"' in content:
        return files

    target_port = api_port or 8080

    # Build proxy section — always include /api, and the base-path rewrite if project_name known
    proxy_lines = f"      '/api': {{ target: 'http://localhost:{target_port}', changeOrigin: true }},\n"
    if project_name:
        proxy_lines += (
            f"      '/app/{project_name}/api': {{ target: 'http://localhost:{target_port}', changeOrigin: true, "
            f"rewrite: (path) => path.replace(/^\\/app\\/{project_name}/, '') }},\n"
        )

    # Build base + full server block
    base_line = f"  base: '/app/{project_name}/',\n" if project_name else ""
    port_line = f"    port: {port},\n    host: '0.0.0.0',\n    hmr: false,\n    allowedHosts: ['localhost'],\n" if port else ""
    fs_line = f"    fs: {{ allow: ['..', '{_DS_CLEAN_JUNCTION}', '{_SHARED_NM_JUNCTION}'] }},\n" if port else ""
    warmup_line = "    warmup: { clientFiles: ['./src/App.tsx', './src/pages/*.tsx'] },\n"
    server_block = (
        base_line
        + "  server: {\n"
        + port_line
        + warmup_line
        + fs_line
        + "    proxy: {\n"
        + proxy_lines
        + "    },\n"
        + "  },\n"
    )

    # Remove any existing base: and server: { ... } block before injecting (prevents duplicates)
    content = re.sub(r"  base:\s*'[^']*',?\n?", "", content)
    # Remove server block by finding matching braces (handles arbitrary nesting)
    server_start = re.search(r"  server\s*:\s*\{", content)
    if server_start:
        depth = 0
        i = server_start.start()
        end = i
        for j in range(server_start.end() - 1, len(content)):
            if content[j] == '{':
                depth += 1
            elif content[j] == '}':
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        # Include trailing comma and newline
        while end < len(content) and content[end] in (',', '\n', ' '):
            end += 1
        content = content[:server_start.start()] + content[end:]

    content = content.replace("})\n", server_block + "})\n", 1)
    files[vite_key] = content
    print(f"[_inject_api_proxy] Injected API proxy into vite.config.ts (project={project_name or 'unknown'}, vite_port={port or 'TBD'}, api_port={target_port})", flush=True)
    return files


def _fix_base_url(files: dict) -> dict:
    """Fix wrong BASE_URL patterns in files that call /api/. Must use import.meta.env.BASE_URL."""
    correct = "(import.meta as any).env?.BASE_URL?.replace(/\\/$/, '') || ''"
    correct_line = f"const BASE_URL = {correct}"
    wrong_patterns = [
        # VITE_API_URL / VITE_BASE_URL / VITE_API_BASE_URL variants (single or double quotes)
        re.compile(r"\(import\.meta\s+as\s+any\)\.env\?\.(VITE_API_URL|VITE_BASE_URL|VITE_API_BASE_URL)\s*\?\?\s*['\"][^'\"]*['\"]"),
        re.compile(r"import\.meta\.env\.(VITE_API_URL|VITE_BASE_URL|VITE_API_BASE_URL)\s*\|\|\s*['\"][^'\"]*['\"]"),
        re.compile(r"import\.meta\.env\?\.(VITE_API_URL|VITE_BASE_URL|VITE_API_BASE_URL)\s*\?\?\s*['\"][^'\"]*['\"]"),
        re.compile(r"import\.meta\.env\.(VITE_API_URL|VITE_BASE_URL|VITE_API_BASE_URL)\s*\?\?\s*['\"][^'\"]*['\"]"),
    ]
    # Hardcoded empty string: const BASE_URL = '' or ""
    empty_base_url = re.compile(r"^(const|let|var)\s+BASE_URL\s*=\s*['\"]['\"]", re.MULTILINE)
    # Bare fetch('/api/...') without any BASE_URL prefix
    bare_api_fetch = re.compile(r"""(fetch\s*\(\s*)(['"`])/api/""")
    has_base_url_decl = re.compile(r"(const|let|var)\s+(BASE_URL|_API_BASE|API_BASE)\s*=")
    has_base_url_usage = re.compile(r"\$\{(BASE_URL|_API_BASE|API_BASE)\}")
    changed = False
    for path, content in list(files.items()):
        if not path.endswith((".tsx", ".ts")):
            continue
        # Only fix files that actually call /api/
        if "/api/" not in content:
            continue
        for pat in wrong_patterns:
            if pat.search(content):
                content = pat.sub(correct, content)
                changed = True
        # Fix hardcoded empty BASE_URL in files that fetch from /api/
        if empty_base_url.search(content):
            content = empty_base_url.sub(correct_line, content)
            changed = True
        # Fix bare fetch('/api/...') — no BASE_URL used at all
        if bare_api_fetch.search(content) and not has_base_url_usage.search(content):
            # Inject BASE_URL declaration after the last import line
            lines = content.split('\n')
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    insert_idx = i + 1
            lines.insert(insert_idx, f"\n{correct_line}\n")
            content = '\n'.join(lines)
            # Replace bare fetch('/api/ with fetch(`${BASE_URL}/api/
            content = bare_api_fetch.sub(r'\1`${BASE_URL}/api/', content)
            # Close backtick-template: '/api/chat' -> `${BASE_URL}/api/chat`
            # Handle patterns: fetch('/api/chat', ...) and fetch("/api/chat", ...)
            # The regex already put `${BASE_URL}/api/ — now fix the closing quote
            # Replace remaining single/double quote closings after /api paths with backtick
            content = re.sub(
                r'(\$\{BASE_URL\}/api/[^\'"`\s,)]+)[\'"]',
                r'\1`',
                content
            )
            changed = True
        files[path] = content
    if changed:
        print("[postprocessor] Fixed wrong BASE_URL pattern -> import.meta.env.BASE_URL", flush=True)
    return files


def _strip_double_browser_router(files: dict) -> dict:
    """Remove BrowserRouter from App.tsx — main.tsx always provides it."""
    app_key = "src/App.tsx"
    if app_key not in files:
        return files
    content = files[app_key]
    if "BrowserRouter" not in content:
        return files

    # Remove BrowserRouter from import statement
    content = re.sub(
        r",?\s*BrowserRouter\s*,?",
        lambda m: ", " if m.group(0).count(",") == 2 else "",
        content,
    )
    # Clean up import artifacts: "import { , Routes" → "import { Routes"
    content = re.sub(r"\{\s*,\s*", "{ ", content)
    content = re.sub(r",\s*\}", " }", content)

    # Remove <BrowserRouter ...> wrapper — handles patterns like:
    #   <BrowserRouter>...<AppInner />...</BrowserRouter>
    #   <BrowserRouter basename={...}>...<App />...</BrowserRouter>
    content = re.sub(r"\s*<BrowserRouter[^>]*>\s*\n?", "", content)
    content = re.sub(r"\s*</BrowserRouter>\s*\n?", "", content)

    # If the LLM split into App + AppInner, collapse the wrapper:
    #   const App = () => { return ( <AppInner /> ) }; export default App;
    # → export default AppInner;
    m = re.search(
        r"(?:const|function)\s+App\b[^{]*\{\s*return\s*\(\s*<(\w+)\s*/>\s*\)\s*;?\s*\}",
        content,
    )
    if m:
        inner_name = m.group(1)
        content = content[:m.start()] + content[m.end():]
        content = re.sub(r"export\s+default\s+App\s*;?", f"export default {inner_name};", content)

    if content != files[app_key]:
        files[app_key] = content
        print("[postprocessor] Stripped BrowserRouter from App.tsx (main.tsx provides it)", flush=True)
    return files


def _fix_diff_map_on_object(files: dict) -> dict:
    """
    Fix LLM bug: diff state is Record<string, {diff: DiffLine[], ...}> but code calls
    `diff.map(...)` instead of `diff.diff.map(...)`.

    Detection: find useState<Record<..., { diff: ... }>> pattern, then look for
    a conditional render `{someVar ? (...someVar.map(...)...) : ...}` where someVar
    was assigned from that record.
    """
    pat_state = re.compile(
        r'useState<Record<[^>]*\{\s*diff\s*:', re.DOTALL
    )
    pat_bad_map = re.compile(
        r'\b(diff|diffResult|diffData)\s*&&\s*.*?\1\.map\('
        r'|\{(diff|diffResult|diffData)\s*\?\s*\([^)]*\2\.map\('
        r'|\{(diff|diffResult|diffData)\s*\?\s*<[^>]*>.*?\3\.map\(',
        re.DOTALL
    )
    pat_simple = re.compile(r'\{diff\.map\(')
    changed = False
    for fpath, content in list(files.items()):
        if not fpath.endswith('.tsx') or 'node_modules' in fpath:
            continue
        if not pat_state.search(content):
            continue
        if pat_simple.search(content):
            content = content.replace('{diff.map(', '{diff.diff.map(')
            files[fpath] = content
            changed = True
    if changed:
        print("[postprocessor] Fixed diff.map() -> diff.diff.map() (state object wraps array)", flush=True)
    return files


def _fix_table_name_mismatches(files: dict) -> dict:
    """
    Validate table names in useApi('...') and apiAggregate('...') calls against
    the actual schema.sql.  The LLM frequently generates singular names when the
    schema uses plural (e.g., 'forecast' instead of 'forecasts'), or vice versa.

    Strategy:
    1. Extract all CREATE TABLE names from schema.sql.
    2. Scan .ts/.tsx files for useApi('x') and apiAggregate('x') calls.
    3. If 'x' is not in the table set, try common variants (add/remove 's'/'es',
       underscore differences) and replace with the matching table name.
    """
    schema_content = files.get("api/schema.sql", "") or files.get("schema.sql", "")
    if not schema_content:
        return files

    table_names = set(
        re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", schema_content, re.IGNORECASE)
    )
    if not table_names:
        return files

    # Build a lookup: normalized form → actual table name
    table_lookup: dict[str, str] = {}
    for t in table_names:
        table_lookup[t.lower()] = t
        # also index without trailing 's' or 'es' for reverse lookup
        if t.lower().endswith('es') and len(t) > 3:
            table_lookup[t.lower()[:-2]] = t
        if t.lower().endswith('s') and len(t) > 2:
            table_lookup[t.lower()[:-1]] = t

    def _find_correct_table(wrong_name: str) -> str | None:
        """Return the correct table name if wrong_name is close to one, else None."""
        low = wrong_name.lower()
        if low in table_lookup:
            actual = table_lookup[low]
            return actual if actual != wrong_name else None
        # Try adding 's' or 'es'
        for suffix in ('s', 'es'):
            candidate = low + suffix
            if candidate in table_lookup:
                return table_lookup[candidate]
        # Try removing trailing 's' or 'es'
        if low.endswith('es') and low[:-2] in table_lookup:
            return table_lookup[low[:-2]]
        if low.endswith('s') and low[:-1] in table_lookup:
            return table_lookup[low[:-1]]
        # Try underscore variants: 'globalSales' -> 'global_sales'
        # camelCase to snake_case
        snake = re.sub(r'([a-z])([A-Z])', r'\1_\2', wrong_name).lower()
        if snake in table_lookup:
            return table_lookup[snake]
        if snake + 's' in table_lookup:
            return table_lookup[snake + 's']
        return None

    # Pattern to match useApi('tableName') or apiAggregate('tableName')
    call_pattern = re.compile(
        r"""(useApi(?:<[^>]*>)?\s*\(\s*|apiAggregate\s*\(\s*)(['"])(\w+)\2"""
    )

    changed = False
    for path, content in list(files.items()):
        if not path.endswith((".tsx", ".ts")):
            continue
        if "useApi" not in content and "apiAggregate" not in content:
            continue

        def _replace_table(m: re.Match) -> str:
            prefix = m.group(1)
            quote = m.group(2)
            name = m.group(3)
            if name.lower() in (t.lower() for t in table_names):
                # Exact match (case-insensitive) — might need case fix
                for t in table_names:
                    if t.lower() == name.lower() and t != name:
                        return f"{prefix}{quote}{t}{quote}"
                return m.group(0)
            correct = _find_correct_table(name)
            if correct:
                return f"{prefix}{quote}{correct}{quote}"
            return m.group(0)

        new_content = call_pattern.sub(_replace_table, content)
        if new_content != content:
            files[path] = new_content
            changed = True
            print(f"[_fix_table_name_mismatches] Fixed table name(s) in {path}", flush=True)

    return files


def _fix_d3_resize_observer(files: dict) -> dict:
    """
    Fix the broken D3 chart/map ResizeObserver pattern where:
    1. ResizeObserver is set up without an initial synchronous measurement, OR
    2. The code uses ref.current?.parentElement instead of a dedicated container ref, OR
    3. A useRef<SVGSVGElement> is used directly with ResizeObserver (SVG has no intrinsic
       dimensions so clientWidth returns 0).

    Without an initial measure(), charts/maps render as 0x0 because Tailwind's preflight
    collapses SVGs with no explicit dimensions, and ResizeObserver may not fire for
    zero-size elements.
    """
    _USEEFFECT_WITH_RO = re.compile(
        r'(useEffect\(\(\)\s*=>\s*\{)(.*?)(return\s*\(\)\s*=>\s*ro\.disconnect\(\))',
        re.DOTALL
    )

    def _find_ro_span(body: str) -> tuple[int, int] | None:
        """Find the full span of 'const ro = new ResizeObserver(...)' using balanced paren counting."""
        start_match = re.search(r'const\s+ro\s*=\s*new\s+ResizeObserver\s*\(', body)
        if not start_match:
            return None
        open_pos = start_match.end() - 1  # position of the opening (
        depth = 0
        for i in range(open_pos, len(body)):
            if body[i] == '(':
                depth += 1
            elif body[i] == ')':
                depth -= 1
                if depth == 0:
                    return (start_match.start(), i + 1)
        return None

    def _inject_measure(m: re.Match) -> str:
        effect_start = m.group(1)
        body = m.group(2)
        cleanup = m.group(3)

        if "measure()" in body or "measure()" in effect_start:
            return m.group(0)

        set_call = re.search(r'(set\w*Width|set\w*Dims|setMapDims|setLineDims|setBarDims|setAreaDims)\s*\(', body)
        if not set_call:
            return m.group(0)

        ro_span = _find_ro_span(body)
        if not ro_span:
            return m.group(0)

        # Detect setter argument shape: object {w,h} vs scalar number
        setter_name = set_call.group(1)
        # Look for how the setter is actually called in the RO body
        setter_call_match = re.search(
            rf'{re.escape(setter_name)}\s*\(\s*\{{',
            body[ro_span[0]:ro_span[1]]
        )
        if setter_call_match or 'Dims' in setter_name:
            # Object shape: { w: width, h: height }
            # Use larger height cap for maps vs regular charts
            if 'Map' in setter_name or 'map' in setter_name:
                setter_arg = "{ w, h: Math.min(w * 0.55, 500) }"
            else:
                setter_arg = "{ w, h: Math.min(w * 0.5, 400) }"
        else:
            # Scalar shape
            setter_arg = "w"

        el_match = re.search(r'const\s+(\w+)\s*=\s*(\w+)\.current', body)
        ref_match = re.search(r'if\s*\(\s*!(\w+)\.current\s*\)', body)

        if el_match:
            el_var = el_match.group(1)
            # Use parentElement width if the ref is on an SVG (SVG clientWidth can be unreliable)
            measure_fn = f"      const measure = () => {{ const w = ({el_var}.parentElement?.clientWidth || {el_var}.clientWidth); if (w > 0) {setter_name}({setter_arg}) }}\n      measure()\n"
            replacement = f'{measure_fn}      const ro = new ResizeObserver(() => measure())'
            new_body = body[:ro_span[0]] + replacement + body[ro_span[1]:]
            if new_body != body:
                return effect_start + new_body + cleanup
        elif ref_match:
            ref_var = ref_match.group(1)
            measure_fn = f"      const measure = () => {{ const w = ({ref_var}.current!.parentElement?.clientWidth || {ref_var}.current!.clientWidth); if (w > 0) {setter_name}({setter_arg}) }}\n      measure()\n"
            replacement = f'{measure_fn}      const ro = new ResizeObserver(() => measure())'
            new_body = body[:ro_span[0]] + replacement + body[ro_span[1]:]
            if new_body != body:
                return effect_start + new_body + cleanup

        return m.group(0)

    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        if "ResizeObserver" not in content:
            continue

        changed = False

        # ── 1. Inject measure() if missing ───────────────────────────────────
        if "measure()" not in content:
            new_content = _USEEFFECT_WITH_RO.sub(_inject_measure, content)
            if new_content != content:
                files[path] = new_content
                content = new_content
                changed = True

        # ── 2. Fix ResizeObserver observe target: must observe parent div, not SVG ──
        # SVG elements with width:100% don't reliably trigger ResizeObserver.
        # Ensure ro.observe() targets the parent element (a regular block div).
        if "ro.observe(" in content:
            new_content = re.sub(
                r'ro\.observe\((\w+)\)',
                r'ro.observe(\1.parentElement || \1)',
                content
            )
            # Avoid double-wrapping if already correct
            new_content = new_content.replace(
                ".parentElement || .parentElement ||",
                ".parentElement ||"
            )
            new_content = re.sub(
                r'ro\.observe\((\w+)\.parentElement \|\| \1\.parentElement \|\| \1\)',
                r'ro.observe(\1.parentElement || \1)',
                new_content
            )
            if new_content != content:
                files[path] = new_content
                content = new_content
                changed = True

        # ── 2b. Fix MISSING deps array: ResizeObserver in useEffect(...) without []
        # causes infinite re-render loop (setDims creates new object → re-render →
        # effect runs again → setDims again → ...). Ensure deps are present.
        #
        # HOWEVER: if the component has an early return for loading (before SVGs mount),
        # using [] means the observer never sets up (refs are null on first mount).
        # In that case, use [loading] so the effect re-runs when data arrives.
        if "ResizeObserver" in content:
            # Detect loading variable used in early return: if (loading) return / if (isLoading) return
            loading_var_match = re.search(
                r'if\s*\(\s*(is[Ll]oading|loading|isLoading)\s*\)\s*\{?\s*return\b',
                content,
            )
            deps_value = f"[{loading_var_match.group(1)}]" if loading_var_match else "[]"

            new_content = re.sub(
                r'(return\s*\(\)\s*=>\s*ro\.disconnect\(\);?\s*\})\)',
                rf'\1, {deps_value})',
                content,
            )
            # Also handle the variant: return () => { ro.disconnect() } })
            new_content = re.sub(
                r'(return\s*\(\)\s*=>\s*\{\s*ro\.disconnect\(\);?\s*\}\s*\})\)',
                rf'\1, {deps_value})',
                new_content,
            )
            # Avoid double deps
            new_content = re.sub(
                r', \[[\w]*\]\), \[[\w]*\]\)',
                f', {deps_value})',
                new_content,
            )
            if new_content != content:
                files[path] = new_content
                content = new_content
                changed = True

        # ── 3. Fix SVG-ref-with-ResizeObserver antipattern in map components ─
        # When the LLM puts the ref directly on <svg> and uses it for
        # ResizeObserver, the SVG has no intrinsic dimensions → clientWidth = 0.
        # Fix: inject a containerRef on the parent div.
        _is_map_file = any(kw in content for kw in [
            'topojson', 'world-atlas', 'us-atlas', 'geoPath', 'geoMercator',
            'geoAlbersUsa', 'geoNaturalEarth', 'geoEquirectangular'
        ])
        if _is_map_file:
            svg_ref_match = re.search(
                r'const\s+(\w+)\s*=\s*useRef<SVGSVGElement>\s*\(\s*null\s*\)',
                content
            )
            has_container_ref = bool(re.search(
                r'useRef<HTMLDivElement>\s*\(\s*null\s*\)', content
            ))
            if svg_ref_match and not has_container_ref:
                svg_ref_name = svg_ref_match.group(1)
                ro_observes_svg = re.search(
                    rf'ro\.observe\(\s*{re.escape(svg_ref_name)}\.current',
                    content
                )
                if ro_observes_svg:
                    # Add containerRef declaration
                    content = re.sub(
                        rf'(const\s+{re.escape(svg_ref_name)}\s*=\s*useRef<SVGSVGElement>\s*\(\s*null\s*\))',
                        r'\1\n  const containerRef = useRef<HTMLDivElement>(null)',
                        content, count=1
                    )
                    # Replace svgRef.current usage in RO useEffect with containerRef.current
                    content = re.sub(
                        rf'const\s+(\w+)\s*=\s*{re.escape(svg_ref_name)}\.current(?!\s*\)[\s\S]*?\.attr)',
                        r'const \1 = containerRef.current',
                        content
                    )
                    content = re.sub(
                        rf'if\s*\(\s*!{re.escape(svg_ref_name)}\.current\s*\)\s*return',
                        'if (!containerRef.current) return',
                        content, count=1
                    )
                    content = re.sub(
                        rf'ro\.observe\(\s*{re.escape(svg_ref_name)}\.current!?\s*\)',
                        'ro.observe(containerRef.current!)',
                        content
                    )
                    # Add ref={containerRef} and minHeight to parent div of <svg>
                    svg_jsx_pattern = re.compile(
                        rf'(<div)([^>]*?)(\s*>[\s\S]*?<svg[^>]*ref=\{{{re.escape(svg_ref_name)}\}})'
                    )
                    jsx_match = svg_jsx_pattern.search(content)
                    if jsx_match:
                        div_attrs = jsx_match.group(2)
                        if 'ref=' not in div_attrs:
                            new_attrs = div_attrs + ' ref={containerRef} style={{ position: "relative", width: "100%", minHeight: 400 }}'
                            content = (content[:jsx_match.start()]
                                       + jsx_match.group(1) + new_attrs + jsx_match.group(3)
                                       + content[jsx_match.end():])
                    # Change d3.select(svgRef.current) to container-based selection
                    content = re.sub(
                        rf'd3\.select\(\s*{re.escape(svg_ref_name)}\.current\s*\)',
                        "d3.select(containerRef.current).select<SVGSVGElement>('svg')",
                        content
                    )
                    files[path] = content
                    changed = True
                    print(f"[_fix_d3_resize_observer] Restructured SVG ref -> container ref in {path}", flush=True)

        # ── 4. Add width:100% to bare <svg ref={}> observed by ResizeObserver ──
        # Without explicit width, Tailwind preflight collapses SVG to 0 width,
        # so clientWidth=0 and measure() never produces a real dimension.
        # Detect refs observed directly (ro.observe(ref.current)) AND indirectly
        # (const el = ref.current; ... ro.observe(el))
        observed_refs = set(re.findall(r'ro\.observe\(\s*(\w+)\.current', content))
        # Also trace: const el = someRef.current ... ro.observe(el)
        for el_m in re.finditer(r'const\s+(\w+)\s*=\s*(\w+)\.current', content):
            local_var = el_m.group(1)
            ref_name_candidate = el_m.group(2)
            if re.search(rf'ro\.observe\(\s*{re.escape(local_var)}\s*[!)]', content):
                observed_refs.add(ref_name_candidate)
        for ref_name in observed_refs:
            svg_tag_pattern = re.compile(
                rf'(<svg\b)([^>]*ref=\{{{re.escape(ref_name)}\}}[^>]*?)(\s*/?>)'
            )
            svg_match = svg_tag_pattern.search(content)
            if not svg_match:
                svg_tag_pattern2 = re.compile(
                    rf'(<svg\b)([^>]*?)(\s+ref=\{{{re.escape(ref_name)}\}})([^>]*?)(\s*/?>)'
                )
                svg_match2 = svg_tag_pattern2.search(content)
                if svg_match2:
                    attrs_combined = svg_match2.group(2) + svg_match2.group(3) + svg_match2.group(4)
                    if 'width' not in attrs_combined or ('style=' in attrs_combined and 'width' not in attrs_combined.split('style=')[1].split('}')[0]):
                        new_tag = (svg_match2.group(1) + svg_match2.group(2) + svg_match2.group(3)
                                   + svg_match2.group(4)
                                   + " style={{ width: '100%', display: 'block' }}"
                                   + svg_match2.group(5))
                        content = content[:svg_match2.start()] + new_tag + content[svg_match2.end():]
                        files[path] = content
                        changed = True
                        print(f"[_fix_d3_resize_observer] Added width:100% to bare <svg ref={{{ref_name}}}> in {path}", flush=True)
            else:
                attrs_part = svg_match.group(2)
                if 'style=' in attrs_part and 'width' in attrs_part.split('style=')[1].split('}')[0]:
                    pass
                elif 'width=' in attrs_part and 'style=' not in attrs_part:
                    pass
                else:
                    new_tag = (svg_match.group(1) + svg_match.group(2)
                               + " style={{ width: '100%', display: 'block' }}"
                               + svg_match.group(3))
                    content = content[:svg_match.start()] + new_tag + content[svg_match.end():]
                    files[path] = content
                    changed = True
                    print(f"[_fix_d3_resize_observer] Added width:100% to bare <svg ref={{{ref_name}}}> in {path}", flush=True)

        if changed:
            print(f"[_fix_d3_resize_observer] Fixed ResizeObserver pattern in {path}", flush=True)

    return files


def _inject_map_click_handler(files: dict) -> dict:
    """
    Inject a click-to-select handler into map components that have hover but no click.
    The LLM sometimes omits the click handler despite prompt instructions.
    This postprocessor guarantees every map supports click-to-select.
    """
    for path, content in list(files.items()):
        if not path.endswith(".tsx"):
            continue
        _is_map = any(kw in content for kw in [
            'topojson', 'world-atlas', 'us-atlas', 'geoPath', 'geoMercator',
            'geoAlbersUsa', 'geoNaturalEarth', 'geoEquirectangular'
        ])
        if not _is_map:
            continue
        _has_hover = (
            ".on('mouseenter'" in content or '.on("mouseenter"' in content
            or ".on('mouseover'" in content or '.on("mouseover"' in content
        )
        _has_click = ".on('click'" in content or '.on("click"' in content
        if not _has_hover or _has_click:
            continue

        # Map has hover but no click — inject click handler
        changed = False

        # 1. Add selectedCountry state if missing
        if 'selectedCountry' not in content:
            # Find the first useState to insert after
            state_insert = re.search(r'(const \[.*?\] = useState.*?\))\n', content)
            if state_insert:
                insert_pos = state_insert.end()
                state_line = "  const [selectedCountry, setSelectedCountry] = useState<string | null>(null)\n"
                content = content[:insert_pos] + state_line + content[insert_pos:]
                changed = True

        # 2. Insert .on('click') after the last .on('mouseenter') or .on('mouseover')
        hover_patterns = [
            r"\.on\('mouseenter'[^)]*\)[^)]*\)",
            r'\.on\("mouseenter"[^)]*\)[^)]*\)',
            r"\.on\('mouseover'[^)]*\)[^)]*\)",
            r'\.on\("mouseover"[^)]*\)[^)]*\)',
        ]
        # Find the mouseleave/mouseout that typically follows hover
        leave_pattern = re.search(
            r"(\.on\('mouseleave'[^)]*\)[\s\S]*?\}[\s]*\))",
            content
        )
        if not leave_pattern:
            leave_pattern = re.search(
                r'(\.on\("mouseleave"[^)]*\)[\s\S]*?\}[\s]*\))',
                content
            )
        if not leave_pattern:
            leave_pattern = re.search(
                r"(\.on\('mouseout'[^)]*\)[\s\S]*?\}[\s]*\))",
                content
            )

        if leave_pattern and 'selectedCountry' in content:
            insert_pos = leave_pattern.end()
            click_handler = (
                "\n      .on('click', function(event: any, d: any) {\n"
                "        const id = String(d.id || d.properties?.name || '')\n"
                "        setSelectedCountry(prev => prev === id ? null : id)\n"
                "      })"
            )
            content = content[:insert_pos] + click_handler + content[insert_pos:]
            changed = True

            # 3. Add selectedCountry to the useEffect dependency array if d3 drawing is inside
            dep_array_match = re.search(
                r'(}\s*,\s*\[)([^\]]*?)(]\s*\)\s*//?\s*(?:end )?useEffect|]\s*\))',
                content
            )
            if dep_array_match and 'selectedCountry' not in dep_array_match.group(2):
                deps = dep_array_match.group(2).rstrip()
                if deps:
                    new_deps = deps + ', selectedCountry'
                else:
                    new_deps = 'selectedCountry'
                content = (content[:dep_array_match.start(1)]
                           + dep_array_match.group(1) + new_deps + dep_array_match.group(3)
                           + content[dep_array_match.end():])
                changed = True

        if changed:
            files[path] = content
            print(f"[_inject_map_click_handler] Injected click-to-select in {path}", flush=True)

    return files


def run_all_postprocessors(files: dict, project_dir=None, project_name: str = "", port: int = 0, api_port: int = 0) -> dict:
    """
    Run all post-processors in the correct order and return the patched files dict.
    This is the single entry-point used by generate_project() in uigen_agent.py.

    project_name, port, and api_port are forwarded to _inject_api_proxy so it can
    set up the base-path-aware proxy rewrite in vite.config.ts.
    """
    from agents.sanitize_js import sanitize_files
    files = sanitize_files(files)
    files = _patch_vite_for_ds(files, project_dir=project_dir)
    files = _inject_api_proxy(files, project_name=project_name, port=port, api_port=api_port)
    files = _patch_highcharts_more(files)
    files = _patch_dynamic_imports(files)
    files = _patch_map_components(files)
    files = _inject_map_click_handler(files)
    files = _fix_badge_variants(files)
    files = _fix_prop_contracts(files)
    files = _fix_d3_resize_observer(files)
    files = _fix_chart_container(files)
    files = _fix_self_wrapping_charts(files)
    files = _strip_double_browser_router(files)
    files = _fix_base_url(files)
    files = _fix_diff_map_on_object(files)
    files = _fix_table_name_mismatches(files)
    files = _patch_index_html(files)
    files = _ensure_tsconfig_vite_types(files)
    files = _strip_data_imports(files)
    files = _warn_unfilled_placeholders(files)
    return files
