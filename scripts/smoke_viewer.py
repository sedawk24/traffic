"""Viewer smoke test (Phase 9): the page boots, renders layers, and is sane.

Checks, against a running API server:
  1. zero uncaught page errors,
  2. ``window.__APP_READY`` fires within the timeout,
  3. the deck overlay holds a healthy layer count,
  4. the WebGL canvas isn't blank (pixel variance),
  5. the HUD chrome exists (top bar, rail cards, timeline).

    uv run python scripts/smoke_viewer.py [--url http://127.0.0.1:8000/?run=40&t=4500&play=0]
"""

from __future__ import annotations

import argparse
import sys


def smoke(url: str, timeout: float) -> int:
    from playwright.sync_api import sync_playwright

    failures: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-gl=angle"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        try:
            page.wait_for_function("window.__APP_READY === true", timeout=timeout * 1000)
        except Exception:  # noqa: BLE001
            failures.append("__APP_READY never fired")
        page.wait_for_timeout(3500)

        if errors:
            failures.append(f"{len(errors)} page errors; first: {errors[0][:300]}")

        n_layers = page.evaluate(
            "() => { const o = window.__overlay; return o && o._deck ? o._deck.props.layers.filter(Boolean).length : -1 }"
        )
        if n_layers is None or n_layers < 4:
            failures.append(f"deck layer count too low: {n_layers}")

        # WebGL canvases read blank via drawImage (no preserveDrawingBuffer), so
        # measure pixel variance on a real compositor screenshot instead.
        import base64

        shot_b64 = base64.b64encode(page.screenshot()).decode()
        variance = page.evaluate(
            """async (b64) => {
              const img = new Image();
              img.src = 'data:image/png;base64,' + b64;
              await img.decode();
              const c2 = document.createElement('canvas');
              c2.width = 160; c2.height = 100;
              const g = c2.getContext('2d');
              g.drawImage(img, 0, 0, 160, 100);
              const d = g.getImageData(0, 0, 160, 100).data;
              let sum = 0, sum2 = 0, n = d.length / 4;
              for (let i = 0; i < d.length; i += 4) {
                const v = (d[i] + d[i+1] + d[i+2]) / 3;
                sum += v; sum2 += v * v;
              }
              const mean = sum / n;
              return Math.sqrt(sum2 / n - mean * mean);
            }""",
            shot_b64,
        )
        if variance is not None and variance < 2.0:
            failures.append(f"canvas looks blank (pixel stddev {variance:.2f})")

        for sel in ("#topbar", "#rail .card", "#timeline", "#tlcanvas"):
            if not page.query_selector(sel):
                failures.append(f"missing HUD element: {sel}")

        stats = page.evaluate(
            "() => document.querySelector('#st-active') && document.querySelector('#st-active').textContent"
        )
        print(
            f"  layers={n_layers}  canvas_stddev={variance and round(variance, 1)}  on_road={stats}"
        )
        browser.close()

    if failures:
        print("SMOKE FAIL:")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    print("SMOKE OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8000/?play=0")
    ap.add_argument("--timeout", type=float, default=60.0)
    return smoke(ap.parse_args().url, ap.parse_args().timeout)


if __name__ == "__main__":
    sys.exit(main())
