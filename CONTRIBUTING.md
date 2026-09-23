# Contributing to quantum-aimd

Thanks for your interest in this project. It accompanies a published study of
ab initio molecular dynamics driven by sample-based quantum diagonalization, and
it is maintained by [Susanta Das](https://github.com/isusanta) at Cleveland Clinic.

The package is at version 0.x: the public API is not yet stable, and interfaces may
change between versions without a deprecation period.

## Table of contents

- [Before you start](#before-you-start)
- [Reporting bugs](#reporting-bugs)
- [Suggesting enhancements](#suggesting-enhancements)
- [Submitting changes](#submitting-changes)
- [Code style](#code-style)
- [Never include a credential](#never-include-a-credential)
- [Contact](#contact)

## Before you start

Only the offline parts of this project can be exercised without external
resources. Running a full trajectory needs AMBER/SANDER, QUICK, an IBM Quantum
entitlement and an HPC allocation, none of which this repository distributes.
The offline path needs none of them:

```bash
git clone https://github.com/isusanta/quantum-aimd.git
cd quantum-aimd
pip install -e ".[dev]"
pytest
python examples/minimal/round_trip.py
```

If the tests pass, your environment is good enough to work on everything that
CI can check.

## Reporting bugs

Open a [bug report](https://github.com/isusanta/quantum-aimd/issues/new?template=bug_report.yml).
The form asks which stage failed, the versions of the quantum and chemistry
stack, and the error output, which is usually enough to reproduce the problem.

A hardware result that differs from a published number is not necessarily a bug.
Measurements on a quantum processor are not byte-for-byte reproducible, and the
manuscript reports the spread we observed. Report it if the difference is far
outside that spread, or if the workflow itself fails.

## Suggesting enhancements

Open a [feature request](https://github.com/isusanta/quantum-aimd/issues/new?template=feature_request.yml).
Proposals that widen the science, such as another QM code, another device
family, or another ansatz, are welcome; say which part of the pipeline the
change would touch.

## Submitting changes

1. Fork the repository and branch from `main`.
2. Keep the change focused. One concern per pull request reviews faster.
3. Add or update a test. Anything that can be tested offline should be.
4. Run `pytest` and `ruff check .` before you push.
5. Open a pull request and fill in the template.

The CI workflow runs the test suite on Python 3.11 and 3.12, plus a job that
installs the package with no optional dependencies and imports it, which is what
keeps the scientific stack out of import time.

## Code style

- `ruff` for linting and formatting; the configuration is in `pyproject.toml`.
- Type annotations on public functions.
- Import the heavy scientific packages inside the function that needs them, not
  at module level. Importing `quantum_aimd` must stay free of PySCF, Qiskit and
  ffsim so that the offline suite runs anywhere.
- Docstrings say why the code does something, not only what it does.

## Never include a credential

Do not put an IBM Quantum API token in an issue, a pull request, a log excerpt,
a configuration file or a test. This package accepts no token anywhere by
design: it calls `QiskitRuntimeService()` with no arguments and reads the
account you saved yourself. See [`docs/ibm-quantum-setup.md`](docs/ibm-quantum-setup.md).

Before pasting output, check it for tokens, instance identifiers and HPC account
names. `tools/scan_secrets.py --history` scans the repository, but it cannot
scan an issue you are about to submit.

## Contact

For scientific questions about the method, please open an issue or write to the
corresponding author of the paper.
