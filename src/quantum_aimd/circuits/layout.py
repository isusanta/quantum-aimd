"""Noise-aware zigzag qubit layout for LUCJ circuits on heavy-hex hardware.

Ported unchanged in substance from the project's `auto_lucj_map.py`. The only
behavioural change is that the FCIDUMP path is an argument instead of the fixed
name `fci_dump.txt`, and the backend is named by the caller: this module contains
no device name and no credential.
"""

import copy
from typing import Sequence

import rustworkx
from qiskit.providers import BackendV2
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke, FakeTorino
from rustworkx import NoEdgeBetweenNodes, PyGraph

IBM_TWO_Q_GATES = {"cx", "ecr", "cz"}

import ffsim
import numpy as np
from pyscf import ao2mo, cc, tools
from qiskit import QuantumCircuit, QuantumRegister
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService

CONNECT_AT_EVERY_N_TH_QUBIT_HEAVY_HEX = 4

def create_linear_chains(num_orbitals: int) -> PyGraph:
    """In zig-zag layout, there are two linear chains (with connecting qubits between
    the chains). This function creates those two linear chains: a rustworkx PyGraph
    with two disconnected linear chains. Each chain contains `num_orbitals` number
    of nodes, i.e., in the final graph there are `2 * num_orbitals` number of nodes.

    Args:
        num_orbitals (int): Number orbitals or nodes in each linear chain. They are
            also known as alpha-alpha interaction qubits.

    Returns:
        A rustworkx.PyGraph with two disconnected linear chains each with `num_orbitals`
            number of nodes.
    """
    G = rustworkx.PyGraph()

    for n in range(num_orbitals):
        G.add_node(n)

    for n in range(num_orbitals - 1):
        G.add_edge(n, n + 1, None)

    for n in range(num_orbitals, 2 * num_orbitals):
        G.add_node(n)

    for n in range(num_orbitals, 2 * num_orbitals - 1):
        G.add_edge(n, n + 1, None)

    return G


def create_lucj_zigzag_layout(
    num_orbitals: int, backend_coupling_graph: PyGraph
) -> tuple[PyGraph, int]:
    """This function creates the complete zigzag graph that 'can be mapped' to a IBM QPU with
    heavy-hex connectivity (the zigzag must be an isomorphic sub-graph to the QPU/backend
    coupling graph for it to be mapped).
    The zigzag pattern includes both linear chains (alpha-alpha interactions) and connecting
    qubits between the linear chains (alpha-beta interactions).

    Args:
        num_orbitals (int): Number of orbitals, i.e., number of nodes in each alpha-alpha linear chain.
        backend_coupling_graph (PyGraph): The coupling graph of the backend on which the LUCJ ansatz
            will be mapped and run. This function takes the coupling graph as a undirected
            `rustworkx.PyGraph` where there is only one 'undirected' edge between two nodes,
            i.e., qubits. Usually, the coupling graph of a IBM backend is directed (e.g., Eagle devices
            such as ibm_sherbrooke) or may have two edges between two nodes (e.g., Heron `ibm_torino`).
            A user needs to be make such graphs undirected and/or remove duplicate edges to make them
            compatible with this function. One way to do this is as follows:
            ```
            graph = backend.coupling_map.graph
            if not graph.is_symmetric():
                graph.make_symmetric()
            backend_coupling_graph = graph.to_undirected()

            edge_list = backend_coupling_graph.edge_list()
            removed_edge = []
            for edge in edge_list:
                if set(edge) in removed_edge:
                    continue
                try:
                    backend_coupling_graph.remove_edge(edge[0], edge[1])
                    removed_edge.append(set(edge))
                except NoEdgeBetweenNodes:
                    pass
            ```

    Returns:
        G_new (PyGraph): The graph with IBM backend compliant zigzag pattern.
        num_alpha_beta_qubits (int): Number of connecting qubits between the linear chains
            in the zigzag pattern. While we want as many connecting (alpha-beta) qubits between
            the linear (alpha-alpha) chains, we cannot accomodate all due to qubit and connectivity
            constraints of backends. This is the maximum number of connecting qubits the zigzag pattern
            can have while being backend compliant (i.e., isomorphic to backend coupling graph).
    """
    isomorphic = False
    G = create_linear_chains(num_orbitals=num_orbitals)

    num_iters = copy.deepcopy(num_orbitals)
    while not isomorphic:
        G_new = copy.deepcopy(G)
        num_alpha_beta_qubits = 0
        for n in range(num_iters):
            if n % 4 == 0:
                new_node = 2 * num_orbitals + num_alpha_beta_qubits
                G_new.add_node(new_node)
                G_new.add_edge(n, new_node, None)
                G_new.add_edge(new_node, n + num_orbitals, None)
                num_alpha_beta_qubits = num_alpha_beta_qubits + 1
        isomorphic = rustworkx.is_subgraph_isomorphic(backend_coupling_graph, G_new)
        num_iters -= 1

    return G_new, num_alpha_beta_qubits


def lightweight_layout_error_scoring(
    backend: BackendV2,
    virtual_edges: Sequence[Sequence[int]],
    physical_layouts: Sequence[int],
    two_q_gate_name: str,
) -> list[list[list[int], float]]:
    """Lighweight and heuristic function to score isomorphic layouts. There can be many zigzag patterns,
    each with different set of physical qubits, that can be mapped to a backend. Some of them may
    include less noise qubits and couplings than others. This function computes a simple error score
    for each such layout. It sums up 2Q gate error for all couplings in the zigzag pattern (layout) and
    meaurement of errors of physical qubits in the layout to compute the error score.

    Note:
        This lightweight scoring can be refined using concepts such as mapomatic.

    Args:
        backend (BackendV2): A backend.
        virtual_edges (Sequence[Sequence[int]]): Edges in the device compliant zigzag pattern where
            nodes are numbered from 0 to (2 * num_orbitals + num_alpha_beta_qubits).
        physical_layouts (Sequence[int]): All physical layouts of the zigzag pattern that are isomorphic
            to each other and to the larger backend coupling map.
        two_q_gate_name (str): The name of the two-qubit gate of the backend. The name is used for fecthing
            two-qubit gate error from backend properties.

    Returns:
        scores (list): A list of lists where each sublist contains two items. First item is the layout, and
            second item is a float representing error score of the layout. The layouts in the `scores` are
            sorted in the ascedning order of error score.
    """
    props = backend.properties()
    scores = []
    for layout in physical_layouts:
        total_2q_error = 0
        for edge in virtual_edges:
            physical_edge = (layout[edge[0]], layout[edge[1]])
            try:
                ge = props.gate_error(two_q_gate_name, physical_edge)
            except:
                ge = props.gate_error(two_q_gate_name, physical_edge[::-1])
            total_2q_error += ge
        total_measurement_error = 0
        for qubit in layout:
            meas_error = props.readout_error(qubit)
            total_measurement_error += meas_error
        scores.append([layout, total_2q_error + total_measurement_error])

    return sorted(scores, key=lambda x: x[1])


def _make_backend_cmap_pygraph(backend: BackendV2) -> PyGraph:
    graph = backend.coupling_map.graph
    if not graph.is_symmetric():
        graph.make_symmetric()
    backend_coupling_graph = graph.to_undirected()

    edge_list = backend_coupling_graph.edge_list()
    removed_edge = []
    for edge in edge_list:
        if set(edge) in removed_edge:
            continue
        try:
            backend_coupling_graph.remove_edge(edge[0], edge[1])
            removed_edge.append(set(edge))
        except NoEdgeBetweenNodes:
            pass

    return backend_coupling_graph


def get_zigzag_physical_layout(
    num_orbitals: int, backend: BackendV2, score_layouts: bool = True
) -> tuple[list[int], int]:
    """The main function that generates the zigzag pattern with physical qubits that can be used
    as an `intial_layout` in a preset passmanager/transpiler.

    Args:
        num_orbitals (int): Number of orbitals.
        backend (BackendV2): A backend.
        score_layouts (bool): Optional. If `True`, it uses the `lightweight_layout_error_scoring`
            function to score the isomorphic layouts and returns the layout with less errorneous qubits.
            If `False`, returns the first isomorphic subgraph.

    Returns:
        A tuple of device compliant layout (list[int]) with zigzag pattern and an int representing
            number of alpha-beta-interactions.
    """
    backend_coupling_graph = _make_backend_cmap_pygraph(backend=backend)

    G, num_aplha_beta_qubits = create_lucj_zigzag_layout(
        num_orbitals=num_orbitals, backend_coupling_graph=backend_coupling_graph
    )

    isomorphic_mappings = rustworkx.vf2_mapping(
        backend_coupling_graph, G, subgraph=True
    )
    isomorphic_mappings = list(isomorphic_mappings)

    edges = list(G.edge_list())

    layouts = []
    for mapping in isomorphic_mappings:
        initial_layout = [None] * (2 * num_orbitals + num_aplha_beta_qubits)
        for key, value in mapping.items():
            initial_layout[value] = key
        layouts.append(initial_layout)

    two_q_gate_name = IBM_TWO_Q_GATES.intersection(
        backend.configuration().basis_gates
    ).pop()

    if score_layouts:
        scores = lightweight_layout_error_scoring(
            backend=backend,
            virtual_edges=edges,
            physical_layouts=layouts,
            two_q_gate_name=two_q_gate_name,
        )

        return scores[0][0][:-num_aplha_beta_qubits], num_aplha_beta_qubits

    return layouts[0][:-num_aplha_beta_qubits], num_aplha_beta_qubits


def prepare_lucj(backend_choice: str, fcidump_path: str = "fci_dump.txt"):
    """Return the optimal physical layout for the LUCJ circuit.

    Args:
        backend_choice: backend name, supplied by the caller. There is no
            default: the device is a parameter of the calculation, not a
            property of this code.
        fcidump_path: FCIDUMP written by the active-space stage.
    """
    # -----------------------------------------------------------------------------------#
    # read FCIDUMP                                                                      #
    # -----------------------------------------------------------------------------------#
    mf_as = tools.fcidump.to_scf(fcidump_path)
    num_orbitals = norb = mf_as.mol.nao
    nela = mf_as.mol.nelectron//2
    nelec = (nela,nela)
    dm0 = np.zeros((norb,norb))
    for i in range(mf_as.mol.nelectron//2): dm0[i,i]= 2.0
    hf = mf_as.kernel(dm0=dm0)

    mc  = cc.CCSD(mf_as)
    mc.kernel()
    t1 = mc.t1
    t2 = mc.t2

    h0e = mf_as.mol.energy_nuc()
    h1e = mf_as.get_hcore()
    h2e = ao2mo.restore(1,mf_as._eri,norb)

    # Main part: generate the zig-zag layout automatically
    # You only need to supply `backend`

    backend = QiskitRuntimeService().backend(backend_choice)
    
    initial_layout, num_alpha_beta_qubits = get_zigzag_physical_layout(
        num_orbitals, backend,
        score_layouts=False # can be `False` as we will do error scoring later
    )

    two_q_gate_name = IBM_TWO_Q_GATES.intersection(
        backend.configuration().basis_gates
    ).pop()

    # Create test LUCJ circuit
    n_reps = 1
    alpha_alpha_indices = [(p, p + 1) for p in range(num_orbitals - 1)]
    alpha_beta_indices = [
        (p, p) for p in range(0, num_orbitals, CONNECT_AT_EVERY_N_TH_QUBIT_HEAVY_HEX)
        if p < CONNECT_AT_EVERY_N_TH_QUBIT_HEAVY_HEX * num_alpha_beta_qubits
    ]

    ucj_op = ffsim.UCJOpSpinBalanced.from_t_amplitudes(
        t2=t2,
        t1=t1,
        n_reps=n_reps,
        interaction_pairs=(alpha_alpha_indices, alpha_beta_indices),
    )

    # create an empty quantum circuit
    qubits = QuantumRegister(2 * num_orbitals, name="q")
    circuit = QuantumCircuit(qubits)

    # prepare Hartree-Fock state as the reference state and append it to the quantum circuit
    circuit.append(ffsim.qiskit.PrepareHartreeFockJW(num_orbitals, nelec), qubits)

    # apply the UCJ operator to the reference state
    circuit.append(ffsim.qiskit.UCJOpSpinBalancedJW(ucj_op), qubits)
    circuit.measure_all()


    # Testing number of 2Q gates with or without the zigzag initial layout
    pm = generate_preset_pass_manager(
        optimization_level=3, backend=backend, initial_layout=initial_layout
    )
    pm.pre_init = ffsim.qiskit.PRE_INIT

    
    # When we explicitly set `initial_layout` in a preset pass manager,
    # it disables `Vf2PostLayout`. `Vf2PostLayout` is the pass that maps
    # a quantum circuit to less noisy quibts after layout.
    # The following code-block explicitly adds the `VF2PostLayout` pass
    # to the routing stage (followed by `ApplyLayout` pass. `VF2PostLayout`
    # tries to find a less noisy mapping/layout and `ApplyLayout` applies
    # that to the circuit).
    # By having both (explicit) `initial_layout` and `VF2PostLayout` in
    # our pass manager, we can adhere to the zigzag pattern and select less
    # noisy qubits at the same time.
    from qiskit.transpiler.passes import VF2PostLayout, ApplyLayout
    from qiskit.passmanager.flow_controllers import ConditionalController
    from qiskit.transpiler import PassManager
    
    from typing import Any
    from qiskit.transpiler.preset_passmanagers.common import _apply_post_layout_condition
    
    def _custom_apply_post_layout_condition(property_set: dict[str, Any]) -> bool:
        return property_set["post_layout"] is not None
    
    # `ConditionalController` applies the `ApplyLayout` pass only if a condition
    # is met. In this case, the condition is whether the `"post_layout"` field
    # in the pass manager `property_set` is True or not.
    # `VF2PostLayout` tries to find a better solution (i.e., better set of qubits).
    # If it finds a better solution, it sets the `property_set["post_layout"]` with
    # the better solution. However, it can happen that the existing layout is already
    # the best, and `VF2PostLayout` does not find any (better) solution. In such a case,
    # no `property_set["post_layout"]` will be set.
    # Therefore, the `ApplyLayout` will only be applied if there is a new and better
    # layout found by the `VF2PostLayout`.
    pm.routing.append(VF2PostLayout(target=backend.target, strict_direction=False))
    pm.routing.append(
        ConditionalController(
            ApplyLayout(),
            condition=_custom_apply_post_layout_condition
        )
    )

    isa_circuit_vf2 = pm.run(circuit)
    num_2q_1 = isa_circuit_vf2.count_ops()[two_q_gate_name]

    optimal_layout = isa_circuit_vf2.layout.initial_index_layout()[:2 * num_orbitals]

    # # Qiskit transpiler without explicit zigzag layout
    # pm = generate_preset_pass_manager(
    #     optimization_level=3,
    #     backend=backend,
    # )
    # pm.pre_init = ffsim.qiskit.PRE_INIT
    # isa_circuit2 = pm.run(circuit)
    # num_2q_2 = isa_circuit2.count_ops()[two_q_gate_name]
    # print(f"Num 2Q gates without zig-zag layout: {num_2q_2}")
    
    return optimal_layout
