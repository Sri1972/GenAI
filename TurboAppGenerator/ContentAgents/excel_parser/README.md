# Excel Parsing Agent

Scans an `.xlsx` workbook and produces a `<workbook>.metadata.json` file
describing every sheet's columns, inferred semantics, data-quality notes, and
inter-sheet relationships — so downstream workflow steps can query the
metadata instead of re-parsing the workbook each time.

## Standalone usage
```bash
python run.py path/to/workbook.xlsx [--out metadata.json] [--sample-rows 15]
```

## As a Claude Code subagent
`Agent({ subagent_type: "excel-parser", prompt: "Parse Sales.xlsx and tell me which column looks like the primary key" })`

## How it works
1. `openpyxl` scans workbook structure locally (sheets, headers, column
   sample values, formulas, merged cells) — no LLM call for this part.
2. That structural scan is handed to Claude (via the Claude Code CLI on
   Bedrock), which infers column semantics and flags data-quality issues.
3. The script parses Claude's JSON response and writes the metadata file.
