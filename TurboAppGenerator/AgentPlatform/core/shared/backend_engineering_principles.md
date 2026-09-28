## Backend Engineering Principles

- Keep transport (HTTP), business logic, and data access in distinct layers
  — no HTTP concepts leaking into the service layer, no business rules
  living in a controller/route handler.
- API naming should be noun-based, plural resources, consistent across the
  codebase (e.g. `/orders`, not `/getOrders`).
- Every endpoint needs input validation before it reaches business logic —
  trust nothing from the client.
- Pagination is not optional for any list endpoint that can return
  unbounded data.
- Return proper HTTP status codes for every outcome — never 200 for an
  error — and never leak internal error details (stack traces, SQL errors)
  to the client.
- Document the error response shape alongside the success response shape.
- Never mix authentication logic into business logic.
- Public-facing endpoints need a rate-limiting strategy.
- Never use sequential, guessable IDs for public-facing resources.
- Prefer idempotent endpoints wherever the operation allows it.
- Log at boundaries (incoming requests, outgoing calls, errors), not inside
  loops.
