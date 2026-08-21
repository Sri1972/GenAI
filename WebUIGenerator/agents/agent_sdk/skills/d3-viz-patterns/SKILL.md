---
name: d3-viz-patterns
description: Canonical D3 + React patterns for charts and maps in TurboUIGen — the mandatory recipe for responsive, tooltip-enabled, non-leaking D3 visualizations. Load before hand-writing any D3 chart or map.
---

# d3-viz-patterns

Mandatory patterns for ALL D3 work (charts and maps). Violating these causes the QA
static checks to fail.

## Rendering
- `useEffect` + `useRef<HTMLDivElement>` on the CONTAINER div (not the `<svg>`); give the
  container a `minHeight`.
- `d3.select(ref.current).select('svg').remove()` before every re-render.
- Wrap in a `ResizeObserver` for responsive width — but call `render()` IMMEDIATELY once,
  then hand it to the observer. Never do D3 drawing *inside* the observer callback only
  (infinite-loop / blank-on-first-paint).
- Never hardcode chart width; derive it from the container.
- Never use `parentElement` to size.

## Tooltips
- React state + an absolutely-positioned `<div>` inside the container. NEVER SVG `<text>`
  tooltips.

## Maps (TopoJSON is imported statically, never fetched)
- USA: `import usaTopo from 'us-atlas/states-10m.json'` + `d3.geoAlbersUsa()`.
- World: `import worldTopo from 'world-atlas/countries-110m.json'` + `d3.geoNaturalEarth1()`.
- Sub-national: public GeoJSON URL (see the country-map skill).
- Maps with hover MUST also support `.on('click', ...)` for select/drill-down.

## Data
- `useApi<any[]>('table_name')` → `/api/data/table_name`; fields are snake_case.
- Numeric guards: `Number(x) || 0`.
- "top 5 brands" means the config MUST have 5 series entries, not 1. Every series needs a
  value for every x — zero is valid, missing is not.

## Libraries
- D3 only. Never Highcharts, Recharts, Chart.js.
