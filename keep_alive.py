#!/usr/bin/env python3
"""
Chenier Environmental Consulting
Streamlit Community Cloud keep-alive pinger

Visits each app with a real headless browser (Playwright) so the visit
counts as genuine traffic. If an app is asleep, clicks the
"Yes, get this app back up!" button and waits for it to boot.

Run by GitHub Actions on a schedule (see .github/workflows/keep_alive.yml).
Exits non-zero if any app could not be confirmed awake, so failures show
up as a red X in the Actions tab.
"""

import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── EDIT THESE: your three deployed app URLs ─────────────────────────────────
APP_URLS = [
    "https://chenierlocationmap.streamlit.app",
    "https://chenier-site-plan-figure.streamlit.app",
    "https://chenier-topo-generator.streamlit.app",
]
# ─────────────────────────────────────────────────────────────────────────────

PAGE_LOAD_TIMEOUT_MS = 60_000      # initial page load
APP_READY_TIMEOUT_MS = 120_000     # wait for Streamlit UI after load/wake
WAKE_BOOT_GRACE_SEC  = 20          # extra settle time after clicking wake


def is_app_ready(page) -> bool:
    """True if the Streamlit app UI is rendered on the page."""
    try:
        page.wait_for_selector('[data-testid="stApp"], .stApp',
                               timeout=APP_READY_TIMEOUT_MS)
        return True
    except PWTimeout:
        return False


def find_wake_button(page):
    """Return the wake-up button locator if the sleeping page is shown."""
    # Streamlit's sleeping page text has varied slightly over time; match
    # loosely on "get this app back up".
    btn = page.get_by_text("get this app back up", exact=False)
    try:
        if btn.count() > 0 and btn.first.is_visible():
            return btn.first
    except Exception:
        pass
    return None


def ping_app(browser, url: str) -> bool:
    print(f"\n=== {url} ===")
    page = browser.new_page()
    try:
        page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        time.sleep(5)  # let the sleeping page or the app shell render

        wake = find_wake_button(page)
        if wake:
            print("App is asleep — clicking wake button...")
            wake.click()
            time.sleep(WAKE_BOOT_GRACE_SEC)

        if is_app_ready(page):
            print("App is awake. ✔")
            return True

        # One retry: a freshly woken app sometimes needs a reload
        print("App UI not detected — reloading once...")
        page.reload(timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        if is_app_ready(page):
            print("App is awake after reload. ✔")
            return True

        print("FAILED: app UI never appeared. ✘")
        return False
    except Exception as e:
        print(f"FAILED: {e!r} ✘")
        return False
    finally:
        page.close()


def main() -> int:
    placeholders = [u for u in APP_URLS if "YOUR-" in u]
    if placeholders:
        print("ERROR: edit APP_URLS in keep_alive.py — placeholder URLs found:")
        for u in placeholders:
            print(f"  {u}")
        return 1

    failures = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for url in APP_URLS:
            if not ping_app(browser, url):
                failures += 1
        browser.close()

    print(f"\nDone: {len(APP_URLS) - failures}/{len(APP_URLS)} apps awake.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
