# IBM Quantum setup

This repository **never accepts, stores, or logs a credential.** It reads only the Qiskit
account you have already saved on your own machine. Nothing here takes a token as an
argument, an environment variable, or a config field, and this page deliberately contains
no credential-bearing code sample, so that nothing on it can be pasted into a file and
committed by accident.

## What you need

| | |
|---|---|
| An IBM Quantum account | Any plan. The open plan is enough to run a circuit, but not enough to reproduce the published trajectories. |
| An instance with QPU time | The published runs used a premium instance. Queue behaviour and available devices differ by plan. |
| `qiskit-ibm-runtime` | Installed with this package. |

Tier 1 of the reproducibility table in the [README](../README.md) needs none of this.

## Saving your account, once

Follow the current
[Qiskit IBM Runtime setup guide](https://docs.quantum.ibm.com/guides/setup-channel) and run
the account-saving step **yourself, in your own Python session, from a directory outside
this repository**. It writes to `~/.qiskit/qiskit-ibm.json`, which is outside the working
tree and cannot be committed from here.

Two habits worth keeping:

- Save the account interactively, or read the token from a password manager or a file that
  your `.gitignore` already excludes. Never place it in a script, a notebook, or a
  `configs/` file, even temporarily. A token pasted "just to test" is the single most
  common way credentials reach a public repository.
- Treat a token that has ever been written into a file as exposed, and rotate it in the
  IBM Quantum dashboard rather than deleting the file and hoping.

## How this project reads it

Code in this repository constructs the runtime service with no arguments:

```python
from qiskit_ibm_runtime import QiskitRuntimeService

service = QiskitRuntimeService()
```

That call resolves the saved account. If it raises, your account is not saved, and the fix
belongs in the step above rather than in any file here.

## Choosing a backend

The published trajectories ran on one superconducting processor, and the device name is a
**parameter, never a literal in the source**. Supplying it explicitly is what lets the
workflow move to another device or another platform:

```python
service = QiskitRuntimeService()
backend = service.backend(name)          # name comes from configuration or the CLI
```

The classical stages after sampling, configuration recovery, subspace diagonalization,
gradient evaluation and the hand-off to the MD engine, consume only measurement counts and
do not depend on which device produced them.

## Safety nets in this repository

Both run in CI over the full history, and locally through the tracked pre-commit hook once
you enable it with `git config core.hooksPath .githooks`:

- `tools/scan_secrets.py` flags credential-shaped strings and reports the rule and location
  only, never the matched value.
- `tools/check_large_files.py` rejects oversized blobs, inspecting the staged blob rather
  than the working-tree file.

Neither is a substitute for keeping the token out of files in the first place.

## Status

**Pre-release (v0.1.0).** The scientific workflow is not yet migrated into this package, so
there is nothing here that submits a job. This page documents the contract the migrated code
will follow: no credential in the repository, and the device chosen by parameter.
