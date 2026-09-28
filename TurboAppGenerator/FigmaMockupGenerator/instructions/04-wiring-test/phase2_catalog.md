# Wiring Test — Phase 2: Catalog

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if a stub screen with this name already exists on the canvas
- 🟢 **Add Screens** — if adding to an existing canvas without stubs (places new frames to the right)
**Canvas:** 1280×800 desktop

> **Prerequisite:** Run Phase 1 (`04_wiretest_phase1_home.md`) first. The Home screen must already exist on the canvas.

Add the Catalog screen. Then run `figma_wire_all` to complete all navigation wiring between Home and Catalog.

---

## Screen: Catalog

### Layout
- Same top nav bar (full width, white, 64px): logo "WireTest", nav links: Home, **Catalog** (active), Contact
- Page heading: "Item Catalog"

### Content sections (top → bottom)

**Filter bar**:
- Search: `search-btn-Catalog` (placeholder "Search catalog…")
- Dropdown: `dropdown-Type-on-Catalog` — options: All Types, Widget, Gadget, Tool, Component

**Item grid** — 2 columns × 3 rows (6 cards, each 360×160):
| # | Name | Type | Price |
|---|------|------|-------|
| 1 | Alpha Widget | Widget | $29 |
| 2 | Beta Gadget | Gadget | $49 |
| 3 | Gamma Tool | Tool | $19 |
| 4 | Delta Component | Component | $99 |
| 5 | Epsilon Widget | Widget | $39 |
| 6 | Zeta Gadget | Gadget | $59 |

Each card: name (bold), type tag, price, "View Details" button.

---

## Overlays to create

| Frame name | Size | Content |
|------------|------|---------|
| `catalog-search-results-modal` | 560×360 | Title "Search Results", 4 item rows (name, type, price), Close button |
| `catalog-type-filter-modal` | 180×200 | 5 option rows: All Types, Widget, Gadget, Tool, Component |
| `item-detail-modal` | 520×440 | Title "Alpha Widget", type badge, price, description text, "Add to Cart" button, Close button |

---

## Wiring

| Source element | Interaction | Destination |
|----------------|-------------|-------------|
| Nav link "Home" | Navigate | Home screen |
| `search-btn-Catalog` | Overlay | `catalog-search-results-modal` |
| `dropdown-Type-on-Catalog` | Overlay | `catalog-type-filter-modal` |
| "View Details" on card 1 (Alpha Widget) | Overlay | `item-detail-modal` |
| "View Details" on card 2 (Beta Gadget) | Overlay | `item-detail-modal` |

After building the screen and overlays, call `figma_wire_all` to connect all top-nav links between Home and Catalog in both directions.
