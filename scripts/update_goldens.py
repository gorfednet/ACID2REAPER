#!/usr/bin/env python3
"""
Regenerate, or check, the golden REAPER projects.

    python scripts/update_goldens.py            # rewrite the goldens
    python scripts/update_goldens.py --check    # non-zero exit if any would change

The ``--check`` form runs in CI so a golden cannot drift because someone
regenerated it without reading the diff.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; fail if any golden would change.",
    )
    args = parser.parse_args()

    env = dict(os.environ)
    if not args.check:
        env["ACID2REAPER_UPDATE_GOLDEN"] = "1"
    else:
        env.pop("ACID2REAPER_UPDATE_GOLDEN", None)

    command = [sys.executable, "-m", "pytest", "-q", "tests/test_golden_rpp.py"]
    result = subprocess.run(command, cwd=ROOT, env=env)
    if args.check and result.returncode != 0:
        print(
            "\ngolden files are out of date: review the diff, then run\n"
            "  python scripts/update_goldens.py",
            file=sys.stderr,
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
