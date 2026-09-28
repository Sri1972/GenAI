# AutoPulse — Phase 3: Forecast

## What to add

Add 1 new page to the existing AutoPulse app. Keep all existing pages and data unchanged.

Add to the sidebar after Inventory:
7. Forecast

---

## New Data

Add a `forecast` table to `schema.sql` and seed it in `seed.sql` with monthly records from Jan 2024 through Dec 2025. Each record: month (YYYY-MM), actual (number for past months, null for future months starting Jan 2025), forecast, lower (forecast × 0.88), upper (forecast × 1.12), ev, ice (ev + ice = forecast), priorYear.

**DO NOT create any `src/data/*.json` files. All data comes from the SQLite database via the `/api/data/forecast` REST endpoint.** Use the `useApi` hook to fetch data on page mount.

---

## New Page

### Forecast
Sales projections and scenario planning.

- Controls row: scenario dropdown (Base Case / Optimistic +15% / Pessimistic -15%), make dropdown (All Makes + each make), confidence band toggle button.
- Full-width line chart Jan 2024 – Dec 2025 with three lines: Actual (solid blue), Forecast (dashed purple), Prior Year (gray). When the confidence band toggle is on, show a shaded area between upper and lower bounds.
- Two charts side by side below: a grouped bar chart of EV vs ICE monthly forecast volumes, and a variance bar chart (actual minus forecast per month, green bars for positive, red for negative).
- Summary table at the bottom — last 6 months + next 6 months: Month, Actual, Forecast, Variance, Variance %, Confidence (progress bar). Apply the selected scenario multiplier to forecast values.
