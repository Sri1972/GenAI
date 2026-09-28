"""
Website Crawling Agent — a bounded, same-origin, breadth-first Playwright
crawl (crawl.py) discovers every reachable page/link/button/tab it can, then
Claude (via the Claude Code CLI, on Bedrock) reasons over the aggregated
per-page content to answer a question or produce a structured site map.

Usage:
    python run.py https://example.com [--max-pages 200] [--max-depth 5]
                   [--question "..."] [--username U --password P] [--ignore-robots]
"""

import argparse
import asyncio
import json
import sys
import tempfile
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.claude_cli import run_claude
from crawl import crawl_site

SYSTEM_PROMPT = """You are the Website Crawling Agent. You are given the
aggregated text content of every page discovered on a website (plus a few
screenshots for visual confirmation) and must either answer a specific
question (citing which page URL(s) the answer came from) or, if no question
was given, produce a structured site map: the site's main sections, how pages
relate to each other via navigation, and what each page is for. Note any
crawl errors or robots.txt-blocked paths you were told about, but don't treat
them as content gaps to solve — they're just out of scope."""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--max-depth", type=int, default=5)
    ap.add_argument("--question")
    ap.add_argument("--username")
    ap.add_argument("--password")
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--max-screenshots", type=int, default=5)
    args = ap.parse_args()

    domain = urllib.parse.urlsplit(args.url).netloc.replace(":", "_")
    out_path = Path(args.out) if args.out else Path.cwd() / f"crawl_{domain}.json"

    with tempfile.TemporaryDirectory() as tmp:
        screenshots_dir = Path(tmp) / "screenshots"
        print(f"Crawling {args.url} (max {args.max_pages} pages, depth {args.max_depth})...")
        crawl = await crawl_site(
            args.url, max_pages=args.max_pages, max_depth=args.max_depth,
            respect_robots=not args.ignore_robots, username=args.username,
            password=args.password, screenshots_dir=screenshots_dir,
        )
        print(f"Visited {crawl['pages_visited']} pages, {len(crawl['errors'])} errors.")

        # Full crawl (minus raw text, kept separately below) goes to disk regardless of the LLM step.
        site_map_pages = [
            {"url": p["url"], "title": p["title"], "depth": p["depth"],
             "links": p["links"], "text_preview": p["text"][:500]}
            for p in crawl["pages"]
        ]
        out_path.write_text(json.dumps({**crawl, "pages": site_map_pages}, indent=2), encoding="utf-8")
        print(f"Wrote crawl data to {out_path}")

        # No extra truncation here beyond what crawl_site() already captured
        # per page (see crawl.py) -- an additional cut here was silently
        # dropping most of each page's content before Claude ever saw it.
        condensed_pages = [
            {"url": p["url"], "title": p["title"], "text": p["text"]}
            for p in crawl["pages"]
        ]
        screenshots = [p["screenshot"] for p in crawl["pages"] if p["screenshot"]][: args.max_screenshots]

        prompt_parts = [f"PAGES DISCOVERED ({len(condensed_pages)}):\n{json.dumps(condensed_pages, indent=2)}"]
        if crawl["errors"]:
            prompt_parts.append(f"\nCRAWL ERRORS/SKIPS: {json.dumps(crawl['errors'], indent=2)}")
        if screenshots:
            prompt_parts.append(f"\nSCREENSHOTS (read these for visual confirmation): {', '.join(screenshots)}")
        if args.question:
            prompt_parts.append(f"\nQuestion: {args.question}")

        result = run_claude(
            "\n".join(prompt_parts), system_prompt=SYSTEM_PROMPT,
            allowed_tools=["Read"], cwd=str(tmp),
        )
        report = result["result"]

    report_path = out_path.with_suffix(".report.md")
    report_path.write_text(report, encoding="utf-8")
    print(f"Wrote report to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
