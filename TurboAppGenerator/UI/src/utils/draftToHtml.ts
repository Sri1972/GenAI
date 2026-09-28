import type { DraftResult } from '../hooks/useApi'

const PAGE_TYPE_ICONS: Record<string, string> = {
  'kpi-dashboard': 'KPI',
  'data-grid': 'DATA',
  'charts': 'CHART',
  'world-map': 'MAP',
  'usa-map': 'USA',
  'ai-chat': 'AI',
  'settings-form': 'SET',
  'custom': '•',
}

export function draftToHtml(draft: DraftResult): string {
  const { architecture, markdown, title, pageCount } = draft
  const pages = architecture?.pages || []
  const navigation = architecture?.navigation || []
  const dataEntities = architecture?.dataEntities || []
  const sharedComponents = architecture?.sharedComponents || []
  const hasAi = architecture?.hasAiFeatures || false
  const projectName = architecture?.projectName || draft.projectName || 'app'

  const navItems = navigation.map((nav: any) =>
    `<div class="nav-item"><span class="nav-icon">${nav.icon || '○'}</span><span>${nav.label || nav.page || '?'}</span></div>`
  ).join('\n')

  const pageCards = pages.map((page: any) => {
    const ptype = page.type || 'custom'
    const icon = PAGE_TYPE_ICONS[ptype] || '•'
    const desc = page.description || ''
    return `
      <div class="page-card">
        <div class="page-header">
          <span class="page-icon">${icon}</span>
          <div>
            <div class="page-name">${page.name || '?'}</div>
            <div class="page-type">${ptype}</div>
          </div>
        </div>
        <div class="page-desc">${desc}</div>
        <div class="page-wireframe">${getWireframeHtml(ptype)}</div>
      </div>`
  }).join('\n')

  const entityRows = dataEntities.map((e: string) =>
    `<tr><td class="cell-name">${e}</td><td class="cell-desc">Auto-generated from requirements</td><td class="cell-path">/api/data/${e}</td></tr>`
  ).join('\n')

  const compList = sharedComponents.map((c: string) =>
    `<span class="comp-chip">${c}</span>`
  ).join('\n')

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
:root {
  --bg: #0f172a;
  --bg-card: rgba(30,41,59,0.7);
  --border: rgba(148,163,184,0.12);
  --text: #f1f5f9;
  --text-sec: #94a3b8;
  --text-dim: #64748b;
  --blue: #60a5fa;
  --purple: #a78bfa;
  --green: #4ade80;
  --amber: #fbbf24;
  --cyan: #22d3ee;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 2rem; min-height: 100vh; }
.container { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 1.5rem; font-weight: 700; background: linear-gradient(135deg, var(--blue), var(--purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.25rem; }
.subtitle { color: var(--text-sec); font-size: 0.72rem; margin-bottom: 1.5rem; }
.meta-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 2rem; }
.chip { background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.25); border-radius: 9999px; padding: 0.28rem 0.7rem; font-size: 0.65rem; font-weight: 500; color: #a5b4fc; }
.section { background: var(--bg-card); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; margin-bottom: 1.5rem; backdrop-filter: blur(8px); }
.section-hdr { font-size: 0.82rem; font-weight: 600; color: var(--text); margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
.section-hdr .icon { font-size: 1rem; }

/* Navigation */
.nav-preview { display: flex; flex-direction: column; background: #1e293b; border-radius: 10px; border: 1px solid var(--border); padding: 0.8rem; max-width: 220px; }
.nav-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.6rem; border-radius: 6px; font-size: 0.7rem; color: var(--text-sec); transition: background 0.15s; }
.nav-item:hover { background: rgba(99,102,241,0.1); color: var(--text); }
.nav-icon { font-size: 0.8rem; width: 1.2rem; text-align: center; }

/* Pages */
.pages-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1.2rem; }
.page-card { background: rgba(15,23,42,0.6); border: 1px solid var(--border); border-radius: 12px; padding: 1.2rem; transition: border-color 0.2s; }
.page-card:hover { border-color: rgba(99,102,241,0.3); }
.page-header { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.6rem; }
.page-icon { font-size: 1.3rem; }
.page-name { font-weight: 600; font-size: 0.78rem; color: var(--text); }
.page-type { font-size: 0.6rem; color: var(--purple); font-family: monospace; font-weight: 500; }
.page-desc { font-size: 0.68rem; color: var(--text-sec); margin-bottom: 0.8rem; line-height: 1.5; }
.page-wireframe { background: #0f172a; border: 1px solid rgba(148,163,184,0.08); border-radius: 8px; padding: 0.8rem; font-family: 'JetBrains Mono', monospace; font-size: 0.55rem; line-height: 1.5; color: var(--text-dim); white-space: pre; overflow-x: auto; }
.page-wireframe .wf-border { color: rgba(148,163,184,0.35); }
.page-wireframe .wf-label { color: var(--text-sec); }
.page-wireframe .wf-accent { color: var(--blue); }

/* Data Model */
table { width: 100%; border-collapse: collapse; font-size: 0.7rem; }
th { text-align: left; padding: 0.5rem 0.6rem; background: rgba(99,102,241,0.08); color: var(--purple); font-weight: 600; font-size: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); }
td { padding: 0.45rem 0.6rem; border-bottom: 1px solid rgba(148,163,184,0.05); color: #cbd5e1; }
tr:hover td { background: rgba(99,102,241,0.04); }
.cell-name { font-weight: 600; color: var(--text); }
.cell-path { font-family: monospace; font-size: 0.62rem; color: var(--cyan); }
.cell-desc { color: var(--text-sec); }

/* Components */
.comp-list { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.comp-chip { background: rgba(99,102,241,0.12); color: #c4b5fd; padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.65rem; font-weight: 500; font-family: monospace; }

/* Actions */
.actions { display: flex; gap: 0.8rem; justify-content: center; margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }
.actions .note { font-size: 0.68rem; color: var(--text-dim); text-align: center; margin-top: 0.8rem; }
</style>
</head>
<body>
<div class="container">
  <h1>Draft: ${title}</h1>
  <p class="subtitle">Project: ${projectName} · ${pageCount} pages planned</p>

  <div class="meta-row">
    <span class="chip">${pageCount} Pages</span>
    <span class="chip">${dataEntities.length} Tables</span>
    <span class="chip">${sharedComponents.length} Components</span>
    ${hasAi ? '<span class="chip">AI Features</span>' : ''}
  </div>

  <!-- Navigation -->
  <div class="section">
    <div class="section-hdr"><span class="icon">•</span> Navigation</div>
    <div class="nav-preview">
      <div class="nav-item" style="font-weight:600;color:var(--text);margin-bottom:0.3rem"><span class="nav-icon">◆</span><span>${title}</span></div>
      ${navItems}
    </div>
  </div>

  <!-- Pages -->
  <div class="section">
    <div class="section-hdr"><span class="icon">•</span> Pages</div>
    <div class="pages-grid">
      ${pageCards}
    </div>
  </div>

  <!-- Data Model -->
  <div class="section">
    <div class="section-hdr"><span class="icon">•</span> Data Model</div>
    <table>
      <thead><tr><th>Table</th><th>Purpose</th><th>API Endpoint</th></tr></thead>
      <tbody>${entityRows}</tbody>
    </table>
    <p style="font-size:0.62rem;color:var(--text-dim);margin-top:0.8rem">All data served via REST API. Frontend uses useApi hook for data fetching.</p>
  </div>

  ${sharedComponents.length > 0 ? `
  <div class="section">
    <div class="section-hdr"><span class="icon">•</span> Shared Components</div>
    <div class="comp-list">${compList}</div>
  </div>` : ''}

  <div class="actions">
    <p class="note">Review this draft. If it looks good, click "Looks Good — Build It" above.<br/>To revise, describe changes and generate a new draft.</p>
  </div>
</div>
</body>
</html>`
}

function getWireframeHtml(ptype: string): string {
  const wireframes: Record<string, string> = {
    'kpi-dashboard': `<span class="wf-border">┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐</span>
<span class="wf-label">│  KPI 1  │ │  KPI 2  │ │  KPI 3  │ │  KPI 4  │</span>
<span class="wf-border">└─────────┘ └─────────┘ └─────────┘ └─────────┘</span>
<span class="wf-border">┌──────────────────────┐ ┌──────────────────────┐</span>
<span class="wf-label">│    Bar Chart         │ │    Donut Chart       │</span>
<span class="wf-border">└──────────────────────┘ └──────────────────────┘</span>
<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-label">│              Line Chart (full width)            │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`,
    'data-grid': `<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-accent">│ [Search...] [Filter ▼] [Filter ▼]   N rows      │</span>
<span class="wf-border">├────┬────────┬────────┬────────┬────────┬────────┤</span>
<span class="wf-label">│ #  │ Col A  │ Col B  │ Col C  │ Col D  │ Col E  │</span>
<span class="wf-border">├────┼────────┼────────┼────────┼────────┼────────┤</span>
<span class="wf-label">│ 1  │ data   │ data   │ data   │ data   │ data   │</span>
<span class="wf-label">│ .. │  ...   │  ...   │  ...   │  ...   │  ...   │</span>
<span class="wf-border">├────┴────────┴────────┴────────┴────────┴────────┤</span>
<span class="wf-accent">│            ◀ Page 1 of N ▶                      │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`,
    'charts': `<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-accent">│  [Tab 1] [Tab 2]                                │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-label">│         Multi-line / Area Chart                 │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-label">│         Grouped Bar / Stacked Chart             │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`,
    'world-map': `<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-accent">│ [Make ▼]  [Quarter ▼]                           │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-label">│          World Choropleth Map                   │</span>
<span class="wf-label">│          (colored by sales volume)              │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-label">│ Region │ Volume │ Revenue │ Top Make            │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`,
    'usa-map': `<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-accent">│ [Make ▼]                                        │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-label">│          USA Choropleth Map                     │</span>
<span class="wf-label">│          (colored by state volume)              │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-label">│ State │ Make │ Volume │ Revenue │ Growth        │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`,
    'ai-chat': `<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-label">│  How can I help you today?                      │</span>
<span class="wf-label">│  Show me sales by region                        │</span>
<span class="wf-label">│  Here's a breakdown...                          │</span>
<span class="wf-label">│     ┌──────────────────────┐                   │</span>
<span class="wf-label">│     │ (inline chart/table) │                   │</span>
<span class="wf-label">│     └──────────────────────┘                   │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-accent">│  [Type your message...              ] [Send]   │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`,
    'settings-form': `<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-label">│  Settings                                       │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-accent">│  Label:    [________________]                   │</span>
<span class="wf-accent">│  Option:   [Dropdown ▼     ]                   │</span>
<span class="wf-accent">│  Toggle:   [●━━] On                             │</span>
<span class="wf-border">├─────────────────────────────────────────────────┤</span>
<span class="wf-accent">│                          [Cancel] [Save]       │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`,
  }
  return wireframes[ptype] || `<span class="wf-border">┌─────────────────────────────────────────────────┐</span>
<span class="wf-label">│         (Custom page layout)                    │</span>
<span class="wf-border">└─────────────────────────────────────────────────┘</span>`
}
