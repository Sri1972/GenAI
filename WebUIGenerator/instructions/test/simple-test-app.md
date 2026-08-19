# QuickTest — Minimal Test App

## Overview

A simple 2-page app to validate the generation pipeline works end-to-end.

**Brand:**
- App name: QuickTest
- Accent: `#2563EB` (blue-600)
- Sidebar: dark `#1E293B` with white text
- Page background: `#F8FAFC`

---

## Navigation

Dark sidebar with 2 pages:
1. Dashboard
2. Products

---

## Data

### Products
Fields: name, category (Electronics / Clothing / Food / Books), price, stock, rating (1-5).
Generate 15 seed records.

**All data comes from SQLite via the `/api/data/products` REST endpoint.** Use the `useApi` hook to fetch data.

---

## Pages

### Dashboard
- 3 KPI cards at top: Total Products (count), Average Price, Low Stock (stock < 10 count). Compute these client-side from the products data fetched via `useApi`.
- One bar chart below: product count by category.

### Products
- Search box to filter by name.
- Sortable table: Name, Category (colored badge), Price, Stock, Rating (star display).
- Export toolbar above the table with "Excel ↓" and "PDF ↓" buttons.

---

## General Requirements

- All data fetched via useApi hook from the API — no local JSON files.
- Responsive at 1440px width.
