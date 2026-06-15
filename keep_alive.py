#!/usr/bin/env python3
"""
Chenier Environmental Consulting
Streamlit Community Cloud keep-alive pinger  (v2 — diagnostics)

Visits each app with a headless browser so the visit counts as real
traffic. Wakes sleeping apps. On failure, prints the page title and
visible text so the Actions log shows exactly what the browser saw.
"""

import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Your three deployed app URLs ─────────────────────────────────────────────
APP_URLS = [
    "https://chenierlocationmap.streamlit.app",
    "https://chenier-site-plan-figure.streamlit.app",
    "https://chenier-topo-figure3.streamlit.app",
    "https://chenier-topo-generator.streamlit.app",
]
# ─────────────────────────────────────────────────────────────────────────────

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

PAGE_LOAD_TIMEOUT_MS = 60_000
APP_READY_TIMEOUT_MS = 45_000
WAKE_BOOT_GRACE_SEC  = 20

# Streamlit's root element has varied across versions; accept any of these.
APP_SELECTOR = ('[data-testid="stApp"], .stApp, '
                '[data-testid="stAppViewContainer"], '
                '[data-testid="stHeader"], section.main')


def dump_page(page, label: str):
    """Print what the browser is actually looking at."""
    try:
        title = page.title()
    except Exception:
        title = "(unavailable)"
    try:
        text = page.evaluate("document.body ? document.body.innerText : ''")
        text = " ".join(text.split())[:600]
    except Exception:
        text = "(unavailable)"
    print(f"  [{label}] page title: {title!r}")
    print(f"  [{label}] page text : {text!r}")


def is_app_ready(page) -> bool:
    try:
        page.wait_for_selector(APP_SELECTOR, timeout=APP_READY_TIMEOUT_MS)
        return True
    except PWTimeout:
        return False


def find_wake_button(page):
    btn = page.get_by_text("get this app back up", exact=False)
    try:
        if btn.count() > 0 and btn.first.is_visible():
            return btn.first
    except Exception:
        pass
    return None


def ping_app(context, url: str) -> bool:
    print(f"\n=== {url} ===")
    page = context.new_page()
    try:
        page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        time.sleep(8)  # let the sleeping page or the app shell render

        wake = find_wake_button(page)
        if wake:
            print("App is asleep — clicking wake button...")
            wake.click()
            time.sleep(WAKE_BOOT_GRACE_SEC)

        if is_app_ready(page):
            print("App is awake. ✔")
            return True

        print("App UI not detected — dumping page state, then reloading once...")
        dump_page(page, "before reload")
        page.reload(timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        time.sleep(8)
        if is_app_ready(page):
            print("App is awake after reload. ✔")
            return True

        print("FAILED: app UI never appeared. ✘")
        dump_page(page, "after reload")
        return False
    except Exception as e:
        print(f"FAILED: {e!r} ✘")
        try:
            dump_page(page, "on exception")
        except Exception:
            pass
        return False
    finally:
        page.close()


def main() -> int:
    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA,
                                      viewport={"width": 1280, "height": 900})
        for url in APP_URLS:
            if not ping_app(context, url):
                failures += 1
        context.close()
        browser.close()

    print(f"\nDone: {len(APP_URLS) - failures}/{len(APP_URLS)} apps awake.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
