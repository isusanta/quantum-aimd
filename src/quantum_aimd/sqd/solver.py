"""Subspace diagonalization and analytical gradients from a QUICK reference.

Derived from Qiskit's `qiskit_addon_sqd.fermion` (Apache-2.0, (C) IBM 2024) and
modified for this project, as recorded in NOTICE. The modifications add a CASCI
kernel that diagonalizes inside a fixed determinant subspace supplied by S-CORE,
and evaluate the analytical nuclear gradient on the final iteration only.

Ported in substance unchanged. The QUICK output and molden paths are arguments
rather than fixed filenames; no device name and no credential appear here.
"""

# This code is a Qiskit project.
#
# (C) Copyright IBM 2024.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# Reminder: update the RST file in docs/apidocs when adding new interfaces.
"""Functions for the study of fermionic systems."""

from __future__ import annotations

import warnings

import numpy as np
from jax import Array, config, grad, jit, vmap
from jax import numpy as jnp
from jax.scipy.linalg import expm
from scipy import linalg as LA

# DSK Add imports needed for CASCI wrapper
from pyscf import ao2mo, gto, scf, fci
from pyscf.mcscf import avas, casci
from pyscf.solvent import pcm
from pyscf.lib import chkfile, logger

from qiskit_addon_sqd.fermion import SCIState, bitstring_matrix_to_ci_strs, _check_ci_strs

from quantum_aimd.io.quick import read_data_between_keywords, get_charges, get_coords

# DSK Below is the modified CASCI kernel compatible with SQD.
# It utilizes the "fci.selected_ci.kernel_fixed_space" 
# as well as enables passing the "batch" and "max_davidson" input arguments from "solve_solvent".
# The "batch" contains the CI addresses corresponding to subspaces derived from LUCJ and S-CORE calculations.
# The "max_davidson" controls the maximum number of cycles of Davidson's algorithm.

def kernel(casci, mo_coeff=None, ci0=None, verbose=logger.NOTE, envs=None):
    '''CASCI solver compatible with SQD.

    Args:
        casci: CASCI or CASSCF object.
        In case of SQD, only CASCI instance is currently incorporated.

        mo_coeff : ndarray
            orbitals to construct active space Hamiltonian.
            In context of SQD, these are either AVAS mo_coeff 
            or all of the MOs (with option to exclude core MOs).
    
        ci0 : ndarray or custom types FCI solver initial guess. 
            For SQD the usage of ci0 was not tested.
    
            For external FCI-like solvers, it can be
            overloaded different data type. For example, in the state-average
            FCI solver, ci0 is a list of ndarray. In other solvers such as
            DMRGCI solver, SHCI solver, ci0 are custom types.

    kwargs:
        envs: dict
            In case of SQD this option was not explored, 
            but in principle this can facilitate the incorporation of the external solvers.
    
            The variable envs is created (for PR 807) to passes MCSCF runtime
            environment variables to SHCI solver. For solvers which do not
            need this parameter, a kwargs should be created in kernel method
            and "envs" pop in kernel function.
    '''
    if mo_coeff is None: mo_coeff = casci.mo_coeff
    if ci0 is None: ci0 = casci.ci

    log = logger.new_logger(casci, verbose)
    t0 = (logger.process_clock(), logger.perf_counter())
    log.debug('Start CASCI')

    ncas = casci.ncas
    nelecas = casci.nelecas

    # The start of SQD version of kernel
    # DSK add the read of configurations for batch
    ci_strs_sqd = casci.batch
    
    # DSK add the input for the maximum number of cycles of Davidson's algorithm
    max_davidson = casci.max_davidson

    # DSK add electron up and down count and norb = ncas
    N_up = nelecas[0]
    N_dn = nelecas[1]
    norb = ncas

    # DSK Eignestate solver info
    sqd_verbose = verbose

    # DSK ERI read
    eri_cas = ao2mo.restore(1,casci.get_h2eff(),casci.ncas)
    t1 = log.timer('integral transformation to CAS space', *t0)

    # DSK 1e integrals
    h1eff, energy_core = casci.get_h1eff()
    log.debug('core energy = %.15g', energy_core)
    t1 = log.timer('effective h1e in CAS space', *t1)

    if h1eff.shape[0] != ncas:
        raise RuntimeError('Active space size error. nmo=%d ncore=%d ncas=%d' %
            (mo_coeff.shape[1], casci.ncore, ncas))

    # DSK fcisolver needs to be defined in accordance with SQD
    # in this software stack it is done in the "solve_solvent" portion of the code.
    myci = casci.fcisolver
    e_cas, sqdvec = fci.selected_ci.kernel_fixed_space(myci, h1eff, eri_cas, norb, (N_up,N_dn),
                                                       ci_strs=ci_strs_sqd, verbose = sqd_verbose, max_cycle = max_davidson)

    # DSK fcivec is the general name for CI vector assinged by PySCF.
    # Depending on type of solver it is either FCI or SCI vector.
    # In case of sqd we can call it "sqdvec" for clarity.
    # Nonetheless, for further processing PySCF expects
    # this data structure to be called fcivec, regardless of the used solver.

    fcivec = sqdvec

    t1 = log.timer('CI solver', *t1)
    e_tot = energy_core + e_cas

    # Returns either standard CASCI data or SQD data. Return depends on "sqd_run" True/False.
    return e_tot, e_cas, fcivec

# Replace standard CASCI kernel with the SQD-compatible CASCI kernel defined above
casci.kernel = kernel

from pyscf import tools, qmmm, mcscf

def solve_from_quick(
    bitstring_matrix: tuple[np.ndarray, np.ndarray] | np.ndarray,
    /,
    myavas: list,
    num_orbitals: int,
    i: int,
    iterations: int,
    *,
    open_shell: bool = False,
    spin_sq: int | None = None,
    max_davidson: int = 100,
    verbose: int | None = 0,
    quick_out: str = "QUICK_job.out",
    quick_molden: str = "QUICK_job.molden",
) -> tuple[float, SCIState, list[np.ndarray], float]:
    """Approximate the ground state given molecular integrals and a set of electronic configurations.

    Args:
        bitstring_matrix: A set of configurations defining the subspace onto which the Hamiltonian
            will be projected and diagonalized. This is a 2D array of ``bool`` representations of bit
            values such that each row represents a single bitstring. The spin-up configurations
            should be specified by column indices in range ``(N, N/2]``, and the spin-down
            configurations should be specified by column indices in range ``(N/2, 0]``, where ``N``
            is the number of qubits.

            (DEPRECATED) The configurations may also be specified by a length-2 tuple of sorted 1D
            arrays containing unsigned integer representations of the determinants. The two lists
            should represent the spin-up and spin-down orbitals, respectively.

        Interface with QUICK is established through QUICK output and molden files.
        At the moment the interface is dedicated to QM/MM SQD simulations, but can be combined with solve_solvent module
        to support SQD IEF-PCM simulations based on HF results from QUICK (as well PySCF-based HF). 

        Ultimately all functionalities can be merged in future "solve_custom" module, which will include:
        1) start from either checkpoint file (supports both PySCF-based or QUICK-based reference HF)
           or using the Molden and Output files of QUICK (this is the simulation specific to QUICK)
        2) SQD energy and gradient simulations both for gas phase, IEF-PCM, and QM/MM implementations

        myavas: This argument allows user to select active space in solute with AVAS.
                The corresponding list should include target atomic orbitals. 
                If myavas=None, then active space selected based on number of orbitals derivde from ci_strs.
                It is assumed that if myavas=None, then the target calculation is either
                a) corresponds to full basis case.
                b) close to full basis case and only few core orbitals are excluded.
        num_orbitals: Number of orbitals, which is essential when myavas = None. 
                In AVAS case number of orbitals and electrons is derived by AVAS procedure itself.
        i: Current iteration of S-CORE. Introduced to perform gradient calculation only on last step.
        iterations: Maximum number of S-CORE iterations requested by user. This is how code checks whether it is time
                        to calculate gradient or if it needs to be skipped on this iteration.
                        Calculating gradient only on last step of S-CORE improves computational efficiency.
        open_shell: A flag specifying whether configurations from the left and right
            halves of the bitstrings should be kept separate. If ``False``, CI strings
            from the left and right halves of the bitstrings are combined into a single
            set of unique configurations and used for both the alpha and beta subspaces.
        spin_sq: Target value for the total spin squared for the ground state.
            If ``None``, no spin will be imposed.
        max_davidson: The maximum number of cycles of Davidson's algorithm
        verbose: A verbosity level between 0 and 10

    Returns:
        - Minimum energy from SCI calculation
        - The SCI ground state
        - Average occupancy of the alpha and beta orbitals, respectively
        - Expectation value of spin-squared
        - Gradient on final S-CORE iterations; otherwise returns None for gradient.
          This is done to save computational time since calculation of gradient on each S-CORE iteration
          makes the whole calculation substantially more computationally expensive.

    """

    # DSK this part handles addresses
    if isinstance(bitstring_matrix, tuple):
        warnings.warn(
            "Passing the input determinants as integers is deprecated. Users should instead pass a bitstring matrix defining the subspace.",
            DeprecationWarning,
            stacklevel=2,
        )
        ci_strs = bitstring_matrix
    else:
        # This will become the default code path after the deprecation period.
        ci_strs = bitstring_matrix_to_ci_strs(bitstring_matrix, open_shell=open_shell)
    ci_strs = _check_ci_strs(ci_strs)

    num_up = format(ci_strs[0][0], "b").count("1")
    num_dn = format(ci_strs[1][0], "b").count("1")
    
    #DSK add 2S spin to check if UHF or RHF
    spin_2S = 2*abs(num_up-num_dn)
    verbose_ci = verbose
    
    # DSK collect MM charges from QUICK output file
    data_between_keywords = read_data_between_keywords(quick_out)
    data_between_keywords = data_between_keywords[ : -1]
    
    # Get the coords of MM point charges:
    coords = get_coords(data_between_keywords)
    
    # Coordinates of MM point charges need to be in tuple format.
    # Converting from 2D array to tuple below.
    list_of_coords_tuple = [tuple(row) for row in coords]
    
    # Get the magnitude of MM point charges:
    charges = get_charges(data_between_keywords)
    charges = np.array(charges)
    charges = charges.flatten()
    
    # DSK collect scf and mol data from QUICK molden file
    mol_in, mo_energy_array, mo_coeff_array, mo_occ_array, labels, spins = tools.molden.load(quick_molden)
    
    # DSK reconstruct mol object based on molden file information
    mol = mol_in

    # DSK; In bookending calculations we can transform from solution to gas phase (and other way around).
    # This transformation results in empty MM charges array in QUICK output in gas phase end point.
    # Code below checks if the current point has MM charges or if the array is empty.
    
    # DSK reconstruct converged RHF or UHF gas phase data. Vacuum end of bookending where MM charges
    # array from QUICK output file is empty.
    if len(list_of_coords_tuple) == 0:
       if spin_2S == 0:
          mf = scf.RHF(mol)
       else:
          mf = scf.UHF(mol)

    # DSK reconstruct converged RHF or UHF QM/MM data. When MM charges are present in QUICK calculations
    # the corresponding XYZ + Q arrays are not empty in external charges section.
    else:
       if spin_2S == 0:
          mf = qmmm.mm_charge(scf.RHF(mol), list_of_coords_tuple, charges)
       else:
          mf = qmmm.mm_charge(scf.UHF(mol), list_of_coords_tuple, charges)
    
    # DSK update mean-filed object (mf) with converged SCF information from molden file
    
    mf.mo_coeff = mo_coeff_array
    mf.mo_energy = mo_energy_array
    mf.mo_occ = mo_occ_array
    
    # DSK define active space based on AVAS or based on user input for number of orbitals
    if myavas is not None:
       ORBS = myavas
       AVAS = avas.AVAS(mf,ORBS,with_iao=True)
       AVAS.kernel()
       ncas, nelecas, mo, occ_weights, vir_weights = AVAS.ncas, AVAS.nelecas, AVAS.mo_coeff, AVAS.occ_weights, AVAS.vir_weights
    else:
       ncas = num_orbitals
       nelecas = (num_up, num_dn)
       
    # DSK set up CASCI object
    mc = mcscf.CASCI(mf, ncas=ncas,nelecas=nelecas)
    if myavas is not None:
       mc.mo_coeff = AVAS.mo_coeff
    mc.batch = ci_strs
    myci = fci.selected_ci.SelectedCI()
    if spin_sq is not None:
        myci = fci.addons.fix_spin_(myci, ss=spin_sq)
    mc.fcisolver = myci
    mc.verbose = verbose_ci
    mc.max_davidson = max_davidson
    
    mc_result = mc.kernel()
        
    # Get data out of CASCI object
    e_sci = mc_result[0]
    sci_vec = mc_result[2]
    
    # Calculate the avg occupancy of each orbital
    dm1 = myci.make_rdm1s(sci_vec, ncas, (num_up, num_dn))
    avg_occupancy = [np.diagonal(dm1[0]), np.diagonal(dm1[1])]

    # Compute total spin
    spin_squared = myci.spin_square(sci_vec, ncas, (num_up, num_dn))[0]

    # Convert the PySCF SCIVector to internal format. We access a private field here,
    # so we assert that we expect the SCIVector output from kernel_fixed_space to
    # have its _strs field populated with alpha and beta strings.
    assert isinstance(sci_vec._strs[0], np.ndarray) and isinstance(sci_vec._strs[1], np.ndarray)
    assert sci_vec.shape == (len(sci_vec._strs[0]), len(sci_vec._strs[1]))
    sci_state = SCIState(
        amplitudes=np.array(sci_vec), ci_strs_a=sci_vec._strs[0], ci_strs_b=sci_vec._strs[1]
    )

    # DSK perform the gradient calculation only if it is last S-CORE iteration
    if i == iterations-1:
       grad_nuclear = mc.Gradients()
       grad_result = grad_nuclear.kernel()
       # DSK flattened gradient is easier to store and it's format that is needed for interface with SANDER
       gradient = grad_result.flatten()
    else:
       gradient = None

    return e_sci, sci_state, avg_occupancy, spin_squared, gradient
