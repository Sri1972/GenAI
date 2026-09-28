"""
PDF Parsing Agent — extracts per-page text/tables with PyMuPDF + pdfplumber,
then asks Claude (via the Claude Code CLI, on Bedrock) to build a structured
outline/summary and, optionally, answer a specific question against the
extracted content.

Scanned pages with near-zero extractable text are flagged "needs_ocr" rather
than silently dropped — OCR itself is a stretch goal, not built here, since it
needs a system Tesseract binary this environment may not have.

Usage:
    python run.py <file.pdf> [--out extract.json] [--question "..."] [--max-page-chars 4000]
"""

import argparse
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.claude_cli import run_claude, extract_json

SYSTEM_PROMPT = """You are the PDF Parsing Agent. You have no tool access in
this call -- the per-page extraction below is already complete and
authoritative. Do not ask to open the file or run scripts yourself; answer
directly from the data given. You are given per-page text
and table extractions from a PDF and must:
1. Build a structured outline of the document (sections/headings you can
   infer from the text, with the page numbers they span, and a short summary
   of each section).
2. If a question is provided, answer it using only the extracted content, and
   cite the page number(s) your answer is based on. If the extracted content
   doesn't contain the answer, say so plainly rather than guessing.

Respond with ONLY a single JSON object, no prose, matching this shape:
{
  "outline": [{"title": "...", "pages": [1, 2], "summary": "..."}],
  "answer": "..." or null
}"""


def scan_pdf(path: Path, max_page_chars: int) -> dict:
    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        needs_ocr = len(text) < 20
        pages.append({
            "page": i + 1,
            "text": text[:max_page_chars],
            "truncated": len(text) > max_page_chars,
            "needs_ocr": needs_ocr,
        })

    with pdfplumber.open(path) as pdf:
        for i, ppage in enumerate(pdf.pages):
            tables = ppage.extract_tables()
            if tables:
                pages[i]["tables"] = tables[:5]  # cap tables per page

    return {"pdf": path.name, "page_count": len(pages), "pages": pages}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out")
    ap.add_argument("--question")
    ap.add_argument("--max-page-chars", type=int, default=4000)
    args = ap.parse_args()

    path = Path(args.pdf).resolve()
    if not path.exists():
        sys.exit(f"File not found: {path}")

    scan = scan_pdf(path, args.max_page_chars)
    needs_ocr_pages = [p["page"] for p in scan["pages"] if p["needs_ocr"]]

    prompt_parts = [
        "Here is the per-page extraction of a PDF:\n",
        json.dumps(scan, indent=2),
    ]
    if args.question:
        prompt_parts.append(f"\n\nQuestion: {args.question}")
    else:
        prompt_parts.append("\n\nNo specific question — just produce the outline.")

    result = run_claude("\n".join(prompt_parts), system_prompt=SYSTEM_PROMPT)
    parsed = extract_json(result["result"])
    parsed["needs_ocr_pages"] = needs_ocr_pages

    out_path = Path(args.out) if args.out else path.with_suffix(".extract.json")
    out_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    print(f"Wrote extraction to {out_path}")
    if args.question:
        print(f"\nAnswer: {parsed.get('answer')}")
    if needs_ocr_pages:
        print(f"\nNote: pages {needs_ocr_pages} had little/no extractable text (likely scanned images) — OCR not run.")


if __name__ == "__main__":
    main()
