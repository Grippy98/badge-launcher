#!/usr/bin/env python3
"""Compatibility entry point for the CPython desktop simulator."""

from __future__ import annotations

import sys
from typing import Sequence

from main import cli


def main(argv: Sequence[str] | None = None) -> int:
    """Run the simulator while preserving caller-supplied CLI options."""

    forwarded = list(sys.argv[1:] if argv is None else argv)
    return cli(["--backend", "desktop", "--no-hardware", *forwarded])


if __name__ == "__main__":
    raise SystemExit(main())
