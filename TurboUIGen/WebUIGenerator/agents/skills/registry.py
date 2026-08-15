"""
Skill registry — capability-based UI skills for TurboUIGen.

A SKILL is a pre-written, domain-agnostic React component or page template.
The LLM's only job is to fill in a tiny config (~30 lines).
The skill renders any domain's data from that config.

Templates are now stored in each agent's templates/ directory:
  - agents/react_ui/templates/        → DataGrid, CardGrid, KpiDashboard, etc.
  - agents/visual_design/templates/   → Charts, WorldMap, UsaMap
  - agents/ai_genai/templates/        → AiChat, DataChat
  - agents/services_engineer/templates/ → app_server_template.py, useApi.hook.ts, etc.
"""

from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent

# Backwards-compat alias used by uigen_agent.py and orchestrator.py
SKILLS_DIR = AGENTS_DIR / "services_engineer" / "templates"

# Template locations by agent
_TEMPLATE_DIRS = {
    "react_ui": AGENTS_DIR / "react_ui" / "templates",
    "visual_design": AGENTS_DIR / "visual_design" / "templates",
    "ai_genai": AGENTS_DIR / "ai_genai" / "templates",
    "services_engineer": AGENTS_DIR / "services_engineer" / "templates",
}


def _find_template(filename: str) -> Path | None:
    """Find a template file across all agent template directories."""
    for agent_dir in _TEMPLATE_DIRS.values():
        path = agent_dir / filename
        if path.exists():
            return path
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Skill definitions
# ─────────────────────────────────────────────────────────────────────────────

SKILL_REGISTRY: dict[str, dict] = {

    # ── Tabular data ──────────────────────────────────────────────────────────
    "data-grid": {
        "template":    "DataGrid.skill.tsx",
        "config_file": "DataGrid.config.ts",
        "owner_agent": "react_ui",
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
    "charts": {
        "template":    "Charts.skill.tsx",
        "config_file": "Charts.config.ts",
        "owner_agent": "visual_design",
        "description": "All-in-one chart page supporting 14 chart types: bar, stacked-bar, line, "
                       "donut/pie, area, grouped-bar, scatter, bubble, histogram, heatmap, "
                       "treemap, radar, waterfall, or multi-panel grid. Set chartType in config.",
        "triggers": [
            "barchart", "bar", "histogram", "ranking", "waterfall", "bridge",
            "linechart", "trend", "timeseries", "timeline", "sparkline", "forecast",
            "donut", "pie", "share", "breakdown", "composition",
            "area", "stacked", "stackedarea", "cumulative",
            "groupedbar", "grouped", "clustered", "multibar",
            "scatter", "bubble", "correlation", "quadrant",
            "heatmap", "matrix", "treemap", "hierarchy", "radar", "spider",
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
            "labelField":   "string — bar label, slice label, treemap label, or waterfall step label",
            "valueField":   "string — numeric field for bar height, slice size, etc.",
            "colorField":   "string | null — per-item colour field (or null for auto-colour)",
            "defaultColor": "string — hex fallback colour (bar, histogram, bubble)",
            "horizontal":   "boolean — true for horizontal bars",
            "valueFormat":  "string — d3 format e.g. ',.0f' or '$,.1f'",
            "centerLabel":  "string — text in donut hole",
            "xField":       "string — x-axis data field",
            "series":       "Array<{field, label, color}> — for line/area/grouped-bar/stacked-bar",
            "yFormat":      "string — d3 format for y axis",
            "stacked":      "boolean — true for stacked area",
            "groupKey":     "string — x-axis group field for grouped-bar/stacked-bar",
            "yField":       "string — y-axis numeric field for scatter/bubble",
            "sizeField":    "string — circle size field for bubble chart",
            "xLabel":       "string — x-axis label text",
            "yLabel":       "string — y-axis label text",
            "groupField":   "string | null — colour grouping for bubble chart",
            "bins":         "number — number of histogram bins (default 20)",
            "colorScheme":  "'blue'|'red'|'green'|'purple' — heatmap/map colour ramp",
            "axes":         "string[] — spoke label names for radar chart",
            "positiveColor": "string — up-step bar colour (default '#22C55E')",
            "negativeColor": "string — down-step bar colour (default '#EF4444')",
            "totalColor":    "string — total/subtotal bar colour (default '#0064D2')",
            "filterField":  "string | null",
            "filterOptions":"string[]",
            "charts":       (
                "Array of self-contained chart configs — each has: "
                "type (any chartType above), title, data, plus the fields for that type."
            ),
            "layout":       "'grid' (default) | 'tabs'",
        },
    },

    # ── Maps ──────────────────────────────────────────────────────────────────
    "world-map": {
        "template":    "WorldMap.skill.tsx",
        "config_file": "WorldMap.config.ts",
        "owner_agent": "visual_design",
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
        "owner_agent": "visual_design",
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

    # ── Country / sub-national map ───────────────────────────────────────────
    "country-map": {
        "template":    "CountryMap.skill.tsx",
        "config_file": "CountryMap.config.ts",
        "owner_agent": "visual_design",
        "description": "Sub-national choropleth map for ANY single country (India states, "
                       "UK regions, Germany Bundesländer, Brazil estados, France régions, etc.). "
                       "Uses public GeoJSON URLs for admin-1 boundaries.",
        "triggers": [
            "countrymap", "indiamap", "india", "ukmap", "germanymap", "germany",
            "brazilmap", "brazil", "francemap", "france", "canadamap", "canada",
            "australiamap", "australia", "japanmap", "japan", "chinamap", "china",
            "mexicomap", "mexico", "italymap", "italy", "spainmap", "spain",
            "southafricamap", "nigeriamap", "indonesiamap",
            "provinces", "bundesland", "prefecture", "estado",
            "subnational", "regional", "statewise", "districtwise",
        ],
        "config_schema": {
            "tableName":      "string — SQLite table name from schema.sql",
            "countryName":    "string — display name (e.g. 'India', 'United Kingdom')",
            "geoJsonUrl":     "string — public URL to GeoJSON with admin-1 boundaries (see config template for common URLs)",
            "regionNameProp": "string — GeoJSON property containing region name (e.g. 'NAME_1', 'name', 'state')",
            "regionField":    "string — column in YOUR data matching region names in the GeoJSON",
            "valueField":     "string — numeric field that drives colour intensity",
            "labelField":     "string — label for tooltips (often same as regionField)",
            "title":          "string",
            "colorScheme":    "'blue'|'green'|'orange'|'purple'|'red'",
            "valueFormat":    "string — d3 format (e.g. ',.0f', '$,.1f')",
            "filterField":    "string | null",
        },
    },

    # ── Dashboard / KPI ───────────────────────────────────────────────────────
    "kpi-dashboard": {
        "template":    "KpiDashboard.skill.tsx",
        "config_file": "KpiDashboard.config.ts",
        "owner_agent": "react_ui",
        "description": "KPI cards row + two summary charts + optional data table. "
                       "Works as a home / overview page for any domain.",
        "triggers": [
            "dashboard", "overview", "home", "summary", "executive",
            "kpi", "metrics", "scorecard",
        ],
        "config_schema": {
            "kpiTableName": "string|null — name of the DB table that holds KPI rows (e.g. 'kpis'). "
                            "Set this so cards are fetched at runtime. Set null ONLY if no suitable table exists.",
            "kpiMapping":   "{label, value, change, direction} — column names in kpiTableName. "
                            "Must match real columns from schema.sql.",
            "kpiCards":     "null (preferred — use kpiTableName) OR static Array<{label,value,change,direction}> as last resort",
            "chart1":      "{type:'bar'|'donut', title, tableName, labelField, valueField, valueFormat}",
            "chart2":      "{type:'line', title, tableName, xField, series:[{field,label,color}], yFormat}",
            "tableName":   "string|null — DB table for optional bottom data table (or null to hide)",
            "tableColumns":"Array<{key, header}> | null — columns for the bottom table",
            "pageTitle":   "string",
        },
    },

    # ── Export capabilities ───────────────────────────────────────────────────
    "pptx-export": {
        "template":    "PptxExport.skill.tsx",
        "config_file": "PptxExport.config.ts",
        "owner_agent": "react_ui",
        "description": "PowerPoint export panel using pptxgenjs. "
                       "Generates a real .pptx with cover slide + content slides from any data.",
        "triggers": [
            "pptx", "powerpoint", "slides", "presentation",
            "slideexport", "pptxexport", "slidereport",
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
        "owner_agent": "react_ui",
        "description": "Excel/CSV export button with optional sheet configuration.",
        "triggers": ["excelexport", "xlsx", "csvexport", "download", "spreadsheet"],
        "config_schema": {
            "sheets": "Array<{name, dataExport, columns: [{key, header}]}>",
            "filename": "string — e.g. 'report.xlsx'",
        },
    },

    "excel-parser": {
        "template":    "ExcelParser.skill.tsx",
        "config_file": "ExcelParser.config.ts",
        "owner_agent": "react_ui",
        "description": "Client-side Excel file upload and analytics page. Parses any .xlsx/.xls, "
                       "auto-detects column types, and renders D3 charts + sortable data table.",
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
        "owner_agent": "react_ui",
        "description": "Multi-section PDF report with a styled cover page, table of contents, "
                       "and one auto-table page per data section.",
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
        "owner_agent": "ai_genai",
        "description": "Three-panel AI chat interface: persona selector + chat window + export panel.",
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
        "owner_agent": "ai_genai",
        "description": "LLM-powered chat interface that connects to ANY data source. "
                       "Uses a local FastAPI backend with Bedrock/LiteLLM.",
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
            "server_template": "datachat_api_server.py",
            "env_template":    "datachat_env_template.txt",
            "requirements":    ["fastapi", "uvicorn", "python-dotenv", "openai", "httpx", "openpyxl", "PyMuPDF"],
        },
    },

    # ── Card grid ─────────────────────────────────────────────────────────────
    "card-grid": {
        "template":    "CardGrid.skill.tsx",
        "config_file": "CardGrid.config.ts",
        "owner_agent": "react_ui",
        "description": "Searchable, filterable grid of summary cards. "
                       "Works for player profiles, product catalog, dealer directory, etc.",
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
        "owner_agent": "react_ui",
        "description": "Multi-section settings / profile form with validation.",
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
        "owner_agent": "react_ui",
        "description": "Chronological activity feed / timeline.",
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

    # ── Tabbed Layout ─────────────────────────────────────────────────────────
    "tab-layout": {
        "template":    "TabLayout.skill.tsx",
        "config_file": "TabLayout.config.ts",
        "owner_agent": "react_ui",
        "description": "Generic tabbed page layout with mixed content sections per tab: "
                       "charts, tables, KPI rows, cards, or rich text. "
                       "Works for any multi-view dashboard or report page.",
        "triggers": [
            "tabs", "tabbed", "tabpanel", "multiview", "tabview",
            "tabbedlayout", "tablayout", "multitab", "paneled",
        ],
        "config_schema": {
            "pageTitle":    "string — page heading",
            "pageSubtitle": "string | null",
            "tabs": "Array<{id, label, sections: Array<Section>}> — each tab has a list of sections",
            "section_types": (
                "Each section has a 'type' field: "
                "'chart' — {type:'chart', title, chartType, data, ...chartFields} "
                "'table' — {type:'table', title, columns:[{key,header}], data} "
                "'kpi-row' — {type:'kpi-row', items:[{label,value,change?,direction?}]} "
                "'cards' — {type:'cards', items:[{title,subtitle?,metrics:[{label,value}]}]} "
                "'text' — {type:'text', title?, content:string}"
            ),
        },
    },

    # ── Kanban Board ──────────────────────────────────────────────────────────
    "kanban": {
        "template":    "Kanban.skill.tsx",
        "config_file": "Kanban.config.ts",
        "owner_agent": "react_ui",
        "description": "Drag-and-drop Kanban board with customizable columns and cards. "
                       "Works for task management, project pipelines, hiring funnels, etc.",
        "triggers": [
            "kanban", "board", "pipeline", "workflow", "tasks",
            "trello", "sprint", "backlog", "funnel", "stages",
        ],
        "config_schema": {
            "pageTitle":    "string",
            "pageSubtitle": "string | null",
            "columns":      "Array<{id, title, color}> — board columns (e.g. To Do, In Progress, Done)",
            "cards":        "Array<{id, columnId, title, subtitle?, priority?, assignee?, tags?:string[]}>",
            "priorityColors": "Record<priority, hexColor> — e.g. {high:'#EF4444', medium:'#F59E0B', low:'#22C55E'}",
        },
    },

    # ── Calendar ──────────────────────────────────────────────────────────────
    "calendar": {
        "template":    "Calendar.skill.tsx",
        "config_file": "Calendar.config.ts",
        "owner_agent": "react_ui",
        "description": "Monthly calendar view with event dots and detail panel. "
                       "Works for schedules, meetings, deadlines, releases, etc.",
        "triggers": [
            "calendar", "schedule", "events", "meetings", "planner",
            "agenda", "booking", "appointments", "dates",
        ],
        "config_schema": {
            "pageTitle":    "string",
            "pageSubtitle": "string | null",
            "events":       "Array<{id, title, date:'YYYY-MM-DD', time?, category?, description?}>",
            "categories":   "Array<{id, label, color}> — colour coding for event types",
            "initialMonth": "number (0-11) — starting month",
            "initialYear":  "number — starting year",
        },
    },

    # ── Detail Page (Master-Detail) ───────────────────────────────────────────
    "detail-page": {
        "template":    "DetailPage.skill.tsx",
        "config_file": "DetailPage.config.ts",
        "owner_agent": "react_ui",
        "description": "Two-panel master-detail layout: scrollable list on left, "
                       "detail view on right. Works for emails, tickets, documents, contacts, etc.",
        "triggers": [
            "detail", "masterdetail", "inspector", "viewer",
            "splitview", "listdetail", "twopanel", "inbox",
            "tickets", "emails", "documents",
        ],
        "config_schema": {
            "pageTitle":    "string",
            "pageSubtitle": "string | null",
            "items":        "Array<{id, title, subtitle?, date?, status?, body, metadata?: Record<string,string>}>",
            "statusColors": "Record<status, hexColor>",
            "searchFields": "string[] — fields to include in text search",
        },
    },

    # ── Notifications ─────────────────────────────────────────────────────────
    "notifications": {
        "template":    "Notifications.skill.tsx",
        "config_file": "Notifications.config.ts",
        "owner_agent": "react_ui",
        "description": "Notification inbox with filters, categories, and mark-as-read. "
                       "Works for alerts, messages, system notifications, approvals, etc.",
        "triggers": [
            "notifications", "alerts", "messages", "inbox",
            "announcements", "updates", "approvals", "bell",
        ],
        "config_schema": {
            "pageTitle":    "string",
            "pageSubtitle": "string | null",
            "notifications": "Array<{id, title, message, timestamp, category, read:boolean, priority?}>",
            "categories":    "Array<{id, label, icon?, color}> — filter chips",
            "priorities":    "Array<{id, label, color}> — e.g. [{id:'urgent',label:'Urgent',color:'#EF4444'}]",
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def _get_template_path(skill: dict) -> Path | None:
    """Resolve the template file from the owning agent's templates/ dir."""
    owner = skill.get("owner_agent", "")
    template_dir = _TEMPLATE_DIRS.get(owner)
    if template_dir:
        path = template_dir / skill["template"]
        if path.exists():
            return path
    # Fallback: search all template dirs
    return _find_template(skill["template"])


def _get_config_path(skill: dict) -> Path | None:
    """Resolve the config template from the owning agent's templates/ dir."""
    owner = skill.get("owner_agent", "")
    template_dir = _TEMPLATE_DIRS.get(owner)
    if template_dir:
        path = template_dir / skill["config_file"]
        if path.exists():
            return path
    return _find_template(skill["config_file"])


def get_skill(page_name: str) -> dict | None:
    """
    Match a page name to a skill.
    Priority: exact skill key → exact trigger → longest substring trigger match.
    """
    key = _normalise(page_name)
    # Exact skill key match
    for skill_key, meta in SKILL_REGISTRY.items():
        if key == _normalise(skill_key):
            return {"skill_key": skill_key, **meta}
    # Exact trigger match
    for skill_key, meta in SKILL_REGISTRY.items():
        for trigger in meta.get("triggers", []):
            if key == _normalise(trigger):
                return {"skill_key": skill_key, **meta}
    # Substring trigger match — prefer longest matching trigger to avoid
    # short generic triggers (e.g. "report") stealing from specific ones (e.g. "pdfreport")
    best_match = None
    best_len = 0
    for skill_key, meta in SKILL_REGISTRY.items():
        for trigger in meta.get("triggers", []):
            t = _normalise(trigger)
            if t in key and len(t) > best_len:
                best_match = {"skill_key": skill_key, **meta}
                best_len = len(t)
    return best_match


def load_skill_template(page_name: str) -> str | None:
    """Return the TSX template content, or None if not found."""
    skill = get_skill(page_name)
    if not skill:
        return None
    path = _get_template_path(skill)
    return path.read_text(encoding="utf-8") if path else None


def load_config_template(page_name: str) -> str | None:
    """Return the config template content, or None if not found."""
    skill = get_skill(page_name)
    if not skill:
        return None
    path = _get_config_path(skill)
    return path.read_text(encoding="utf-8") if path else None


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
