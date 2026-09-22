"""Circuit execution and measurement collection.

One job per MD step. The only thing that leaves this stage is a dictionary of
bitstring counts, which is the whole interface to the classical side: nothing
downstream knows or cares which device produced them.
"""

from __future__ import annotations

from typing import Any

from quantum_aimd.config import RunConfig

__all__ = ["build_sampler", "read_counts", "run_and_collect_counts", "write_counts"]


def build_sampler(backend: Any, config: RunConfig) -> Any:
    """Return a sampler configured with the run's error-suppression settings.

    Dynamical decoupling fills idle qubit windows; gate twirling randomizes
    coherent error into stochastic Pauli noise. Measurement twirling is left off:
    it applies to operator measurement, not to the computational-basis sampling
    this workflow does.
    """
    from qiskit_ibm_runtime import SamplerV2

    sampler = SamplerV2(mode=backend)
    sampler.options.dynamical_decoupling.enable = config.dynamical_decoupling
    sampler.options.twirling.enable_gates = config.twirl_gates
    sampler.options.twirling.enable_measure = config.twirl_measurement
    sampler.options.default_shots = config.shots
    if config.job_tags:
        sampler.options.environment = {"job_tags": list(config.job_tags)}
    return sampler


def run_and_collect_counts(transpiled: Any, backend: Any, config: RunConfig) -> dict[str, int]:
    """Submit the circuit and return the measured counts.

    Blocks on the result rather than spinning on the job status, so a queued job
    costs no local CPU.

    Raises:
        RuntimeError: if the job does not complete, carrying the job id so the
            run can be traced in the provider's records.
    """
    sampler = build_sampler(backend, config)
    job = sampler.run([transpiled])
    job_id = job.job_id()
    print(f">>> Job ID: {job_id}")

    try:
        result = job.result()
    except Exception as exc:
        raise RuntimeError(f"job {job_id} did not return a result: {exc}") from exc

    counts = result[0].data.meas.get_counts()
    print(f">>> Unique bitstrings: {len(counts)} from {config.shots} shots")
    return counts


def write_counts(counts: dict[str, int], path: str) -> None:
    """Write counts as JSON.

    The original pipeline wrote Python's ``repr`` of the dictionary, which reads
    back only after quote substitution. JSON is the same information without that
    step, and :func:`read_counts` accepts either so that existing run directories
    stay readable.
    """
    import json

    with open(path, "w") as handle:
        json.dump(counts, handle)


def read_counts(path: str) -> dict[str, int]:
    """Read a counts file written either as JSON or as a Python ``repr``."""
    import json

    with open(path, "r") as handle:
        text = handle.read().replace("\n", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Files written by the original pipeline use single quotes.
        return json.loads(text.replace("'", '"'))
