"""Command-line entry point.

Deliberately minimal. Scientific subcommands are added as the corresponding
modules are migrated, so that ``quantum-aimd --help`` never advertises a
capability the package does not have.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__

PRE_RELEASE_NOTICE = (
    f"PRE-RELEASE (v{__version__}): scaffolding only. No scientific workflow is "
    "implemented yet, and the command-line interface is not stable."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantum-aimd",
        description="Quantum-centric ab initio molecular dynamics with SQD.",
        epilog=PRE_RELEASE_NOTICE,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"quantum-aimd {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    # No subcommands exist yet, so bare invocation prints help rather than
    # silently succeeding and implying work was done.
    parser.print_help()
    print(f"\n{PRE_RELEASE_NOTICE}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
