# ExcelInsight — Smart Excel Analytics Dashboard

## Overview

**ExcelInsight** is a client-side Excel analytics tool. Users upload any `.xlsx` or `.xls` file and the app automatically parses all worksheets, detects data types, and generates interactive charts and summary insights for each sheet — all in the browser, no server required.

**Brand:**
- App name: ExcelInsight
- Primary gradient: `#4F46E5` (indigo-600) to `#7C3AED` (violet-600)
- Sidebar/header: dark `#111827` with white text
- Page background: `#F9FAFB`
- Card background: white with subtle `shadow-sm` and `rounded-xl`
- Accent blue: `#3B82F6` · Success: `#10B981` · Warning: `#F59E0B` · Danger: `#EF4444`
- Typography: Inter font family, clean and modern

---

## Dependencies

Add these to `package.json`:
- `xlsx` (SheetJS) — for parsing Excel files client-side
- `d3` — for rendering all charts (useEffect + useRef + SVG + ResizeObserver pattern)

Do NOT add `react-dropzone` — use native HTML5 drag-and-drop (`onDragOver`, `onDrop`) + `<input type="file">`.

**IMPORTANT:** Do NOT use Recharts, Chart.js, or Highcharts. ALL charts must use D3.js directly.

---

## Architecture

This is a SINGLE-PAGE application with no routing. The layout has two states:

### State 1: Upload State (no file loaded)
Full-screen centered upload zone with:
- Large drag-and-drop area (dashed border, indigo accent)
- Icon (upload cloud) + "Drop your Excel file here" text
- "or click to browse" subtext
- Accepted formats: `.xlsx`, `.xls`
- File size limit display: "Up to 50MB"
- Subtle animated gradient background behind the drop zone

### State 2: Analysis State (file loaded)
After upload, transitions to the analytics dashboard:
- **Top bar:** File name, sheet count badge, total rows badge, "Upload New File" button
- **Tab bar:** One tab per worksheet in the Excel file, using the sheet names as tab labels. Active tab has indigo underline.
- **Content area:** Analytics for the active sheet (see below)

---

## Sheet Analysis Logic

For each worksheet, the app must:

1. **Parse the data** using `xlsx` (SheetJS). First row = headers. Remaining rows = data records.

2. **Classify each column** by type:
   - `numeric` — all non-empty values parse as numbers
   - `date` — values match date patterns or are Excel serial dates
   - `categorical` — string values with fewer than 20 unique values
   - `text` — string values with 20+ unique values (not useful for charts)
   - `percentage` — numeric values between 0-1 or 0-100 with "%" in header

3. **Generate summary statistics** for each column:
   - Numeric: min, max, mean, median, sum, count
   - Categorical: value counts (top 10), mode
   - Date: range (earliest to latest)

4. **Auto-select charts** — pick the BEST chart types based on the detected column types. Use this decision matrix:

   | Data Pattern | Chart Type | When to Use |
   |---|---|---|
   | 1 categorical + 1 numeric | Bar Chart (vertical) | Compare values across categories (< 12 categories) |
   | 1 categorical + 1 numeric | Horizontal Bar | When category labels are long or > 8 categories |
   | 1 date/time + 1 numeric | Line Chart | Show trend over time |
   | 1 date/time + multiple numeric | Multi-line Chart | Compare trends across series |
   | 1 categorical + multiple numeric | Grouped Bar Chart | Compare multiple metrics per category |
   | 2 numeric columns | Scatter Plot | Show correlation/relationship |
   | 1 categorical (< 8 unique) + 1 numeric | Donut Chart | Show part-of-whole composition |
   | 1 numeric (continuous) | Histogram | Show distribution |
   | 1 date + 1 numeric + 1 categorical | Stacked Area | Show composition over time |

   Rules:
   - Generate between 3–6 charts per sheet depending on data richness
   - Never create charts for text-only columns
   - If a sheet has < 3 rows, show only the data table (no charts)
   - Prefer variety — don't repeat the same chart type unless the data demands it
   - Use the first suitable column combinations found; label charts with descriptive auto-generated titles

---

## UI Layout — Analysis State

### Top Stats Bar
A row of 4 KPI cards across the top:
- Total Rows
- Total Columns
- Numeric Columns (count)
- Categorical Columns (count)

Each card: white background, rounded-xl, subtle shadow, large bold number, small gray label below.

### Tab Bar
Horizontal scrollable tab bar below the stats. Each tab shows:
- Sheet name
- Row count badge (small, gray)

Active tab: indigo bottom border, bold text. Inactive: gray text, hover highlight.

### Content Grid (per tab)
Two-column grid layout (`grid-cols-1 lg:grid-cols-2`) for charts:
- Each chart in a white card with `rounded-xl`, `shadow-sm`, and 16px padding
- Chart title (bold, dark gray) + subtitle (light gray, describes what's being shown)
- Chart height: 280px
- Responsive: stacks to single column on mobile

### Data Table (below charts)
Collapsible section "Raw Data" with:
- Horizontal scroll for wide tables
- Sticky first column
- Alternating row colors (`bg-gray-50` on even rows)
- Show first 100 rows with "Showing 100 of X rows" note
- Column headers: bold, `bg-gray-100`, sticky top
- Numeric values right-aligned, formatted with commas
- Sort by clicking column headers (toggle asc/desc)

---

## Chart Styling (D3.js)

All charts must use this consistent color palette:
```typescript
const CHART_COLORS = [
  '#4F46E5', '#7C3AED', '#EC4899', '#F59E0B', '#10B981',
  '#3B82F6', '#EF4444', '#8B5CF6', '#06B6D4', '#84CC16'
]
```

D3 chart pattern (every chart component follows this):
```typescript
import { useRef, useEffect } from 'react'
import * as d3 from 'd3'

export default function MyChart({ data, height = 280 }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || !data?.length) return
    d3.select(ref.current).select('svg').remove()
    const width = ref.current.clientWidth
    const svg = d3.select(ref.current)
      .append('svg').attr('width', width).attr('height', height)
    // ... D3 rendering logic ...
  }, [data, height])
  return <div ref={ref} style={{ width: '100%', height }} />
}
```

Chart styling rules:
- Rounded bar corners: `.attr('rx', 4)`
- Grid lines: `stroke="#E5E7EB"`, `stroke-dasharray="3,3"`
- Axis text: `font-size: 12px`, `fill: #6B7280`
- Tooltips: dark background (`#1F2937`), white text, rounded, absolute-positioned div
- Legend: below chart, centered, small text
- Animate on first render: `.transition().duration(600)`
- Responsive: use `ResizeObserver` to re-render on container resize
- Use `d3.scaleBand()` for categorical axes, `d3.scaleLinear()` for numeric, `d3.scaleTime()` for dates
- Line charts: `d3.line()` + `d3.curveMonotoneX`
- Area charts: `d3.area()` + `d3.curveMonotoneX`

---

## Interactions and UX Polish

- **File upload:** Show progress indicator while parsing (spinner + "Analyzing X sheets...")
- **Tab switching:** Instant, no loading state (all sheets parsed upfront)
- **Chart hover:** Tooltips with formatted values
- **Empty state per chart:** If chart cannot be generated, show a subtle "Not enough data for this visualization" message
- **Error handling:** If file is corrupted or unreadable, show friendly error with retry option
- **Animations:** Fade-in cards on tab switch, smooth tab indicator transition
- **Dark mode support:** Not required (light mode only)

---

## File Structure

IMPORTANT: Keep the file count minimal. Do NOT create separate files for each component.
Consolidate into as few files as possible to avoid exceeding output limits.

```
src/
  App.tsx              — Main app shell with upload state, tab bar, ALL inline components
                         (upload zone, stats bar, tab bar, chart cards, data table — all in this one file)
  pages/
    SheetView.tsx      — Single page: chart grid + data table for one sheet, all chart rendering inline
  utils/
    parseExcel.ts      — XLSX parsing + column type detection + chart selection logic (combine all analysis here)
  types.ts             — TypeScript interfaces
```

Rules:
- Maximum 5 files in `src/` total (including types.ts)
- ALL UI components go INLINE in App.tsx or SheetView.tsx — NO separate component files
- ALL utility logic (parsing, chart selection, formatting) goes in parseExcel.ts — ONE util file
- Do NOT create components/ directory
- Do NOT create separate files for StatsBar, TabBar, ChartCard, DataTable, UploadZone, etc.

---

## Skill Usage — MANDATORY

**You MUST use the `excel-parser` skill for this app.** The skill file `ExcelParser.skill.tsx` contains a production-ready, self-contained Excel analytics component with:
- Professional D3.js charts with body-appended tooltips (never clipped)
- Hover interactions (opacity change, stroke highlight, arc expansion)
- Label truncation to prevent overlaps
- Locale-aware number formatting
- Column type auto-detection and chart auto-selection
- Drag-and-drop upload with native HTML5 (no react-dropzone)
- Sortable data table
- 7 chart types: bar, horizontal-bar, line/multi-line, donut, scatter, histogram, grouped-bar

**How to use:** Copy the skill component as your main page content. Customize the config file (`ExcelParser.config.ts`) with appropriate page title, subtitle, accent color, and chart color palette. The skill is self-contained — it handles upload, parsing, chart selection, and rendering all in one component.

**Do NOT re-implement chart rendering from scratch.** The skill already includes all tooltip, hover, and anti-overlap logic. Use it as-is.

**CRITICAL — Page naming:** Name your main page `ExcelInsight` or `ExcelUpload` or `ExcelParser` so the skill auto-matching triggers correctly. Do NOT name it `SheetView`, `Analytics`, `Dashboard`, or any generic name.

---

## Important Implementation Notes

1. **All parsing is client-side.** Use `xlsx` (SheetJS) `read()` with `FileReader`. Never send the file to a server.
2. **Handle large files gracefully.** If a sheet has > 10,000 rows, only use the first 5,000 for chart generation (note this to the user). Always show full row count in the stats.
3. **Date detection:** Check for Excel serial date numbers (> 25000 and < 60000 for typical dates) and convert using `xlsx` utilities. Also detect ISO date strings.
4. **Number formatting:** Use `Intl.NumberFormat` for locale-aware number display in tooltips and tables.
5. **Chart data aggregation:** For bar/donut charts with categorical data, aggregate (sum or average) the numeric column by category. Don't plot raw rows.
6. **Sheet tab order:** Preserve the original order from the Excel file.
7. **Use D3.js for all charts.** Each chart is a React component using `useRef` + `useEffect` + `import * as d3 from 'd3'`. NEVER use Recharts, Chart.js, or Highcharts.
8. **Use the ExcelParser skill.** The skill provides all chart rendering with professional tooltips, hover effects, and anti-overlap. Do not create your own chart components.
