"""
Skill registry — capability-based UI skills for TurboUIGen.

A SKILL is a pre-written, domain-agnostic React component or page template.
The LLM's only job is to fill in a tiny config (~30 lines).
The skill renders any domain's data from that config.

Skills are organised by CAPABILITY, not by domain:
  - DataGrid  →  works for sales, player stats, orders, products, anything tabular
  - WorldMap  →  works for sales, elections, climate, population, anything geographic
  - BarChart  →  works for revenue, goals scored, stock prices, anything with bars
  - ChatBot   →  works for AI concierge, customer support, FAQ, anything chat-like
  - PPTExport →  works for any app that needs slide export
  etc.

The generator checks: "what capability does this page need?" → finds the matching skill
→ copies the skill template → asks LLM to fill in the 30-line config.

Adding a new skill = write one .skill.tsx + one .config.ts in this directory.
"""

from pathlib import Path

SKILLS_DIR = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# Skill definitions
#
# Each entry:
#   template      — the .skill.tsx file (generic, domain-agnostic React)
#   config_file   — the .config.ts template the LLM fills in
#   description   — one line explaining what this skill renders
#   triggers      — lowercase keywords in a page name that select this skill
#   config_schema — field descriptions sent to the LLM so it knows what to fill in
# ─────────────────────────────────────────────────────────────────────────────

SKILL_REGISTRY: dict[str, dict] = {

    # ── Tabular data ──────────────────────────────────────────────────────────
    "data-grid": {
        "template":    "DataGrid.skill.tsx",
        "config_file": "DataGrid.config.ts",
        "description": "Filterable, sortable, paginated data table with CSV export. "
                       "Works for any tabular dataset: sales, orders, players, products, etc.",
        "triggers": [
            "grid", "table", "list", "records", "explorer",
            "orders", "transactions", "inventory", "products",
            "players", "matches", "roster", "standings", "leaderboard",
        ],
        "config_schema": {
            "tableName":   "string — SQLite table name from schema.sql (data fetched from /api/data/{tableName})",
            "pageTitle":   "string — displayed as the page heading",
            "pageSubtitle":"string — optional description line",
            "rowKey":      "string — field name that is unique per row (for React key)",
            "searchFields":"string[] — field names included in the global text search",
            "filters":     "Array<{label, field, options: string[]}> — dropdown filters",
            "columns":     "Array<{key, header, type, align?, badgeColors?, divisor?, suffix?, progressMax?}>  "
                           "type = 'text'|'number'|'currency'|'percent'|'badge'|'progress'|'date'  "
                           "badgeColors maps value → 'default'|'success'|'warning'|'error'|'info'|'accent'",
            "defaultSort": "{key, dir: 'asc'|'desc'}",
            "csvFilename": "string — download filename, e.g. 'players.csv'",
        },
    },

    # ── Charts (all types unified in one skill) ───────────────────────────────
    #
    # One skill file covers ALL chart types. The LLM sets chartType in the config.
    # chartType options: 'bar'|'stacked-bar'|'line'|'donut'|'pie'|'area'|'grouped-bar'|
    #                    'scatter'|'bubble'|'histogram'|'heatmap'|'treemap'|'radar'|'waterfall'|'multi'
    "charts": {
        "template":    "Charts.skill.tsx",
        "config_file": "Charts.config.ts",
        "description": "All-in-one chart page supporting 14 chart types: bar, stacked-bar, line, "
                       "donut/pie, area, grouped-bar, scatter, bubble, histogram, heatmap, "
                       "treemap, radar, waterfall, or multi-panel grid. Set chartType in config.",
        "triggers": [
            # bar / histogram
            "barchart", "bar", "histogram", "ranking", "waterfall", "bridge",
            # line / time-series
            "linechart", "trend", "timeseries", "timeline", "sparkline", "forecast",
            # donut / pie
            "donut", "pie", "share", "breakdown", "composition",
            # area
            "area", "stacked", "stackedarea", "cumulative",
            # grouped / scatter / bubble
            "groupedbar", "grouped", "clustered", "multibar",
            "scatter", "bubble", "correlation", "quadrant",
            # heatmap / treemap / radar
            "heatmap", "matrix", "treemap", "hierarchy", "radar", "spider",
            # generic chart pages
            "chart", "charts", "analytics", "stats", "reports", "performance", "visualization",
        ],
        "config_schema": {
            "chartType":    (
                "'bar'|'stacked-bar'|'line'|'donut'|'pie'|'area'|'grouped-bar'|"
                "'scatter'|'bubble'|'histogram'|'heatmap'|'treemap'|'radar'|'waterfall'|'multi' — MUST be set"
            ),
            "tableName":    "string — SQLite table name from schema.sql (data fetched from /api/data/{tableName})",
            "pageTitle":    "string",
            "pageSubtitle": "string | null",
            # bar / donut / treemap / histogram
            "labelField":   "string — bar label, slice label, treemap label, or waterfall step label",
            "valueField":   "string — numeric field for bar height, slice size, etc.",
            "colorField":   "string | null — per-item colour field (or null for auto-colour)",
            "defaultColor": "string — hex fallback colour (bar, histogram, bubble)",
            "horizontal":   "boolean — true for horizontal bars",
            "valueFormat":  "string — d3 format e.g. ',.0f' or '$,.1f'",
            "centerLabel":  "string — text in donut hole",
            # line / area / stacked-bar / grouped-bar
            "xField":       "string — x-axis data field",
            "series":       "Array<{field, label, color}> — for line/area/grouped-bar/stacked-bar",
            "yFormat":      "string — d3 format for y axis",
            "stacked":      "boolean — true for stacked area",
            "groupKey":     "string — x-axis group field for grouped-bar/stacked-bar",
            # scatter / bubble
            "yField":       "string — y-axis numeric field for scatter/bubble",
            "sizeField":    "string — circle size field for bubble chart",
            "xLabel":       "string — x-axis label text",
            "yLabel":       "string — y-axis label text",
            "groupField":   "string | null — colour grouping for bubble chart",
            # histogram
            "bins":         "number — number of histogram bins (default 20)",
            # heatmap
            # uses xField (columns), yField (rows), valueField; colorScheme: 'blue'|'red'|'green'|'purple'
            "colorScheme":  "'blue'|'red'|'green'|'purple' — heatmap/map colour ramp",
            # treemap
            "groupField":   "string | null — parent group field for treemap hierarchy",
            # radar
            "axes":         "string[] — spoke label names for radar chart",
            # for radar, series entries need: {label, color, values: number[]} — one value per axis
            # waterfall
            "positiveColor": "string — up-step bar colour (default '#22C55E')",
            "negativeColor": "string — down-step bar colour (default '#EF4444')",
            "totalColor":    "string — total/subtotal bar colour (default '#0064D2')",
            # each waterfall data row can have isTotal: true to draw from zero (grand total bar)
            # filter
            "filterField":  "string | null",
            "filterOptions":"string[]",
            # multi mode — each entry in charts[] is a complete chart config
            "charts":       (
                "Array of self-contained chart configs — each has: "
                "type (any chartType above), title, data, plus the fields for that type. "
                "Examples: "
                "{type:'bar', title:'Revenue', data:revenueData, labelField:'region', valueField:'revenue', horizontal:true}, "
                "{type:'donut', title:'Market Share', data:shareData, labelField:'brand', valueField:'share', centerLabel:'Share'}, "
                "{type:'line', title:'Trend', data:trendData, xField:'month', series:[{field:'sales',label:'Sales',color:'#0064D2'}]}, "
                "{type:'bubble', title:'Risk vs Return', data:fundData, xField:'risk', yField:'return', sizeField:'aum', labelField:'fund'}, "
                "{type:'radar', title:'Skill Matrix', axes:['Speed','Quality','Cost'], series:[{label:'Team A',color:'#0064D2',values:[80,70,90]}]}, "
                "{type:'waterfall', title:'P&L Bridge', data:bridgeData, labelField:'item', valueField:'amount'}, "
                "{type:'scatter', title:'Price vs Vol', data:tradeData, xField:'price', yField:'volume', labelField:'ticker'}, "
                "{type:'histogram', title:'Distribution', data:scoreData, valueField:'score', bins:15}"
            ),
            "layout":       (
                "'grid' (default) | 'tabs' — controls multi-mode rendering. "
                "Use 'tabs' when the spec says the page has tabs, two tabs, or tabbed sections. "
                "Use 'grid' (or omit) for a 2-column auto-fit grid of charts."
            ),
        },
    },

    # ── Maps ──────────────────────────────────────────────────────────────────
    "world-map": {
        "template":    "WorldMap.skill.tsx",
        "config_file": "WorldMap.config.ts",
        "description": "Interactive D3 world choropleth map shaded by any numeric metric. "
                       "Works for global sales, population, election results, climate data, etc.",
        "triggers": [
            "worldmap", "globalmap", "world", "global", "international",
            "choropleth", "heatmap", "countries",
        ],
        "config_schema": {
            "dataExport":     "imported array from ../data",
            "countryCodeField":"string — ISO-2 country code field (e.g. 'countryCode')",
            "valueField":     "string — numeric field that drives colour intensity",
            "labelField":     "string — country name field for tooltip",
            "title":          "string",
            "colorScheme":    "'blue'|'green'|'orange'|'purple' — heatmap colour ramp",
            "filterField":    "string | null — optional dropdown filter field",
        },
    },

    "usa-map": {
        "template":    "UsaMap.skill.tsx",
        "config_file": "UsaMap.config.ts",
        "description": "Interactive D3 USA state-level choropleth map. "
                       "Works for state sales, election maps, demographic data, etc.",
        "triggers": [
            "usamap", "usmap", "northamerica", "states", "statemap",
            "usachoropleth", "unitedstates",
        ],
        "config_schema": {
            "dataExport":     "imported array from ../data",
            "stateField":     "string — state name or abbreviation field",
            "valueField":     "string — numeric field that drives colour intensity",
            "title":          "string",
            "colorScheme":    "'blue'|'green'|'orange'|'purple'",
            "filterField":    "string | null",
        },
    },

    # ── Dashboard / KPI ───────────────────────────────────────────────────────
    "kpi-dashboard": {
        "template":    "KpiDashboard.skill.tsx",
        "config_file": "KpiDashboard.config.ts",
        "description": "KPI cards row + two summary charts + optional data table. "
                       "Works as a home / overview page for any domain.",
        "triggers": [
            "dashboard", "overview", "home", "summary", "executive",
            "kpi", "metrics", "scorecard",
        ],
        "config_schema": {
            "kpiExport":   "imported KPI array — each item: {label, value, change, direction}",
            "chart1":      "{type:'bar'|'donut', title, dataExport, labelField, valueField, colorField?}",
            "chart2":      "{type:'line', title, dataExport, xField, series: [{field,label,color}]}",
            "tableExport": "imported array for optional bottom table (or null)",
            "tableColumns":"Array<{key, header, type}> — same schema as data-grid columns",
            "pageTitle":   "string",
        },
    },

    # ── Export capabilities ───────────────────────────────────────────────────
    "pptx-export": {
        "template":    "PptxExport.skill.tsx",
        "config_file": "PptxExport.config.ts",
        "description": "PowerPoint export panel using pptxgenjs. "
                       "Generates a real .pptx with cover slide + content slides from any data. "
                       "Works for any app that needs slide export.",
        "triggers": [
            "pptx", "powerpoint", "slides", "presentation", "export",
            "report", "slideexport",
        ],
        "config_schema": {
            "slideTemplates":  "Array<{id, name, description, primaryColor}> — visual themes",
            "buildSlides":     "function signature hint — describe what data to put on each slide",
            "filenamePrefix":  "string — e.g. 'report' → 'report-2024-01.pptx'",
        },
    },

    "excel-export": {
        "template":    "ExcelExport.skill.tsx",
        "config_file": "ExcelExport.config.ts",
        "description": "Excel/CSV export button with optional sheet configuration. "
                       "Works for any table data.",
        "triggers": ["excelexport", "xlsx", "csvexport", "download", "spreadsheet"],
        "config_schema": {
            "sheets": "Array<{name, dataExport, columns: [{key, header}]}>",
            "filename": "string — e.g. 'report.xlsx'",
        },
    },

    "excel-parser": {
        "template":    "ExcelParser.skill.tsx",
        "config_file": "ExcelParser.config.ts",
        "description": "Client-side Excel file upload and analytics page. Parses any .xlsx/.xls, "
                       "auto-detects column types, selects chart types from data shape, and renders "
                       "D3 charts + sortable data table per worksheet tab. Fully self-contained.",
        "triggers": [
            "excelparser", "excelupload", "excelinsight", "excelanalytics",
            "uploadexcel", "parseexcel", "fileupload", "excelimport",
            "dataimport", "fileanalytics", "excelreader",
        ],
        "config_schema": {
            "pageTitle":    "string — heading shown on the upload page",
            "pageSubtitle": "string — description below the heading",
            "accentColor":  "hex string — accent colour for upload zone + active tab (e.g. '#4F46E5')",
            "chartColors":  "string[10] — palette of 10 hex colours for chart series/slices/bars",
        },
    },

    "pdf-export": {
        "template":    "PdfExport.skill.tsx",
        "config_file": "PdfExport.config.ts",
        "description": "Multi-section PDF report with a styled cover page, table of contents, "
                       "and one auto-table page per data section. Accent colour is configurable. "
                       "Works for any app that needs printable PDF reports.",
        "triggers": ["pdf", "pdfexport", "exportpdf", "pdfreport", "printable", "printreport"],
        "config_schema": {
            "reportTitle":    "string — main heading on the cover page",
            "subtitle":       "string — optional subtitle on cover",
            "author":         "string — optional author name",
            "filenamePrefix": "string — e.g. 'sales-report'",
            "theme":          "'striped' | 'grid' | 'plain'",
            "accentColor":    "hex string — e.g. '#0064D2'",
            "sections":       "Array<{title, description, dataExport, columns: [{key, header, format?, pdfWidth?}]}>",
        },
    },

    # ── AI / Chat ─────────────────────────────────────────────────────────────
    "ai-chat": {
        "template":    "AiChat.skill.tsx",
        "config_file": "AiChat.config.ts",
        "description": "Three-panel AI chat interface: persona selector + chat window + export panel. "
                       "All responses pre-built from a data file — no real API call. "
                       "Works for AI concierge, customer support, FAQ assistant, etc.",
        "triggers": [
            "faqassistant", "faqbot", "helpdesk",
        ],
        "config_schema": {
            "personasExport":  "imported personas array — each: {id, name, role, accentColor, prompts:[{id,label,question}]}",
            "responsesExport": "imported responses map — Record<questionString, responseString>",
            "slideTemplates":  "imported slide templates (or null if no PPTX export)",
            "pageTitle":       "string",
            "pageSubtitle":    "string",
        },
    },

    # ── DataChat (LLM-powered) ────────────────────────────────────────────────
    "data-chat": {
        "template":    "DataChat.skill.tsx",
        "config_file": "DataChat.config.ts",
        "description": "LLM-powered chat interface that connects to ANY data source (Excel, PDF, "
                       "tables, custom). Uses a local FastAPI backend with Bedrock/LiteLLM to "
                       "answer questions, generate charts, and query data via natural language. "
                       "Includes file upload, inline chart rendering, and table responses.",
        "triggers": [
            "datachat", "chatwithdata", "dataillm", "aichat",
            "chatbot", "askdata", "nlq", "naturalanguage",
            "chatexcel", "chatpdf", "chatwithai", "copilot",
            "dataassistant", "querydata", "smartchat",
        ],
        "config_schema": {
            "pageTitle":       "string — heading displayed above the chat",
            "pageSubtitle":    "string — description below the heading",
            "apiBaseUrl":      "string — base URL for the API server (default '/api')",
            "accentColor":     "hex string — accent for user bubbles (e.g. '#4F46E5')",
            "contextType":     "'structured'|'document'|'custom'|'upload-excel'|'upload-pdf'",
            "initialContext":  "null (for upload modes) or {schema?, sampleRows?, text?, metadata?}",
            "suggestedPrompts":"string[4] — clickable prompt chips shown when chat is empty",
            "systemPromptOverride": "string|null — custom system prompt or null for default",
        },
        "backend": {
            "server_template": "app_server_template.py",
            "env_template":    "app_server_env_template.txt",
            "requirements":    ["fastapi", "uvicorn", "python-dotenv", "openai", "httpx", "openpyxl", "PyMuPDF"],
        },
    },

    # ── Card grid ─────────────────────────────────────────────────────────────
    "card-grid": {
        "template":    "CardGrid.skill.tsx",
        "config_file": "CardGrid.config.ts",
        "description": "Searchable, filterable grid of summary cards. "
                       "Works for player profiles, product catalog, dealer directory, team roster, etc.",
        "triggers": [
            "cards", "cardgrid", "profiles", "team", "roster", "dealers",
            "directory", "catalog", "gallery", "people",
        ],
        "config_schema": {
            "tableName":      "string — SQLite table name from schema.sql (data fetched from /api/data/{tableName})",
            "nameField":      "string — primary card title field",
            "subtitleField":  "string | null",
            "imageField":     "string | null — URL field for card image",
            "badgeField":     "string | null — field shown as a coloured badge",
            "badgeColors":    "Record<value, 'default'|'success'|'warning'|'error'|'info'|'accent'>",
            "metrics":        "Array<{field, label, format:'number'|'currency'|'percent'}>",
            "filters":        "Array<{label, field, options: string[]}>",
            "pageTitle":      "string",
        },
    },

    # ── Forms ─────────────────────────────────────────────────────────────────
    "settings-form": {
        "template":    "SettingsForm.skill.tsx",
        "config_file": "SettingsForm.config.ts",
        "description": "Multi-section settings / profile form with validation. "
                       "Works for user settings, preferences, configuration pages.",
        "triggers": ["settings", "preferences", "profile", "config", "form", "setup"],
        "config_schema": {
            "sections": "Array<{title, fields: [{key, label, type:'text'|'email'|'select'|'toggle'|'number', options?}]}>",
            "pageTitle": "string",
        },
    },

    # ── Timeline / Feed ───────────────────────────────────────────────────────
    "activity-feed": {
        "template":    "ActivityFeed.skill.tsx",
        "config_file": "ActivityFeed.config.ts",
        "description": "Chronological activity feed / timeline. "
                       "Works for match results, news, audit logs, notifications, events.",
        "triggers": [
            "feed", "timeline", "activity", "news", "events",
            "results", "history", "log", "audit",
        ],
        "config_schema": {
            "dataExport":   "imported array from ../data",
            "dateField":    "string",
            "titleField":   "string",
            "subtitleField":"string | null",
            "badgeField":   "string | null",
            "badgeColors":  "Record<value, variant>",
            "pageTitle":    "string",
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def get_skill(page_name: str) -> dict | None:
    """
    Match a page name to a skill.
    Checks: exact skill key → trigger list.
    Returns skill metadata dict or None.
    """
    key = _normalise(page_name)
    # Exact skill key match
    for skill_key, meta in SKILL_REGISTRY.items():
        if key == _normalise(skill_key):
            return {"skill_key": skill_key, **meta}
    # Trigger match
    for skill_key, meta in SKILL_REGISTRY.items():
        for trigger in meta.get("triggers", []):
            if key == _normalise(trigger) or _normalise(trigger) in key:
                return {"skill_key": skill_key, **meta}
    return None


def load_skill_template(page_name: str) -> str | None:
    """Return the TSX template content, or None if not found."""
    skill = get_skill(page_name)
    if not skill:
        return None
    path = SKILLS_DIR / skill["template"]
    return path.read_text(encoding="utf-8") if path.exists() else None


def load_config_template(page_name: str) -> str | None:
    """Return the config template content, or None if not found."""
    skill = get_skill(page_name)
    if not skill:
        return None
    path = SKILLS_DIR / skill["config_file"]
    return path.read_text(encoding="utf-8") if path.exists() else None


def get_config_schema(page_name: str) -> dict | None:
    skill = get_skill(page_name)
    return skill.get("config_schema") if skill else None


def list_skills() -> list[str]:
    return list(SKILL_REGISTRY.keys())


def skill_summary() -> str:
    """One-line summary of all skills — injected into the Pass 1 system prompt."""
    lines = ["Available UI skills (use these capabilities; they are pre-built and tested):"]
    for key, meta in SKILL_REGISTRY.items():
        triggers = ", ".join(meta["triggers"][:5])
        lines.append(f"  {key}: {meta['description'].split('.')[0]}. Triggers: {triggers}")
    return "\n".join(lines)
