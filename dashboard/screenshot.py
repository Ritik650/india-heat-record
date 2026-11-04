"""Capture the Grafana dashboard for the README. Needs Grafana running and Chrome installed.

Usage: python dashboard/screenshot.py [output_dir]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:3000/d/india-heat/india-s-heat-record?kiosk&theme=light"
OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "outputs" / "dashboard"
WIDTH, HEIGHT = 1600, 3500


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(4)
        # Grafana renders panels as they scroll into view, so visit the whole page before capturing.
        for y in range(0, 6000, 700):
            page.mouse.wheel(0, 700)
            time.sleep(0.8)
        page.mouse.wheel(0, -8000)
        time.sleep(4)
        errors = page.locator('[data-testid="data-testid Panel status error"]').count()
        print("panels showing errors:", errors)
        print("page title:", page.title())
        path = OUTPUT / "dashboard_full.png"
        page.screenshot(path=str(path), full_page=False)
        print("saved", path)
        browser.close()


if __name__ == "__main__":
    main()
