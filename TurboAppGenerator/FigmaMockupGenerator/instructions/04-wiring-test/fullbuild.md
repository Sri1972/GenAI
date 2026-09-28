# Wiring Smoke Test — Full Build

**UI Mode:** 🟢 **New Wireframe**

Build a minimal 2-screen app to verify all interaction types work: navigate between screens, open overlays, and close them. Keep visuals simple — this is a wiring test, not a design showcase. Desktop layout, 1280×800.

**Colors:** Background `#f8fafc` · Cards `#ffffff` · Accent `#6366f1` · Text `#1e293b`

---

## Screen 1: Home

Top navigation bar (full width, white, 64px): logo text "WireTest" on the left, nav links on the right: Home, Catalog, Contact.
Hero section (120px, below nav): heading "Wiring Test App", subheading "Test all interaction types".

**Tab bar** — 3 tabs below hero:
- Overview (active/selected)
- Details
- Settings

**Content card** (below tabs, 800px wide, 280px tall): heading "Overview Panel", body "This is the overview tab content."

**Action row** — 3 controls side by side:
1. "Search Items" button
2. "Category" dropdown button (options: All, Electronics, Books, Clothing, Tools)
3. "Go to Catalog" primary button

**What opens what:**
- Overview tab → stays on Home screen (self-link, active tab)
- Details tab → navigates to Catalog screen
- Settings tab → opens settings modal as an overlay
- "Search Items" button → opens search results modal as an overlay
- "Category" dropdown → opens category filter modal as an overlay
- "Go to Catalog" button → navigates to Catalog screen
- "Catalog" nav link → navigates to Catalog screen

---

## Screen 2: Catalog

Same top nav bar: logo "WireTest", links Home (navigates to Home), Catalog (active), Contact.
Page heading: "Item Catalog".

**Filter bar:** search field, Type dropdown (options: All Types, Widget, Gadget, Tool, Component).

**6 item cards in a 2-column grid** (each 360×160):

| Name | Type | Price |
|------|------|-------|
| Alpha Widget | Widget | $29 |
| Beta Gadget | Gadget | $49 |
| Gamma Tool | Tool | $19 |
| Delta Component | Component | $99 |
| Epsilon Widget | Widget | $39 |
| Zeta Gadget | Gadget | $59 |

Each card shows: name (bold), type tag, price, "View Details" button.

**What opens what:**
- "Home" nav link → navigates to Home screen
- Search field → opens search results modal as an overlay
- Type dropdown → opens type filter modal as an overlay
- "View Details" on card 1 (Alpha Widget) → opens item detail modal
- "View Details" on card 2 (Beta Gadget) → opens item detail modal (same frame)

---

## Modals

### Settings modal — 600×400
Title "Settings". 3 preference rows with toggle switches: Dark Mode, Email Notifications, Auto-save. Save button. Close button.

### Search results modal — 560×360
Title "Search Results". 4 item rows showing name, type, price. Close button.

### Category filter modal — 180×220
5 options: All, Electronics, Books, Clothing, Tools.

### Type filter modal — 180×200
5 options: All Types, Widget, Gadget, Tool, Component.

### Item detail modal — 520×440
Title "Alpha Widget". Type badge. Price $29. Description text. "Add to Cart" primary button. Close button.

---

## Prototype start
Set **Home** as the prototype start screen.
