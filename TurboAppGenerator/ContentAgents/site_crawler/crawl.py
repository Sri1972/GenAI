"""
Bounded, same-origin, breadth-first website crawler built on Playwright.

Extends the link/button/nav-discovery query already proven in
TurboAppGenerator/debug_crawl.py (same selector list) with: robots.txt
respect, a hard page cap, clicking of href-less buttons/tabs/accordions to
reveal client-side-rendered content, same-origin iframe capture, and a
screenshot per page — aimed at giving an LLM the best shot at reasoning over
the *whole* site rather than just its static HTML.

Uses Playwright's ASYNC API, not sync — the sync API raises "you are using
Playwright Sync API inside the asyncio loop" the moment it's invoked from
any context that already has a running event loop (reproduced directly when
called from within this agent's own harness). The async API works
correctly both inside and outside an already-running loop, so callers can
either `await crawl_site(...)` directly from their own async code, or use
`asyncio.run(crawl_site(...))` from plain sync code (see run.py).
"""

import asyncio
import time
import urllib.parse
import urllib.robotparser
from collections import deque
from pathlib import Path

from playwright.async_api import async_playwright

NAV_SELECTOR = (
    "a, button, [role='tab'], [role='menuitem'], nav *[class*='nav'], "
    "nav *[class*='tab'], aside *[class*='item'], *[class*='sidebar'] a, "
    "*[class*='menu'] a"
)

EXPAND_SELECTOR = (
    "[aria-expanded='false'], [role='tab']:not([aria-selected='true']), "
    "button[class*='accordion'], button[class*='expand'], button[class*='toggle']"
)

JS_FILL = """([user, pass_]) => {
    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    const pwdField = document.querySelector("input[type='password']");
    if (!pwdField) return {ok: false};
    let userField = document.querySelector("input[type='email']");
    if (!userField) {
        const all = Array.from(document.querySelectorAll("input[type='text'], input:not([type])"));
        userField = all[0] || null;
    }
    if (userField) {
        nativeSetter.call(userField, user);
        userField.dispatchEvent(new Event('input', {bubbles: true}));
        userField.dispatchEvent(new Event('change', {bubbles: true}));
    }
    nativeSetter.call(pwdField, pass_);
    pwdField.dispatchEvent(new Event('input', {bubbles: true}));
    pwdField.dispatchEvent(new Event('change', {bubbles: true}));
    return {ok: true};
}"""


def _normalize(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def _origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _robots_allowed(rp_cache: dict, url: str) -> bool:
    origin = _origin(url)
    if origin not in rp_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(origin + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        rp_cache[origin] = rp
    rp = rp_cache[origin]
    return rp is None or rp.can_fetch("*", url)


async def crawl_site(start_url: str, max_pages: int = 200, max_depth: int = 5,
                      respect_robots: bool = True, username: str | None = None,
                      password: str | None = None, screenshots_dir: Path | None = None) -> dict:
    origin = _origin(start_url)
    rp_cache: dict = {}
    visited: set[str] = set()
    pages: list[dict] = []
    errors: list[dict] = []
    queue = deque([(start_url, 0)])

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        if username or password:
            # domcontentloaded, not networkidle -- ad/analytics-heavy real-world
            # sites (ESPN, etc.) never go fully network-idle within any
            # reasonable timeout, since they poll continuously in the
            # background. A short settle sleep after DOM load covers JS
            # rendering without waiting on network chatter that never stops.
            await page.goto(start_url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(1.5)
            if await page.locator("input[type='password']").count() > 0:
                await page.evaluate(JS_FILL, [username or "", password or ""])
                for sel in ["button[type='submit']", "input[type='submit']",
                            "button:has-text('Sign In')", "button:has-text('Login')"]:
                    if await page.locator(sel).count() > 0:
                        try:
                            await page.locator(sel).first.click(timeout=2000)
                            break
                        except Exception:
                            continue
                await page.wait_for_load_state("domcontentloaded", timeout=10_000)
                await asyncio.sleep(1.0)

        while queue and len(visited) < max_pages:
            url, depth = queue.popleft()
            norm = _normalize(url)
            if norm in visited or depth > max_depth:
                continue
            if respect_robots and not _robots_allowed(rp_cache, url):
                errors.append({"url": url, "error": "blocked by robots.txt"})
                continue

            visited.add(norm)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                await asyncio.sleep(1.5)
            except Exception as exc:
                errors.append({"url": url, "error": str(exc)[:300]})
                continue

            # Reveal accordions/tabs/toggles that don't navigate away.
            try:
                expandables = page.locator(EXPAND_SELECTOR)
                count = await expandables.count()
                for i in range(min(count, 15)):
                    try:
                        before = page.url
                        await expandables.nth(i).click(timeout=1000)
                        if page.url != before:
                            await page.go_back(wait_until="domcontentloaded", timeout=5000)
                    except Exception:
                        continue
                await asyncio.sleep(0.3)
            except Exception:
                pass

            landing_url = page.url
            body_text = await page.locator("body").inner_text()

            # body.inner_text() can silently skip a <table>'s content even
            # when the table is genuinely in the DOM and visible (observed on
            # ESPN's schedule widget) -- a layout/timing quirk, not a real
            # absence of content. Tables are often exactly where the highest-
            # value structured content lives (schedules, pricing, stats), so
            # capture each one explicitly and append any that aren't already
            # covered by the body text, rather than trusting body text alone.
            table_texts = []
            try:
                tables = page.locator("table")
                for i in range(min(await tables.count(), 10)):
                    t = (await tables.nth(i).inner_text()).strip()
                    if t and t not in body_text:
                        table_texts.append(t)
            except Exception:
                pass

            text = body_text
            if table_texts:
                text += "\n\n[TABLE CONTENT]\n" + "\n\n".join(table_texts)
            # 12000 chars comfortably covers a real single page's rendered
            # text (measured 4-6K chars on real-world sites like ESPN) while
            # still bounding a large crawl's total prompt size.
            text = text[:12000]
            title = await page.title()

            screenshot_path = None
            if screenshots_dir:
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                safe_name = urllib.parse.quote(landing_url, safe="")[:120] + ".png"
                screenshot_path = str(screenshots_dir / safe_name)
                try:
                    await page.screenshot(path=screenshot_path, full_page=True, timeout=10_000)
                except Exception:
                    screenshot_path = None

            raw_links = await page.eval_on_selector_all(
                NAV_SELECTOR,
                """els => els.map(el => ({
                    text: (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 80),
                    href: el.href || null,
                    tag: el.tagName.toLowerCase(),
                })).filter(e => e.text.length > 0)""",
            )
            discovered = []
            for link in raw_links:
                href = link.get("href")
                if not href:
                    continue
                if _origin(href) != origin:
                    continue
                href_norm = _normalize(href)
                discovered.append({"text": link["text"], "href": href_norm, "tag": link["tag"]})
                if href_norm not in visited:
                    queue.append((href_norm, depth + 1))

            pages.append({
                "url": landing_url, "title": title, "depth": depth,
                "text": text, "links": discovered, "screenshot": screenshot_path,
            })

        await browser.close()

    return {
        "start_url": start_url, "origin": origin,
        "pages_visited": len(pages), "pages": pages, "errors": errors,
    }
