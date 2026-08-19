"""The package must import and the CLI must run without any scientific stack."""

from __future__ import annotations

import subprocess
import sys


def test_package_imports():
    import quantum_aimd

    assert quantum_aimd.__version__


def test_cli_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "quantum_aimd.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "quantum-aimd" in result.stdout


def test_cli_advertises_pre_release():
    """The CLI must not imply the workflow exists."""
    from quantum_aimd.cli import PRE_RELEASE_NOTICE

    assert "PRE-RELEASE" in PRE_RELEASE_NOTICE


def test_cli_exposes_no_scientific_subcommands_yet():
    """Guards against advertising capability before it is migrated."""
    from quantum_aimd.cli import build_parser

    actions = [a for a in build_parser()._actions if a.dest not in ("help", "version")]
    assert actions == []
