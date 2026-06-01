"""Entry point: ``uv run python -m sim <command>``."""

from __future__ import annotations

import sys

from sim.cli import main

if __name__ == "__main__":
    sys.exit(main())
