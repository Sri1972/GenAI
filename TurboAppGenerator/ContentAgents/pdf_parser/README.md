# PDF Parsing Agent

Extracts per-page text/tables from a PDF and produces a `<file>.extract.json`
with a structured outline, per-section summaries, and (optionally) a direct
answer to a question — with page citations.

## Standalone usage
```bash
python run.py path/to/file.pdf [--out extract.json] [--question "What was Q3 revenue?"]
```

## As a Claude Code subagent
`Agent({ subagent_type: "pdf-parser", prompt: "Parse contract.pdf and tell me the termination notice period" })`

## Notes
- Text extraction uses PyMuPDF; table extraction uses pdfplumber.
- Scanned pages with little/no extractable text are flagged in
  `needs_ocr_pages` rather than silently skipped — OCR (pytesseract) isn't
  wired in yet since it needs a system Tesseract binary.
