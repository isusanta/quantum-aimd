# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
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
- Rotate the IBM Quantum credential (external, blocking).
- Confirm copyright holder, Apache-2.0 approval, and IBM-derived provenance.
- ~~Update `[project.urls]` and `CITATION.cff:repository-code` if transferred.~~
  Decided 2026-09-21: the repository stays under the personal account, so these
  URLs are final and the manuscript cites them.
- Confirm the author list; add `date-released` and tag `v0.1.0`.
- Replace the `preferred-citation` preprint reference with the journal
  reference once the paper is published.
