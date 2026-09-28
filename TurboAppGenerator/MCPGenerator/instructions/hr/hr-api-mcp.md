# HR Project Staffing — API-source MCP

## Overview

API-source MCP wrapping the already-running `hr-python-1` Web API — no
intermediate backing API generated this time, since the source already is
one; the MCP's tools call these endpoints directly. Good API-source test
case specifically because several of its endpoints are ALREADY
multi-table joins done server-side (`headcount-report`, `budget-report`,
`workload`, `utilization`) — confirms the MCP can wrap a
join-already-baked-into-the-endpoint just as easily as a plain list/get,
with no custom-tool logic needed on the MCP side at all.

## Source

- Source type: **API**
- Base URL: `http://127.0.0.1:8400` (the port `hr-python-1` is currently
  running on — check the Web API tab or
  `WebAPIGenerator\generated\.ports.json` if it's since changed)
- Auth: Basic — `admin` / `KV_0WcdiAp-TpUnG` (from that project's own
  `.env`; re-check there if the project's been regenerated since)

## Endpoints

Select at least these (skip the plain create/list ones if you want a
smaller tool set — the reporting ones are the interesting part of this
test):

- `GET /departments/{id}/headcount-report` — employee count, avg salary,
  active-project count for a department
- `GET /employees/{id}/workload` — hours logged by an employee, broken
  down by project
- `GET /employees/{id}/utilization` — an employee's current total
  allocation across active/planning projects
- `GET /projects/{id}/team` — everyone staffed on a project
- `GET /projects/{id}/budget-report` — budget vs. estimated labor cost for
  a project
- `GET /departments`, `GET /employees`, `GET /projects` — plain catalogs,
  useful so the chat can look up an id/name before calling a report tool

## Instructions (paste into the Instructions field)

```
No custom joins needed here — every reporting endpoint already does its
own join server-side. Just write clear, natural descriptions for each
tool so it's obvious from the tool list alone which one answers a
headcount question vs. a workload question vs. a budget question.
```

## Suggested test questions (via "Try it")

- "What's the headcount and average salary in [pick a department]?"
- "How is [pick an employee]'s time split across projects?"
- "Is [pick an employee] over-allocated right now?"
- "What's the budget situation on [pick a project]?" — confirms it
  correctly reports remaining budget, not just total budget.
