# Automotive Production & Sales Forecasting API

## Overview

A manufacturing-and-planning platform for an automaker: vehicle programs (by
powertrain and segment) → plants and production lines → bill of materials
(components + suppliers) → monthly sales and production forecasts vs. actuals.
Distinct from the dealership/retail domain — no customers or point-of-sale here;
this is upstream planning and supply-chain data. Sized to exercise multi-table
joins, a many-to-many supplier relationship, and forecast-vs-actual variance
calculations rather than simple CRUD lookups.

## Suggested form settings (API options)

- Language: Python (FastAPI) or Java (Spring Boot) — either works
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### PowertrainTypes
Fields: id, name (ICE / Hybrid / PHEV / BEV / FCEV), description, created_at.

### VehiclePrograms
The vehicle model/program being planned and forecasted — distinct from a specific
manufactured unit. Fields: id, name, segment (sedan / suv / truck / crossover),
powertrain_type_id (FK → powertrain_types.id), launch_year, created_at.

### Regions
Fields: id, name, code (unique), created_at.

### Plants
Fields: id, name, region_id (FK → regions.id), country,
capacity_units_per_month, created_at.

### ProductionLines
A line within a plant, dedicated to one vehicle program. Fields: id,
plant_id (FK → plants.id), vehicle_program_id (FK → vehicle_programs.id), name,
max_units_per_month, created_at.

### Components
A reusable parts catalog. Fields: id, part_number (unique), name,
category (battery / engine / transmission / chassis / electronics / interior),
created_at.

### Suppliers
Fields: id, name, country, reliability_score (0-100), created_at.

### ComponentSuppliers
Many-to-many join table between Components and Suppliers — which suppliers can
provide which components, and on what terms. Fields: id,
component_id (FK → components.id), supplier_id (FK → suppliers.id), unit_cost,
lead_time_days, is_primary (bool — exactly one primary supplier per component),
created_at.

### BillOfMaterials
Which components go into which vehicle program, and how many per unit built.
Fields: id, vehicle_program_id (FK → vehicle_programs.id),
component_id (FK → components.id), quantity_per_vehicle, created_at.

### SalesForecasts
Fields: id, vehicle_program_id (FK → vehicle_programs.id),
region_id (FK → regions.id), period (format 'YYYY-MM'), forecast_units,
actual_units (nullable — filled in once the period closes), created_at.

### ProductionForecasts
Fields: id, production_line_id (FK → production_lines.id),
period (format 'YYYY-MM'), planned_units, actual_units (nullable — filled in
once the period closes), created_at.

---

## Endpoints

### Catalog
- `GET /powertrain-types` — list all
- `GET /vehicle-programs` — list all; support `powertrain_type_id` and `segment` filters
- `GET /vehicle-programs/{id}` — one, including its powertrain type nested
- `POST /vehicle-programs` — create

### Manufacturing Network
- `GET /regions` — list all
- `GET /plants` — list all; support `region_id` filter
- `GET /production-lines` — list all; support `plant_id` and `vehicle_program_id` filters
- `GET /production-lines/{id}` — one, including its plant and vehicle program nested

### Components & Suppliers
- `GET /components` — list all; support `category` filter
- `POST /components` — create
- `GET /suppliers` — list all
- `GET /components/{id}/suppliers` — every supplier for this component, with
  unit_cost, lead_time_days, is_primary
- `POST /component-suppliers` — link a supplier to a component; reject with 400
  if `is_primary=true` and a primary supplier already exists for that component
- `GET /vehicle-programs/{id}/bill-of-materials` — **complex join**: every
  component in this program's BOM, with its name, category,
  quantity_per_vehicle, and its primary supplier's name + unit_cost

### Forecasting
- `GET /sales-forecasts` — list all; support `vehicle_program_id`, `region_id`,
  `period` filters
- `POST /sales-forecasts` — create (actual_units defaults to null)
- `PATCH /sales-forecasts/{id}/actual` — set actual_units once the period closes
- `GET /production-forecasts` — list all; support `production_line_id`, `period` filters
- `POST /production-forecasts` — create (actual_units defaults to null)
- `PATCH /production-forecasts/{id}/actual` — set actual_units once the period closes

### Reporting (multi-table aggregates)
- `GET /vehicle-programs/{id}/forecast-accuracy` — **complex join**: every
  period with a non-null actual for this program (summed across regions),
  forecast_units, actual_units, and variance_pct =
  (actual - forecast) / forecast * 100
- `GET /plants/{id}/capacity-utilization` — **complex join**: for each
  production line at this plant, its most recent period's planned_units,
  actual_units (if closed), and utilization_pct = actual_or_planned /
  max_units_per_month * 100
- `GET /vehicle-programs/{id}/component-risk` — **complex join**: every
  component in this program's BOM with its supplier count and minimum
  lead_time_days across suppliers; flag `single_source: true` when a
  component has exactly one supplier
- `GET /regions/{id}/powertrain-mix` — **complex join**: total forecast_units
  in this region broken down by powertrain type (join sales_forecasts →
  vehicle_programs → powertrain_types), across all periods

---

## Data Rules

- `Components.part_number` and `Regions.code` must be unique; reject
  duplicates with 400.
- Exactly one `ComponentSuppliers` row per component may have `is_primary=true`
  — reject a second one with 400 and a clear message.
- `period` is always `'YYYY-MM'`. `actual_units` stays null until explicitly
  set via the `/actual` endpoints — forecast-accuracy/utilization
  calculations only include periods where it's been set.
- `BillOfMaterials.quantity_per_vehicle` must be > 0.
- Seed data: 4 powertrain types, 6 vehicle programs (spread across all
  powertrain types and at least 3 segments), 3 regions, 3 plants (one per
  region), 5 production lines across those plants, 15 components across at
  least 4 categories, 8 suppliers, ~25 component-supplier links (make at
  least 3 components single-sourced — exactly one supplier — so
  `component-risk` has something real to flag), ~30 bill-of-materials rows
  (several components per program), sales forecasts for 6 programs × 3
  regions × 4 months (with `actual_units` filled in for the first 2-3 months
  and left null for the most recent), and production forecasts for all 5
  lines × the same 4 months (same actuals pattern) — enough that every
  complex-join endpoint above returns realistic, non-empty, multi-row results
  out of the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`) so the
  larger tables (sales_forecasts, production_forecasts, component_suppliers)
  don't dump everything by default.
- Include a README with setup + run instructions, an entity-relationship
  summary, and where to find the generated Basic Auth credentials.
