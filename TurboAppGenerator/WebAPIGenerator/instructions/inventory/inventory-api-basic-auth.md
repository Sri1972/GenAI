# Inventory API — Basic Auth + Rate Limiting

## Overview

A warehouse inventory API for tracking products and stock movements across multiple
warehouses. Sized to exercise the platform's enterprise-grade defaults: basic auth and
throttling, not just the bare minimum.

## Suggested form settings (API options)

- Language: Python (FastAPI) — or try Java (Spring Boot) to compare the two pipelines
- Auth type: Basic Auth (credentials land in the generated .env file after generation)
- Rate limit: 60 (req/min) — low enough to trip on purpose while testing

---

## Resources

### Warehouses
Fields: id, name, location, created_at.

### Products
Fields: id, sku (unique), name, category, unit_price, created_at.

### StockMovements
Fields: id, product_id (FK → products.id), warehouse_id (FK → warehouses.id),
quantity_delta (positive = stock in, negative = stock out), reason
(purchase / sale / adjustment / transfer), created_at.

---

## Endpoints

### Warehouses
- `GET /warehouses` — list all
- `POST /warehouses` — create

### Products
- `GET /products` — list all; support `category` filter query param
- `GET /products/{id}` — get one, including current total quantity across all warehouses
- `POST /products` — create
- `PUT /products/{id}` — update

### Stock Movements
- `GET /stock-movements` — list all; support `product_id` and `warehouse_id` filters
- `POST /stock-movements` — record a movement (adjusts the product's computed stock level)
- `GET /products/{id}/stock-by-warehouse` — current quantity of this product per warehouse

---

## Data Rules

- `quantity_delta` cannot be zero — reject with 400.
- A `sale` or `transfer`-out movement that would drive a warehouse's stock for that product
  below zero must be rejected with 400 and a clear message.
- Seed 3 warehouses, 12 products across 4 categories, and ~40 stock movements with a mix of
  all four reasons, resulting in realistic non-trivial stock levels per warehouse.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- Include a README with setup + run instructions, and where to find the generated
  Basic Auth credentials.
