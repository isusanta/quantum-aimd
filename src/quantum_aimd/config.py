"""Run configuration.

Everything that varies between runs lives here: the device, the sampling budget,
the active space, the S-CORE settings and the file names exchanged with QUICK.
Nothing in this package hard-codes a device, and nothing reads a credential.

A configuration can be written as YAML and passed with ``--config``, which is
what makes a run reproducible and what lets the same code target another device
or another platform without editing a source file.

    backend: <device name>          # required; no default
    shots: 10000
    num_orbitals: 7
    num_electrons_a: 5
    num_electrons_b: 5
    num_atoms: 3
    score_iterations: 2
    batches: 10
    samples_per_batch: 800
"""

from __future__ import annotations

import dataclasses
import os
from typing import Any

__all__ = ["BACKEND_ENV_VAR", "RunConfig"]

BACKEND_ENV_VAR = "QUANTUM_AIMD_BACKEND"


@dataclasses.dataclass(frozen=True)
class RunConfig:
    """Settings for one MD step of the SQD-driven workflow.

    The defaults describe the *shape* of the published runs, not the device they
    ran on: ``backend`` has no default, because which processor executed a
    trajectory is a fact about that trajectory and belongs in its configuration
    file, not in this code.
    """

    # --- quantum execution ---------------------------------------------------
    backend: str
    shots: int = 10000
    dynamical_decoupling: bool = True
    twirl_gates: bool = True
    twirl_measurement: bool = False
    job_tags: tuple[str, ...] = ()

    # --- active space --------------------------------------------------------
    num_orbitals: int = 7
    num_electrons_a: int = 5
    num_electrons_b: int = 5
    num_atoms: int = 3
    open_shell: bool = False
    spin_sq: int | None = 0
    avas_orbitals: list[str] | None = None

    # --- LUCJ ansatz ---------------------------------------------------------
    n_reps: int = 2
    optimization_level: int = 3

    # --- S-CORE / subspace diagonalization -----------------------------------
    score_iterations: int = 2
    batches: int = 10
    samples_per_batch: int = 800
    max_davidson_cycles: int = 200
    ray_num_cpus: int | None = 10

    # --- files exchanged with QUICK and sander --------------------------------
    quick_out: str = "QUICK_job.out"
    quick_molden: str = "QUICK_job.molden"
    quick_out_modified: str = "QUICK_job_PySCF_modified.out"
    fcidump: str = "fci_dump.txt"
    layout: str = "layout.npy"
    counts: str = "count_dict.txt"
    session_file: str = "session.txt"
    results_dir: str = "results"

    # Step index, when the driver knows it. Supplying it makes the per-batch
    # amplitude and address files step-specific instead of overwriting each
    # other, which is what makes a trajectory reanalysable after the fact.
    step: int | None = None

    def __post_init__(self) -> None:
        if not self.backend:
            raise ValueError(
                "no backend given. Pass --backend, set backend: in the config file, "
                f"or export {BACKEND_ENV_VAR}. This package deliberately ships no "
                "default device."
            )
        if self.shots <= 0:
            raise ValueError(f"shots must be positive, got {self.shots}")
        if self.batches <= 0:
            raise ValueError(f"batches must be positive, got {self.batches}")
        if self.score_iterations <= 0:
            raise ValueError(f"score_iterations must be positive, got {self.score_iterations}")

    # --- derived -------------------------------------------------------------
    @property
    def nelec(self) -> tuple[int, int]:
        """Electron count per spin sector."""
        return (self.num_electrons_a, self.num_electrons_b)

    @property
    def num_gradient_components(self) -> int:
        """Length of the flattened gradient: x, y and z for each atom."""
        return 3 * self.num_atoms

    def batch_artifact(self, kind: str, iteration: int, batch: int) -> str:
        """Path for a per-batch artifact, step-indexed when the step is known.

        The original pipeline wrote a fixed name per batch, so each MD step
        overwrote the previous one and only the final step survived. That is why
        per-frame wave-function data was unavailable afterwards. Including the
        step keeps every frame.
        """
        stem = f"{kind}-for-iter-{iteration}-batch-{batch}"
        if self.step is not None:
            stem = f"{kind}-for-step-{self.step}-iter-{iteration}-batch-{batch}"
        return os.path.join(self.results_dir, f"{stem}.txt")

    # --- construction --------------------------------------------------------
    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> RunConfig:
        """Build from a plain dict, rejecting unknown keys rather than ignoring them."""
        known = {field.name for field in dataclasses.fields(cls)}
        unknown = sorted(set(mapping) - known)
        if unknown:
            raise ValueError(
                f"unknown configuration key(s): {', '.join(unknown)}. "
                f"Known keys: {', '.join(sorted(known))}"
            )
        values = dict(mapping)
        if "job_tags" in values and values["job_tags"] is not None:
            values["job_tags"] = tuple(values["job_tags"])
        if not values.get("backend"):
            # Fall back to the environment, then to the empty string so that
            # __post_init__ raises the explanatory error. Leaving the key absent
            # would surface a bare TypeError about a missing argument instead.
            values["backend"] = os.environ.get(BACKEND_ENV_VAR, "")
        return cls(**values)

    @classmethod
    def from_yaml(cls, path: str) -> RunConfig:
        """Load from a YAML file."""
        import yaml  # imported here so that `import quantum_aimd` needs no extras

        with open(path, "r") as handle:
            loaded = yaml.safe_load(handle) or {}
        if not isinstance(loaded, dict):
            # ValueError, not TypeError: the CLI catches ValueError to report a
            # readable message, and a malformed config file is a bad value.
            raise ValueError(  # noqa: TRY004
                f"{path} must contain a mapping at the top level"
            )
        return cls.from_mapping(loaded)

    def to_mapping(self) -> dict[str, Any]:
        """Return a plain dict, suitable for writing next to the results."""
        return dataclasses.asdict(self)
