"""LUCJ circuit construction.

The local unitary cluster Jastrow ansatz is built from CCSD amplitudes computed
in the active space, with the interaction pairs restricted to what the heavy-hex
connectivity supports: nearest-neighbour pairs within each spin chain, and a
sparse set of alpha-beta pairs bridged by auxiliary qubits.

Heavy imports are function-local, so importing this module costs nothing.
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["build_lucj_circuit", "ccsd_amplitudes", "interaction_pairs", "transpile_for"]


def ccsd_amplitudes(fcidump: str) -> tuple[Any, int, tuple[int, int]]:
    """Return ``(t2, norb, nelec)`` from a CCSD calculation in the active space.

    The doubles amplitudes parameterise the ansatz. The Hartree-Fock guess is
    built explicitly as a diagonal density rather than left to PySCF's default,
    because the FCIDUMP carries no molecular structure to guess from.
    """
    from pyscf import cc, tools

    mf_as = tools.fcidump.to_scf(fcidump)
    norb = int(mf_as.mol.nao)
    nela = mf_as.mol.nelectron // 2
    nelec = (nela, nela)

    dm0 = np.zeros((norb, norb))
    for i in range(nela):
        dm0[i, i] = 2.0
    mf_as.kernel(dm0=dm0)

    ccsd = cc.CCSD(mf_as)
    ccsd.kernel()
    return ccsd.t2, norb, nelec


def interaction_pairs(norb: int) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Return the ``(alpha_alpha, alpha_beta)`` interaction pairs for ``norb``.

    Alpha-alpha pairs are nearest neighbours along each spin chain. Alpha-beta
    pairs are placed every fourth orbital: on a heavy-hex lattice each one needs
    an auxiliary qubit to bridge the two chains, so a denser choice would cost
    more two-qubit depth than it returns.
    """
    alpha_alpha = [(p, p + 1) for p in range(norb - 1)]
    alpha_beta = [(p, p) for p in range(0, norb, 4)]
    return alpha_alpha, alpha_beta


def build_lucj_circuit(t2: Any, norb: int, nelec: tuple[int, int], n_reps: int = 2) -> Any:
    """Return the measured LUCJ circuit for the given amplitudes.

    The circuit prepares the Hartree-Fock state under Jordan-Wigner, applies the
    spin-balanced LUCJ operator, and measures every qubit: the measured
    bitstrings are the only thing the classical stages consume.
    """
    import ffsim
    from qiskit import QuantumCircuit, QuantumRegister

    ucj_op = ffsim.UCJOpSpinBalanced.from_t_amplitudes(
        t2, n_reps=n_reps, interaction_pairs=interaction_pairs(norb)
    )

    qubits = QuantumRegister(2 * norb, name="q")
    circuit = QuantumCircuit(qubits)
    circuit.append(ffsim.qiskit.PrepareHartreeFockJW(norb, nelec), qubits)
    circuit.append(ffsim.qiskit.UCJOpSpinBalancedJW(ucj_op), qubits)
    circuit.measure_all()
    return circuit


def transpile_for(
    circuit: Any,
    backend: Any,
    initial_layout: Any,
    optimization_level: int = 3,
) -> Any:
    """Transpile the circuit onto a backend using a fixed initial layout.

    The layout comes from the layout-selection stage and is reused for every step
    of a trajectory, so that circuit structure is constant and only the
    amplitudes change from step to step.
    """
    import ffsim
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

    pass_manager = generate_preset_pass_manager(
        optimization_level=optimization_level,
        backend=backend,
        initial_layout=initial_layout,
    )
    pass_manager.pre_init = ffsim.qiskit.PRE_INIT
    return pass_manager.run(circuit)
