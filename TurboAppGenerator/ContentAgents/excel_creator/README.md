# Excel Creation Agent

Designs a workbook (one or more sheets, real rows) with Claude and builds it
with `openpyxl`. The inverse of `excel_parser` — this one writes `.xlsx`
files instead of reading them.

## Standalone usage
```bash
python run.py --brief "Q3 sales by region and product, 3 regions x 4 products"
python run.py --brief "Turn this into a spreadsheet" --context "<pasted content from a PDF/report>"
```

## As a Claude Code subagent
`Agent({ subagent_type: "excel-creator", prompt: "Create a workbook tracking Q3 headcount by department" })`

## Notes
- `--context` is meant for upstream content (e.g. a PDF/Excel/image parser's
  output when chained in a workflow) — the brief says what to *do* with it.
- Won't fabricate specific numbers that aren't in the brief/context; if
  exact figures aren't given, it builds a clearly labeled structure instead.
