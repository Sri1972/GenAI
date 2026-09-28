# HR Project Staffing API

## Overview

An internal HR/PMO system: departments, employees, projects, who's staffed
on what (a many-to-many assignment with a business constraint), and
timesheets logged against that staffing. Different shape from the other
sample domains specifically to exercise a many-to-many relationship that
carries its own business rule enforced ACROSS rows (an employee's total
allocation across active assignments can't exceed 100%), and cost/budget
reporting derived by joining timesheets back through assignments to salary
data.

## Suggested form settings (API options)

- Language: Python (FastAPI) or Java (Spring Boot) — either works
- Auth type: Basic Auth
- Rate limit: 100 (req/min)

---

## Resources

### Departments
Fields: id, name, location, created_at.

### Employees
Fields: id, department_id (FK → departments.id), first_name, last_name,
email (unique), title, hire_date, annual_salary, created_at.

### Projects
Fields: id, department_id (FK → departments.id, the owning department),
name, start_date, end_date (nullable — still open if null), status
(planning / active / completed / on_hold), budget, created_at.

### ProjectAssignments
Many-to-many join table between Employees and Projects — an employee can be
assigned to more than one project at once, at a partial allocation each.
Fields: id, project_id (FK → projects.id), employee_id
(FK → employees.id), role_on_project, allocation_percent (1-100),
assigned_date, created_at.

### Timesheets
Fields: id, employee_id (FK → employees.id), project_id
(FK → projects.id), work_date, hours, description, created_at.

---

## Endpoints

### Catalog
- `GET /departments` — list all
- `GET /employees` — list all; support `department_id` filter
- `GET /projects` — list all; support `department_id` and `status` filters
- `POST /departments` — create
- `POST /employees` — create
- `POST /projects` — create

### Staffing
- `POST /project-assignments` — assign an employee to a project; reject
  with 400 if this employee's `allocation_percent` across every OTHER
  assignment on an `active` or `planning` project would sum to more than
  100 including this new one — a real cross-row check, not just validating
  this one row in isolation
- `GET /projects/{id}/team` — **complex join**: every employee assigned to
  this project, each with their role, allocation_percent, and their
  department's name

### Timesheets
- `POST /timesheets` — create (reject with 400 if the employee has no
  ProjectAssignment for that project)
- `GET /employees/{id}/timesheets` — list all for this employee; support
  `start_date`/`end_date` range filters
- `GET /employees/{id}/workload` — **complex join**: total hours logged in
  the given date range, broken down by project name

### Reporting (multi-table aggregates)
- `GET /departments/{id}/headcount-report` — **complex join**: employee
  count, average annual_salary, and count of currently-active projects, for
  that department only
- `GET /projects/{id}/budget-report` — **complex join**: the project's
  budget, total hours logged against it by every assigned employee, an
  estimated labor cost (sum over each employee of
  `hours_logged * (annual_salary / 2080)` — a standard annual-hours
  divisor for an hourly rate), and `budget - estimated_cost` as the
  remaining budget
- `GET /employees/{id}/utilization` — **complex join**: this employee's
  CURRENT total allocation_percent summed across every assignment on an
  `active` or `planning` project, plus the list of those projects and each
  one's allocation

---

## Data Rules

- `Employees.email` must be unique; reject duplicates with 400.
- A ProjectAssignment's `allocation_percent` must be 1-100 on its own, AND
  the employee's total across all their assignments on `active`/`planning`
  projects must never exceed 100 — reject the new assignment with 400 and a
  clear message (stating the employee's current total) if it would.
  Assignments on `completed`/`on_hold` projects don't count toward this
  limit.
- A Timesheet can only be created for a project the employee actually has a
  ProjectAssignment for — reject with 400 otherwise.
- The hourly-rate divisor (2080 = 40 hours/week × 52 weeks) is a fixed
  constant used only for the budget-report estimate — never store a
  computed hourly rate anywhere, always derive it from `annual_salary` at
  request time.
- Seed data: 3 departments, 12 employees spread across them (varied
  salaries), 6 projects across all four status values, 15
  ProjectAssignments (including at least 2 employees genuinely split across
  two active projects at partial allocation, to exercise the 100% rule
  realistically), and 40+ timesheet entries spread across employees,
  projects, and at least a 4-week date range — enough that every
  complex-join endpoint above returns realistic, non-empty, multi-row
  results out of the box.

---

## General Requirements

- Return proper HTTP status codes and JSON error bodies `{"error": "..."}`.
- All list endpoints should support pagination (`limit`/`offset`).
- Include a README with setup + run instructions, an entity-relationship
  summary, and where to find the generated Basic Auth credentials.
