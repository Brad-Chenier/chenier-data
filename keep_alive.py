#!/usr/bin/env python3
"""
Chenier Environmental Consulting
Streamlit Community Cloud keep-alive pinger  (v5)

Streamlit renders as a JS app (often inside an iframe), so the top-level
document body stays empty even when the app is fully up. v5 detects
readiness the right way: it wakes any sleeping app, waits for the network
to go idle, and confirms the app by checking the correct page title plus
rendered content in the page OR any child frame.
"""

import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Four deployed app URLs ────────────────────────────────────────────────────
APP_URLS = [
    "https://chenierlocationmap.streamlit.app",
    "https://chenier-site-plan-figure.streamlit.app",
    "https://chenier-topo-generator.streamlit.app",
]
# ─────────────────────────────────────────────────────────────────────────────

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

PAGE_LOAD_TIMEOUT_MS    = 60_000
NETWORK_IDLE_TIMEOUT_MS = 60_000
WAKE_BOOT_GRACE_SEC     = 25

# Streamlit's root element has varied across versions; accept any of these.
APP_SELECTOR = (
    '[data-testid="stApp"], .stApp, '
    '[data-testid="stAppViewContainer"], '
    '[data-testid="stHeader"], section.main'
)


def rendered_text_len(page) -> int:
    """Total visible text length across the page and all its frames."""
    total = 0
    for fr in page.frames:
        try:
            t = fr.evaluate("document.body ? document.body.innerText : ''")
            total += len(t.strip())
        except Exception:
            pass
    return total


def app_selector_present(page) -> bool:
    """True if the Streamlit root element exists in the page or any frame."""
    for fr in page.frames:
        try:
            if fr.query_selector(APP_SELECTOR):
                return True
        except Exception:
            pass
    return False


def find_wake_button(page):
    """Look for the 'get this app back up' button in any frame."""
    for fr in page.frames:
        try:
            btn = fr.get_by_text("get this app back up", exact=False)
            if btn.count() > 0 and btn.first.is_visible():
                return btn.first
        except Exception:
            pass
    return None


def wait_ready(page) -> bool:
    """Wait for network idle, then poll for rendered content in any frame."""
    try:
        page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT_MS)
    except PWTimeout:
        pass  # fall through to content checks anyway
    # Give late JS a moment, then poll for rendered content.
    for _ in range(10):
        if app_selector_present(page) or rendered_text_len(page) > 0:
            return True
        time.sleep(2)
    return False


def dump_page(page, label: str):
    try:
        title = page.title()
    except Exception:
        title = "(unavailable)"
    print(
        f"  [{label}] title={title!r}  frames={len(page.frames)}  "
        f"text_len={rendered_text_len(page)}  "
        f"selector={app_selector_present(page)}"
    )


def ping_app(context, url: str) -> bool:
    print(f"\n=== {url} ===")
    page = context.new_page()
    try:
        page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        time.sleep(5)

        wake = find_wake_button(page)
        if wake:
            print("App is asleep — clicking wake button...")
            wake.click()
            time.sleep(WAKE_BOOT_GRACE_SEC)

        if wait_ready(page):
            print("App is awake. ✔")
            return True

        print("App not confirmed — reloading once...")
        dump_page(page, "before reload")
        page.reload(timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        time.sleep(5)
        if wait_ready(page):
            print("App is awake after reload. ✔")
            return True

        print("FAILED: app never confirmed ready. ✘")
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
        context = browser.new_context(
            user_agent=UA, viewport={"width": 1280, "height": 900}
        )
        for url in APP_URLS:
            if not ping_app(context, url):
                failures += 1
        context.close()
        browser.close()

    print(f"\nDone: {len(APP_URLS) - failures}/{len(APP_URLS)} apps awake.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
