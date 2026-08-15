<div id="top"></div>

# TurboUIGen — Complete Documentation

> AI-powered platform that generates production-ready React/TypeScript/Tailwind web applications from text prompts or Figma designs, with a multi-agent pipeline, self-healing code, and a shared design system.

---

<div id="nav"></div>

## Navigation

| [Product](#product) | [Technical](#technical) |
|---|---|
| What it does, how to use it, capabilities | Architecture, code, setup, APIs, troubleshooting |

### Product Sub-sections

| [Platform Overview](#prod-overview) | [FigmaMockupGenerator](#prod-figmamockup) | [WebUIGenerator](#prod-webuigen) | [UIDesignSystem](#prod-designsystem) |
|---|---|---|---|

### Technical Sub-sections

| [Platform Architecture](#tech-architecture) | [FigmaMockupGenerator](#tech-figmamockup) | [WebUIGenerator](#tech-webuigen) | [UIDesignSystem](#tech-designsystem) | [Setup & Config](#tech-setup) | [Troubleshooting](#tech-troubleshooting) |
|---|---|---|---|---|---|

---
---

<div id="product"></div>

# PRODUCT

---

<div id="prod-overview"></div>

## Platform Overview

TurboUIGen is a three-module AI platform that turns ideas into working software:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          TurboUIGen Platform                                      │
│                       http://localhost:3000                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────┐  ┌─────────────────────┐  ┌────────────────────┐  │
│  │                          │  │                      │  │                     │  │
│  │  FigmaMockupGenerator    │  │   WebUIGenerator     │  │  UIDesignSystem     │  │
│  │                          │  │                      │  │                     │  │
│  │  Text Prompt ──────────┐ │  │  Text Prompt ──────┐ │  │  Branded React      │  │
│  │                        │ │  │  Figma URL ───────┐│ │  │  components for     │  │
│  │                        │ │  │                   ││ │  │  all generated      │  │
│  │                        ▼ │  │                   ▼▼ │  │  apps               │  │
│  │  Interactive Figma      │  │  React/TS/Tailwind   │  │                     │  │
│  │  Wireframe with         │  │  Web App with        │  │  18 components      │  │
│  │  clickable navigation   │  │  SQLite + API        │  │  Design tokens      │  │
│  │                          │  │                      │  │  Storybook docs     │  │
│  └─────────────────────────┘  └─────────────────────┘  └────────────────────┘  │
│           │                          │                           │               │
│           │                          │                           │               │
│           ▼                          ▼                           ▼               │
│   Built in Figma Desktop      Live on localhost          Component library       │
│   (real-time)                 (auto-assigned port)       (Storybook :6006)       │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

| Module | Input | Output | Time |
|---|---|---|---|
| **FigmaMockupGenerator** | Text prompt | Interactive Figma prototype with clickable navigation | ~30-60s |
| **WebUIGenerator** | Text prompt OR Figma URL | React/TypeScript/Tailwind/Vite app with SQLite + REST API | ~60-120s |
| **UIDesignSystem** | — (pre-built library) | 18 branded React components + design tokens + Storybook | — |

All three share a single UI at `http://localhost:3000` and are powered by Claude (via LiteLLM proxy or AWS Bedrock).

### End-to-End Workflows

```
Workflow A:  Text Prompt ──→ WebUIGenerator ──→ React App on localhost

Workflow B:  Figma URL ──→ WebUIGenerator ──→ React App on localhost

Workflow C:  Text Prompt ──→ FigmaMockupGenerator ──→ Figma Wireframe
                                                          │
                                                   (copy URL)
                                                          │
                                                          ▼
                                               WebUIGenerator ──→ React App
```

[↑ Navigation](#nav) · [↑ Product](#product)

---

<div id="prod-figmamockup"></div>

## FigmaMockupGenerator — Product

### What It Does

Converts a text description of an app into an interactive Figma wireframe — complete with screens, navigation, modals, and clickable prototype wiring. The wireframe is built in real-time directly in Figma Desktop.

### Product Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FigmaMockupGenerator — User View                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   INPUT                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐           │
│   │  📝 Text Prompt                                              │           │
│   │  "Build a fleet management dashboard with vehicle tracking,  │           │
│   │   maintenance schedules, driver performance, and alerts"     │           │
│   └──────────────────────────────┬──────────────────────────────┘           │
│                                  ▼                                            │
│              ┌─────────────────────────────────┐                            │
│              │   LLM Agent + 19 Figma Tools    │                            │
│              │   (up to 60 turns of actions)    │                            │
│              │   ~30-60 seconds                 │                            │
│              └────────────────┬────────────────┘                            │
│                               ▼                                              │
│   OUTPUT (appears live in Figma Desktop)                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  Interactive Figma Wireframe                                         │   │
│   │                                                                      │   │
│   │  ✓ Multiple screens (Dashboard, Details, Settings, etc.)            │   │
│   │  ✓ Navigation wiring (click tab → navigate to screen)              │   │
│   │  ✓ Modals and drawers (click button → show overlay)                │   │
│   │  ✓ Cards, tables, charts, KPIs, buttons, forms                     │   │
│   │  ✓ Responsive layout with auto-layout frames                       │   │
│   │  ✓ Scrollable content areas                                        │   │
│   │  ✓ Prototype-ready (hit Play in Figma to test)                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   THEN (optional): Copy Figma URL → paste into WebUIGenerator → React app   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What You Need on Your Laptop

| Requirement | Why | How to get it |
|---|---|---|
| **Figma Desktop app** | Bridge plugin only works in desktop app (not browser) | figma.com/downloads |
| **Figma Desktop Bridge plugin** | Receives commands from TurboUIGen, draws on canvas | Import from `FigmaMockupGenerator/figma/mcp/plugin/manifest.json` |
| **Open Figma file** | Plugin draws into the currently active file | Create or open any Figma file |
| **MCP server running** | Routes LLM tool calls to Figma | Run `FigmaMockupGenerator/figma/mcp/start.bat` |
| **Ports 7771 + 9223 free** | MCP server + Figma bridge | Typically free by default |

### How to Use

```
Step 1: Start the MCP server
         → Run: FigmaMockupGenerator/figma/mcp/start.bat
         → Keep this terminal open

Step 2: Open Figma Desktop
         → Open/create a file
         → Plugins → Development → Figma Desktop Bridge → Run
         → Wait for "Local Ready" in plugin panel

Step 3: In TurboUIGen UI (http://localhost:3000)
         → Click "Figma Mockup" tab
         → Check MCP status is green (✓ Ready · 19 tools)
         → Type prompt, click "Build Wireframe"
         → Watch wireframe appear live in Figma
```

**Important:** `start.bat` MUST run BEFORE opening the Bridge plugin. If reversed, the plugin shows "Connecting..." forever.

### Modes

| Mode | What it does |
|---|---|
| **Create** | Build new wireframe from scratch in current file |
| **Replace** | Delete existing frames, build fresh |
| **Append** | Add new screens to existing wireframe |

### What Happens Next (Optional)

After the wireframe is built, you can:
1. Copy the Figma file URL
2. Go to **UI App Creation** tab in TurboUIGen
3. Paste the Figma URL
4. Generate a full React app matching the wireframe design

This gives you the full **Text → Figma → React** pipeline.

[↑ Navigation](#nav) · [↑ Product](#product)

---

<div id="prod-webuigen"></div>

## WebUIGenerator — Product

### What It Does

Generates complete, production-ready React web applications from either a text description or a Figma design URL. The output is a fully working app with real data, responsive layout, interactive charts, and self-healing code.

### Product Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WebUIGenerator — User View                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   INPUT (choose one)                                                         │
│   ┌─────────────────────────────┐  ┌──────────────────────────────────┐    │
│   │  📝 Text Prompt              │  │  🎨 Figma URL                     │    │
│   │  "Build an IPL cricket       │  │  https://figma.com/design/...    │    │
│   │   dashboard with player      │  │                                  │    │
│   │   stats, match analytics,    │  │  Paste any design/file/make/     │    │
│   │   and team comparison"       │  │  proto URL from Figma            │    │
│   └──────────────┬──────────────┘  └───────────────┬──────────────────┘    │
│                  │                                  │                        │
│                  └──────────────┬───────────────────┘                        │
│                                 ▼                                            │
│              ┌─────────────────────────────────┐                            │
│              │   6-Agent AI Pipeline            │                            │
│              │   + Self-Healing (auto-fix)      │                            │
│              │   ~60-120 seconds                │                            │
│              └────────────────┬────────────────┘                            │
│                               ▼                                              │
│   OUTPUT                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  Complete React/TypeScript/Tailwind/Vite Web Application             │   │
│   │                                                                      │   │
│   │  ✓ Multi-page app with sidebar navigation                           │   │
│   │  ✓ 15+ chart types (D3.js) — bar, line, pie, radar, sankey, etc.   │   │
│   │  ✓ US + World maps with drill-down                                  │   │
│   │  ✓ SQLite database with schema + realistic seed data                │   │
│   │  ✓ REST API server (FastAPI)                                        │   │
│   │  ✓ DataChat — AI conversational analytics (optional)                │   │
│   │  ✓ Export toolbar (CSV, Excel, PDF)                                 │   │
│   │  ✓ Responsive design, design system integration                     │   │
│   │  ✓ Full TypeScript type safety                                      │   │
│   │  ✓ Self-healed — TypeScript + runtime errors auto-fixed             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   LIVE AT: http://localhost:3000/app/<project-name>                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How to Use

**From the UI:**
1. Open `http://localhost:3000`
2. Click **UI App Creation** tab
3. Create a new project (give it a name)
4. Type a prompt describing your app (or select a domain instruction)
5. Click **Generate**
6. Wait ~60-120 seconds — watch progress in real-time
7. App appears in the preview iframe, running on its own port

**From CLI:**
```bash
cd TurboUIGen/WebUIGenerator
python -m cli.client generate "IPL cricket dashboard with player stats"
python -m cli.client generate --figma "https://www.figma.com/design/ABC123/MyApp"
python -m cli.client list
python -m cli.client start my-project
python -m cli.client stop my-project
python -m cli.client delete my-project
```

**Docker packaging:**
```bash
python cli/dockerize.py <project-name>    # Package as nginx Docker container
python cli/dockerize.py --status          # Show running containers
python cli/dockerize.py --stop-all        # Stop all containers
```

### Features of Generated Apps

| Feature | Details |
|---|---|
| **React 18 + TypeScript** | Full type safety, functional components with hooks |
| **Tailwind CSS** | Utility-first styling, responsive design |
| **Vite** | Fast dev server with HMR, optimized builds |
| **SQLite + REST API** | Real database with schema.sql, seed.sql, FastAPI server |
| **useApi hook** | Data fetching with retry, abort on unmount, pagination |
| **D3.js charts** | Responsive charts with ResizeObserver, tooltips |
| **Sidebar navigation** | React Router with collapsible sidebar |
| **Design system** | Mobility Global components (Header, Sidebar, KpiCard, etc.) |
| **Export toolbar** | CSV/Excel/PDF export on tables |
| **DataChat (optional)** | AI-powered conversational analytics |
| **Self-heal** | Auto-fixes TypeScript errors and runtime bugs |

### Chart Types Supported

| Chart Type | Use case |
|---|---|
| Bar chart | Category comparisons, rankings |
| Line chart | Time series, trends |
| Pie/Donut chart | Part-to-whole composition |
| Radar/Spider chart | Multi-dimensional profiles |
| Treemap | Hierarchical data, market share |
| Sunburst | Nested hierarchies with drill-down |
| Funnel chart | Conversion pipelines, retention |
| Gauge chart | KPI vs target, progress meters |
| Waterfall chart | Sequential additions/subtractions |
| Sankey diagram | Flow relationships, resource allocation |
| Bubble chart | Three-variable scatter plots |
| Histogram | Distribution analysis |
| Candlestick chart | Financial OHLC data |
| Box plot | Statistical distributions by group |
| Polar/Rose chart | Cyclical data (day-of-week, monthly) |
| Choropleth (US) | State-level data on US map |
| Choropleth (World) | Country-level data on world map |

### Supported Domains

Pre-built instruction files for instant generation in:

| Domain | Example apps |
|---|---|
| **Automotive** | Inventory portal, sales dashboard, global market tracker |
| **Financial Services** | Wealth advisor, portfolio analytics, risk dashboard |
| **Healthcare** | Clinical operations, patient flow, unit analytics |
| **Human Resources** | People analytics, workforce planning, talent dashboard |
| **Logistics** | Supply chain tracker, fleet management, route optimizer |
| **Retail** | Store operations, performance lab, inventory management |
| **Education** | Campus insights, student success, academic analytics |

[↑ Navigation](#nav) · [↑ Product](#product)

---

<div id="prod-designsystem"></div>

## UIDesignSystem — Product

### What It Does

A branded React component library (Mobility Global) that provides consistent, pre-built UI components to all generated web apps. Ships with Storybook documentation.

### Product Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       UIDesignSystem — User View                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   COMPONENTS (18 branded React components)                                   │
│                                                                              │
│   Layout & Navigation        Data Display           Form & Input             │
│   ┌──────────────────┐      ┌──────────────────┐   ┌──────────────────┐    │
│   │ Header           │      │ Card             │   │ Button           │    │
│   │ Sidebar          │      │ KpiCard          │   │ Input            │    │
│   │ Footer           │      │ DataTable        │   │ SearchBar        │    │
│   │ Breadcrumb       │      │ Badge            │   │ Dropdown         │    │
│   │ Tabs             │      │ Avatar/Group     │   │                  │    │
│   │                  │      │ ProgressBar      │   │                  │    │
│   └──────────────────┘      └──────────────────┘   └──────────────────┘    │
│                                                                              │
│   Feedback & Overlay                                                         │
│   ┌──────────────────┐                                                      │
│   │ Modal            │                                                      │
│   │ Alert            │                                                      │
│   │ Tooltip          │                                                      │
│   │ Pagination       │                                                      │
│   └──────────────────┘                                                      │
│                                                                              │
│   DESIGN TOKENS                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  Colors (primary, secondary, accent, semantic)                       │   │
│   │  Typography (font families, sizes, weights)                          │   │
│   │  Spacing (4px grid, padding/margin scale)                            │   │
│   │  Shadows (elevation levels)                                          │   │
│   │  Border radii                                                        │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   HOW IT REACHES GENERATED APPS                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  UIDesignSystem/ (source)                                            │   │
│   │       │ setup-deps copies to:                                        │   │
│   │       ▼                                                              │   │
│   │  $TURBOUI_JUNCTION_DIR/mgds/ (runtime copy)                          │   │
│   │       │ every generated app imports from:                            │   │
│   │       ▼                                                              │   │
│   │  import { Header, KpiCard } from '@mobility-global/design-system'    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   STORYBOOK: http://localhost:6006                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components Reference

#### Layout & Navigation
- `Header` — Top app bar with logo, nav links, user avatar
- `Sidebar` — Collapsible left nav with sections and active state
- `Footer` — Bottom bar with links and copyright
- `Breadcrumb` — Hierarchy trail with separator
- `Tabs` — Horizontal tab switcher (line and pill variants)

#### Data Display
- `Card` — Content container with header, footer, padding variants
- `KpiCard` — Metric card with value, label, trend delta, accent color
- `DataTable` — Sortable table with column definitions, row click, empty state
- `Badge` — Status chip (default, success, warning, error, info)
- `Avatar` / `AvatarGroup` — User picture or initials, group stacking
- `ProgressBar` — Fill bar (default, success, warning, error)

#### Form & Input
- `Button` — Primary, secondary, ghost, danger; sizes sm/md/lg; loading state
- `Input` — Text field with label, helper text, error state, icons
- `SearchBar` — Search input with clear button
- `Dropdown` — Select menu with options and placeholder

#### Feedback & Overlay
- `Modal` — Overlay dialog (sm/md/lg/xl), header/body/footer slots
- `Alert` — Inline message (info, success, warning, error) with dismiss
- `Tooltip` — Hover hint (top/bottom/left/right placement)
- `Pagination` — Page controls with prev/next

### Storybook

```bash
cd TurboUIGen/UIDesignSystem
npm install        # first time only
npm run storybook  # opens http://localhost:6006
```

[↑ Navigation](#nav) · [↑ Product](#product)

---
---

<div id="technical"></div>

# TECHNICAL

---

<div id="tech-architecture"></div>

## Platform Architecture

### System-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          TurboUIGen — Technical Architecture                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ENTRY POINTS                                                                       │
│   ┌────────────────────────────────────────────────────────────────────────────┐    │
│   │  run.py / start.bat ──→ uvicorn(API/server.py) ──→ http://localhost:3000   │    │
│   │  CLI: python -m cli.client generate "..."                                   │    │
│   └────────────────────────────────────────────────────────────────────────────┘    │
│         │                                                                            │
│         ▼                                                                            │
│   API GATEWAY (API/server.py — FastAPI)                                              │
│   ┌────────────────────────────────────────────────────────────────────────────┐    │
│   │  /api/generate ──→ WebUIGenerator (uigen_agent.generate_project)           │    │
│   │  /api/figma/wireframe ──→ FigmaMockupGenerator (wireframe_agent)           │    │
│   │  /app/{name}/* ──→ Reverse proxy to Vite dev servers                       │    │
│   │  /* ──→ Static UI (UI/dist/)                                               │    │
│   └────────────────────────────────────────────────────────────────────────────┘    │
│         │                                    │                                       │
│         ▼                                    ▼                                       │
│   ┌──────────────────────────┐     ┌─────────────────────────────┐                 │
│   │  WebUIGenerator/agents/  │     │  FigmaMockupGenerator/      │                 │
│   │                          │     │  figma/                      │                 │
│   │  uigen_agent.py          │     │  ├── mcp/server.py          │                 │
│   │  orchestrator.py         │     │  ├── mcp/relay.py           │                 │
│   │  prompts.py              │     │  └── wireframe/             │                 │
│   │  postprocessors.py       │     │      prompt_to_figma_agent  │                 │
│   │  qa_agent.py             │     │                             │                 │
│   │  llm.py                  │     └──────────────┬──────────────┘                 │
│   │  figma_to_web_*_agent.py │                    │                                 │
│   └─────────────┬────────────┘                    │                                 │
│                 │                                  │                                 │
│                 ▼                                  ▼                                 │
│   ┌──────────────────────────────────────────────────────────────────────────┐     │
│   │  LLM BACKEND (Claude via LiteLLM proxy or AWS Bedrock)                    │     │
│   │  LITELLM_API_BASE / LITELLM_API_KEY in .env                              │     │
│   └──────────────────────────────────────────────────────────────────────────┘     │
│                                                                                      │
│   SHARED INFRASTRUCTURE (used by WebUIGenerator's generated apps)                    │
│   ┌──────────────────────────────────────────────────────────────────────────┐     │
│   │                                                                           │     │
│   │  $TURBOUI_JUNCTION_DIR/                                                   │     │
│   │  ├── shared-nm/node_modules/ ←── npm deps shared by ALL generated apps   │     │
│   │  └── mgds/ ←── Design system copy (imported by generated apps via paths) │     │
│   │                                                                           │     │
│   │  .env ←── All configuration (API keys, paths, ports)                     │     │
│   │  requirements.txt ←── Python deps (platform + generated app servers)     │     │
│   │                                                                           │     │
│   └──────────────────────────────────────────────────────────────────────────┘     │
│                                                                                      │
│   OUTPUT                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────────┐     │
│   │  WebUIGenerator/generated/web-apps/<name>/ ←── React/Vite apps           │     │
│   │  FigmaMockupGenerator/generated/figma-mockups/ ←── Wireframe metadata    │     │
│   └──────────────────────────────────────────────────────────────────────────┘     │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
TurboUIGen/
├── run.py                           ← Entry point — launches everything
├── start.bat                        ← Windows launcher (calls run.py)
├── setup-deps.bat                   ← Windows: install all dependencies
├── setup-deps.sh                    ← Linux/Mac: install all dependencies
├── requirements.txt                 ← Python dependencies for the platform
├── .env                             ← Environment configuration (API keys, ports)
├── .env.example                     ← Template for .env on fresh installs
│
├── API/
│   └── server.py                    ← FastAPI gateway (UI + all /api/* endpoints)
│
├── UI/
│   └── dist/                        ← Built React frontend (served by API/server.py)
│
├── WebUIGenerator/
│   ├── agents/
│   │   ├── uigen_agent.py           ← Project lifecycle + self-heal
│   │   ├── orchestrator.py          ← Parallel page generation
│   │   ├── prompts.py              ← LLM prompt templates (charts, maps)
│   │   ├── postprocessors.py       ← Code safety-net fixes
│   │   ├── qa_agent.py             ← Playwright-based QA testing
│   │   ├── llm.py                  ← LLM client (LiteLLM/Bedrock)
│   │   ├── figma_to_web_using_api_agent.py
│   │   ├── figma_to_web_using_playwright_agent.py
│   │   ├── shared-nm-package.json  ← npm deps (version-controlled)
│   │   ├── ux_architect/           ← UX Architect agent
│   │   ├── data_architect/         ← Data Architect agent
│   │   ├── visual_design/          ← Visual Design agent
│   │   ├── services_engineer/      ← Services Engineer (templates/)
│   │   └── ai_genai/              ← AI/GenAI agent (DataChat)
│   ├── cli/
│   │   ├── client.py              ← CLI interface
│   │   └── dockerize.py           ← Docker packaging
│   ├── instructions/               ← Domain-specific instruction files
│   ├── config.py                   ← Paths, ports, registry
│   └── generated/
│       ├── projects-web-apps.json  ← Project registry
│       ├── .ports.json             ← Port assignments
│       └── web-apps/              ← Generated projects
│
├── FigmaMockupGenerator/
│   ├── figma/
│   │   ├── mcp/
│   │   │   ├── server.py          ← MCP server (19 Figma tools)
│   │   │   ├── relay.py           ← MCP ↔ Figma Desktop bridge
│   │   │   └── start.bat          ← Starts MCP + relay
│   │   └── wireframe/
│   │       ├── prompt_to_figma_agent.py
│   │       └── webapp_to_figma_agent.py
│   └── generated/figma-mockups/
│
├── UIDesignSystem/
│   ├── src/
│   │   ├── tokens.ts              ← Brand design tokens
│   │   ├── index.ts               ← Barrel export
│   │   ├── components/            ← 18 React components
│   │   └── stories/               ← Storybook compositions
│   └── package.json
│
└── documentation/
```

### API Endpoints

| Method | Path | Module | Purpose |
|---|---|---|---|
| POST | `/api/generate` | WebUIGenerator | Generate app (prompt or Figma URL) |
| POST | `/api/refine/{name}` | WebUIGenerator | Refine existing project |
| POST | `/api/draft` | WebUIGenerator | Preview architecture |
| GET | `/api/projects` | WebUIGenerator | List all projects |
| POST | `/api/projects/create` | WebUIGenerator | Create project |
| DELETE | `/api/projects/{name}` | WebUIGenerator | Delete project |
| POST | `/api/projects/{name}/start` | WebUIGenerator | Start dev server |
| POST | `/api/projects/{name}/stop` | WebUIGenerator | Stop dev server |
| GET | `/api/projects/{name}/history` | WebUIGenerator | Build history |
| GET | `/api/projects/{name}/files` | WebUIGenerator | List files |
| POST | `/api/figma/wireframe` | FigmaMockupGenerator | Build wireframe |
| POST | `/api/figma/projects/create` | FigmaMockupGenerator | Create project |
| GET | `/api/figma/projects` | FigmaMockupGenerator | List projects |
| POST | `/api/figma/webapp-to-figma` | FigmaMockupGenerator | Import app → Figma |
| GET | `/api/figma/mcp/status` | FigmaMockupGenerator | MCP health |
| ALL | `/app/{project}/*` | Proxy | Route to Vite dev server |

[↑ Navigation](#nav) · [↑ Technical](#technical)

---

<div id="tech-figmamockup"></div>

## FigmaMockupGenerator — Technical

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                FigmaMockupGenerator — Technical Architecture                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   CONNECTION CHAIN (5 hops — all must be running)                                │
│                                                                                  │
│   ┌──────────────────┐                                                          │
│   │  TurboUIGen UI    │  POST /api/figma/wireframe                              │
│   │  (localhost:3000) │                                                          │
│   └────────┬─────────┘                                                          │
│            │                                                                     │
│            ▼                                                                     │
│   ┌──────────────────┐                                                          │
│   │  API/server.py    │  Routes to wireframe_agent.run_agent()                  │
│   │  (FastAPI)        │                                                          │
│   └────────┬─────────┘                                                          │
│            │  Agentic loop (up to 60 LLM turns)                                 │
│            ▼                                                                     │
│   ┌──────────────────┐                                                          │
│   │  MCP Server       │  Python — port 7771                                     │
│   │  (server.py)      │  Exposes 19 Figma tools to the LLM                     │
│   │                   │  WebSocket endpoint: ws://localhost:7771/relay           │
│   └────────┬─────────┘                                                          │
│            │  WebSocket messages                                                  │
│            ▼                                                                     │
│   ┌──────────────────┐                                                          │
│   │  relay.py         │  Bridges WebSocket ↔ stdio (JSON-RPC)                   │
│   │  (Python)         │  Spawns figma-console-mcp as child process              │
│   │                   │  Auto-patches plugin manifest on startup                │
│   └────────┬─────────┘                                                          │
│            │  stdio (JSON-RPC)                                                    │
│            ▼                                                                     │
│   ┌──────────────────┐                                                          │
│   │  figma-console-   │  Node.js npm package                                    │
│   │  mcp              │  Connects to Figma Desktop on port 9223                 │
│   └────────┬─────────┘                                                          │
│            │  WebSocket port 9223                                                 │
│            ▼                                                                     │
│   ┌──────────────────┐                                                          │
│   │  Figma Desktop    │  Bridge Plugin (loaded from manifest.json)              │
│   │  Bridge Plugin    │  Listens on WebSocket, executes Figma Plugin API        │
│   └────────┬─────────┘                                                          │
│            │  Figma Plugin API                                                    │
│            ▼                                                                     │
│   ┌──────────────────┐                                                          │
│   │  Figma Canvas     │  Wireframe appears here in real-time                    │
│   └──────────────────┘                                                          │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   LLM AGENT LOOP                                                                 │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │                                                                         │    │
│   │  Claude receives: prompt + system instructions + 19 tool definitions    │    │
│   │       │                                                                 │    │
│   │       ├── Turn 1: figma_get_status → check connection                  │    │
│   │       ├── Turn 2: figma_create_frame "Dashboard" 1440x900              │    │
│   │       ├── Turn 3: figma_create_auto_layout_frame (sidebar)             │    │
│   │       ├── Turn 4-N: create components, text, buttons, cards...         │    │
│   │       ├── Turn N+1: figma_wire_all (set up all navigation)             │    │
│   │       ├── Turn N+2: figma_set_prototype_start "Dashboard"              │    │
│   │       └── Turn N+3: figma_audit_frame (verify wiring complete)         │    │
│   │                                                                         │    │
│   │  Max 60 turns per wireframe generation                                  │    │
│   │                                                                         │    │
│   └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Client-Side Requirements — Detailed

| Requirement | Why | How to verify |
|---|---|---|
| **Figma Desktop app** | Bridge plugin uses desktop-only WebSocket API | `figma --version` or check Applications folder |
| **Bridge plugin installed** | Receives MCP commands, draws on canvas | Figma → Plugins → Development → should list "Figma Desktop Bridge" |
| **Node.js 18+** | Runs `figma-console-mcp` (WebSocket bridge) | `node --version` |
| **Python 3.11+** | Runs MCP server + relay | `python --version` |
| **Ports 7771 + 9223 free** | MCP server (7771), Figma bridge (9223) | `netstat -an | grep 7771` |
| **Open Figma file** | Plugin draws into active file's current page | Have any file open in Figma Desktop |
| **Network: localhost only** | All communication is local (no internet needed for wireframing) | Works offline once running |

### Setup (one-time)

```bash
# 1. Install Bridge plugin in Figma Desktop:
#    Figma → Main menu → Plugins → Development → Import plugin from manifest
#    Navigate to: FigmaMockupGenerator/figma/mcp/plugin/manifest.json

# 2. Install Node.js deps for the bridge:
cd FigmaMockupGenerator/figma/mcp
npm install

# 3. Verify: both steps are also checked by setup-deps.bat/sh
```

### Running Order (Critical)

```
1. Start MCP:     FigmaMockupGenerator/figma/mcp/start.bat  (keep terminal open)
2. Open plugin:   Figma → Plugins → Development → Figma Desktop Bridge → Run
3. Wait:          Plugin shows "Local Ready"
4. Use UI:        http://localhost:3000 → Figma Mockup tab → verify green status
```

**If done out of order:** Plugin shows "Connecting..." forever. Fix: close plugin, restart `start.bat`, re-open plugin.

### MCP Tools (19 total)

| Tool | Purpose |
|---|---|
| `figma_get_status` | Check connection, return frame list |
| `figma_list_frames` | List all frames with sizes/positions |
| `figma_create_frame` | Create a screen container |
| `figma_create_rectangle` | Create decorative rectangle |
| `figma_create_text` | Create text node |
| `figma_create_button` | Create clickable FRAME (not rectangle) |
| `figma_create_auto_layout_frame` | Create flex container |
| `figma_create_ellipse` | Create circle/avatar |
| `figma_set_stroke` | Add border to node |
| `figma_set_prototype_link` | Wire ON_CLICK → navigate |
| `figma_add_overlay_link` | Wire ON_CLICK → show overlay |
| `figma_set_active_tab_style` | Highlight active nav tab |
| `figma_set_scrollable` | Make frame scrollable |
| `figma_set_prototype_start` | Set first screen |
| `figma_wire_all` | Wire ALL interactions in one call |
| `figma_audit_frame` | Report unwired elements |
| `figma_inspect_reactions` | Show reactions on nodes |
| `figma_delete_frame` | Delete frame by name |
| `figma_execute_js` | Run arbitrary Figma Plugin API JS |

### Node Naming Convention

```
Nav tabs:     tab-{TargetScreen}-on-{ParentScreen}
Action btns:  {action}-btn-{Screen}
Content:      {role}-{Screen}
Overlays:     {name}-modal  or  {name}-drawer
```

### Plugin Manifest Requirement

The Bridge plugin's manifest must have:
```json
"documentAccess": "dynamic-page-requires-explicit-load"
```
This is patched automatically by `relay.py` on startup.

### Key Files

| File | Purpose |
|---|---|
| `figma/mcp/server.py` | MCP server — 19 Figma tools, port 7771 |
| `figma/mcp/relay.py` | WebSocket ↔ stdio bridge, auto-patches manifest |
| `figma/mcp/start.bat` | Starts server + relay together |
| `figma/wireframe/prompt_to_figma_agent.py` | LLM agentic loop (prompt → wireframe) |
| `figma/wireframe/webapp_to_figma_agent.py` | Import existing web app → Figma wireframe |

[↑ Navigation](#nav) · [↑ Technical](#technical)

---

<div id="tech-webuigen"></div>

## WebUIGenerator — Technical

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    WebUIGenerator — Technical Architecture                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  INPUT ROUTING                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐      │
│  │  Text Prompt ──→ _augment_prompt() ──→ Multi-Agent Pipeline           │      │
│  │                                                                        │      │
│  │  Figma URL:                                                            │      │
│  │  ├── /design/ or /file/ ──→ figma_to_web_using_api_agent.py           │      │
│  │  │       REST API → frames + wiring → LLM vision → requirements doc   │      │
│  │  └── /make/ or /proto/ ──→ figma_to_web_using_playwright_agent.py     │      │
│  │          Browser screenshots → LLM vision → requirements doc           │      │
│  │                                         │                              │      │
│  │                                         ▼                              │      │
│  │                              Multi-Agent Pipeline                       │      │
│  └───────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  MULTI-AGENT PIPELINE (6 agents)                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐      │
│  │                                                                        │      │
│  │  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐       │      │
│  │  │ 1. UX        │    │ 2. Data       │    │ 3. Visual Design │       │      │
│  │  │ Architect    │───▶│ Architect     │───▶│ Agent            │       │      │
│  │  │              │    │               │    │                  │       │      │
│  │  │ Pages, nav,  │    │ schema.sql,   │    │ Tailwind theme,  │       │      │
│  │  │ layout       │    │ seed.sql,     │    │ color palette    │       │      │
│  │  │              │    │ relationships │    │                  │       │      │
│  │  └──────────────┘    └───────────────┘    └──────────────────┘       │      │
│  │         │                    │                      │                  │      │
│  │         ▼                    ▼                      ▼                  │      │
│  │  ┌──────────────────────────────────────────────────────────────┐    │      │
│  │  │ 4. Orchestrator (ThreadPoolExecutor — parallel page gen)      │    │      │
│  │  │    Uses prompts.py templates for charts, maps, tables, forms  │    │      │
│  │  └──────────────────────────────────┬───────────────────────────┘    │      │
│  │                                     │                                 │      │
│  │         ┌───────────────────────────┼───────────────────┐            │      │
│  │         ▼                           ▼                   ▼            │      │
│  │  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐       │      │
│  │  │ 5. Services  │    │ 6. AI/GenAI      │    │ Postproc.    │       │      │
│  │  │ Engineer     │    │ (if DataChat)    │    │              │       │      │
│  │  │              │    │                  │    │ _fix_d3      │       │      │
│  │  │ app_server,  │    │ DataChat.tsx,    │    │ _fix_props   │       │      │
│  │  │ useApi.ts,   │    │ chat_api.py,     │    │ _fix_imports │       │      │
│  │  │ vite.config  │    │ system prompts   │    │ _fix_maps    │       │      │
│  │  └──────────────┘    └──────────────────┘    └──────────────┘       │      │
│  │                                                                        │      │
│  └───────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  SELF-HEAL PIPELINE                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐      │
│  │                                                                        │      │
│  │  ┌────────────────┐         ┌─────────────────┐    ┌──────────────┐  │      │
│  │  │ _tsc_heal      │────────▶│ QA Agent        │───▶│ _qa_heal     │  │      │
│  │  │ (3 rounds max) │         │ (Playwright)    │    │ (2 rounds)   │  │      │
│  │  │                │         │                 │    │              │  │      │
│  │  │ tsc --noEmit   │         │ Launch Chromium │    │ Group errors │  │      │
│  │  │ Parse errors   │         │ Visit each route│    │ by page file │  │      │
│  │  │ LLM fix each   │         │ Capture console │    │ LLM fix each │  │      │
│  │  │ file, re-check │         │ errors + Vite   │    │ Re-run QA    │  │      │
│  │  │                │         │ overlay detect  │    │              │  │      │
│  │  └────────────────┘         └─────────────────┘    └──────────────┘  │      │
│  │                                                                        │      │
│  └───────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  OUTPUT STRUCTURE                                                                │
│  ┌───────────────────────────────────────────────────────────────────────┐      │
│  │  web-apps/<project>/                                                   │      │
│  │  ├── src/ (App.tsx, pages/*.tsx, hooks/useApi.ts, components/)         │      │
│  │  ├── api/ (app_server.py, schema.sql, seed.sql)                       │      │
│  │  ├── node_modules → $TURBOUI_JUNCTION_DIR/shared-nm/node_modules      │      │
│  │  ├── package.json, vite.config.ts, tsconfig.json, tailwind.config.js  │      │
│  │  └── .meta.json, .history.json, .buildlog.json                        │      │
│  └───────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Internal Lifecycle — Step by Step

When a user clicks "Generate", here is exactly what happens:

| Step | Action | Output |
|---|---|---|
| 1 | `POST /api/generate` received by `API/server.py` | Routes to `uigen_agent.generate_project()` |
| 2 | Create project directory | `web-apps/<name>/`, `src/`, `api/` |
| 3 | Create `node_modules` junction | Points to `$TURBOUI_JUNCTION_DIR/shared-nm/node_modules` |
| 4 | Agent 1: UX Architect | `{ pages: [...], navigation, layout }` |
| 5 | Agent 2: Data Architect | `api/schema.sql`, `api/seed.sql` |
| 6 | Agent 3: Visual Design | `tailwind.config.js` theme values |
| 7 | Agent 4: Orchestrator (parallel) | All `src/pages/*.tsx` files |
| 8 | Agent 5: Services Engineer | `App.tsx`, `useApi.ts`, `app_server.py`, `vite.config.ts`, `package.json` |
| 9 | Agent 6: AI/GenAI (if needed) | `DataChat.tsx`, `datachat_api_server.py` |
| 10 | Postprocessors run | Fix D3, imports, props, maps |
| 11 | `_tsc_heal` (up to 3 rounds) | Fix TypeScript compilation errors |
| 12 | Start Vite dev server | Next available port from `TURBOUI_REACT_PORT_START` |
| 13 | Start API server | `python app_server.py` → SQLite DB from schema + seed |
| 14 | QA Agent (Playwright) | Navigate all routes, capture errors |
| 15 | `_qa_heal` (up to 2 rounds) | Fix runtime errors, re-run QA |
| 16 | Done | App live at assigned port, proxied at `/app/<name>` |

### Shared npm Modules — How the Junction Works

**Problem:** Each React app needs `node_modules` (~300MB). Installing per-app wastes disk and time.

**Solution:** One shared `node_modules`, linked via filesystem junction/symlink.

```
$TURBOUI_JUNCTION_DIR/shared-nm/
├── package.json           ← Master list of all npm deps
├── package-lock.json      ← Locked versions
└── node_modules/          ← ONE real copy (~300MB)
    ├── react/
    ├── d3/
    ├── vite/
    ├── typescript/
    ├── tailwindcss/
    └── ... (all shared packages)

web-apps/my-project/
├── node_modules → $TURBOUI_JUNCTION_DIR/shared-nm/node_modules  ← JUNCTION
├── package.json           ← Same deps listed (for IDE resolution)
└── src/...
```

**How it's created:**
1. `setup-deps` copies `WebUIGenerator/agents/shared-nm-package.json` → `$TURBOUI_JUNCTION_DIR/shared-nm/package.json`
2. Runs `npm install` in that directory → creates `node_modules`
3. When `generate_project()` creates a new app, it creates a junction:
   - Windows: `mklink /J "web-apps/my-project/node_modules" "$TURBOUI_JUNCTION_DIR/shared-nm/node_modules"`
   - Linux: `ln -s "$TURBOUI_JUNCTION_DIR/shared-nm/node_modules" "web-apps/my-project/node_modules"`

**Why `TURBOUI_JUNCTION_DIR` is needed:**
- OneDrive paths contain spaces (`OneDrive - S&P Global`) which break npm
- The junction target must be a clean path without special characters
- Multiple TurboUIGen installs can share one set of modules

**Adding new packages:**
1. Edit `WebUIGenerator/agents/shared-nm-package.json`
2. Re-run `setup-deps.bat` or `setup-deps.sh`
3. All future generated apps get the new package automatically

### D3 Chart Rendering Pattern

All charts follow this exact pattern to prevent the "blank chart" bug:

```typescript
import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

export default function MyChart({ data }: { data: any[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const measure = () => {
      const w = el.clientWidth
      if (w > 0) setContainerWidth(w)
    }
    measure()  // CRITICAL: call immediately before RO
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!containerWidth || !data.length) return
    const svg = d3.select(containerRef.current).select('svg')
    // ... D3 rendering logic ...
  }, [data, containerWidth])

  return (
    <div ref={containerRef} style={{ minHeight: 300, width: '100%' }}>
      <svg width={containerWidth} height={300} />
    </div>
  )
}
```

**Rules enforced across all agents:**
1. `useRef` on container `<div>` (NOT `<svg>`)
2. Container div has `minHeight`
3. Call `measure()` immediately BEFORE `ro.observe()`
4. NEVER use `ref.current?.parentElement`
5. NEVER rely on ResizeObserver alone for initial render

Enforced in: `prompts.py`, `postprocessors.py` (`_fix_d3_resize_observer`), `uigen_agent.py` (`_augment_prompt` + `_qa_heal` system prompt).

### useApi Hook

Every generated app uses a resilient data-fetching hook:

```typescript
const { data, loading, error, refetch } = useApi<Employee[]>('employees')
```

Features: retry with backoff (2x on 500+), AbortController on unmount, pagination support, BASE_URL aware.

DataChat: 180s timeout, 3-attempt retry on 502/503/504, exponential backoff, client recreation on stale connections.

### Figma-to-Web — URL Routing

| URL pattern | Agent | Method |
|---|---|---|
| `figma.com/design/...` | API agent | REST API (frames + wiring extraction) |
| `figma.com/file/...` | API agent | REST API (same as design) |
| `figma.com/make/...` | Playwright agent | Browser screenshots |
| `figma.com/proto/...` | Playwright agent | Browser screenshots |
| Any + 403 error | Playwright agent | Automatic fallback |

**REST API path:** Parse URL → GET frames → GET images → GET wiring → LLM vision → requirements → pipeline

**Playwright path:** Launch Edge (copies logged-in profile) → navigate → multi-strategy screenshot capture (arrows, clicks, scroll) → MD5 dedup → LLM vision → requirements → pipeline

**Client-side prerequisites:**

| Requirement | For REST API path | For Playwright path |
|---|---|---|
| `FIGMA_ACCESS_TOKEN` in .env | Required | Not needed |
| Playwright + Chromium | Not needed | Required |
| Edge browser with Figma login | Not needed | Required |
| Network access to figma.com | Required | Required |

Both paths always delegate to `uigen_agent.generate_project()` → full React app.

### Key Files

| File | Purpose |
|---|---|
| `agents/uigen_agent.py` | Project lifecycle, `generate_project()`, `_tsc_heal`, `_qa_heal` |
| `agents/orchestrator.py` | Parallel page generation via ThreadPoolExecutor |
| `agents/prompts.py` | All LLM prompt templates (15+ chart patterns) |
| `agents/postprocessors.py` | Code fixers (D3, props, imports, maps) |
| `agents/qa_agent.py` | Playwright browser testing |
| `agents/llm.py` | LLM client (retry, SSL, token tracking) |
| `agents/figma_to_web_using_api_agent.py` | Figma REST API → React |
| `agents/figma_to_web_using_playwright_agent.py` | Browser screenshots → React |
| `agents/shared-nm-package.json` | npm deps for generated apps |
| `agents/services_engineer/templates/` | Template files (useApi, vite config, etc.) |
| `agents/ai_genai/templates/` | DataChat templates |
| `config.py` | Paths, ports, registry file locations |
| `instructions/` | Domain instruction files (automotive, finserv, etc.) |

[↑ Navigation](#nav) · [↑ Technical](#technical)

---

<div id="tech-designsystem"></div>

## UIDesignSystem — Technical

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    UIDesignSystem — Technical Architecture                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   SOURCE (version-controlled)                                                    │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │  TurboUIGen/UIDesignSystem/                                             │    │
│   │  ├── src/                                                               │    │
│   │  │   ├── tokens.ts          ← Brand design tokens (colors, spacing)    │    │
│   │  │   ├── index.ts           ← Barrel export (all components)           │    │
│   │  │   ├── components/                                                    │    │
│   │  │   │   ├── Header.tsx                                                 │    │
│   │  │   │   ├── Sidebar.tsx                                                │    │
│   │  │   │   ├── KpiCard.tsx                                                │    │
│   │  │   │   ├── DataTable.tsx                                              │    │
│   │  │   │   ├── Modal.tsx                                                  │    │
│   │  │   │   └── ... (18 total)                                             │    │
│   │  │   └── stories/           ← Storybook compositions                   │    │
│   │  └── package.json                                                       │    │
│   └────────────────────────────────────────────────────────────────────────┘    │
│         │                                                                        │
│         │ setup-deps copies to junction dir                                      │
│         ▼                                                                        │
│   RUNTIME COPY (outside OneDrive, clean path)                                    │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │  $TURBOUI_JUNCTION_DIR/mgds/                                            │    │
│   │  ├── src/index.ts           ← Same content, clean file path            │    │
│   │  ├── brand_tokens.json      ← JSON export of tokens for LLM agents    │    │
│   │  └── package.json                                                       │    │
│   └────────────────────────────────────────────────────────────────────────┘    │
│         │                                                                        │
│         │ Generated apps import from here (via tsconfig paths)                   │
│         ▼                                                                        │
│   GENERATED APPS                                                                 │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │  web-apps/<project>/src/pages/Dashboard.tsx:                            │    │
│   │                                                                         │    │
│   │  import { Header, Sidebar, KpiCard } from '@mobility-global/ds'        │    │
│   │  import { tokens } from '@mobility-global/ds/tokens'                    │    │
│   │                                                                         │    │
│   │  tsconfig.json paths:                                                   │    │
│   │  "@mobility-global/ds": ["$TURBOUI_JUNCTION_DIR/mgds/src/index.ts"]    │    │
│   │  "@mobility-global/ds/*": ["$TURBOUI_JUNCTION_DIR/mgds/src/*"]         │    │
│   └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│   LLM AGENT INTEGRATION                                                          │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │  Visual Design Agent reads brand_tokens.json → informs color choices    │    │
│   │  Orchestrator's prompts.py includes component import snippets           │    │
│   │  Services Engineer templates wire tsconfig paths to junction dir        │    │
│   └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│   STORYBOOK (local development)                                                  │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │  cd UIDesignSystem && npm run storybook → http://localhost:6006         │    │
│   │  Shows all 18 components with interactive props + compositions          │    │
│   └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### How the Design System Reaches Generated Apps

1. **Setup phase:** `setup-deps` copies `UIDesignSystem/` → `$TURBOUI_JUNCTION_DIR/mgds/`
2. **Generation phase:** Services Engineer writes `tsconfig.json` with path aliases pointing to `mgds/`
3. **Code generation:** Orchestrator's prompts include `import { Header, KpiCard } from '@mobility-global/ds'`
4. **Runtime:** Vite resolves these imports via tsconfig paths → direct source imports (no build step needed)

### Design Tokens

```typescript
// UIDesignSystem/src/tokens.ts
export const tokens = {
  colors: {
    primary: { 50: '#eff6ff', 100: '#dbeafe', ..., 900: '#1e3a5f' },
    secondary: { ... },
    accent: { ... },
    semantic: { success: '#10b981', warning: '#f59e0b', error: '#ef4444', info: '#3b82f6' }
  },
  spacing: { xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px' },
  typography: { fontFamily: '...', sizes: { xs: '0.75rem', ... } },
  shadows: { sm: '...', md: '...', lg: '...' },
  radii: { sm: '4px', md: '8px', lg: '12px', full: '9999px' }
}
```

### Key Files

| File | Purpose |
|---|---|
| `src/tokens.ts` | Brand design tokens (colors, spacing, typography, shadows) |
| `src/index.ts` | Barrel export — all components |
| `src/components/*.tsx` | 18 React components |
| `src/stories/*.stories.tsx` | Storybook stories |
| `package.json` | Package definition + Storybook scripts |

[↑ Navigation](#nav) · [↑ Technical](#technical)

---

<div id="tech-setup"></div>

## Setup & Configuration

### Fresh Machine Install

#### Prerequisites

| Software | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend, agents, API servers |
| Node.js | 18+ | Vite dev servers, npm packages |
| npm | 9+ | Package management (comes with Node.js) |

#### Step-by-step

```bash
# 1. Copy/clone the TurboUIGen folder to the new machine

# 2. Create .env from template
cp .env.example .env
# Edit .env — fill in at minimum:
#   LITELLM_API_BASE=https://your-litellm-proxy.example.com
#   LITELLM_API_KEY=sk-your-key
#   TURBOUI_JUNCTION_DIR=/home/youruser/.turboui-junctions  (Linux)
#   TURBOUI_JUNCTION_DIR=C:/Users/youruser/.turboui-junctions  (Windows)

# 3. Run the setup script (installs everything)
# Windows:
setup-deps.bat

# Linux/Mac:
bash setup-deps.sh

# 4. Start TurboUIGen
# Windows:
start.bat

# Linux/Mac:
python3 run.py
```

#### What `setup-deps` Does (5 steps)

| Step | Action | Location |
|---|---|---|
| 0 | Check prerequisites (Python, Node.js, npm) | — |
| 1 | Check/create `.env` from `.env.example` | TurboUIGen root |
| 2 | `pip install -r requirements.txt` | Active Python environment |
| 3 | `playwright install chromium` | Playwright browser cache |
| 4 | Copy `shared-nm-package.json` → `npm install` | `$TURBOUI_JUNCTION_DIR/shared-nm/` |
| 5 | Copy UIDesignSystem → junction dir | `$TURBOUI_JUNCTION_DIR/mgds/` |

### .env Configuration

The `.env` file lives at the TurboUIGen root.

#### Required Variables

| Variable | Purpose | Example |
|---|---|---|
| `LITELLM_API_BASE` | LiteLLM proxy URL (primary LLM backend) | `https://lit-main-qa.example.com` |
| `LITELLM_API_KEY` | API key for LiteLLM proxy | `sk-...` |
| `TURBOUI_JUNCTION_DIR` | Shared npm modules + design system location | `C:/Users/you/.turboui-junctions` |

#### Optional Variables

| Variable | Purpose | Default |
|---|---|---|
| `LITELLM_SSL_CERT` | PEM cert for proxy (\\n-escaped) | (system CA) |
| `LITELLM_TIMEOUT` | LLM call timeout seconds | `120` |
| `LITELLM_HAIKU_MODEL` | Fast model for simple tasks | `claude-haiku-4-5` |
| `FIGMA_ACCESS_TOKEN` | Figma personal access token | (Figma-to-web disabled) |
| `TURBOUI_HOST` | Server hostname | `localhost` |
| `TURBOUI_PORT` | Main server port | `3000` |
| `TURBOUI_MCP_HOST` | Figma MCP server host | `localhost` |
| `TURBOUI_MCP_PORT` | Figma MCP server port | `7771` |
| `TURBOUI_REACT_PORT_START` | First port for generated apps | `5173` |
| `DESIGN_SYSTEM_PATH` | Custom design system path | (bundled MGDS) |
| `AWS_REGION` | AWS region (Bedrock alternative) | `us-east-1` |
| `CLAUDE_MODEL_ID` | Bedrock model ARN | (none) |

#### Why .env Matters

The `.env` file is the single source of truth for:
- **LLM access** — without `LITELLM_API_BASE` + `LITELLM_API_KEY`, nothing generates
- **File paths** — `TURBOUI_JUNCTION_DIR` determines where shared packages live
- **Figma access** — `FIGMA_ACCESS_TOKEN` enables Figma-to-web from design/file URLs
- **Port allocation** — controls where TurboUIGen and generated apps listen
- **SSL/Network** — corporate environments need `LITELLM_SSL_CERT` for proxy certs

If `.env` is missing or misconfigured, you get: `ModuleNotFoundError`, connection timeouts, 403 from Figma API, or blank junction directories.

[↑ Navigation](#nav) · [↑ Technical](#technical)

---

<div id="tech-troubleshooting"></div>

## Troubleshooting

### Setup Issues

| Symptom | Fix |
|---|---|
| `pip install` fails | Ensure Python 3.11+ is on PATH. Try `pip3` instead of `pip`. |
| `npm install` fails in junction dir | Check Node.js 18+ installed. Verify `TURBOUI_JUNCTION_DIR` path exists and is writable. |
| `playwright install chromium` fails | May need admin/sudo. Try: `python -m playwright install chromium` |
| `.env` not loading | File must be at TurboUIGen root (same folder as `run.py`). Check no BOM encoding. |
| `setup-deps` exits at step 1 | It created `.env` from example — edit it with your API keys, then re-run. |

### WebUIGenerator Issues

| Symptom | Fix |
|---|---|
| "ModuleNotFoundError: agents.uigen_agent" | Run from TurboUIGen root via `run.py` or `start.bat`. Never `cd API && python server.py`. |
| Port 3000 in use | Change `TURBOUI_PORT=3001` in `.env`, or kill the process on 3000. |
| LLM calls timing out | Increase `LITELLM_TIMEOUT=180` in `.env`. Check proxy is reachable. |
| SSL certificate errors | Set `LITELLM_SSL_CERT` in `.env` with org PEM cert (\\n-escaped). |
| Generated app shows blank charts | Self-heal should fix. If persists, postprocessor catches on next generate. |
| Generated app API server won't start | Check `pip install -r requirements.txt` was done. Check `api/.env` in the project. |
| `node_modules` missing in generated app | Junction broken — re-run `setup-deps`. Check `TURBOUI_JUNCTION_DIR` path exists. |
| TypeScript errors after generation | Self-heal ran 3 rounds max. Manually fix or re-generate with refined prompt. |

### FigmaMockupGenerator Issues

| Symptom | Fix |
|---|---|
| "Relay not connected" | Run `start.bat` in `FigmaMockupGenerator/figma/mcp/`. Then open Bridge plugin. |
| Plugin shows "Connecting..." forever | Wrong order — close plugin, restart `start.bat`, re-open plugin. |
| MCP shows "0 tools" | Restart `start.bat`. Tool enumeration runs on startup. |
| Wireframe not appearing in Figma | Check you have a file open. Check plugin shows "Local Ready". |
| "Tool call failed" in build log | One hop in the chain died. Restart `start.bat` + re-open plugin. |

### Figma-to-Web Issues

| Symptom | Fix |
|---|---|
| "FIGMA_ACCESS_TOKEN not set" | Add token to `.env`. Get: Figma → Account Settings → Personal Access Tokens. |
| Figma URL gives 403 | Token lacks permissions, or file is private. Pipeline auto-falls back to Playwright. |
| Playwright path fails | Ensure `playwright install chromium` was run. Need Edge/Chrome with Figma login. |
| Screenshots are blank/wrong | Figma file may use features that render differently. Try REST API path (design/ URL). |

### Design System Issues

| Symptom | Fix |
|---|---|
| Storybook won't start | `cd UIDesignSystem && npm install && npm run storybook` |
| Port 6006 in use | `npm run storybook -- --port 6007` |
| Components not found in generated apps | Verify `$TURBOUI_JUNCTION_DIR/mgds/` exists with `src/index.ts` |
| Import errors for @mobility-global/ds | Check tsconfig.json paths in generated app point to correct junction dir |

[↑ Navigation](#nav) · [↑ Technical](#technical)

---

## Quick Reference

| Action | Command |
|---|---|
| **First-time setup** | `setup-deps.bat` (Windows) or `bash setup-deps.sh` (Linux/Mac) |
| **Start TurboUIGen** | `start.bat` or `python run.py` |
| **Open UI** | `http://localhost:3000` |
| **Start Figma MCP** | `FigmaMockupGenerator\figma\mcp\start.bat` |
| **Start Storybook** | `cd UIDesignSystem && npm run storybook` |
| **CLI generate** | `python -m cli.client generate "prompt"` |
| **CLI from Figma** | `python -m cli.client generate --figma "url"` |
| **Docker package** | `python cli/dockerize.py <project-name>` |
| **Generated apps** | `WebUIGenerator/generated/web-apps/` |
| **Figma mockups** | `FigmaMockupGenerator/generated/figma-mockups/` |
| **Environment config** | `.env` at TurboUIGen root |
| **Python deps** | `requirements.txt` at TurboUIGen root |
| **npm shared deps** | `$TURBOUI_JUNCTION_DIR/shared-nm/package.json` |
| **Design tokens** | `UIDesignSystem/src/tokens.ts` |

[↑ Navigation](#nav) · [↑ Technical](#technical)
