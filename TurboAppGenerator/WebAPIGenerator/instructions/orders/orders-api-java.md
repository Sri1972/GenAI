# Orders API — Java / Spring Boot Test

## Overview

A small order-management API, specifically meant to exercise the Java (Spring Boot)
generation path — entities/relationships, Spring Security basic auth, and the
deterministic rate-limit/usage-metering filters that get dropped into `com.api.security`
after generation.

## Suggested form settings (API options)

- Language: Java (Spring Boot)
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Customers
Fields: id, name, email (unique), created_at.

### Orders
Fields: id, customer_id (FK → customers.id), status (pending / shipped / delivered / cancelled),
total_amount, created_at, updated_at.

### OrderItems
Fields: id, order_id (FK → orders.id), product_name, quantity, unit_price.

---

## Endpoints

### Customers
- `GET /customers` — list all
- `GET /customers/{id}` — get one, including their order count
- `POST /customers` — create

### Orders
- `GET /orders` — list all; support `status` and `customer_id` filters
- `GET /orders/{id}` — get one, including its line items
- `POST /orders` — create an order with a list of line items in the same request body;
  compute and store `total_amount` server-side (don't trust a client-supplied total)
- `PATCH /orders/{id}/status` — transition status (validate it's a legal transition:
  pending → shipped → delivered, or pending/shipped → cancelled; reject anything else with 400)

---

## Data Rules

- `quantity` and `unit_price` on order items must be positive — reject with 400 otherwise.
- Seed 8 customers and ~20 orders spread across all four statuses, each with 1-4 line items.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- Include a README with setup + run instructions (`mvn spring-boot:run` from the project root).
