# Minimal offline example

Tier 1 of the reproducibility table in the [top-level README](../../README.md):
this runs with no IBM account, no AMBER, no QUICK and no HPC, and it exercises
the part of the workflow where a silent error would corrupt a trajectory, namely
the file exchange with the MD driver.

```bash
python examples/minimal/round_trip.py
```

It reads the synthetic QUICK-style file in `tests/fixtures/`, extracts the
converged Hartree-Fock energy and the embedding point charges, then writes the
output back with a stand-in energy and gradient in the format `sander` reads, and
checks that what was written reads back unchanged.

What it does **not** do is run a circuit or a solver: those need the scientific
stack, an entitlement and a QM/MM setup, and inventing numbers for them here
would teach the wrong thing about what this repository can demonstrate on its
own.
