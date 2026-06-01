"""Shared ETL helpers."""

from __future__ import annotations

from pathlib import Path


def download_file(url: str, dst: Path, refresh: bool = False, timeout: int = 600) -> Path:
    """Stream a URL to ``dst`` (cached unless ``refresh``). Safe for large files."""
    if dst.exists() and dst.stat().st_size > 0 and not refresh:
        print(f"  cached: {dst.name} ({dst.stat().st_size:,} bytes)")
        return dst
    import requests

    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"  GET {url}")
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    print(f"  saved: {dst} ({dst.stat().st_size:,} bytes)")
    return dst
