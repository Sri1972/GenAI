# Data Quality Agent — example files

Small, hand-built sample data with intentional data-quality issues baked in,
so you can try the agent and immediately see it catch something real. None
of these are used by the app itself -- just local test fixtures.

## Files

| File | Source type in the UI | Header? | Notes |
|---|---|---|---|
| `customers.csv` | Delimited file (delimiter `,`) | Yes | 10 rows |
| `customers.xlsx` | Excel file | Yes | Same data as the CSV |
| `customers.parquet` | Parquet file (**Python only**) | n/a -- schema is embedded | Same data as the CSV |
| `orders_pipe_noheader.txt` | Delimited file (delimiter `\|`) | **No** -- paste columns | 7 rows |
| `orders.sqlite` | Database → SQLite | -- | table `orders`, 7 rows |
| `employees.sqlite` | Database → SQLite | -- | table `employees`, 7 rows |

## Try these rules

**`customers.csv` / `customers.xlsx`** (columns: `id, email, age, country`)
```
email must never be empty; age must be between 0 and 120; id must be unique
```
Planted issues: row 3 has a blank email, row 4 has age 150, row 6 has age -4,
id 8 appears twice.

**`orders_pipe_noheader.txt`** -- no header row, so in the UI pick "No header"
and paste these column names:
```
order_id, customer_email, amount, status
```
Rules to try:
```
customer_email must never be empty; amount must be greater than 0; status must be one of shipped, pending, cancelled
```
Planted issues: row 2 has a negative amount, row 3 has a blank email, row 5
has status "unknown", row 6 has a zero amount.

**`orders.sqlite`** (table `orders`, same columns as above) -- DB type
SQLite, database file path = this file's full path, table = `orders`. Same
rules as the pipe file work here too.

**`employees.sqlite`** (table `employees`, columns: `emp_id, name,
department, salary, hire_date`) -- DB type SQLite, table = `employees`.
```
department must never be empty; salary must be greater than 0; emp_id must be unique; hire_date must be a valid date
```
Planted issues: emp_id 3 has no department, emp_id 4 has a negative salary,
emp_id 5 appears twice, emp_id 6 has hire_date "not-a-date".

## About `customers.parquet`

Pick "Parquet file" as the source, upload it, no header/delimiter fields to
fill in (the schema is embedded in the file). Same rules as the CSV/Excel
version work here -- same planted issues, same expected result. Parquet is
Python-only in this agent (Java is disabled when Parquet is selected) --
real Java Parquet support needs Apache Parquet + Hadoop client dependencies,
which wasn't worth the added fragility for this agent's scope.
