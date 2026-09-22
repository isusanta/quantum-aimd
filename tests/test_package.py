"""The package must import and the CLI must run without any scientific stack.

The scientific dependencies are imported inside the functions that need them, so
these tests hold in an environment with none of qiskit, pyscf, ffsim or ray
installed. That is what keeps CI runnable by a contributor with no entitlements.
"""

from __future__ import annotations

import subprocess
import sys


def _subparsers(parser):
    """Return the single subparser action of the CLI parser."""
    actions = [
        action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
    ]
    assert len(actions) == 1
    return actions[0]


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
    """The CLI must not imply the interfaces are stable."""
    from quantum_aimd.cli import PRE_RELEASE_NOTICE

    assert "PRE-RELEASE" in PRE_RELEASE_NOTICE


def test_cli_exposes_every_migrated_stage():
    """One subcommand per stage of an MD step.

    This replaces an earlier test asserting that no scientific subcommand
    existed, which was the right guard while the package was a scaffold.
    """
    from quantum_aimd.cli import build_parser

    names = set(_subparsers(build_parser()).choices)
    assert {"session", "active-space", "layout", "sample", "solve"} <= names


def test_every_stage_accepts_a_backend_flag():
    """The device is a parameter of every stage, never a literal in the code."""
    from quantum_aimd.cli import build_parser

    choices = _subparsers(build_parser()).choices
    for name in ("active-space", "layout", "sample", "solve"):
        flags = {option for action in choices[name]._actions for option in action.option_strings}
        assert "--backend" in flags, name


def test_stage_without_a_backend_fails_cleanly(tmp_path):
    """A readable error and exit code 1, not a traceback and not a default device."""
    import os
    import pathlib

    import quantum_aimd

    # Run from an empty directory so no stray config is picked up, but keep the
    # package importable: a relative PYTHONPATH would not survive the cwd change.
    package_root = pathlib.Path(quantum_aimd.__file__).parent.parent
    env = dict(os.environ, PYTHONPATH=str(package_root))
    result = subprocess.run(
        [sys.executable, "-m", "quantum_aimd.cli", "layout"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
        env=env,
    )
    assert result.returncode == 1
    assert "no backend given" in result.stderr
    assert "Traceback" not in result.stderr


def test_no_module_imports_the_scientific_stack_at_module_level():
    """Importing any module must stay free of heavy or optional dependencies.

    If this breaks, CI would need the whole scientific stack to run a help
    message, and the offline tests would stop being offline.
    """
    import importlib

    for name in (
        "quantum_aimd.config",
        "quantum_aimd.cli",
        "quantum_aimd.io.quick",
        "quantum_aimd.chemistry.active_space",
        "quantum_aimd.circuits.lucj",
        "quantum_aimd.runtime.service",
        "quantum_aimd.runtime.sampler",
        "quantum_aimd.runtime.session",
        "quantum_aimd.sqd.driver",
    ):
        importlib.import_module(name)

    # numpy and yaml are allowed: the offline tier uses arrays and loads YAML.
    # Everything heavy must stay unimported until a function asks for it.
    for heavy in ("qiskit", "qiskit_ibm_runtime", "pyscf", "ffsim", "jax", "rustworkx", "ray"):
        assert heavy not in sys.modules, f"{heavy} imported at module level"
