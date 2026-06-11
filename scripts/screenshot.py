"""Headless viewer screenshot (Phase 9 verification tooling).

Captures the running viewer at a given URL once the app signals readiness
(``window.__APP_READY``), letting layers settle a moment first:

    uv run python scripts/screenshot.py \
        --url 'http://127.0.0.1:8000/?run=40&t=4500&zoom=15.5&lng=-123.138&lat=49.264&play=0' \
        --out docs/images/after_street.png [--width 1600 --height 1000] [--settle 4]

Requires: `uv add --dev playwright && uv run playwright install chromium`,
and the API server running (`uv run uvicorn api.main:app`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def shoot(url: str, out: Path, width: int, height: int, settle: float, timeout: float) -> int:
    from playwright.sync_api import sync_playwright

    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_function("window.__APP_READY === true", timeout=timeout * 1000)
        except Exception:  # noqa: BLE001
            print("WARN: __APP_READY never fired; capturing anyway", file=sys.stderr)
        page.wait_for_timeout(int(settle * 1000))  # let tiles + layers settle
        page.screenshot(path=str(out))
        browser.close()
    print(f"wrote {out}")
    if errors:
        print(f"page errors ({len(errors)}):", *errors[:5], sep="\n  ", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1000)
    ap.add_argument("--settle", type=float, default=4.0, help="extra seconds after ready")
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()
    return shoot(a.url, a.out, a.width, a.height, a.settle, a.timeout)


if __name__ == "__main__":
    sys.exit(main())
