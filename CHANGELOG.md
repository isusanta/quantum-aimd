# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **The workflow itself.** The pipeline that produced the published trajectories
  is now part of the package, restructured from scripts into modules: every
  original file executed its work at import time, which made it impossible to
  call a stage, test it, or run two of them in one process.
  - `quantum_aimd.io.quick` reads and writes the files exchanged with QUICK and
    `sander`. Pure text and array handling, no quantum dependency, so the format
    the MD driver depends on can be tested offline.
  - `quantum_aimd.chemistry.active_space` rebuilds the embedded Hartree-Fock
    reference from the QUICK output and molden file, projects the Hamiltonian
    onto the active space, and writes the FCIDUMP.
  - `quantum_aimd.circuits.lucj` builds the LUCJ circuit from CCSD amplitudes and
    transpiles it; `quantum_aimd.circuits.layout` selects the noise-aware zigzag
    layout.
  - `quantum_aimd.runtime` holds service access, session lifecycle and sampling.
  - `quantum_aimd.sqd.solver` diagonalizes in the recovered subspace and
    evaluates the analytical gradient; `quantum_aimd.sqd.driver` runs the S-CORE
    loop and writes the QUICK output that advances the trajectory.
- `quantum_aimd.config.RunConfig`: one place for the device, the sampling budget,
  the active space, the S-CORE settings and the file names, loadable from YAML so
  that a run is reproducible from a file rather than from edited source.
- CLI subcommands, one per stage: `session open|close`, `active-space`, `layout`,
  `sample`, `solve`.
- `examples/minimal/round_trip.py`, Tier 1 of the reproducibility table: reads a
  synthetic QUICK output, writes it back with an energy and gradient, and checks
  the round trip. No account, no hardware, no AMBER. CI runs it.
- `configs/examples/run.yaml`, a documented configuration with no credential and
  a placeholder device name.
- Tests for the file format and the configuration, including that per-step
  artifacts do not collide, that unknown configuration keys are rejected, and
  that no module imports the scientific stack at module level.

### Security
- **No credential anywhere in the package.** The original `creation.py` and
  `lucj_get_optimal_layout_production.py` carried a 128-character API token as a
  literal, and one also carried an instance identifier. Neither was migrated. The
  runtime now builds the service with no arguments, so it reads only the account
  saved outside this repository, and nothing accepts, stores or logs a token.
  The credential still has to be rotated: it existed in plaintext in files.
- **No device name in the source.** `ibm_cleveland` appeared five times across
  the original scripts. The device is now a required parameter with no default,
  from `--backend`, the configuration file or `QUANTUM_AIMD_BACKEND`, which is
  what makes the workflow portable to another processor or platform rather than
  merely describable as portable.

### Changed
- `jax` and `rustworkx` promoted to direct dependencies, now that the modules
  importing them have landed. `ray` stays optional under the `hpc` extra: the
  driver parallelizes batches with it when present and runs them in sequence when
  absent.
- Per-step artifacts carry the step index when it is supplied, so each frame's
  amplitudes and addresses survive instead of being overwritten. Overwriting is
  why per-frame wave functions were unavailable for later analysis.
- The sampler blocks on the job result instead of spinning on `job.status()`,
  which previously burned local CPU for the whole queue wait.
- Counts are written as JSON; the reader still accepts the old Python `repr`
  format, so existing run directories stay readable.
- Block detection in `update_quick_out` tolerates trailing whitespace while
  staying anchored to the whole assignment and header line, rather than matching
  a loose substring: this function writes the file the MD driver reads, so a
  wrong match would corrupt a step.
- `extract_final_scf_energy` raises when a file holds no SCF table, instead of
  returning a silent zero.

### Fixed
- The two modules moved verbatim are excluded from the formatter and given
  per-file lint ignores, with the reason recorded in `pyproject.toml`: they stay
  diffable against the code that produced the published results.
- An earlier test asserted the CLI exposed no scientific subcommands, which was
  right while the package was a scaffold. It now asserts the opposite.
- Repository scaffolding: license, ignore rules, packaging metadata, citation.
- Minimal `quantum_aimd` package and `quantum-aimd` CLI. The CLI exposes no
  scientific subcommands and states that this is a pre-release scaffold.
- `tools/check_large_files.py` — rejects oversized files by inspecting the
  staged Git blob rather than the working-tree file, and can scan the whole HEAD
  tree for CI.
- `tools/scan_secrets.py` — history-aware scan for credential-shaped strings
  that reports rule name and location only, never a matched value, with a
  reviewed baseline in `tools/secret-scan-baseline.txt`.
- Tracked `.githooks/pre-commit` running both checks, enabled with
  `git config core.hooksPath .githooks`.
- CI workflow named `CI`: safety checks over full history, plus install, import,
  CLI help, lint, format, tests, and `CITATION.cff` validation on Python
  3.11 and 3.12. Actions pinned to commit SHAs.
- `docs/environment-evidence.md` recording the versions the science actually
  runs on, as evidence rather than a supported matrix.
- `preferred-citation` in `CITATION.cff` and a citation block in `README.md`,
  pointing at the preprint this code belongs to: arXiv:2607.28548,
  DOI 10.48550/arXiv.2607.28548. Title and author order were taken from the
  arXiv API record and checked against the manuscript and DataCite rather than
  written by hand.
- `docs/ibm-quantum-setup.md`, which `README.md` already linked but which did
  not exist. States the no-credential-in-the-repository contract, the
  argument-free `QiskitRuntimeService()` call, and that the device name is a
  parameter rather than a literal.

### Fixed
- The previous pre-commit hook stat'ed working-tree files, so a large blob could
  be staged and the working copy truncated afterwards and still be committed.
  Reproduced, then fixed.
- `.gitignore` was excluding intended `tests/fixtures/*.out` fixtures and the
  safe `.env.example` template.
- `pip install -e .` succeeded while `quantum-aimd --help` failed, because
  `quantum_aimd.cli` did not exist.
- `CITATION.cff` failed CFF 1.2.0 validation on a non-date `date-released`
  placeholder. The field is omitted until a real release exists.
- Dependency lower bounds were described as a validated production stack and
  sat below the transitive minima of the versions actually in use. Corrected
  against PyPI metadata. `pydantic` was declared but imported nowhere; removed.
- Removed a `save_account` documentation example from `README.md` that carried
  a literal `token="..."` placeholder inviting copy-paste.
- `README.md` linked `docs/ibm-quantum-setup.md`, which did not exist. Written.
- The author affiliation in `CITATION.cff` gave ZIP 44106; the manuscript gives
  44195 in all seven places. Corrected.

### TODO before first release
- Clean up style in the two verbatim-ported modules, as its own reviewable change.
- Exercise the migrated stages against a real QUICK output and a device, which
  needs an entitlement and cannot run in CI.
- Rotate the IBM Quantum credential (external, blocking).
- Confirm copyright holder, Apache-2.0 approval, and IBM-derived provenance.
- ~~Update `[project.urls]` and `CITATION.cff:repository-code` if transferred.~~
  Decided 2026-09-21: the repository stays under the personal account, so these
  URLs are final and the manuscript cites them.
- Confirm the author list; add `date-released` and tag `v0.1.0`.
- Replace the `preferred-citation` preprint reference with the journal
  reference once the paper is published.
