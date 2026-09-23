"""Quantum-centric ab initio molecular dynamics with sample-based quantum diagonalization.

The workflow that produced the trajectories in the accompanying paper, one
subpackage per stage of an MD step: ``io`` (the QUICK and sander file exchange),
``chemistry`` (active-space Hamiltonian), ``circuits`` (LUCJ circuit and qubit
layout), ``runtime`` (sessions and sampling) and ``sqd`` (configuration recovery,
subspace diagonalization and analytical gradients).

Version 0.x: interfaces may change between minor versions; see CHANGELOG.md.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
