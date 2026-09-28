"""
PDF Creation Agent — designs a document plan with Claude (via the Claude
Code CLI, on Bedrock) and builds it with reportlab. The inverse of
pdf_parser — this one writes PDFs instead of reading them.

Usage:
    python run.py --brief "One-page summary of Q3 results" [--context "..."] [--out out.pdf]
"""

import argparse
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.claude_cli import run_claude, extract_json

SYSTEM_PROMPT = """You are the PDF Creation Agent. You have no tool access
in this call -- the brief and any reference content below are already
complete. Do not ask to open files or run scripts yourself; design the plan
directly from what's given. Given a content brief (and optionally reference
content from an upstream source), design a document as a sequence of
sections with real written content, not placeholders.

Respond with ONLY a single JSON object, no prose, matching this shape:
{
  "title": "<document title>",
  "sections": [
    {"heading": "<section heading, or null for an unheaded intro>",
     "level": 1,
     "paragraphs": ["...", "..."],
     "table": {"headers": ["...", "..."], "rows": [["...", "..."]]} or null}
  ]
}
Rules:
- "level" is 1 for a top-level heading, 2 for a sub-heading.
- Use "table" only for genuinely tabular content; omit/null it otherwise.
- Never fabricate specific facts/figures that aren't in the brief or
  reference content -- write around what's actually given rather than
  inventing false precision."""


def build_pdf(plan: dict, out_path: Path):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out_path), pagesize=LETTER,
                             topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    story = [Paragraph(plan.get("title") or "Untitled", styles["Title"]), Spacer(1, 0.3 * inch)]

    for section in plan.get("sections", []):
        heading = section.get("heading")
        if heading:
            style = styles["Heading1"] if section.get("level", 1) == 1 else styles["Heading2"]
            story.append(Paragraph(heading, style))

        for para in section.get("paragraphs") or []:
            story.append(Paragraph(para, styles["BodyText"]))
            story.append(Spacer(1, 0.08 * inch))

        table_data = section.get("table")
        if table_data and table_data.get("headers"):
            rows = [table_data["headers"]] + [[str(v) for v in row] for row in table_data.get("rows", [])]
            table = Table(rows, hAlign="LEFT")
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(Spacer(1, 0.1 * inch))
            story.append(table)

        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True, help="What the document should contain")
    ap.add_argument("--context", help="Optional reference content (e.g. from an upstream source) to base the document on")
    ap.add_argument("--out")
    args = ap.parse_args()

    prompt_parts = [f"BRIEF: {args.brief}"]
    if args.context:
        prompt_parts.append(f"\nREFERENCE CONTENT:\n{args.context}")

    result = run_claude("\n".join(prompt_parts), system_prompt=SYSTEM_PROMPT)
    plan = extract_json(result["result"])

    out_path = Path(args.out) if args.out else Path.cwd() / f"{(plan.get('title') or 'document').strip().replace(' ', '_')[:60]}.pdf"
    build_pdf(plan, out_path)

    print(f"Wrote {len(plan.get('sections', []))} section(s) to {out_path}")


if __name__ == "__main__":
    main()
