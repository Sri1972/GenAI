# Visualization Agent

Turns tabular data (pasted CSV/JSON, or an uploaded `.csv`/`.json`/`.xlsx`
file) into a single self-contained, interactive HTML file: charts via
D3.js, spatial data (lat/lng columns) via Leaflet + OpenStreetMap tiles
(no API key needed).

Claude only decides *what* to chart — a small structured spec (chart
types, which columns map to which axes) — never the D3/Leaflet JavaScript
itself. This file's own fixed, hand-written templates render the spec
deterministically, which is what makes the output reliable: there's no
LLM-authored chart code to be subtly broken. The tradeoff is that only the
chart types actually implemented here are available (bar, line, area, pie,
scatter, plus a marker map) — not anything an LLM could freely invent.

## Standalone usage
```bash
python run.py --brief "Revenue by region over time" --data-file sales.csv
python run.py --brief "Plot these store locations" --context "name,lat,lng\n..."
```

## As a Claude Code subagent
`Agent({ subagent_type: "visualization-agent", prompt: "Chart this data: <paste CSV>. Show revenue by month." })`

## Notes
- `--data-file` accepts `.csv`, `.json` (an array of objects, or `{"data": [...]}`/`{"rows": [...]}`),
  or `.xlsx` (first sheet, header row + data rows).
- `--context` is for pasted data directly, or upstream content when chained
  in a workflow — same convention as `excel_creator`/`pdf_creator`.
- A map is only added when the data has real latitude/longitude columns —
  never guessed.
- Column names in the spec are validated to be exact matches from the real
  data; there's no fuzzy-matching, since a wrong column name would just mean
  an empty chart.
