"""Entry point so the pipeline runs as ``uv run python -m etl <command>``."""

from __future__ import annotations

import sys

from etl.cli import main

if __name__ == "__main__":
    sys.exit(main())
