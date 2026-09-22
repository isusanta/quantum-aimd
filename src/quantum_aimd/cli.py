"""Command-line entry point.

One subcommand per stage of an MD step, so each can be run and inspected on its
own and so the MD driver can call exactly the stage it needs:

    quantum-aimd session open   --backend NAME     once per trajectory
    quantum-aimd active-space                      per step: FCIDUMP from QUICK
    quantum-aimd layout        --backend NAME      once per system and device
    quantum-aimd sample        --backend NAME      per step: execute the circuit
    quantum-aimd solve                             per step: energy and gradient
    quantum-aimd session close                     once per trajectory

No subcommand takes a credential, and none has a default device.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import BACKEND_ENV_VAR, RunConfig

PRE_RELEASE_NOTICE = (
    f"PRE-RELEASE (v{__version__}): the interfaces are not stable. Stages that "
    "contact hardware need a Qiskit account you saved yourself, outside this "
    "repository; see docs/ibm-quantum-setup.md."
)


def _load_config(args: argparse.Namespace) -> RunConfig:
    """Build the run configuration from a file, then apply CLI overrides."""
    base = RunConfig.from_yaml(args.config).to_mapping() if args.config else {}
    for key in ("backend", "shots", "step", "num_orbitals", "num_atoms"):
        value = getattr(args, key, None)
        if value is not None:
            base[key] = value
    return RunConfig.from_mapping(base)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="YAML run configuration")
    parser.add_argument(
        "--backend",
        help=f"device name; required unless set in --config or ${BACKEND_ENV_VAR}",
    )
    parser.add_argument("--shots", type=int, help="shots for this MD step")
    parser.add_argument("--step", type=int, help="MD step index; keeps per-step artifacts distinct")
    parser.add_argument("--num-orbitals", type=int, dest="num_orbitals")
    parser.add_argument("--num-atoms", type=int, dest="num_atoms")


def cmd_session_open(args: argparse.Namespace) -> int:
    config = _load_config(args)

    from .runtime.session import open_session

    session_id = open_session(config.backend, config.session_file)
    print(f"session open; id written to {config.session_file}")
    print(f"session id: {session_id}")
    return 0


def cmd_session_close(args: argparse.Namespace) -> int:
    config = _load_config(args)

    from .runtime.session import close_session

    close_session(config.session_file)
    print("session closed")
    return 0


def cmd_active_space(args: argparse.Namespace) -> int:
    config = _load_config(args)

    from .chemistry.active_space import prepare_active_space

    norb = prepare_active_space(
        config.quick_out, config.quick_molden, config.fcidump, config.avas_orbitals
    )
    print(f"active space: {norb} orbitals; FCIDUMP written to {config.fcidump}")
    return 0


def cmd_layout(args: argparse.Namespace) -> int:
    config = _load_config(args)

    import numpy as np

    from .circuits.layout import prepare_lucj

    optimal_layout = prepare_lucj(config.backend, config.fcidump)
    np.save(config.layout, optimal_layout)
    print(f"layout for {config.backend}: {optimal_layout}")
    print(f"saved to {config.layout}")
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    config = _load_config(args)

    import numpy as np

    from .circuits.lucj import build_lucj_circuit, ccsd_amplitudes, transpile_for
    from .runtime.sampler import run_and_collect_counts, write_counts
    from .runtime.service import get_backend

    t2, norb, nelec = ccsd_amplitudes(config.fcidump)
    circuit = build_lucj_circuit(t2, norb, nelec, n_reps=config.n_reps)

    backend = get_backend(config.backend)
    transpiled = transpile_for(
        circuit,
        backend,
        np.load(config.layout),
        optimization_level=config.optimization_level,
    )
    two_qubit_depth = transpiled.depth(lambda instruction: instruction[0].name == "ecr")
    print(
        f"transpiled: {transpiled.count_ops()}, depth {transpiled.depth()}, "
        f"two-qubit depth {two_qubit_depth}"
    )

    counts = run_and_collect_counts(transpiled, backend, config)
    write_counts(counts, config.counts)
    print(f"counts written to {config.counts}")
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    config = _load_config(args)

    from .runtime.sampler import read_counts
    from .sqd.driver import run_score_loop, write_step_output

    counts = read_counts(config.counts)
    result = run_score_loop(counts, config)
    write_step_output(result, config)
    print(f"energy {result.energy:.9f} Hartree")
    print(f"gradient written to {config.quick_out_modified}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantum-aimd",
        description="Quantum-centric ab initio molecular dynamics with SQD.",
        epilog=PRE_RELEASE_NOTICE,
    )
    parser.add_argument("--version", action="version", version=f"quantum-aimd {__version__}")
    sub = parser.add_subparsers(dest="command")

    session = sub.add_parser("session", help="open or close a runtime session")
    session_sub = session.add_subparsers(dest="session_command")
    for name, handler, help_text in (
        ("open", cmd_session_open, "open a session and record its id"),
        ("close", cmd_session_close, "close the recorded session"),
    ):
        child = session_sub.add_parser(name, help=help_text)
        _add_common(child)
        child.set_defaults(handler=handler)

    for name, handler, help_text in (
        ("active-space", cmd_active_space, "build the FCIDUMP from QUICK output"),
        ("layout", cmd_layout, "choose the qubit layout for this system and device"),
        ("sample", cmd_sample, "execute the LUCJ circuit and store the counts"),
        ("solve", cmd_solve, "recover the subspace, then the energy and gradient"),
    ):
        child = sub.add_parser(name, help=help_text)
        _add_common(child)
        child.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        # Bare invocation prints help rather than implying work was done.
        parser.print_help()
        print(f"\n{PRE_RELEASE_NOTICE}", file=sys.stderr)
        return 0

    try:
        return handler(args)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
