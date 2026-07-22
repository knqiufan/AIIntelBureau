"""SQLite ledger backup/restore utility with integrity and checksum evidence.

It deliberately backs up the local case/event/session ledger only.  Remote
OceanBase/seekdb data must be protected by the provider's own backup policy;
the operational runbook defines its export/restore order.  In embedded mode,
back up the configured seekdb directory alongside this SQLite artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"SQLite file does not exist: {path}")
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        connection.close()
    if result != "ok":
        raise ValueError(f"SQLite integrity check failed: {result}")


def backup(source: Path, destination: Path) -> None:
    verify(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError(f"backup destination already exists: {destination}")
    original = sqlite3.connect(source)
    copy = sqlite3.connect(destination)
    try:
        original.backup(copy)
    finally:
        copy.close()
        original.close()
    verify(destination)
    print(f"backup={destination} sha256={checksum(destination)}")


def restore(source: Path, destination: Path) -> None:
    verify(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A sibling staging file prevents an interrupted copy from leaving a
    # partially-written live database in place.
    staging = destination.with_suffix(destination.suffix + ".restore-staging")
    if staging.exists():
        staging.unlink()
    original = sqlite3.connect(source)
    copy = sqlite3.connect(staging)
    try:
        original.backup(copy)
    finally:
        copy.close()
        original.close()
    verify(staging)
    staging.replace(destination)
    print(f"restored={destination} sha256={checksum(destination)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Back up or restore the AI Intel Bureau SQLite ledger")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("backup", "restore"):
        command = subcommands.add_parser(name)
        command.add_argument("--source", required=True, type=Path)
        command.add_argument("--destination", required=True, type=Path)
        if name == "restore":
            command.add_argument("--confirm", action="store_true", help="acknowledge replacement of the destination database")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            backup(args.source, args.destination)
        else:
            if not args.confirm:
                parser.error("restore requires --confirm")
            restore(args.source, args.destination)
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"backup/restore failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
