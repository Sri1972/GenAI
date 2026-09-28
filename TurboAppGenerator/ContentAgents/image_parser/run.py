"""
Image Parsing Agent — hands an image straight to Claude (via the Claude Code
CLI's native vision support, on Bedrock) to describe or extract structured
data from it. No OCR/vision library needed locally; Claude reads the image
file itself.

Usage:
    python run.py <image.png> [--instruction "..."] [--out result.json] [--format json|md] [--max-dim 2000]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.claude_cli import run_claude, extract_json

SYSTEM_PROMPT = """You are the Image Parsing Agent. Read the image file at the
path you're given and carry out the user's instruction against it — describing
the image, transcribing text, reading a chart's values, or describing a
diagram's structure, as asked. Be precise about numbers/labels you read
directly from the image rather than guessing."""

DEFAULT_INSTRUCTION = "Describe this image and extract any structured data (text, tables, chart values) it contains."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--instruction", default=DEFAULT_INSTRUCTION)
    ap.add_argument("--out")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    ap.add_argument("--max-dim", type=int, default=2000)
    args = ap.parse_args()

    path = Path(args.image).resolve()
    if not path.exists():
        sys.exit(f"File not found: {path}")

    with tempfile.TemporaryDirectory() as tmp:
        read_path = path
        with Image.open(path) as im:
            if max(im.size) > args.max_dim:
                im.thumbnail((args.max_dim, args.max_dim))
                read_path = Path(tmp) / path.name
                im.save(read_path)

        if args.format == "json":
            task = f'Instruction: {args.instruction}\n\nRead the image at "{read_path}" and respond with ONLY a single JSON object capturing your findings, no prose.'
        else:
            task = f'Instruction: {args.instruction}\n\nRead the image at "{read_path}" and respond in well-structured Markdown.'

        result = run_claude(task, system_prompt=SYSTEM_PROMPT, allowed_tools=["Read"], cwd=str(read_path.parent))
        text = result["result"]

        out_path = Path(args.out) if args.out else path.with_suffix(f".parsed.{args.format}")
        if args.format == "json":
            parsed = extract_json(text)
            out_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        else:
            out_path.write_text(text, encoding="utf-8")

    print(f"Wrote result to {out_path}")


if __name__ == "__main__":
    main()
