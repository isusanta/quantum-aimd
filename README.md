# quantum-aimd

Quantum-centric ab initio molecular dynamics driven by sample-based quantum
diagonalization (SQD).

**Paper** — Das, S.; Bhowmik, S.; Li, Z.; Bazayeva, M.; Kaliakin, D.; Shajan, A.;
Merz, K. M., Jr. *Quantum Computing Enabled ab initio Molecular Dynamics
Simulations*. [arXiv:2607.28548](https://arxiv.org/abs/2607.28548) (2026).
Under review; this link will be replaced by the journal reference once it appears.

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

## Repository layout

| Path | Contents |
|---|---|
| [`src/quantum_aimd/`](src/quantum_aimd/) | The package: one subpackage per stage of an MD step |
| [`tests/`](tests/) | Offline test suite; runs with no account and no scientific stack |
| [`examples/minimal/`](examples/minimal/) | Round trip through the QUICK file exchange, no hardware needed |
| [`configs/examples/`](configs/examples/) | Annotated `run.yaml` showing every setting and its default |
| [`docs/`](docs/) | IBM Quantum setup, and the environment the published runs used |
| [`tools/`](tools/) | Repository checks: history secret scan, large-file guard |

### Source files

| File | Role |
|---|---|
| [`config.py`](src/quantum_aimd/config.py) | `RunConfig`: every setting of a run in one frozen object, loaded from YAML. No default device |
| [`io/quick.py`](src/quantum_aimd/io/quick.py) | Reads and writes the files exchanged with QUICK and `sander`: point charges, SCF energy, energy and gradient write-back |
| [`chemistry/active_space.py`](src/quantum_aimd/chemistry/active_space.py) | Rebuilds the embedded Hartree-Fock reference, projects onto the active space, writes the FCIDUMP |
| [`circuits/lucj.py`](src/quantum_aimd/circuits/lucj.py) | Builds the LUCJ circuit from CCSD amplitudes and transpiles it to the device |
| [`circuits/layout.py`](src/quantum_aimd/circuits/layout.py) | Zigzag physical-qubit layout on a heavy-hex lattice, selected for noise |
| [`runtime/service.py`](src/quantum_aimd/runtime/service.py) | Resolves the locally saved Qiskit account. Accepts no credential, by construction |
| [`runtime/session.py`](src/quantum_aimd/runtime/session.py) | Session lifecycle: one session per trajectory, not per step |
| [`runtime/sampler.py`](src/quantum_aimd/runtime/sampler.py) | Executes the circuit with dynamical decoupling and gate twirling; returns counts |
| [`sqd/solver.py`](src/quantum_aimd/sqd/solver.py) | Diagonalizes in the recovered subspace and evaluates the analytical nuclear gradient |
| [`sqd/driver.py`](src/quantum_aimd/sqd/driver.py) | The S-CORE loop: configuration recovery, batching, and the energy and gradient of one MD step |
| [`cli.py`](src/quantum_aimd/cli.py) | One subcommand per stage, so each can be run and inspected on its own |

## Installation

```bash
pip install -e ".[dev]"
```

## Quickstart (no IBM account needed)

```bash
quantum-aimd --help
python examples/minimal/round_trip.py
```

The example reads a synthetic QUICK-style output, extracts the converged
Hartree-Fock energy and the embedding point charges, writes the file back in the
format `sander` reads, and verifies that the energies and every gradient
component survive the round trip. No account, no hardware, no AMBER.

## How one MD step runs

One subcommand per stage, so each can be run and inspected on its own. The
device is a parameter of every stage that can reach hardware; there is no
default, and no subcommand accepts a credential.

```bash
quantum-aimd session open  --backend NAME        # once per trajectory
quantum-aimd active-space                        # QUICK output -> FCIDUMP
quantum-aimd layout       --backend NAME         # once per system and device
quantum-aimd sample       --backend NAME --step N  # execute the circuit
quantum-aimd solve                  --step N     # energy and gradient
quantum-aimd session close                       # once per trajectory
```

Settings live in a YAML file rather than in the source, which is what makes a
run reproducible and what lets the same code target another device:

```bash
quantum-aimd solve --config configs/examples/run.yaml --step 17
```

Passing `--step` keeps the per-batch artifacts of each frame distinct instead of
each step overwriting the last.

## Running on IBM Quantum

This project **never accepts, stores, or logs a credential.** It reads only from
the Qiskit account you have already saved locally.

Save your account once, yourself, in your own Python session and outside this
repository, following the current
[Qiskit IBM Runtime documentation](https://docs.quantum.ibm.com/guides/setup-channel).
This repository deliberately shows no credential-bearing code sample, so that
nothing here can be copied into a file and committed by accident.

See `docs/ibm-quantum-setup.md`.

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

If you use `quantum-aimd` in your research, please cite the paper:

```bibtex
@misc{das2026quantumaimd,
  author       = {Das, Susanta and Bhowmik, Subhamoy and Li, Zhen and
                  Bazayeva, Milana and Kaliakin, Danil and Shajan, Akhil and
                  Merz, Jr., Kenneth M.},
  title        = {{Quantum Computing Enabled ab initio Molecular Dynamics Simulations}},
  year         = {2026},
  eprint       = {2607.28548},
  archivePrefix = {arXiv},
  doi          = {10.48550/arXiv.2607.28548},
  url          = {https://arxiv.org/abs/2607.28548}
}
```

The preprint is under review; this reference will be updated to the journal version
once it appears. [CITATION.cff](CITATION.cff) carries the same record in machine-readable
form, with the paper as `preferred-citation` and this repository as the software entry.

## Contributing

Bug reports, feature requests and pull requests are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for how to set up an environment that needs
no account and no hardware, and for what belongs in a report.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE) — this project contains
IBM-derived Apache-2.0 code with modifications.
