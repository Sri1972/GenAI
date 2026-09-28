# Orders API — Refine Test (additive only)

Use this AFTER generating an API from `orders-api-java.md` in this same folder.
Paste the "Refinement request" text below into the **Refine API** box in the
project's middle panel — not the main generation form.

This is deliberately small and purely additive (one new field on an existing
entity, one new endpoint on a different existing entity) so it's easy to check
the result: open `Orders.java`/`OrderService`/`OrderController` (or their
Python equivalents) afterward and confirm the existing fields/endpoints are
still there untouched, with only the new field/endpoint added.

---

## Refinement request

Add a `shipping_address` text field to Orders, and include it in the existing
`GET /orders`, `GET /orders/{id}`, and `POST /orders` responses.

Also add a new endpoint: `GET /customers/{id}/orders` — every order placed by
that customer, most recent first.

---

## What to check afterward

- `Customers`, `OrderItems`, and every existing `Orders` field (`status`,
  `total_amount`, etc.) should be completely unchanged — only `shipping_address`
  should be new.
- The existing `PATCH /orders/{id}/status` status-transition validation should
  still work exactly as before.
- `GET /customers/{id}/orders` should return real orders for a customer that
  already has some (seeded data has ~20 orders across 8 customers), not an
  empty list.
- If running Java: no restart-time errors — the new column should just appear
  automatically (Hibernate `ddl-auto=update`), no manual migration needed.
- If running Python: check `migrations_pending.sql` gets created and then
  disappears after the app restarts (that's the ALTER TABLE being applied
  directly against the live database).
