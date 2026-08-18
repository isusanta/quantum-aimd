# quantum-aimd

Quantum-centric ab initio molecular dynamics driven by sample-based quantum
diagonalization (SQD).

> **Status: pre-release (v0.1.0).** The public API is not stable. This
> repository is under active preparation and has not yet been released.

## What this does

Couples classical QM/MM molecular dynamics to quantum hardware. Each MD step
takes a QUICK/AMBER QM region, builds a PySCF Hamiltonian, executes a LUCJ
circuit on IBM Quantum, recovers a selected-CI energy and gradient with S-CORE,
and returns forces to SANDER to advance the trajectory.

```
QUICK output / Molden
        |
        v
PySCF Hamiltonian + FCIDUMP
        |
        v
LUCJ circuit + qubit layout
        |
        v
IBM Quantum sampler  ->  counts
        |
        v
S-CORE selected-CI  ->  energy + gradient
        |
        v
modified QUICK output  ->  SANDER  (next MD step)
```

Target systems: H2O, NH3, CH4 in vacuum and aqueous QM/MM, benchmarked against
full-basis FCI references.

## Installation

```bash
pip install -e ".[dev]"
```

## Quickstart (no IBM account needed)

<!-- TODO: fill in once examples/minimal/ exists -->

```bash
quantum-aimd --help
```

## Running on IBM Quantum

This project **never accepts, stores, or logs a credential.** It reads only from
your locally saved Qiskit account:

```python
from qiskit_ibm_runtime import QiskitRuntimeService
QiskitRuntimeService.save_account(channel="ibm_quantum", token="<your token>")
```

Run that once, yourself, outside this repository. See `docs/ibm-quantum-setup.md`.

## Reproducibility

Three tiers, honestly labelled:

| Tier | What | Needs |
|---|---|---|
| 1 | Offline smoke test | nothing — runs in CI |
| 2 | Published analysis | processed data bundle (DOI, see below) |
| 3 | Full QPU/HPC workflow | AMBER, QUICK, IBM entitlement, HPC |

Hardware measurements are **not** byte-for-byte reproducible. Do not expect CI
or an unaffiliated user to reproduce Tier 3.

## Data

Trajectories and processed results are **not** in this repository. They are
deposited separately with a DOI.

<!-- TODO: add DOI and link once deposited -->

## External requirements

AMBER/SANDER, QUICK, and IBM Quantum access are **not** distributed or licensed
by this repository. Obtain them independently.

## Citation

See [CITATION.cff](CITATION.cff).

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE) — this project contains
IBM-derived Apache-2.0 code with modifications.
