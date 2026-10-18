#!/usr/bin/env python3
"""afterFileEdit hook: auto-format and autofix a Python file the agent just edited.

Fails open: any problem is ignored so editing is never blocked.
"""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    file_path = payload.get("file_path", "")
    if not file_path.endswith(".py") or not Path(file_path).exists():
        return 0

    for args in (
        ["ruff", "check", "--fix", "--quiet", "--exit-zero", file_path],
        ["ruff", "format", "--quiet", file_path],
    ):
        try:
            subprocess.run(["uv", "run", "--quiet", *args], check=False, timeout=25)
        except (OSError, subprocess.TimeoutExpired):
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
