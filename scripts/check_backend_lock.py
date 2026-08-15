"""Ensure the generated backend lock still matches its direct dependency pins."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "backend" / "pyproject.toml"
LOCK = ROOT / "backend" / "requirements.lock"

DIRECT_PIN = re.compile(
    r'^\s*"(?P<name>[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?=='
    r'(?P<version>[^";]+)(?:\s*;[^\"]+)?",?\s*$'
)
LOCK_PIN = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\\\s]+)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def direct_pins() -> dict[str, str]:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    dependencies = list(project.get("dependencies", []))
    for values in project.get("optional-dependencies", {}).values():
        dependencies.extend(values)

    pins: dict[str, str] = {}
    for dependency in dependencies:
        match = DIRECT_PIN.match(f'"{dependency}",')
        if match is None:
            raise ValueError(f"Direct dependency must use an exact pin: {dependency}")
        pins[normalize(match["name"])] = match["version"].strip()
    return pins


def lock_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        match = LOCK_PIN.match(line)
        if match is not None:
            pins[normalize(match["name"])] = match["version"]
    return pins


def main() -> int:
    expected = direct_pins()
    actual = lock_pins()
    mismatches = [
        f"{name}: pyproject.toml requires {version}, requirements.lock has {actual.get(name, 'no entry')}"
        for name, version in expected.items()
        if actual.get(name) != version
    ]
    if mismatches:
        print("Backend dependency lock is out of sync:", *mismatches, sep="\n  - ")
        return 1
    print("Backend dependency lock matches all direct pins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
