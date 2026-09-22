"""Runtime session lifecycle.

A trajectory runs hundreds of jobs, one per MD step, and a session keeps them
together in the queue instead of each step queueing from scratch. The session is
opened once before the trajectory, its id written to a file the per-step jobs
read, and closed once at the end.

No credential appears here; the service comes from :mod:`quantum_aimd.runtime.service`.
"""

from __future__ import annotations

from quantum_aimd.runtime.service import get_backend, get_service

__all__ = ["close_session", "open_session", "read_session_id"]


def open_session(backend_name: str, session_file: str = "session.txt") -> str:
    """Open a session on ``backend_name`` and record its id.

    Args:
        backend_name: device name from the run configuration.
        session_file: where to write the session id for the per-step jobs.

    Returns:
        The session id, also written to ``session_file``.
    """
    from qiskit_ibm_runtime import Session

    service = get_service()
    backend = get_backend(backend_name, service=service)
    session = Session(backend=backend)

    with open(session_file, "w") as handle:
        handle.write(session.session_id)
    return session.session_id


def read_session_id(session_file: str = "session.txt") -> str:
    """Return the session id recorded by :func:`open_session`.

    Raises:
        FileNotFoundError: if the file is absent, which means the session was
            never opened rather than that the id is empty.
    """
    with open(session_file, "r") as handle:
        session_id = handle.read().strip()
    if not session_id:
        raise ValueError(f"{session_file} is empty; no session id to resume")
    return session_id


def close_session(session_file: str = "session.txt") -> None:
    """Close the session recorded in ``session_file``.

    Leaving a session open holds the reservation, so this runs at the end of a
    trajectory whether or not the trajectory succeeded.
    """
    from qiskit_ibm_runtime import Session

    session_id = read_session_id(session_file)
    Session.from_id(session_id, get_service()).close()
