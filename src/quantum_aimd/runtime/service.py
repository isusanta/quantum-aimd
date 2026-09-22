"""Access to the quantum runtime.

**This module never accepts, stores, or logs a credential.** It constructs the
service with no arguments, which resolves the account you saved yourself with the
Qiskit tooling, outside this repository. There is no token parameter, no
environment variable read for a token, and no ``save_account`` call anywhere in
this package: see ``docs/ibm-quantum-setup.md``.

The device is likewise never named here. Callers pass a backend name that comes
from the run configuration, which is what allows the same code to target another
processor, or another platform, without an edit.
"""

from __future__ import annotations

from typing import Any

__all__ = ["get_backend", "get_service"]

_SETUP_HINT = (
    "Could not resolve a saved Qiskit account. Save one yourself, outside this "
    "repository, following docs/ibm-quantum-setup.md. This package deliberately "
    "accepts no token."
)


def get_service() -> Any:
    """Return a runtime service built from the locally saved account.

    Raises:
        RuntimeError: if no account resolves, with a pointer to the setup doc
            rather than an invitation to paste a token into a file.
    """
    from qiskit_ibm_runtime import QiskitRuntimeService

    try:
        return QiskitRuntimeService()
    except Exception as exc:
        raise RuntimeError(f"{_SETUP_HINT} Original error: {exc}") from exc


def get_backend(name: str, service: Any | None = None) -> Any:
    """Return the backend called ``name``.

    Args:
        name: device name from the run configuration. Required: this package
            ships no default device, so that no result is ever attributed to a
            processor by accident.
        service: an existing service, or ``None`` to build one.

    Raises:
        ValueError: if ``name`` is empty.
    """
    if not name:
        raise ValueError(
            "no backend name given. The device is a parameter of the run: pass "
            "--backend or set backend: in the configuration file."
        )
    return (service or get_service()).backend(name)
