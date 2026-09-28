# Wiring Test — Phase 1: Home

**UI Mode:** 🟢 **Build Wireframe**
**Canvas:** 1280×800 desktop

> ⚠️ **STRICT PHASE SCOPE — build ONLY these 4 frames, nothing else:**
> - Screen: `Home`
> - Overlay: `home-search-results-modal`
> - Overlay: `home-category-dropdown-modal`
> - Overlay: `home-settings-modal`
>
> Do NOT create the Catalog screen. Nav links and tab items pointing to Catalog are **visual placeholders only** — leave them unwired. The QA pass must NOT flag those as errors or attempt to build the Catalog screen.

Build the first screen of a minimal 2-screen wiring smoke test. Keep visuals simple — this tests navigate, overlay, and back interactions.

**Theme:** Light minimal — bg `#f8fafc`, card `#ffffff`, accent `#6366f1`, text `#1e293b`.

---

## Screen: Home

### Layout
- Top nav bar (full width, white, 64px): logo text "WireTest" (left), nav links as buttons: Home, Catalog, Contact (right)
- Hero section (120px): heading "Wiring Test App", subheading "Test all interaction types"
- Centered content area (800px wide)

### Content sections (top → bottom)

**Tab bar** — 3 tabs:
- `tab-Overview-on-Home` — "Overview" (active/selected)
- `tab-Details-on-Home` — "Details"
- `tab-Settings-on-Home` — "Settings"

**Content card** (800×280) — heading "Overview Panel", body "This is the overview tab content. Use the controls below to test interactions."

**Action row** — 3 controls side by side:
| Control | Name | Type |
|---------|------|------|
| "Search Items" button | `search-btn-Home` | Search trigger |
| "Category" dropdown button | `dropdown-Category-on-Home` | Dropdown trigger |
| "Go to Catalog" primary button | — | Navigate |

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `home-search-results-modal` | 560×360 | Title "Search Results", 4 item rows (name, type, price), Close button |
| `home-category-dropdown-modal` | 180×220 | 5 option rows: All, Electronics, Books, Clothing, Tools |
| `home-settings-modal` | 600×400 | Title "Settings", 3 preference rows with toggle switches, Save + Close buttons |

---

## Wiring

After ALL four frames are built, call `figma_list_frame_nodes(frame_name="Home")` to confirm node names, then wire in a single call:

```
figma_wire_all(
  links=[
    {"source_frame": "Home", "source_node": "tab-Overview-on-Home",  "target_frame": "Home",                      "type": "NAVIGATE"},
    {"source_frame": "Home", "source_node": "tab-Settings-on-Home",  "target_frame": "home-settings-modal",        "type": "OVERLAY"},
    {"source_frame": "Home", "source_node": "search-btn-Home",        "target_frame": "home-search-results-modal",  "type": "OVERLAY"},
    {"source_frame": "Home", "source_node": "dropdown-Category-on-Home", "target_frame": "home-category-dropdown-modal", "type": "OVERLAY"},
  ],
  start_frame="Home"
)
```

**Do NOT** wire `tab-Details-on-Home`, the "Go to Catalog" button, or the "Catalog" nav link — that screen doesn't exist yet.

---

## Prototype start
Handled by `start_frame="Home"` in the `figma_wire_all` call above.

---

## Prototype start
Set **Home** as the prototype start frame.
