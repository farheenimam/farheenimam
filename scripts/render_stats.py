"""Render the README images from the live stats pages.
Usage: python scripts/render_stats.py http://localhost:8000 assets
"""
import sys
from playwright.sync_api import sync_playwright

base, out = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
jobs = [
    ("index.html", "banner.png", (1300, 660), "#stage", 5000),
    ("stats-github.html", "stats-github.png", (1000, 900), None, 2000),
    ("stats-streak.html", "stats-streak.png", (1000, 900), None, 2000),
    ("stats-panels.html", "stats-panels.png", (1000, 900), None, 2000),
    ("achievements.html", "achievements.png", (960, 900), None, 1500),
    ("readme-closing.html", "closing.png", (960, 900), None, 1500),
]
with sync_playwright() as p:
    browser = p.chromium.launch()
    for page_name, img, vp, sel, wait in jobs:
        page = browser.new_page(viewport={"width": vp[0], "height": vp[1]})
        page.goto(f"{base}/{page_name}", wait_until="load")
        page.wait_for_timeout(wait)
        target = f"{out}/{img}"
        if sel:
            page.locator(sel).screenshot(path=target)
        else:
            page.screenshot(path=target, full_page=True)
        page.close()
        print("rendered", target)
    browser.close()
