#!/usr/bin/env python3
"""Reject oversized files.

Checks the *Git blob* recorded in the index, not the working-tree file. The
working-tree size is not authoritative: a large blob can be staged and the
working copy truncated afterwards, and a size check that stats the path would
pass while the large object still enters history.

Modes:
    --staged  (default)  inspect entries staged for commit
    --tree               inspect every blob reachable from HEAD (for CI, since
                         .git/hooks is never cloned and --no-verify exists)
"""

from __future__ import annotations

import argparse
import subprocess
import sys

DEFAULT_LIMIT_MIB = 10
SYMLINK_MODE = "120000"


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE).stdout


def _blob_size(sha: str) -> int:
    return int(_git("cat-file", "-s", sha).decode().strip())


def staged_entries() -> list[tuple[str, str, str]]:
    """Return (mode, sha, path) for each staged addition or modification.

    Deletions are excluded by the diff filter. Rename and copy records carry two
    paths; the destination is the one that matters.
    """
    raw = _git("diff", "--cached", "--raw", "-z", "--diff-filter=ACMRT")
    fields = raw.split(b"\0")
    entries: list[tuple[str, str, str]] = []
    i = 0
    while i < len(fields):
        meta = fields[i]
        if not meta.startswith(b":"):
            i += 1
            continue
        # :<srcmode> <dstmode> <srcsha> <dstsha> <status>
        parts = meta[1:].decode().split()
        if len(parts) < 5:
            i += 1
            continue
        dstmode, dstsha, status = parts[1], parts[3], parts[4]
        # Renames and copies are followed by source AND destination paths.
        npaths = 2 if status[:1] in ("R", "C") else 1
        path = fields[i + npaths].decode("utf-8", "surrogateescape")
        entries.append((dstmode, dstsha, path))
        i += npaths + 1
    return entries


def tree_entries() -> list[tuple[str, str, str]]:
    """Return (mode, sha, path) for every blob in the HEAD tree."""
    try:
        raw = _git("ls-tree", "-r", "-z", "HEAD")
    except subprocess.CalledProcessError:
        return []
    entries: list[tuple[str, str, str]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, _, path = record.partition(b"\t")
        mode, objtype, sha = meta.decode().split()
        if objtype != "blob":
            continue
        entries.append((mode, sha, path.decode("utf-8", "surrogateescape")))
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", default=True)
    group.add_argument("--tree", action="store_true")
    parser.add_argument("--limit-mib", type=int, default=DEFAULT_LIMIT_MIB)
    args = parser.parse_args()

    limit = args.limit_mib * 1024 * 1024
    entries = tree_entries() if args.tree else staged_entries()

    oversized = []
    for mode, sha, path in entries:
        # A symlink blob holds its target path, not the target's contents. Never
        # follow it; the blob itself is a few bytes.
        if mode == SYMLINK_MODE:
            continue
        size = _blob_size(sha)
        if size > limit:
            oversized.append((path, size))

    if not oversized:
        return 0

    print(f"BLOCKED: {len(oversized)} file(s) exceed {args.limit_mib} MiB:", file=sys.stderr)
    for path, size in sorted(oversized, key=lambda item: -item[1]):
        print(f"  {size / 1024 / 1024:8.1f} MiB  {path}", file=sys.stderr)
    print(
        "\nLarge data belongs in an external archive with a DOI, not in Git.\n"
        "Committed blobs stay in history permanently even if deleted later.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
