# Environment evidence

Recorded 2026-08-18 from `/Users/dass11/wspace-lri/md_qc/requirements.txt` by
read-only inspection.

**This is evidence, not a compatibility claim.** It documents the one stack the
published science is known to have run on. It is not a supported matrix, not a
lock file, and not a statement that any other combination works.

## Versions in the research environment

| Package | Version |
|---|---|
| qiskit | 2.0.0 |
| qiskit-ibm-runtime | 0.37.0 |
| qiskit-addon-sqd | 0.9.0 |
| ffsim | 0.0.49 |
| pyscf | 2.8.0 |
| ray | 2.42.1 |
| rustworkx | 0.16.0 |
| jax / jaxlib | 0.5.3 |
| numpy | 2.2.4 |
| scipy | 1.15.2 |
| h5py | 3.13.0 |
| pyyaml | 6.0.2 |

No credential-shaped strings are present in that file.

## How this maps to `pyproject.toml`

Declared floors are the transitive minima of the versions above, verified
against PyPI metadata on 2026-08-18:

- `qiskit-addon-sqd` 0.9.0 requires `numpy>=1.26`, `scipy>=1.13.1`,
  `qiskit>=1.2`, `jax>=0.4.30`, `jaxlib>=0.4.30`
- `ffsim` 0.0.49 requires `pyscf>=2.7`, `qiskit>=1.1`

Floors are **not** set below these. A lower floor would advertise compatibility
with a combination nobody has ever run.

## Imports observed in `md_qc/src`

Third-party: `ffsim`, `jax`, `numpy`, `pyscf`, `qiskit`, `qiskit_addon_sqd`,
`qiskit_ibm_runtime`, `ray`, `rustworkx`, `scipy`.

Local modules that must migrate with their dependents: `auto_lucj_map`,
`quick_parsing_utilities`, `solve_from_quick`.

`jax`, `rustworkx`, and `ray` are imported directly by that source but are
**not** declared as direct dependencies of this package yet. Promote each one at
the moment the module importing it is migrated, and not before.

## Open question

`requires-python = ">=3.11"` in `pyproject.toml` is a choice, not evidence. The
interpreter version used for the published runs has not been recorded here.
Confirm it and narrow or widen accordingly before the first release.
