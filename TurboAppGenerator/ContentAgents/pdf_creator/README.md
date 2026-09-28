# PDF Creation Agent

Designs a document (sections, paragraphs, tables) with Claude and builds it
with `reportlab`. The inverse of `pdf_parser` — this one writes PDFs
instead of reading them.

## Standalone usage
```bash
python run.py --brief "One-page summary of Q3 results: revenue, churn, roadmap"
python run.py --brief "Write this up as a report" --context "<pasted content from an Excel/image/website parser>"
```

## As a Claude Code subagent
`Agent({ subagent_type: "pdf-creator", prompt: "Create a one-page project status PDF covering the Q3 numbers" })`

## Notes
- `--context` is meant for upstream content (e.g. a PDF/Excel/image parser's
  output when chained in a workflow) — the brief says what to *do* with it.
- Pure-Python `reportlab` — no native/system libraries needed, safe on
  Windows.
