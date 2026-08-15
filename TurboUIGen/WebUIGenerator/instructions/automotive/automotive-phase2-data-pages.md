# AutoPulse — Phase 2: Sales Grid + Inventory

## What to add

Add 2 new pages to the existing AutoPulse app. Keep all existing pages and data unchanged.

Update the sidebar navigation to include these new items after Analytics:
5. Sales Grid
6. Inventory

---

## New Data

### Inventory
Add a new `inventory` table to `schema.sql` and seed it in `seed.sql`. Fields: vin (17-char string), make, model, year (2021–2025), trim (Base/Sport/Premium/Platinum/EV), color, msrp, status (Available/Reserved/In Transit/Sold), dealerCity, daysOnLot, region.

Generate 50 seed records spread across all makes and regions.

**DO NOT create any `src/data/*.json` files. All data comes from the SQLite database via the `/api/data/inventory` REST endpoint.** Use the `useApi` hook to fetch data on page mount.

---

## New Pages

### Sales Grid
Full data explorer for the existing `global_sales` table (fetched via `/api/data/global_sales`). Use the `useApi` hook.

- Filter bar: search box, Region dropdown, Make dropdown, Quarter dropdown, Reset button, row count badge.
- Sortable data table: Country, Region (colored badge), Make (badge), Model, Quarter, Volume, Revenue, YTD Growth (green/red badge), Market Share (progress bar).
- Pagination at 20 rows per page.
- **Export toolbar** above the table with "Excel ↓" and "PDF ↓" buttons that export the currently-filtered data.

### Inventory
Vehicle stock management view. Fetch data from `/api/data/inventory` using the `useApi` hook.

- Four KPI cards at top: Total Stock, % Available, In Transit, Avg Days on Lot.
- Filter bar: search (by VIN/model/dealer city), Status dropdown, Make dropdown, Reset button.
- Sortable table: VIN (monospace), Make (badge), Model, Year, Trim, Color, MSRP, Status (color badge: Available=green, Reserved=amber, In Transit=blue, Sold=gray), Dealer City, Days on Lot (0–30 green, 31–60 amber, 61+ red).
- **Export toolbar** above the table with "Excel ↓" and "PDF ↓" buttons that export the currently-filtered inventory data.
- Below the table: a horizontal bar chart showing vehicle count in 4 age buckets (0–30 / 31–60 / 61–90 / 90+ days).
