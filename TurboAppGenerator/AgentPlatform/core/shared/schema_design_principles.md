## Schema Design Principles

- Normalize appropriately for the workload — 3NF for transactional data,
  denormalized where it genuinely serves analytics/reporting.
- Use meaningful table and column names that match the business domain, not
  generic placeholders.
- Every relationship must be expressed via a clearly, consistently named
  foreign key column (e.g. `customer_id`, not `cid` or `ref1`).
- Use snake_case for every SQL table and column identifier, regardless of
  the application layer's own naming convention.
- Never create circular foreign key dependencies between tables.
- A SQL-level `FOREIGN KEY` constraint may ONLY reference a column that is
  that table's PRIMARY KEY or has an explicit `UNIQUE` constraint — SQLite
  rejects any other target with "foreign key mismatch" the moment a row is
  inserted (not at schema-creation time, so this is invisible until real
  data is seeded). Reproduced directly: a shipments/carriers relationship
  matched by carrier NAME (a natural business key, not the numeric primary
  key) declared `FOREIGN KEY (carrier) REFERENCES carriers (name)`, but
  `carriers.name` only had a plain index, not `UNIQUE` — every single
  seed insert failed. Whenever a foreign key targets a business-key column
  instead of the referenced table's primary key, that column MUST also be
  declared `UNIQUE` in the same CREATE TABLE statement — do not just index
  it and assume that's equivalent, a plain index does not satisfy this
  requirement.
- Index columns that will actually be filtered, joined, or sorted on.
- Don't cram unrelated concerns into one overly wide table — split out a
  genuinely separate concept into its own table instead.
