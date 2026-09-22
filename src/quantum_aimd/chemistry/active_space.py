"""Active-space Hamiltonian from a QUICK/molden reference.

Each MD step, QUICK writes the converged Hartree-Fock reference and the MM point
charges that embed the QM region. This module rebuilds the PySCF mean-field
object from those, projects the Hamiltonian onto the active space, and writes the
FCIDUMP that the circuit and solver stages consume.

The published runs used the complete STO-3G manifold of the solute as the active
space, with all electrons active and no frozen core, which is why full
configuration interaction in that space is the exact reference.

PySCF is imported inside the functions so that ``import quantum_aimd`` stays
free of the scientific stack, which keeps the offline test suite and CI runnable
with no entitlements and no heavy install.
"""

from __future__ import annotations

from typing import Any

from quantum_aimd.io.quick import read_mm_charges

__all__ = ["build_casci", "build_mean_field", "prepare_active_space", "write_fcidump"]


def build_mean_field(quick_out: str, quick_molden: str) -> Any:
    """Rebuild the embedded Hartree-Fock reference for one MD step.

    The molecular orbitals are taken from the molden file rather than recomputed,
    so the active space is the one QUICK converged. When the step has MM point
    charges, they enter as an external electrostatic potential through PySCF's
    QM/MM one-electron integral modification; with no charges the same call gives
    the gas-phase reference, which is what the vacuum trajectories used.

    Args:
        quick_out: QUICK output for this step, holding the point-charge block.
        quick_molden: molden file with the converged orbitals.

    Returns:
        A PySCF mean-field object carrying the stored orbitals.
    """
    from pyscf import qmmm, scf, tools

    coords, charges = read_mm_charges(quick_out)
    mol, mo_energy, mo_coeff, mo_occ, _labels, _spins = tools.molden.load(quick_molden)

    mf = scf.RHF(mol)
    if len(charges):
        mf = qmmm.mm_charge(mf, [tuple(row) for row in coords], charges)

    # Adopt the converged solution rather than re-running the SCF.
    mf.mo_coeff = mo_coeff
    mf.mo_energy = mo_energy
    mf.mo_occ = mo_occ
    return mf


def build_casci(mf: Any, avas_orbitals: list[str] | None = None) -> Any:
    """Return a CASCI object for the active space.

    With ``avas_orbitals`` the active space is selected by AVAS from the named
    atomic orbitals. Without it the complete manifold is used, all electrons
    active, which is the setting the published trajectories ran in.
    """
    from pyscf import mcscf
    from pyscf.mcscf import avas as avas_module

    if avas_orbitals is not None:
        avas_obj = avas_module.AVAS(mf, avas_orbitals, with_iao=True)
        avas_obj.kernel()
        mc = mcscf.CASCI(mf, ncas=avas_obj.ncas, nelecas=avas_obj.nelecas)
        mc.mo_coeff = avas_obj.mo_coeff
        return mc

    return mcscf.CASCI(mf, ncas=mf.mol.nao, nelecas=mf.mol.nelec)


def write_fcidump(mc: Any, path: str) -> int:
    """Write the active-space Hamiltonian as a FCIDUMP and return its dimension.

    The FCIDUMP is the interface between this stage and everything downstream:
    the layout search, the LUCJ amplitudes and the subspace solver all read it,
    so they need no knowledge of QUICK or of the MM environment.
    """
    from pyscf import ao2mo, tools

    h1e_cas, ecore = mc.get_h1eff()
    h2e_cas = ao2mo.restore(1, mc.get_h2eff(), mc.ncas)
    tools.fcidump.from_integrals(
        path,
        h1e_cas,
        h2e_cas,
        mc.ncas,
        mc.nelecas,
        nuc=ecore,
        ms=0,
        orbsym=[1] * mc.ncas,
    )
    return int(mc.ncas)


def prepare_active_space(
    quick_out: str,
    quick_molden: str,
    fcidump: str,
    avas_orbitals: list[str] | None = None,
) -> int:
    """Run the whole stage: reference, active space, FCIDUMP.

    Returns:
        The number of active orbitals, which fixes the qubit count at ``2 * n``
        plus the auxiliary qubits the LUCJ layout adds.
    """
    mf = build_mean_field(quick_out, quick_molden)
    mc = build_casci(mf, avas_orbitals=avas_orbitals)
    norb = write_fcidump(mc, fcidump)
    return norb
