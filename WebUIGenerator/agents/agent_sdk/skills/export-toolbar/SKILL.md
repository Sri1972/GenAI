---
name: export-toolbar
description: The shared ExportToolbar React component used by data pages to offer CSV/Excel/PDF exports. Use when a page (data table, dashboard) needs a consistent export toolbar.
---

# export-toolbar

The `ExportToolbar` component is a shared, TurboUIGen-managed export UI. It is already
bundled into every generated app at `src/components/ExportToolbar.tsx` (Python seeds it) —
**import it, do not re-create it**: `import ExportToolbar from '../components/ExportToolbar'`.

Reference source: `references/ExportToolbar.component.tsx` (for prop shapes only).
