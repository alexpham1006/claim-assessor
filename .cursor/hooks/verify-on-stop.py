#!/usr/bin/env python3
"""stop hook: enforce the definition of done.

When the agent finishes and Python/config files changed, run `make check`. If it fails,
send the failure back as a follow-up message so the agent fixes it (bounded by loop_limit).
No-op for Q&A turns, aborted runs, or when nothing relevant changed. Fails open.
"""

import json
import subprocess
import sys

RELEVANT_SUFFIXES = (".py", "pyproject.toml", "Makefile")
MAX_OUTPUT_CHARS = 3000


def changed_relevant_files() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],  # -uall: list files inside untracked dirs
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    files = [line[3:] for line in result.stdout.splitlines() if len(line) > 3]
    return [f for f in files if f.endswith(RELEVANT_SUFFIXES)]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if payload.get("status") != "completed":
            return 0
        if not changed_relevant_files():
            return 0
        result = subprocess.run(
            ["make", "check"], capture_output=True, text=True, check=False, timeout=170
        )
    except (json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        return 0

    if result.returncode == 0:
        return 0

    output = (result.stdout + result.stderr)[-MAX_OUTPUT_CHARS:]
    message = (
        "`make check` failed after your changes. Fix the root cause (do not weaken checks), "
        f"then re-run `make check`.\n\n```\n{output}\n```"
    )
    print(json.dumps({"followup_message": message}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
