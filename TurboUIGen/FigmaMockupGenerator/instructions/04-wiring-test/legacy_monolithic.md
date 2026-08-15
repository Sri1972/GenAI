Create a minimal 2-screen app to test all wiring types: navigate, overlay, and back navigation. Keep visuals simple — this is a wiring smoke test.

**Theme:** Light minimal — bg `#f8fafc`, card `#ffffff`, accent `#6366f1`, text `#1e293b`.
**Canvas size:** 1280×800 per screen.

---

## Screen 1 — Home

### Layout
- Centered content area (800px wide), vertically centred on canvas
- Top nav bar (full width, white, 64px tall): logo text "WireTest" (left), nav links: Home, Catalog, Contact (right, as buttons)
- Hero section below nav (120px tall): heading "Wiring Test App", subheading "Test all interaction types"

### Sections (top → bottom in content area)

**Tab bar** (below hero) — 3 tabs:
- `tab-Overview-on-Home` — label "Overview" (selected / active state)
- `tab-Details-on-Home` — label "Details"
- `tab-Settings-on-Home` — label "Settings"

**Content card** (below tabs, 800×280):
- Heading: "Overview Panel"
- Body text: "This is the overview tab content. Use the controls below to test interactions."

**Action row** (3 controls side by side):

| Control | Name | Type |
|---------|------|------|
| "Search Items" button | `search-btn-Home` | Search |
| "Category" dropdown | `dropdown-Category-on-Home` | Dropdown |
| "Go to Catalog" button | (primary button) | Navigate |

### Wiring
| Source element | Interaction | Destination | Notes |
|----------------|-------------|-------------|-------|
| `tab-Overview-on-Home` | Navigate | Home screen | Stays on same screen (active tab) |
| `tab-Details-on-Home` | Navigate | Catalog screen | Navigate between screens |
| `tab-Settings-on-Home` | Overlay | Settings overlay modal (600×400) | Inline overlay |
| `search-btn-Home` | Overlay | Search results modal (560×360) | Overlay with results list |
| `dropdown-Category-on-Home` | Overlay | Category dropdown modal (180×220) | Small dropdown overlay |
| "Go to Catalog" button | Navigate | Catalog screen | Full screen navigation |
| Nav link "Catalog" (top nav) | Navigate | Catalog screen | Top nav wiring |

---

## Screen 2 — Catalog

### Layout
- Same top nav bar: logo "WireTest", links Home, Catalog (active), Contact
- Page heading: "Item Catalog"

### Sections

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

### Wiring
| Source element | Interaction | Destination | Notes |
|----------------|-------------|-------------|-------|
| Nav link "Home" | Navigate | Home screen | Back to home |
| `search-btn-Catalog` | Overlay | Search results modal (560×360) | Same frame as Home's search modal |
| `dropdown-Type-on-Catalog` | Overlay | Type filter modal (180×200) | Dropdown overlay |
| "View Details" on card 1 (Alpha Widget) | Overlay | Item Detail modal (520×440) | Detail overlay |
| "View Details" on card 2 (Beta Gadget) | Overlay | Item Detail modal (520×440) | Same detail modal frame |

---

## Overlay frames to create

| Frame name | Size | Contents |
|------------|------|---------|
| `settings-overlay-modal` | 600×400 | Heading "Settings", 3 toggle rows (Notifications / Dark Mode / Auto-save), Close button |
| `search-results-modal` | 560×360 | Heading "Search Results", 4 item rows (name + type + price), Close button |
| `category-dropdown-modal` | 180×220 | 5 option rows: All, Electronics, Tools, Gadgets, Components |
| `type-filter-modal` | 180×200 | 5 option rows: All Types, Widget, Gadget, Tool, Component |
| `item-detail-modal` | 520×440 | Heading "Alpha Widget", description paragraph, price tag, "Add to Cart" button (accent), Close button |

---

## Prototype start screen
Set **Home** as the prototype start frame.

---

## What this test validates
- Navigate: tab bar → cross-screen, nav links → cross-screen, "Go to Catalog" button
- Overlay: dropdowns, search, settings, item detail
- Back: Close buttons on all modals dismiss the overlay and return to underlying screen
