"""The S-CORE loop: measured bitstrings to energy, gradient and a QUICK file.

For each configuration-recovery iteration the measured bitstrings are
post-selected onto the correct electron number per spin sector, split into
batches, and each batch is diagonalized in its own recovered determinant
subspace. The orbital occupancies from one iteration refine the recovery in the
next. The energy of a step is the lowest across batches, and the gradient is the
one belonging to that batch, evaluated on the final iteration only.

Ray parallelizes the batches because each PySCF solve is single-threaded; it is
optional, and without it the batches run in sequence.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from quantum_aimd.config import RunConfig
from quantum_aimd.io.quick import (
    correlation_energy,
    extract_final_scf_energy,
    update_quick_out,
)

__all__ = ["StepResult", "run_score_loop", "write_step_output"]


class StepResult:
    """Outcome of one MD step.

    Attributes:
        energy: lowest batch energy at the final iteration, in Hartree.
        gradient: flattened nuclear gradient for that batch, in Hartree/Bohr.
        energy_history: per-iteration, per-batch energies.
        spin_history: per-iteration, per-batch total spin.
        subspace_dimensions: recovered subspace dimension per iteration and batch,
            the quantity that says whether the sampling spanned the full space.
        duration_seconds: wall-clock time of the loop.
    """

    def __init__(
        self,
        energy: float,
        gradient: np.ndarray,
        energy_history: np.ndarray,
        spin_history: np.ndarray,
        subspace_dimensions: np.ndarray,
        duration_seconds: float,
    ) -> None:
        self.energy = energy
        self.gradient = gradient
        self.energy_history = energy_history
        self.spin_history = spin_history
        self.subspace_dimensions = subspace_dimensions
        self.duration_seconds = duration_seconds


def _solve_batches(batches: list[Any], iteration: int, config: RunConfig) -> list[tuple]:
    """Diagonalize every batch, in parallel when ray is available."""
    from quantum_aimd.sqd.solver import solve_from_quick

    def solve(batch: Any) -> tuple:
        return solve_from_quick(
            batch,
            config.avas_orbitals,
            config.num_orbitals,
            iteration,
            config.score_iterations,
            open_shell=config.open_shell,
            spin_sq=config.spin_sq,
            max_davidson=config.max_davidson_cycles,
            quick_out=config.quick_out,
            quick_molden=config.quick_molden,
        )

    try:
        import ray
    except ImportError:
        return [solve(batch) for batch in batches]

    if not ray.is_initialized():
        ray.init(num_cpus=config.ray_num_cpus, log_to_driver=False)
    remote_solve = ray.remote(solve)
    return ray.get([remote_solve.remote(batch) for batch in batches])


def run_score_loop(counts: dict[str, int], config: RunConfig) -> StepResult:
    """Run configuration recovery and subspace diagonalization for one MD step."""
    from qiskit_addon_sqd.configuration_recovery import recover_configurations
    from qiskit_addon_sqd.counts import counts_to_arrays
    from qiskit_addon_sqd.fermion import (
        bitstring_matrix_to_ci_strs,
        flip_orbital_occupancies,
    )
    from qiskit_addon_sqd.subsampling import postselect_and_subsample

    start = time.time()
    bitstring_matrix_full, probs_arr_full = counts_to_arrays(counts)

    n_batches = config.batches
    n_iter = config.score_iterations
    norb = config.num_orbitals

    occupancies_bitwise = None
    e_hist = np.zeros((n_iter, n_batches))
    s_hist = np.zeros((n_iter, n_batches))
    dim_hist = np.zeros((n_iter, n_batches), dtype=int)
    gradient_hist = np.zeros((n_iter, config.num_gradient_components))
    lowest_energy = float("nan")

    for iteration in range(n_iter):
        print(f"Starting configuration recovery iteration {iteration}")

        if occupancies_bitwise is None:
            # Nothing known yet about occupancies: post-select the full set on
            # Hamming weight alone.
            bs_mat, probs = bitstring_matrix_full, probs_arr_full
        else:
            bs_mat, probs = recover_configurations(
                bitstring_matrix_full,
                probs_arr_full,
                occupancies_bitwise,
                config.num_electrons_a,
                config.num_electrons_b,
            )

        batches = postselect_and_subsample(
            bs_mat,
            probs,
            hamming_right=config.num_electrons_a,
            hamming_left=config.num_electrons_b,
            samples_per_batch=config.samples_per_batch,
            num_batches=n_batches,
        )

        for j, batch in enumerate(batches):
            ci_strs = bitstring_matrix_to_ci_strs(batch, open_shell=config.open_shell)
            dim_hist[iteration, j] = len(ci_strs[0]) * len(ci_strs[1])
            print(f"Subspace dimension for batch {j} is: {dim_hist[iteration, j]}")

        results = _solve_batches(list(batches), iteration, config)

        occs = np.zeros((n_batches, 2 * norb))
        gradients = np.zeros((n_batches, config.num_gradient_components))
        for j, (energy, sci_state, avg_occs, spin, gradient) in enumerate(results):
            e_hist[iteration, j] = energy
            s_hist[iteration, j] = spin
            occs[j, :norb] = avg_occs[0]
            occs[j, norb:] = avg_occs[1]
            if gradient is not None:
                gradients[j, :] = gradient

            np.savetxt(config.batch_artifact("address_list", iteration, j), batches[j])
            np.savetxt(config.batch_artifact("c", iteration, j), sci_state.amplitudes)

        avg_occupancy = np.mean(occs, axis=0)
        occupancies_bitwise = flip_orbital_occupancies(avg_occupancy)

        best = int(np.argmin(e_hist[iteration, :]))
        lowest_energy = float(np.min(e_hist[iteration, :]))
        gradient_hist[iteration, :] = gradients[best, :]

        print(f"Lowest energy batch: {best}")
        print(f"Lowest energy value: {lowest_energy}")
        print(
            "Calculated gradient for current step"
            if iteration == n_iter - 1
            else "Skipped gradient calculation for current step"
        )
        print("-----------------------------------")

    duration = time.time() - start
    print(f"SCI_solver totally takes: {duration} seconds")

    return StepResult(
        energy=lowest_energy,
        gradient=gradient_hist[n_iter - 1],
        energy_history=e_hist,
        spin_history=s_hist,
        subspace_dimensions=dim_hist,
        duration_seconds=duration,
    )


def write_step_output(result: StepResult, config: RunConfig) -> None:
    """Write the QUICK output that ``sander`` reads to advance the trajectory."""
    hf_energy = extract_final_scf_energy(config.quick_out)
    update_quick_out(
        config.quick_out,
        config.quick_out_modified,
        result.energy,
        result.gradient,
        hf_energy,
        correlation_energy(result.energy, hf_energy),
    )
