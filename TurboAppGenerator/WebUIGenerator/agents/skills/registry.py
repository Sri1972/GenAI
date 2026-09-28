"""
Skill registry — capability-based UI skills for TurboUIGen.

A SKILL is a pre-written, domain-agnostic React component or page template.
The LLM's only job is to fill in a tiny config (~30 lines).
The skill renders any domain's data from that config.

Templates are now stored in each agent's templates/ directory:
  - agents/react_ui/templates/        -> DataGrid, CardGrid, KpiDashboard, etc.
  - agents/visual_design/templates/   -> Charts, WorldMap, UsaMap
  - agents/ai_genai/templates/        -> DataChat
  - agents/webui_integration_engineer/templates/ -> app_server_template.py, useApi.hook.ts, etc.

Matching (get_skill) is always deterministic-first and always includes ALL skills,
regardless of USE_SDK_AGENTS — a page name/description either clearly matches a
pre-built component (map, chart, grid, dashboard, export, chat, ...) or it doesn't.
USE_SDK_AGENTS only controls HOW a matched skill's config gets filled in
(orchestrator._gen_skill_page calls the Claude SDK Tool Runner vs. a legacy direct
LLM call) — it never controls WHICH skills exist. Pages with no deterministic or
LLM-semantic match fall through to full custom generation, where the SDK agents'
creative generation is used for genuinely bespoke pages.
"""

import os
from pathlib import Path

# Templates now live alongside each agent in the shared catalog, not here —
# see AgentPlatform/catalog/<agent_id>/templates/.
CATALOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "AgentPlatform" / "catalog"

SKILLS_DIR = CATALOG_DIR / "webui_integration_engineer" / "templates"

# Template locations by agent
_TEMPLATE_DIRS = {
    "react_ui": CATALOG_DIR / "react_ui" / "templates",
    "visual_design": CATALOG_DIR / "visual_design" / "templates",
    "ai_genai": CATALOG_DIR / "ai_genai" / "templates",
    "webui_integration_engineer": CATALOG_DIR / "webui_integration_engineer" / "templates",
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
        "categories": ["chart", "graph", "plot", "visualiz", "analytic", "metric", "trend"],
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
            "series":       (
                "For line/area/grouped-bar/stacked-bar: Array<{field, label, color}> — "
                "field references a column in tableName's rows, fetched live. "
                "For radar ONLY: Array<{label, color, values: number[]}> — a DIFFERENT shape. "
                "values is a static array of numbers, one per axis in the SAME ORDER as `axes`, "
                "normalized to a common scale (e.g. 0-100) — YOU must compute/estimate these "
                "numbers yourself from what you know about the table/domain, since a radar "
                "series has no live per-row fetch. NEVER leave values as an empty array — the "
                "chart renders nothing if you do. Do NOT add field/tableName/aggMethod to a "
                "radar series object; those belong only to the other chart types."
            ),
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
            "aggMethod":    "'sum'|'avg'|'count'|'min'|'max' (default 'sum') — how rows sharing the same labelField are combined for bar/donut/pie/treemap/waterfall",
            "joinTableName":"string | null — a SECOND table to fetch and join onto tableName's rows by joinKey, when the label/group you need lives on a different table",
            "joinKey":      "string | null — shared column name present on both tableName and joinTableName (e.g. 'store_code')",
            "joinFields":   "string[] — column names to pull from joinTableName onto each row (e.g. ['format'])",
            "charts":       (
                "Array of self-contained chart configs for 'multi' mode — each entry is a FULL chart "
                "config in its own right: type (any chartType above), title, and its OWN tableName "
                "(fetched live, independently of the other entries) plus that type's fields. `data` on "
                "a sub-chart should be omitted/null when tableName is set — do NOT hardcode a data "
                "array of invented numbers as a substitute for a real tableName fetch."
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
            "globalsales", "globalsalesmap", "regionalsales",
        ],
        "categories": ["map", "geo", "region", "country", "global"],
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
            "usamap", "usmap", "northamerica", "statemap",
            "usachoropleth", "unitedstates", "usstate",
            "ussales", "ussalesmap", "usstatemap", "usstatesales",
            "usstateanalysis", "statesales", "salesmapus",
        ],
        "categories": ["map", "state", "usa", "geographic"],
        "config_schema": {
            "tableName":      "string — SQLite table name from schema.sql (data fetched from /api/data/{tableName})",
            "dataExport":     "null (use tableName instead for API-backed apps)",
            "stateField":     "string — column containing state name or 2-letter abbreviation",
            "valueField":     "string — numeric column that drives colour intensity",
            "title":          "string",
            "colorScheme":    "'blue'|'green'|'orange'|'purple'",
            "filterField":    "string | null — optional dropdown filter column",
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
        "categories": ["map", "geo", "region", "province", "district"],
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
        "categories": ["export", "download", "report", "presentation"],
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
        "categories": ["export", "download", "spreadsheet"],
        "config_schema": {
            "sheets": "Array<{name, dataExport, columns: [{key, header}]}>",
            "filename": "string — e.g. 'report.xlsx'",
        },
    },

    "pdf-export": {
        "template":    "PdfExport.skill.tsx",
        "config_file": "PdfExport.config.ts",
        "owner_agent": "react_ui",
        "description": "Multi-section PDF report with a styled cover page, table of contents, "
                       "and one auto-table page per data section.",
        "triggers": ["pdf", "pdfexport", "exportpdf", "pdfreport", "printable", "printreport"],
        "categories": ["export", "download", "report", "print"],
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
    # NOTE: a static, canned-response "ai-chat" skill (AiChat.skill.tsx) used
    # to live here. Retired — every real case this pipeline has generated
    # wanted the data-aware skill below, and data-chat is a strict superset
    # (it can also answer plain FAQ-style questions, just via real LLM
    # reasoning instead of a fixed lookup table). See data-chat's own
    # triggers/description for the disambiguation this replaced.

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
            "dataassistant", "querydata", "smartchat", "concierge",
        ],
        "categories": ["chat", "assistant", "ai", "llm", "ask", "converse", "concierge", "copilot"],
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
            "mcp_template":    "mcp_server_template.py",
            "env_template":    "datachat_env_template.txt",
            "requirements":    ["fastapi", "uvicorn", "python-dotenv", "openai", "httpx", "openpyxl", "PyMuPDF", "fastmcp", "anthropic[bedrock]"],
        },
    },

    # ── Ad-hoc query builder ────────────────────────────────────────────────────
    "query-builder": {
        "template":    "QueryBuilder.skill.tsx",
        "config_file": "QueryBuilder.config.ts",
        "owner_agent": "react_ui",
        "description": "Ad-hoc query tool: pick which columns to show, compose AND-combined "
                       "filter conditions (field/operator/value), sort, and run against the "
                       "REST API's server-side filtering (?filter=col:op:val;...). "
                       "Not a static table — for building/running custom queries interactively.",
        "triggers": [
            "querybuilder", "advancedsearch", "reportbuilder", "customquery",
            "adhocquery", "queryexplorer", "dataquery", "sqlbuilder",
            "filterbuilder", "querytool", "dataexplorer",
        ],
        "categories": ["query", "filter", "adhoc", "sqlbuilder"],
        "config_schema": {
            "tableName":   "string — SQLite table name from schema.sql (data fetched from /api/data/{tableName})",
            "pageTitle":   "string",
            "pageSubtitle":"string",
            "csvFilename": "string — filename for exported query results",
        },
    },

}

# ── Standard-shape skills ──────────────────────────────────────────────────
# Common, unambiguous page shapes (grids, dashboards, forms, feeds, ...). Always
# available for deterministic matching so a page named e.g. "ExecutiveOverview"
# reliably maps to kpi-dashboard instead of depending on the LLM fallback.
_STANDARD_SKILLS: dict[str, dict] = {

    "data-grid": {
        "template":    "DataGrid.skill.tsx",
        "config_file": "DataGrid.config.ts",
        "owner_agent": "react_ui",
        "description": "Filterable, sortable, paginated data table with CSV export.",
        "triggers": [
            "grid", "table", "list", "records", "explorer",
            "orders", "transactions", "inventory", "products",
            "players", "matches", "roster", "standings", "leaderboard",
        ],
        "categories": ["table", "grid", "list", "data", "record"],
        "config_schema": {
            "tableName":   "string — SQLite table name",
            "pageTitle":   "string",
            "pageSubtitle":"string",
            "rowKey":      "string",
            "searchFields":"string[]",
            "filters":     "Array<{label, field, options: string[]}>",
            "columns":     "Array<{key, header, type, align?, badgeColors?}>",
            "defaultSort": "{key, dir: 'asc'|'desc'}",
            "csvFilename": "string",
        },
    },

    "kpi-dashboard": {
        "template":    "KpiDashboard.skill.tsx",
        "config_file": "KpiDashboard.config.ts",
        "owner_agent": "react_ui",
        "description": "KPI cards row + two summary charts + optional data table.",
        "triggers": [
            "dashboard", "overview", "home", "summary", "executive",
            "kpi", "metrics", "scorecard",
        ],
        "categories": ["dashboard", "overview", "summary", "kpi", "metric"],
        "config_schema": {
            "kpiTableName": "string|null",
            "kpiMapping":   "{label, value, change, direction}",
            "kpiCards":     "null or static Array",
            "chart1":      "{type: 'bar'|'donut'|'line', title, tableName, labelField, valueField} (bar/donut) or {type:'line', title, tableName, xField, series} (line)",
            "chart2":      "same shape options as chart1 — pick whichever type this specific chart needs, independent of chart1's type",
            "chart3":      "optional — same shape options as chart1/chart2. Rendered FULL-WIDTH below the chart1/chart2 side-by-side row. Use this when the page needs a THIRD chart (e.g. two charts side by side plus a full-width trend line) — omit (leave null) if the page only needs two.",
            "tableName":   "string|null",
            "tableColumns":"Array<{key, header}> | null",
            "pageTitle":   "string",
        },
    },

    "card-grid": {
        "template":    "CardGrid.skill.tsx",
        "config_file": "CardGrid.config.ts",
        "owner_agent": "react_ui",
        "description": "Searchable, filterable grid of summary cards.",
        "triggers": [
            "cards", "cardgrid", "profiles", "team", "roster", "dealers",
            "directory", "catalog", "gallery", "people",
        ],
        "categories": ["card", "profile", "directory", "catalog", "gallery"],
        "config_schema": {
            "tableName":      "string",
            "nameField":      "string",
            "subtitleField":  "string | null",
            "badgeField":     "string | null",
            "badgeColors":    "Record<value, variant>",
            "metrics":        "Array<{field, label, format}>",
            "filters":        "Array<{label, field, options}>",
            "pageTitle":      "string",
        },
    },

    "settings-form": {
        "template":    "SettingsForm.skill.tsx",
        "config_file": "SettingsForm.config.ts",
        "owner_agent": "react_ui",
        "description": "Multi-section settings / profile form with validation.",
        "triggers": ["settings", "preferences", "profile", "config", "form", "setup"],
        "categories": ["settings", "form", "config", "preference"],
        "config_schema": {
            "sections": "Array<{title, fields: [{key, label, type, options?}]}>",
            "pageTitle": "string",
        },
    },

    "activity-feed": {
        "template":    "ActivityFeed.skill.tsx",
        "config_file": "ActivityFeed.config.ts",
        "owner_agent": "react_ui",
        "description": "Chronological activity feed / timeline.",
        "triggers": [
            "feed", "timeline", "activity", "news", "events",
            "results", "history", "log", "audit",
        ],
        "categories": ["feed", "timeline", "activity", "history", "log"],
        "config_schema": {
            "dataExport":   "imported array",
            "dateField":    "string",
            "titleField":   "string",
            "badgeField":   "string | null",
            "pageTitle":    "string",
        },
    },

    "tab-layout": {
        "template":    "TabLayout.skill.tsx",
        "config_file": "TabLayout.config.ts",
        "owner_agent": "react_ui",
        "description": "Generic tabbed page layout with mixed content sections per tab.",
        "triggers": [
            "tabs", "tabbed", "tabpanel", "multiview", "tabview",
            "tabbedlayout", "tablayout", "multitab", "paneled",
        ],
        "categories": ["tab", "panel", "section", "multi"],
        "config_schema": {
            "pageTitle":    "string",
            "tabs": "Array<{id, label, sections: Array<Section>}>",
        },
    },

    "kanban": {
        "template":    "Kanban.skill.tsx",
        "config_file": "Kanban.config.ts",
        "owner_agent": "react_ui",
        "description": "Drag-and-drop Kanban board with customizable columns and cards.",
        "triggers": [
            "kanban", "board", "pipeline", "workflow", "tasks",
            "trello", "sprint", "backlog", "funnel", "stages",
        ],
        "categories": ["board", "kanban", "workflow", "task", "pipeline"],
        "config_schema": {
            "pageTitle":    "string",
            "columns":      "Array<{id, title, color}>",
            "cards":        "Array<{id, columnId, title, priority?, assignee?}>",
            "priorityColors": "Record<priority, hexColor>",
        },
    },

    "calendar": {
        "template":    "Calendar.skill.tsx",
        "config_file": "Calendar.config.ts",
        "owner_agent": "react_ui",
        "description": "Monthly calendar view with event dots and detail panel.",
        "triggers": [
            "calendar", "schedule", "events", "meetings", "planner",
            "agenda", "booking", "appointments", "dates",
        ],
        "categories": ["calendar", "schedule", "event", "meeting", "booking"],
        "config_schema": {
            "pageTitle":    "string",
            "events":       "Array<{id, title, date, category?}>",
            "categories":   "Array<{id, label, color}>",
        },
    },

    "detail-page": {
        "template":    "DetailPage.skill.tsx",
        "config_file": "DetailPage.config.ts",
        "owner_agent": "react_ui",
        "description": "Two-panel master-detail layout: list on left, detail on right.",
        "triggers": [
            "detail", "masterdetail", "inspector", "viewer",
            "splitview", "listdetail", "twopanel", "inbox",
            "tickets", "emails", "documents",
        ],
        "categories": ["detail", "inspect", "view", "inbox", "ticket"],
        "config_schema": {
            "pageTitle":    "string",
            "items":        "Array<{id, title, body, status?}>",
            "statusColors": "Record<status, hexColor>",
            "searchFields": "string[]",
        },
    },

    "notifications": {
        "template":    "Notifications.skill.tsx",
        "config_file": "Notifications.config.ts",
        "owner_agent": "react_ui",
        "description": "Notification inbox with filters, categories, and mark-as-read.",
        "triggers": [
            "notifications", "alerts", "messages", "inbox",
            "announcements", "updates", "approvals", "bell",
        ],
        "categories": ["notification", "alert", "message", "approval"],
        "config_schema": {
            "pageTitle":    "string",
            "notifications": "Array<{id, title, message, category, read}>",
            "categories":    "Array<{id, label, color}>",
        },
    },

    "excel-parser": {
        "template":    "ExcelParser.skill.tsx",
        "config_file": "ExcelParser.config.ts",
        "owner_agent": "react_ui",
        "description": "Client-side Excel file upload and analytics page.",
        "triggers": [
            "excelparser", "excelupload", "excelinsight", "excelanalytics",
            "uploadexcel", "parseexcel", "fileupload", "excelimport",
            "dataimport", "fileanalytics", "excelreader",
        ],
        "categories": ["upload", "import", "parse", "file", "excel"],
        "config_schema": {
            "pageTitle":    "string",
            "pageSubtitle": "string",
            "accentColor":  "hex string",
            "chartColors":  "string[10]",
        },
    },
}

# Always merge standard-shape skills — matching stays deterministic regardless
# of USE_SDK_AGENTS. See module docstring.
SKILL_REGISTRY.update(_STANDARD_SKILLS)


# ─────────────────────────────────────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def _tokenize(name: str) -> set[str]:
    """
    Split a page name into lowercase word tokens on camelCase/space/hyphen/
    underscore boundaries, e.g. "LogisticsAi" -> {"logistics", "ai"}. Used to
    require whole-word alignment for short triggers in substring matching
    (see get_skill strategy 3) - a short trigger like "log" is a common
    English word-start (Logistics, Blog, Login...) that raw substring
    containment matches by pure spelling accident, unrelated to the trigger's
    actual meaning ("audit log").
    """
    import re as _re
    spaced = _re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return {w.lower() for w in _re.split(r"[^a-zA-Z0-9]+", spaced) if w}


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


def _llm_match_skill(page_name: str, description: str = "", candidate: str | None = None) -> str | None:
    """
    Use a fast LLM call to confirm or override a heuristic skill-match guess.
    This is the FINAL arbiter (see get_skill's docstring for why) —
    deterministic heuristics only ever produce a hint fed into this prompt,
    never an authoritative answer on their own. Returns the skill_key
    string, or None if no skill fits.

    Raises on a technical failure (network/parsing) rather than swallowing
    it — get_skill() decides how to degrade (falls back to the heuristic
    `candidate` rather than losing the match outright on a transient error).
    """
    skill_catalog = "\n".join(
        f"  {key}: {meta['description'].split('.')[0]}"
        for key, meta in SKILL_REGISTRY.items()
    )
    candidate_line = (
        f"A keyword-matching heuristic suggests \"{candidate}\" — this is usually right, "
        f"so lean toward confirming it. Only override it if the description clearly shows "
        f"it's a coincidental name/word overlap unrelated to the page's actual purpose "
        f"(judge from the description, not just the name).\n\n"
        if candidate else
        "No keyword-matching heuristic found a guess for this page — decide from scratch.\n\n"
    )
    prompt = (
        f"Page name: \"{page_name}\"\n"
        f"Page description: \"{description}\"\n\n"
        f"Available UI component skills (each is a SPECIFIC pre-built component type):\n{skill_catalog}\n\n"
        f"{candidate_line}"
        f"Which skill is this page CLEARLY an instance of? Reply with ONLY the skill key or \"none\".\n\n"
        f"RULES — be conservative:\n"
        f"- Only match if the page is OBVIOUSLY that component type (e.g. a map page -> map skill)\n"
        f"- \"none\" is the SAFE DEFAULT — use it when uncertain\n"
        f"- A dashboard/overview/summary page is NOT pptx-export or pdf-export\n"
        f"- A page with 'export' or 'report' in its name that shows DATA is NOT an export skill\n"
        f"- Only match export skills if the page's PRIMARY purpose is file generation/download\n"
        f"- Only match data-chat if the page is a CHAT INTERFACE (conversational, message bubbles) — "
        f"this includes FAQ bots, help desks, and AI concierges/assistants/copilots that query data, "
        f"since data-chat is the only chat skill available\n"
        f"- A 'global' map = world-map, NOT usa-map\n"
        f"- If the description explicitly says the page is NOT a table/dashboard/map (e.g. "
        f"'NOT a dashboard', 'grid layout', 'spatial arrangement', 'monitoring wall'), do not "
        f"match a generic layout skill like kpi-dashboard — prefer \"none\" so it gets a bespoke "
        f"custom layout instead\n"
    )
    from agents.sdk_client import _get_litellm_client, _get_bedrock_client, \
        LITELLM_API_BASE, LITELLM_API_KEY, _using_fallback, BEDROCK_MODEL_ID
    from agents.llm import get_selected_model
    import token_tracker
    haiku_model = os.environ.get("LITELLM_HAIKU_MODEL", "claude-haiku-4-5")

    # temperature=0: this is now the mandatory arbiter for every page (see
    # get_skill), not an occasional last-resort call - a classification
    # judgment like this should be as consistent as possible run to run,
    # not subject to sampling variance on borderline-obvious cases.
    #
    # Respect the header's explicit provider choice — this call used to
    # ALWAYS try LiteLLM first regardless of what the user picked, checking
    # only sdk_client.py's own sticky Bedrock-unavailable flag. Reproduced
    # directly: a user picked "Bedrock Sonnet 5" in the header, yet every
    # single page still triggered a LiteLLM call here first (visible in the
    # server log as a wall of "lit-main-qa... 503 Service Unavailable"
    # retries), because this function never looked at the user's actual
    # selection at all, only at whether Bedrock had already failed once.
    user_selected_bedrock = get_selected_model().get("provider") == "bedrock"
    if user_selected_bedrock or _using_fallback or not LITELLM_API_BASE:
        call_model = BEDROCK_MODEL_ID
        client = _get_bedrock_client()
        response = client.messages.create(
            model=call_model,
            max_tokens=50,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    else:
        call_model = haiku_model
        client = _get_litellm_client()
        response = client.messages.create(
            model=call_model,
            max_tokens=50,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    # Called directly against the Anthropic SDK client rather than through
    # llm.py/sdk_client.py's chat()/run_agent() wrappers (this is a one-off,
    # every-page arbiter call, not a pipeline stage) — those wrappers are
    # also where every other call in this platform gets its usage recorded,
    # so without this, every single page paid a real Haiku/Bedrock call that
    # never showed up in token_tracker's totals at all.
    usage = getattr(response, "usage", None)
    if usage:
        token_tracker.record(
            token_tracker.get_run_id(),
            getattr(usage, "input_tokens", 0),
            getattr(usage, "output_tokens", 0),
            model=call_model,
        )
    answer = response.content[0].text.strip().lower().strip('"\'')
    if answer and answer != "none" and answer in SKILL_REGISTRY:
        note = f" (heuristic guess was '{candidate}')" if candidate and candidate != answer else ""
        print(f"  [skill-registry] LLM matched '{page_name}' -> '{answer}'{note}", flush=True)
        return answer
    if candidate:
        print(f"  [skill-registry] LLM overrode heuristic guess '{candidate}' -> none for '{page_name}'", flush=True)
    return None


def _deterministic_candidate(page_name: str, description: str = "") -> str | None:
    """
    Fast heuristic guess at which skill a page matches — used ONLY as a hint
    fed into the mandatory LLM confirmation in get_skill(), never returned
    directly. Deterministic string/substring matching is fast but prone to
    coincidental false positives: a page name or architect-assigned `type`
    string happening to contain/equal a trigger word unrelated to its actual
    meaning. Observed repeatedly: "LogisticsAi" matching on "log" (fixed by
    the whole-word-token requirement below), the generic type "ai-chat"
    exact-matching the wrong chat skill, "BedBoard" matching "kanban" on
    "board". Layered strategies, in order:
      1. Exact skill key match
      2. Exact trigger match
      3. Substring trigger match — longest trigger found in page name
      4. Multi-category match — 2+ category keywords in page name
      5. Description-based category match — keywords in page description
    """
    import re as _re

    key = _normalise(page_name)
    # 1. Exact skill key match
    for skill_key in SKILL_REGISTRY:
        if key == _normalise(skill_key):
            return skill_key
    # 2. Exact trigger match
    for skill_key, meta in SKILL_REGISTRY.items():
        for trigger in meta.get("triggers", []):
            if key == _normalise(trigger):
                return skill_key
    # 3. Substring trigger match — prefer longest matching trigger.
    # Short triggers (<=4 chars, e.g. "log", "form", "list") are common
    # English word-starts and match unrelated page names by pure spelling
    # coincidence via raw substring containment (e.g. "log" inside
    # "LogisticsAi") - require those to align with a whole camelCase/word
    # token instead. Longer compound triggers (e.g. "globalsalesmap",
    # "chatwithdata") are specific enough that raw substring containment is
    # safe and intentional (matching a partial compound page name).
    name_tokens = _tokenize(page_name)
    best_match = None
    best_len = 0
    for skill_key, meta in SKILL_REGISTRY.items():
        for trigger in meta.get("triggers", []):
            t = _normalise(trigger)
            matched = (t in name_tokens) if len(t) <= 4 else (t in key)
            if matched and len(t) > best_len:
                best_match = skill_key
                best_len = len(t)
    if best_match:
        return best_match
    # 4. Multi-category match in page name — if 2+ category words from a skill
    #    appear in the normalized page name, it's a match
    cat_scored = []
    for skill_key, meta in SKILL_REGISTRY.items():
        categories = meta.get("categories", [])
        if not categories:
            continue
        hits = sum(1 for cat in categories if cat in key)
        if hits >= 2:
            cat_scored.append((hits, skill_key))
    if cat_scored:
        cat_scored.sort(key=lambda x: x[0], reverse=True)
        if len(cat_scored) == 1 or cat_scored[0][0] > cat_scored[1][0]:
            return cat_scored[0][1]
    # 5. Category match against page description
    if description:
        desc_words = set(_re.findall(r"[a-z]{3,}", description.lower()))

        def _cat_matches(cat: str) -> bool:
            if len(cat) < 5:
                return cat in desc_words
            return any(w.startswith(cat) for w in desc_words)

        scored = []
        for skill_key, meta in SKILL_REGISTRY.items():
            categories = meta.get("categories", [])
            if not categories:
                continue
            hits = sum(1 for cat in categories if _cat_matches(cat))
            if hits >= 3:
                scored.append((hits, skill_key))
        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            if len(scored) == 1 or scored[0][0] > scored[1][0]:
                return scored[0][1]
    return None


def get_skill(page_name: str, description: str = "") -> dict | None:
    """
    Match a page to a skill. A fast deterministic heuristic
    (_deterministic_candidate) proposes a guess, but the LLM always makes
    the final call — deterministic matching alone was repeatedly wrong in
    ways that mattered (see _deterministic_candidate's docstring), and each
    prior fix was a one-off patch for an already-discovered collision. The
    LLM call is cheap (Haiku on the primary path) and is handed the
    heuristic guess as a hint, so it usually just confirms it quickly rather
    than reasoning from scratch — this isn't paying full semantic-matching
    cost on every page, just a small confirmation step.

    If the LLM call itself fails (network/parsing, not a semantic "none"),
    fall back to the heuristic guess rather than losing the match outright —
    a transient error shouldn't silently downgrade every page in the app to
    full custom generation.
    """
    candidate = _deterministic_candidate(page_name, description)
    try:
        confirmed = _llm_match_skill(page_name, description, candidate=candidate)
    except Exception as e:
        print(f"  [skill-registry] LLM confirmation call failed ({e}) — trusting heuristic guess", flush=True)
        confirmed = candidate
    if confirmed and confirmed in SKILL_REGISTRY:
        return {"skill_key": confirmed, **SKILL_REGISTRY[confirmed]}
    return None


def list_skills() -> list[str]:
    return list(SKILL_REGISTRY.keys())


def skill_summary() -> str:
    """One-line summary of all skills — injected into the Pass 1 system prompt."""
    lines = ["Available UI skills (use these capabilities; they are pre-built and tested):"]
    for key, meta in SKILL_REGISTRY.items():
        triggers = ", ".join(meta["triggers"][:5])
        lines.append(f"  {key}: {meta['description'].split('.')[0]}. Triggers: {triggers}")
    return "\n".join(lines)
