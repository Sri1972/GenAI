# Website Crawling Agent

A bounded, same-origin, breadth-first Playwright crawl (`crawl.py`) discovers
every reachable page, link, button, tab, and accordion it can, then Claude
reasons over the aggregated content to answer a question or produce a
structured site map.

Builds on the link/button/nav-discovery query already proven in
`TurboAppGenerator/debug_crawl.py`, extended with: robots.txt respect, a hard
page cap, clicking of href-less buttons/tabs/accordions to reveal
client-side-rendered content, and a full-page screenshot per page.

## Standalone usage
```bash
python run.py https://example.com --max-pages 100 --question "List every product category and its URL"

# Behind a login
python run.py https://internal.example.com --username user --password pass
```

## As a Claude Code subagent
`Agent({ subagent_type: "site-crawler", prompt: "Crawl https://example.com and build me a full site map" })`

## Guardrails (on by default)
- Same-origin only.
- `--max-pages` (default 200) and `--max-depth` (default 5) hard caps —
  crawling isn't safe to leave unbounded by default.
- Respects `robots.txt`; override with `--ignore-robots` only for sites you
  control.

## Notes / upgrade path
This is a **scripted** BFS crawl, not Claude driving the browser turn by
turn — that's deliberate: it's far more exhaustive (guaranteed to visit every
discovered same-origin link) and far cheaper for "cover the whole site" than
an LLM clicking around one page at a time. A live Playwright-MCP session
(Claude driving the browser directly) remains a documented option for sites
with multi-step interactive flows (e.g. complex auth) this scripted crawler
can't get through — not built here.
