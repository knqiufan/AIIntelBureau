"""Fail fast when logs, private keys, or high-confidence cloud keys enter Git."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


DISALLOWED_PATH = re.compile(r"(^|/)(?:[^/]+\.log|logs(?:/|$))", re.IGNORECASE)
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"\b(?:sk|rk)_[A-Za-z0-9]{20,}\b"),
)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def tracked_paths() -> list[str]:
    return [entry.decode("utf-8", "surrogateescape") for entry in git("ls-files", "-z").split(b"\0") if entry]


def history_paths() -> list[str]:
    return [line for line in git("log", "--all", "--name-only", "--format=").decode("utf-8", "replace").splitlines() if line]


def main() -> int:
    violations = [f"tracked: {path}" for path in tracked_paths() if DISALLOWED_PATH.search(path.replace("\\", "/"))]
    violations.extend(f"history: {path}" for path in history_paths() if DISALLOWED_PATH.search(path.replace("\\", "/")))
    for path in tracked_paths():
        file_path = Path(path)
        if not file_path.is_file():
            continue
        content = file_path.read_bytes()
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            violations.append(f"secret-like content: {path}")
    if violations:
        print("security check failed; remove the following before committing:", file=sys.stderr)
        print("\n".join(f"- {item}" for item in sorted(set(violations))), file=sys.stderr)
        return 1
    print("security check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
