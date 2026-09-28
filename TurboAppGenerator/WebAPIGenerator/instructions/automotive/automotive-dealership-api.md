# Automotive Dealership & Service Network API

## Overview

A multi-dealership automotive platform covering the full vehicle lifecycle: manufacturer
catalog → dealership inventory → sale → post-sale service history. Sized well beyond the
simple 2-3 table samples specifically to exercise multi-level foreign keys, a many-to-many
join table (service parts), and endpoints that require joining 4-5 tables in one response
rather than just simple lookups.

## Suggested form settings (API options)

- Language: Python (FastAPI) — or try Java (Spring Boot) to compare the two pipelines
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Manufacturers
Fields: id, name, country, founded_year, created_at.

### VehicleModels
Fields: id, manufacturer_id (FK → manufacturers.id), name, category
(sedan / suv / truck / coupe), model_year, base_price, created_at.

### Dealerships
Fields: id, name, city, state, created_at.

### Vehicles
A specific physical unit with a VIN — distinct from VehicleModels, which is the catalog
entry. Fields: id, vehicle_model_id (FK → vehicle_models.id), dealership_id
(FK → dealerships.id, the dealership currently holding or that sold it), vin (unique),
color, current_mileage, status (in_stock / reserved / sold), created_at.

### Customers
Fields: id, first_name, last_name, email (unique), phone, city, created_at.

### Salespeople
Fields: id, dealership_id (FK → dealerships.id), first_name, last_name, hire_date,
created_at.

### Sales
One row per vehicle sale — a vehicle can only ever have one Sale row (it moves to
status=sold at that point). Fields: id, vehicle_id (FK → vehicles.id, unique),
customer_id (FK → customers.id), salesperson_id (FK → salespeople.id), sale_price,
sale_date, created_at.

### ServiceCenters
Fields: id, dealership_id (FK → dealerships.id), name, created_at.

### Technicians
Fields: id, service_center_id (FK → service_centers.id), first_name, last_name,
specialty (engine / electrical / body / general), created_at.

### Parts
A reusable parts catalog, not tied to any one service order. Fields: id,
part_number (unique), name, category, unit_cost, created_at.

### ServiceAppointments
Fields: id, vehicle_id (FK → vehicles.id), service_center_id (FK → service_centers.id),
technician_id (FK → technicians.id), appointment_date, status
(scheduled / in_progress / completed / cancelled), description, labor_cost, created_at.

### ServiceOrderParts
Many-to-many join table between ServiceAppointments and Parts — a real part-usage line
item, not just a link row. Fields: id, service_appointment_id
(FK → service_appointments.id), part_id (FK → parts.id), quantity,
unit_price_at_time (snapshot of the part's unit_cost at the moment it was used — don't
join back to today's Parts price for historical service orders), created_at.

---

## Endpoints

### Catalog
- `GET /manufacturers` — list all
- `GET /manufacturers/{id}` — one, including its vehicle model count
- `POST /manufacturers` — create
- `GET /vehicle-models` — list all; support `manufacturer_id` filter
- `POST /vehicle-models` — create

### Dealerships & Inventory
- `GET /dealerships` — list all
- `GET /vehicles` — list all; support `dealership_id` and `status` filters
- `GET /vehicles/{id}` — one, including its model and manufacturer info joined in
- `POST /vehicles` — create (status defaults to in_stock)

### Customers & Sales
- `GET /customers` — list all
- `POST /sales` — create a sale for a vehicle; reject with 400 if the vehicle's status
  isn't `in_stock` or `reserved`; on success, set the vehicle's status to `sold`
- `GET /customers/{id}/vehicles` — **complex join**: every vehicle this customer has
  bought (via Sales), each with its model name, manufacturer name, purchase price/date,
  and the date of its most recent completed service appointment (null if none)

### Service Network
- `GET /service-centers` — list all; support `dealership_id` filter
- `GET /technicians` — list all; support `service_center_id` filter
- `GET /parts` — list all; support `category` filter
- `POST /parts` — create
- `GET /service-appointments` — list all; support `vehicle_id` and `status` filters
- `POST /service-appointments` — create
- `POST /service-appointments/{id}/parts` — add a part-usage line item; capture
  `unit_price_at_time` from the part's current `unit_cost` at creation time
- `GET /service-appointments/{id}/full` — **complex join**: the appointment plus its
  vehicle (with model + manufacturer nested), the owning customer (via the vehicle's
  Sale, null if the vehicle hasn't been sold yet), the service center (with its
  dealership nested), the technician, the full list of parts used with per-line and
  total cost, and a computed `total_cost` = labor_cost + sum(parts line totals)

### Reporting (multi-table aggregates)
- `GET /dealerships/{id}/sales-report` — **complex join**: total sales count, total
  revenue, and a breakdown by vehicle model name (joining sales → vehicles →
  vehicle_models → manufacturers), for that dealership only
- `GET /technicians/{id}/workload` — **complex join**: this technician's appointment
  count by status, total parts used, and total revenue generated (sum of labor_cost
  across their appointments + sum of all parts line totals on those appointments)

---

## Data Rules

- `Vehicles.vin` must be unique; reject duplicates with 400.
- A `Sale` can only be created for a vehicle currently `in_stock` or `reserved` —
  reject with 400 and a clear message otherwise. Creating the sale must also flip the
  vehicle's `status` to `sold` in the same operation.
- `ServiceOrderParts.unit_price_at_time` is captured once at creation from the part's
  current `unit_cost` — it must never be recomputed from today's price on read.
- Seed data: 3 manufacturers, 2 vehicle models per manufacturer (6 total), 2
  dealerships, 10 vehicles spread across both dealerships and all three statuses, 8
  customers, 4 salespeople, 5 completed sales, 2 service centers (one per dealership),
  5 technicians, 10 parts across at least 3 categories, 8 service appointments in a mix
  of statuses, and at least 15 ServiceOrderParts line items spread across the completed
  appointments — enough that every complex-join endpoint above returns realistic,
  non-empty, multi-row results out of the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`) so the larger tables
  (vehicles, service_appointments, service_order_parts) don't dump everything by default.
- Include a README with setup + run instructions, an entity-relationship summary, and
  where to find the generated Basic Auth credentials.
