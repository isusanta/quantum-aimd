# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-09-23

### Changed
- Release notes rewritten to describe what each release contains. Development
  notes that had been kept in this file were removed.

## [0.1.0] - 2026-09-23

First public release, alongside the first revision of the paper
([arXiv:2607.28548](https://arxiv.org/abs/2607.28548)).

### Added
- The workflow that produced the trajectories in the paper, as a package with
  one subpackage per stage of an MD step:
  - `quantum_aimd.io.quick` reads and writes the files exchanged with QUICK and
    `sander`: MM point charges, the SCF energy, and the energy and gradient
    returned to the MD driver.
  - `quantum_aimd.chemistry.active_space` rebuilds the embedded Hartree-Fock
    reference from the QUICK output and molden file, projects the Hamiltonian
    onto the active space and writes the FCIDUMP.
  - `quantum_aimd.circuits` builds the LUCJ circuit from CCSD amplitudes and
    selects a noise-aware zigzag qubit layout on heavy-hex hardware.
  - `quantum_aimd.runtime` handles service access, the session lifecycle and
    sampling with dynamical decoupling and gate twirling.
  - `quantum_aimd.sqd` runs S-CORE configuration recovery, diagonalizes in the
    recovered subspace and evaluates the analytical nuclear gradient.
- `RunConfig`, one place for every setting of a run, loadable from YAML, with
  an annotated example in `configs/examples/run.yaml`.
- The `quantum-aimd` command line, one subcommand per stage: `session open|close`,
  `active-space`, `layout`, `sample`, `solve`.
- An offline example, `examples/minimal/round_trip.py`, that needs no account,
  no hardware and no AMBER.
- A test suite and CI on Python 3.11 and 3.12: tests, lint, format, the offline
  example, `CITATION.cff` validation, and a full-history scan for credentials and
  oversized files.
- Documentation: IBM Quantum setup, the software environment of the published
  runs, contributing guide, issue forms and a pull-request template.
- `CITATION.cff` with the paper as the preferred citation, and `NOTICE` listing
  the Apache-2.0 code this project derives from and what was changed in it.

### Security
- The package contains no credential and accepts none. The runtime service is
  built with no arguments, so it reads only an account the user saved outside
  this repository. The device is a required parameter with no default.

### Known limitations
- The hardware-facing stages were restructured from the scripts that produced
  the published trajectories. Their offline parts are covered by the test suite;
  the packaged hardware path has not yet been re-run end to end on a device.
