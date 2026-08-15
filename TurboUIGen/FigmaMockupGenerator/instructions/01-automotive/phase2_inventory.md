# Automotive Analytics — Phase 2: Vehicle Inventory

**UI Mode:**
- 🟡 **Rebuild Wireframe** — if you ran Phase 1 first (replaces the placeholder Vehicle Inventory screen with full content)
- 🟢 **Add Screens** — if running standalone (adds Vehicle Inventory to the right of existing frames)

> ⚠️ **Build ONLY the `Vehicle Inventory` screen and its 5 modals. Do NOT touch or rebuild `Sales Overview` or `Forecast` — they already exist on the canvas.**

Build the Vehicle Inventory screen with a full data table, search bar, and filter dropdowns.

---

## Screen: Vehicle Inventory

Left sidebar (240px): Sales Overview, **Vehicle Inventory** (active), Forecast.
Header: "Vehicle Inventory", "Add Vehicle" primary button, "Export" ghost button.
Filter bar below header: search field, Make dropdown (All/Toyota/Ford/BMW/Mercedes/Honda), Status dropdown (All/In Stock/Reserved/Sold).

**Data table — 8 rows:**

| VIN | Make | Model | Year | Color | Status | Days on Lot |
|-----|------|-------|------|-------|--------|-------------|
| 1HGBH41JXMN109186 | Honda | Civic | 2024 | Pearl White | In Stock | 12 |
| 2T1BURHE0JC043821 | Toyota | Camry | 2023 | Midnight Blue | Reserved | 28 |
| 3VWFE21C04M000001 | BMW | 3 Series | 2024 | Jet Black | In Stock | 5 |
| 1FTFW1ET5DFC10312 | Ford | F-150 | 2023 | Rapid Red | Sold | 45 |
| WDDNG7BB4EA395614 | Mercedes | C-Class | 2024 | Silver | In Stock | 8 |
| 5FNRL5H6XEB040128 | Honda | Odyssey | 2022 | Lunar Silver | Reserved | 31 |
| 2HKRM3H71FH500123 | Toyota | RAV4 | 2024 | Super White | In Stock | 3 |
| 1G1ZD5ST8JF123456 | Chevrolet | Malibu | 2023 | Mosaic Black | Sold | 67 |

---

## Modals to build

| Modal | Size | Content |
|-------|------|---------|
| Search results | 600×450 | Title "Search Results", 4 vehicle rows (VIN, Make, Model, Status), Close button |
| Make filter | 160×220 | 6 options: All, Toyota, Ford, BMW, Mercedes, Honda |
| Status filter | 160×180 | 4 options: All, In Stock, Reserved, Sold |
| Add Vehicle form | 540×400 | Title "Add Vehicle", fields: VIN, Make, Model, Year, Color, Status; Save + Cancel |
| Vehicle detail | 480×520 | Title "Honda Civic", VIN, all fields, Days on Lot 12, history notes, Close button |

---

## What opens what

- Search bar → opens search results modal as an overlay
- Make dropdown → opens Make filter modal as an overlay
- Status dropdown → opens Status filter modal as an overlay
- "Add Vehicle" button → opens Add Vehicle form modal as an overlay
- Clicking table row 1 (Honda Civic) → opens vehicle detail modal as an overlay

