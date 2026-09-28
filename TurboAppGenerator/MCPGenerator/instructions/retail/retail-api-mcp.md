# Retail Store — API-source MCP

## Overview

API-source MCP wrapping the already-running `retail-java-api-1` Web API —
the Java counterpart to the HR API-source test, confirming the API-source
path works identically regardless of which language actually generated
the backing REST API (the MCP just sees an OpenAPI spec either way).

## Source

- Source type: **API**
- Base URL: `http://127.0.0.1:8407` (the port `retail-java-api-1` is
  currently running on — check the Web API tab or
  `WebAPIGenerator\generated\.ports.json` if it's since changed)
- Auth: Basic — `admin` / `HqrPdb0zNG4xgoBe` (from that project's own
  `.env`; re-check there if the project's been regenerated since)

## Endpoints

- `GET /api/v1/products/{id}/availability` — is this product in stock, and
  where
- `GET /api/v1/stores/{id}/low-stock` — which products at a store are
  running low
- `GET /api/v1/stores/{id}/sales-report` — a store's sales performance
- `GET /api/v1/customers/{id}/purchase-history` — a customer's past orders
- `GET /api/v1/products`, `GET /api/v1/stores`, `GET /api/v1/customers` —
  plain catalogs, for looking up ids/names

## Instructions (paste into the Instructions field)

```
No custom joins possible or needed here — these are already the store's
real reporting endpoints. Focus the tool descriptions on making it clear
which ones are per-store vs. per-product vs. per-customer, since several
names (low-stock, sales-report) could otherwise be ambiguous about which
entity they apply to.
```

## Suggested test questions (via "Try it")

- "Is [pick a product] in stock anywhere?"
- "Which products at [pick a store] are running low?"
- "How did [pick a store] do last month?" — exercises the sales-report
  tool; if the report doesn't take a date range, confirm the chat says so
  rather than inventing one.
- "What has [pick a customer] bought before?"
