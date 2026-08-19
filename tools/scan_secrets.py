#!/usr/bin/env python3
"""Scan for credential-shaped strings, reporting locations only.

Never prints a matched value. A finding is reported as location plus the name of
the rule that fired, so the report can be pasted anywhere safely.

This is a coarse net, not a replacement for GitHub secret scanning or push
protection - neither of which is available on a free-plan private repository.
Filename patterns in .gitignore are not secret scanning either: .gitignore stops
a file being *added*, it does nothing about a secret pasted into a tracked file.

Modes:
    --worktree  (default)  tracked files in the working tree
    --history              every blob reachable from any ref (slow but thorough;
                           a secret deleted in a later commit is still in history)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

# (rule name, compiled pattern). Kept deliberately broad; false positives are
# cheap to triage, a missed credential is not.
RULES: list[tuple[str, re.Pattern[bytes]]] = [
    ("ibm-crn", re.compile(rb"crn:v[0-9]+:")),
    ("qiskit-save-account", re.compile(rb"save_account\s*\(")),
    (
        "assigned-token",
        re.compile(rb"(?i)\b(token|api_?key|apikey|secret|password)\s*=\s*[\"'][^\"']{8,}"),
    ),
    ("bearer-header", re.compile(rb"(?i)authorization\s*:\s*bearer\s+\S+")),
    ("aws-access-key", re.compile(rb"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("long-hex-secret", re.compile(rb"\b[0-9a-f]{64,}\b")),
]

SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".whl")
# This scanner necessarily contains the patterns it looks for.
SELF = "tools/scan_secrets.py"
BASELINE = "tools/secret-scan-baseline.txt"


def load_baseline() -> set[str]:
    """Reviewed findings that are known benign. Anything absent still fails."""
    try:
        with open(BASELINE, encoding="utf-8") as handle:
            return {
                line.strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            }
    except OSError:
        return set()


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE).stdout


def scan_blob(data: bytes, location: str) -> list[tuple[str, str, int]]:
    findings = []
    for lineno, line in enumerate(data.split(b"\n"), start=1):
        if len(line) > 8192:
            continue
        for name, pattern in RULES:
            if pattern.search(line):
                findings.append((name, location, lineno))
    return findings


def worktree_targets() -> list[tuple[str, bytes]]:
    out = []
    for path in _git("ls-files", "-z").split(b"\0"):
        if not path:
            continue
        name = path.decode("utf-8", "surrogateescape")
        if name == SELF or name.endswith(SKIP_SUFFIXES):
            continue
        try:
            with open(name, "rb") as handle:
                out.append((name, handle.read()))
        except OSError:
            continue
    return out


def history_targets() -> list[tuple[str, bytes]]:
    out = []
    listing = _git("rev-list", "--objects", "--all").decode("utf-8", "surrogateescape")
    for entry in listing.splitlines():
        sha, _, name = entry.partition(" ")
        if not name or name == SELF or name.endswith(SKIP_SUFFIXES):
            continue
        try:
            kind = _git("cat-file", "-t", sha).decode().strip()
            if kind != "blob":
                continue
            data = _git("cat-file", "blob", sha)
        except subprocess.CalledProcessError:
            continue
        out.append((f"{name} (blob {sha[:9]})", data))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--worktree", action="store_true", default=True)
    group.add_argument("--history", action="store_true")
    args = parser.parse_args()

    targets = history_targets() if args.history else worktree_targets()
    baseline = load_baseline()
    findings: list[tuple[str, str, int]] = []
    for location, data in targets:
        findings.extend(scan_blob(data, location))

    suppressed = [f for f in findings if f"[{f[0]}] {f[1]}:{f[2]}" in baseline]
    findings = [f for f in findings if f"[{f[0]}] {f[1]}:{f[2]}" not in baseline]

    scope = "history" if args.history else "working tree"
    if suppressed:
        print(f"{len(suppressed)} baselined finding(s) suppressed - see {BASELINE}.")
    if not findings:
        print(f"No new credential-shaped strings in {scope} ({len(targets)} objects scanned).")
        return 0

    print(f"POSSIBLE CREDENTIALS in {scope} - values withheld:", file=sys.stderr)
    for name, location, lineno in sorted(set(findings)):
        print(f"  [{name}] {location}:{lineno}", file=sys.stderr)
    print(
        "\nInspect each location yourself. If a real credential is present it must be "
        "revoked at the provider first; removing the line does not remove it from history.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
