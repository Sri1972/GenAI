# Retail Store API

## Overview

A multi-location retail chain's product/inventory/sales system: stores,
products, per-store stock levels, customers, and sales transactions with
line items. Different shape from the other sample domains specifically to
exercise a single product's stock being tracked independently PER STORE
(the same product row has many different, independently-decrementing stock
levels) plus a transaction that must validate and decrement stock at a
SPECIFIC store, not the product globally.

## Suggested form settings (API options)

- Language: Python (FastAPI) or Java (Spring Boot) — either works
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Stores
Fields: id, name, city, region, created_at.

### Products
Fields: id, sku (unique), name, category
(electronics / apparel / home / grocery / toys), unit_price, created_at.

### Inventory
Per-store stock for a product — the same product has one row here per
store it's stocked in. Fields: id, store_id (FK → stores.id), product_id
(FK → products.id), quantity_on_hand, reorder_threshold, created_at.

### Customers
Fields: id, first_name, last_name, email (unique), loyalty_tier
(standard / silver / gold), created_at.

### Sales
One row per checkout transaction at a specific store. Fields: id,
store_id (FK → stores.id), customer_id (FK → customers.id, nullable —
walk-in sales have no customer), sale_datetime, created_at.

### SaleItems
Fields: id, sale_id (FK → sales.id), product_id (FK → products.id),
quantity, unit_price_at_sale (snapshot of the product's price at sale
time), created_at.

---

## Endpoints

### Catalog
- `GET /stores` — list all; support `region` filter
- `GET /products` — list all; support `category` filter
- `GET /products/{id}/availability` — **complex join**: this product's
  `quantity_on_hand` at every store that stocks it, with each store's name
- `POST /stores` — create
- `POST /products` — create
- `POST /inventory` — set a product's initial stock at a store (reject
  with 400 if a row for this store+product pair already exists — use the
  restock endpoint for existing stock instead)

### Sales
- `POST /sales` — create a sale AND its line items in one call (request
  body includes an `items` array of `{product_id, quantity}`); reject with
  400 if any item's requested `quantity` exceeds that product's
  `quantity_on_hand` AT THIS SALE'S STORE specifically; on success,
  decrement each item's Inventory row for that store, and capture
  `unit_price_at_sale` from the product's current `unit_price`
- `PATCH /inventory/{id}/restock` — increment `quantity_on_hand` by a given
  amount at that store
- `GET /sales/{id}` — **complex join**: the sale plus the store's name, the
  customer's name (if any), every SaleItem with its product's name and a
  computed line total, and a computed `total_amount`

### Reporting (multi-table aggregates)
- `GET /stores/{id}/low-stock` — **complex join**: every product at this
  store whose `quantity_on_hand` is at or below its `reorder_threshold`,
  with the product's name and current quantity
- `GET /stores/{id}/sales-report` — **complex join**: total transaction
  count, total revenue (sum of every sale's computed total), and a
  breakdown of revenue by product category, for that store only
- `GET /customers/{id}/purchase-history` — **complex join**: this
  customer's sales across every store, each with the store's name and
  that sale's computed `total_amount`

---

## Data Rules

- `Products.sku` and `Customers.email` must be unique; reject duplicates
  with 400.
- Stock is tracked per store, never globally — the same product can be
  well-stocked at one store and out of stock at another; every stock check
  and decrement must resolve the specific store's Inventory row, never any
  Inventory row for that product.
- A Sale's total is never a stored column — always computed from its
  SaleItems' `quantity * unit_price_at_sale`.
- `SaleItems.unit_price_at_sale` is captured once at sale time and never
  recomputed from the product's current price on later reads, even after a
  price change.
- A sale can't be created if it would drive any item's store-level
  `quantity_on_hand` negative — reject the whole sale with 400 and a clear
  message naming which product/store is short.
- Seed data: 3 stores across different regions, 15 products across all
  categories, Inventory rows covering most store×product combinations
  (with at least 3 deliberately near/at their `reorder_threshold` at one
  store, and well-stocked at another, to exercise per-store variation), 10
  customers, and 20 sales spread across stores with realistic multi-item
  SaleItems (2-4 items per sale) — enough that every complex-join endpoint
  above returns realistic, non-empty, multi-row results out of the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`).
- Include a README with setup + run instructions, an entity-relationship
  summary, and where to find the generated Basic Auth credentials.
