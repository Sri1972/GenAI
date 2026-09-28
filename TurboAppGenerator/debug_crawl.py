"""
Debug script — run to see exactly what the crawler discovers.

Usage:
    python debug_crawl.py <url> [username] [password]
    python debug_crawl.py http://localhost:3000/sandbox/automotive-portal-5 user pass
"""
import sys, time, re

def rewrite_sandbox(url):
    m = re.match(r"(https?://[^/]+)/sandbox/([^/?#]+)(.*)", url)
    if m:
        return f"{m.group(1)}/app/{m.group(2)}/{m.group(3)}"
    return url

url      = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
username = sys.argv[2] if len(sys.argv) > 2 else ""
password = sys.argv[3] if len(sys.argv) > 3 else ""
url = rewrite_sandbox(url)
print(f"[debug] Resolved URL: {url}")

from playwright.sync_api import sync_playwright

def _normalise(u): return u.split("#")[0].rstrip("/")

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
        userField.dispatchEvent(new Event('input',  {bubbles: true}));
        userField.dispatchEvent(new Event('change', {bubbles: true}));
    }
    nativeSetter.call(pwdField, pass_);
    pwdField.dispatchEvent(new Event('input',  {bubbles: true}));
    pwdField.dispatchEvent(new Event('change', {bubbles: true}));
    return {ok: true, hadUserField: !!userField};
}"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width":1440,"height":900}).new_page()

    print(f"[debug] Opening {url}")
    page.goto(url, wait_until="networkidle", timeout=30_000)
    time.sleep(1.5)
    print(f"[debug] After goto: {page.url!r}  title={page.title()!r}")

    if username or password:
        pwd_count = page.locator("input[type='password']").count()
        if pwd_count > 0:
            print("[debug] Login form detected — filling via JS")
            result = page.evaluate(JS_FILL, [username, password])
            print(f"[debug] JS fill result: {result}")
            # Click submit
            for sel in ["button[type='submit']","input[type='submit']",
                        "button:has-text('Sign In')","button:has-text('Login')"]:
                locs = page.locator(sel)
                if locs.count() > 0:
                    try:
                        locs.first.click(timeout=2000)
                        print(f"[debug] Clicked: {sel}")
                        break
                    except: continue
            page.wait_for_load_state("networkidle", timeout=10_000)
            time.sleep(1.5)
            print(f"[debug] After login: {page.url!r}  title={page.title()!r}")
        else:
            print("[debug] No password field found — skipping login")

    landing_url = page.url
    landing_origin = landing_url.split("/")[0] + "//" + landing_url.split("/")[2]
    print(f"[debug] landing_url={landing_url!r}")
    print(f"[debug] landing_origin={landing_origin!r}")

    raw_links = page.eval_on_selector_all(
        "a, button, [role='tab'], [role='menuitem'], nav *[class*='nav'], "
        "nav *[class*='tab'], aside *[class*='item'], *[class*='sidebar'] a, "
        "*[class*='menu'] a",
        """els => els.map(el => ({
            text: (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 80),
            href: el.href || null,
            tag:  el.tagName.toLowerCase(),
        })).filter(e => e.text.length > 0)"""
    )

    print(f"\n[debug] Elements matched: {len(raw_links)}")
    print("\n--- All links (text | href | tag | skip-reason) ---")
    nav_count = 0
    for i, lk in enumerate(raw_links):
        href = lk.get("href") or ""
        flag = ""
        if href and "://" in href and not href.startswith(landing_origin):
            flag = "← SKIP external"
        elif href and _normalise(href) == _normalise(landing_url):
            flag = "← SKIP same as landing"
        else:
            nav_count += 1
        print(f"  {i:3d}  {lk['text']!r:40s}  {href!r:55s}  {lk['tag']}  {flag}")

    print(f"\n[debug] Pages that would be visited: {nav_count}")
    browser.close()
