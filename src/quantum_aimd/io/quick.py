"""Reading and writing QUICK output.

QUICK is the QM engine that AMBER's ``sander`` drives. Each MD step it writes an
output file holding the QM geometry, the MM point charges that embed it, and the
SCF result; this module reads those, and writes the file back with the SQD energy
and analytical gradient in place of the Hartree-Fock ones so that ``sander`` can
take the next step.

Everything here is pure text and array handling: no quantum dependency, no device
name, no credential. That is deliberate, so the parsing can be tested offline.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

__all__ = [
    "MM_SECTION_END",
    "MM_SECTION_START",
    "correlation_energy",
    "extract_final_scf_energy",
    "get_charges",
    "get_coords",
    "read_data_between_keywords",
    "read_mm_charges",
    "update_quick_out",
]

MM_SECTION_START = "EXTERNAL POINT CHARGES: (X,Y,Z,Q)"
MM_SECTION_END = "DISTANCE MATRIX"

_SCF_TABLE_START = "| NCYC       ENERGY"
_SCF_TABLE_END = "| REACH CONVERGENCE"
_SCF_ROW = re.compile(r"\|\s*\d+\s+(-\d+\.\d+)")

# Written verbatim into the output, so the column positions match QUICK's own.
_TOTAL_ENERGY_KEY = " TOTAL ENERGY         ="
_METHOD_KEY = "METHOD = HATREE FOCK"  # QUICK's own spelling; do not "correct" it

# Used only to find the blocks. These stay as specific as the literal strings
# they replace, matching the whole assignment and the whole header line, and
# differ only in tolerating surrounding whitespace: QUICK writes a trailing
# space after the gradient header, and a file that has passed through an editor
# may not keep it. A loose substring match is deliberately avoided, because this
# function rewrites the file the MD driver reads, so matching the wrong line
# would corrupt a step rather than merely fail.
_TOTAL_ENERGY_RE = re.compile(r"^\s*TOTAL ENERGY\s*=")
_GRADIENT_RE = re.compile(r"^\s*ANALYTICAL GRADIENT:\s*$")


def read_data_between_keywords(filename: str) -> list[list[float]]:
    """Return the external point-charge block as rows of floats.

    Each row is ``[x, y, z, q]``, with coordinates in the same frame and units as
    the QM geometry in the same file.

    The blank line that QUICK leaves before ``DISTANCE MATRIX`` is returned as a
    trailing empty row. That is preserved on purpose: callers ported from the
    original pipeline drop it with ``[:-1]``, and silently removing it here would
    discard a real charge instead. New code should prefer :func:`read_mm_charges`.
    """
    data: list[list[float]] = []
    reading = False
    with open(filename, "r") as handle:
        for line in handle:
            if MM_SECTION_START in line:
                reading = True
                continue
            if MM_SECTION_END in line:
                reading = False
            if reading:
                data.append([float(value) for value in line.split()])
    return data


def read_mm_charges(filename: str) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(coords, charges)`` for the embedding point charges.

    ``coords`` has shape ``(n, 3)`` and ``charges`` shape ``(n,)``, with blank and
    malformed rows dropped. This is the accessor new code should use; it has no
    trailing-row convention to remember.
    """
    rows = [row for row in read_data_between_keywords(filename) if len(row) == 4]
    if not rows:
        return np.zeros((0, 3)), np.zeros((0,))
    table = np.asarray(rows, dtype=float)
    return table[:, :3], table[:, 3]


def extract_final_scf_energy(filename: str) -> float:
    """Return the converged Hartree-Fock energy from the SCF cycle table.

    QUICK prints one row per cycle; the last row before convergence is the
    converged value.

    Raises:
        ValueError: if the file holds no SCF table, which means the QM step did
            not run rather than that the energy is zero.
    """
    energy: float | None = None
    in_table = False
    with open(filename, "r") as handle:
        for line in handle:
            if _SCF_TABLE_START in line:
                in_table = True
                continue
            if _SCF_TABLE_END in line:
                in_table = False
            if in_table:
                match = _SCF_ROW.search(line)
                if match:
                    energy = float(match.group(1))
    if energy is None:
        raise ValueError(f"no SCF energy table found in {filename}")
    return energy


def get_coords(array_2d: Sequence[Sequence[float]]) -> list[Sequence[float]]:
    """Return the first three columns of each row, the point-charge positions."""
    return [row[:3] for row in array_2d]


def get_charges(array_2d: Sequence[Sequence[float]]) -> list[Sequence[float]]:
    """Return the fourth column of each row, the point-charge magnitudes."""
    return [row[3:] for row in array_2d]


def correlation_energy(total_energy: float, hf_energy: float) -> float:
    """Return the correlation energy, the part the subspace solver recovers."""
    return total_energy - hf_energy


def update_quick_out(
    oldfilename: str,
    newfilename: str,
    energy: float,
    gradient: Sequence[float],
    hf_energy: float,
    electron_corr: float,
) -> None:
    """Write a QUICK output file carrying the SQD energy and gradient.

    ``sander`` reads this file to advance the trajectory, so the layout has to
    match what QUICK itself would have written: the total energy on its own line,
    and one gradient component per line in the analytical-gradient block, with the
    original column positions preserved.

    Args:
        oldfilename: the QUICK output to use as the template.
        newfilename: where to write the modified copy.
        energy: SQD total energy, in Hartree.
        gradient: flattened nuclear gradient, x, y, z per atom, in Hartree/Bohr.
        hf_energy: the Hartree-Fock energy from the same step.
        electron_corr: ``energy - hf_energy``.

    Raises:
        ValueError: if the template lacks the energy or gradient blocks, rather
            than writing a file that ``sander`` would misread.
    """
    with open(oldfilename, "r") as handle:
        lines = handle.readlines()

    for index, line in enumerate(lines):
        if _METHOD_KEY in line:
            lines.insert(index, " PySCF METHOD = CASCI\n")
            break

    wrote_energy = False
    wrote_gradient = False
    for index, line in enumerate(lines):
        if _TOTAL_ENERGY_RE.match(line):
            lines[index] = (
                f" HF ENERGY            ={hf_energy:17.9f}\n\n"
                " @ PySCF Energy calculation \n"
                f" CORR ENERGY          ={electron_corr:17.9f}\n"
                + _TOTAL_ENERGY_KEY
                + f"{energy:17.9f}\n"
            )
            wrote_energy = True
        if _GRADIENT_RE.match(line):
            lines[index - 1] = " @ Begin PySCF Gradient Integration\n"
            for offset, value in enumerate(gradient):
                target = index + offset + 4
                lines[target] = lines[target][:-18] + f"{value:17.10f}\n"
            wrote_gradient = True

    if not wrote_energy:
        raise ValueError(f"{oldfilename} has no 'TOTAL ENERGY =' line")
    if not wrote_gradient:
        raise ValueError(f"{oldfilename} has no 'ANALYTICAL GRADIENT:' block")

    with open(newfilename, "w") as handle:
        handle.writelines(lines)
