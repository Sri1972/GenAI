"""
Shared, deterministic group-by aggregation for any ContentAgents agent that
needs to turn raw rows into totals/averages/counts before an LLM writes
about them (a chart, a report table, a slide's key numbers, ...).

Extracted from visualization_agent/run.py, where the exact same need first
showed up concretely: a chart brief like "total revenue by region" against
raw per-month rows silently produced one overlapping bar per row instead of
one correct total per region, because nothing combined rows sharing the
same category. The fix there, and the point of pulling it out here, is the
same split every agent in this codebase already uses for anything
mechanical: an LLM may pick WHICH operation makes sense (sum/avg/count/min/
max) -- a judgment call -- but the actual arithmetic always runs here, in
plain Python, never inside the LLM's own response.

Only visualization_agent calls this today. excel_creator/pdf_creator/
ppt_creator don't yet have a step where they'd call it -- each plans its
entire output (sheets/rows, sections, slides) in one LLM call from a brief
+ free-text reference content, with no point in that flow that already
extracts clean structured rows the way visualization_agent's own
read_csv_text/read_data_file do. Wiring this in for them means giving each
one that same "get real rows first" step -- a real per-agent change, not
just a call to this function -- so it's deliberately not done here yet.
"""

import re

AGGREGATIONS = ("sum", "avg", "count", "min", "max", "none")


def aggregate_rows(rows: list[dict], group_by: str, value_field: str,
                    agg: str = "none", series_by: str | None = None) -> list[dict]:
    """Group `rows` by (group_by, series_by) and reduce each group's
    value_field with `agg`. Returns one {"group": ..., "value": ..., "series":
    ...} dict per group (series omitted when series_by is None).

    agg="none" skips grouping entirely and returns one row per input row
    (unchanged, just renamed) -- use this ONLY when group_by (+series_by) is
    already unique per row, e.g. a real time series with one row per date.
    Grouping rows that share a key under "none" silently overlaps them
    instead of combining them -- that's the exact bug this function exists
    to prevent when the right agg is used instead.
    """
    filtered = [r for r in rows if group_by in r and value_field in r]

    if agg == "none":
        out = []
        for r in filtered:
            entry = {"group": r.get(group_by), "value": _coerce_numeric(r.get(value_field))}
            if series_by and series_by in r:
                entry["series"] = r.get(series_by)
            out.append(entry)
        return out

    groups: dict[tuple, list] = {}
    order: list[tuple] = []
    for r in filtered:
        key = (r.get(group_by), r.get(series_by) if series_by else None)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(_coerce_numeric(r.get(value_field)))

    out = []
    for key in order:
        group, series = key
        entry = {"group": group, "value": _reduce(groups[key], agg)}
        if series_by:
            entry["series"] = series
        out.append(entry)
    return out


def _reduce(values: list, agg: str) -> float | int:
    if agg == "count":
        return len(values)
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return 0
    if agg == "avg":
        return sum(nums) / len(nums)
    if agg == "min":
        return min(nums)
    if agg == "max":
        return max(nums)
    return sum(nums)  # "sum", and the fallback for any unrecognized agg value


_CURRENCY_PREFIX_RE = re.compile(r"^[$€£¥]\s*")


def _coerce_numeric(v):
    """Turn a numeric-looking value into a real int/float, stripping the
    formatting real spreadsheet/report exports commonly add: currency
    symbols, thousands separators, a trailing %, K/M/B magnitude suffixes,
    and accounting-style (1,234) negatives. Reproduced directly: "$1,234.56"
    failed a plain float() outright and was silently filtered out of every
    sum/avg (not a numeric value -> dropped, no error) -- an entire chart
    of real dollar amounts rendered as flat zero bars with nothing
    indicating why. Returns the value unchanged if it genuinely isn't
    numeric, same as before."""
    if isinstance(v, (int, float)):
        return v
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return v

    is_percent = s.endswith("%")
    cleaned = s[:-1].strip() if is_percent else s
    cleaned = _CURRENCY_PREFIX_RE.sub("", cleaned).replace(",", "").strip()

    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]

    mult = 1
    if cleaned and cleaned[-1].upper() in ("K", "M", "B"):
        mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[cleaned[-1].upper()]
        cleaned = cleaned[:-1]

    try:
        f = float(cleaned) * mult
    except (ValueError, TypeError):
        return v
    if negative:
        f = -f
    return int(f) if f.is_integer() else f
