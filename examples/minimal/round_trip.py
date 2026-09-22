#!/usr/bin/env python3
"""Offline round trip through the QUICK file exchange.

Runs with no account, no hardware and no scientific stack: it uses only
``quantum_aimd.io.quick``, which is deliberately dependency-light so that the
format handling can be exercised anywhere.

    python examples/minimal/round_trip.py
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

from quantum_aimd.io.quick import (
    correlation_energy,
    extract_final_scf_energy,
    read_mm_charges,
    update_quick_out,
)

FIXTURE = (
    pathlib.Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "quick_job_minimal.out"
)


def main() -> int:
    if not FIXTURE.exists():
        print(f"fixture not found: {FIXTURE}", file=sys.stderr)
        return 1

    print(f"reading {FIXTURE.name}")

    coords, charges = read_mm_charges(str(FIXTURE))
    print(f"  embedding point charges: {len(charges)}")
    if len(charges):
        print(f"  first charge {charges[0]:+.4f} at {coords[0].round(3).tolist()}")

    hf_energy = extract_final_scf_energy(str(FIXTURE))
    print(f"  converged Hartree-Fock energy: {hf_energy:.9f} Hartree")

    # Stand-ins for what the solver would return. The point of the example is the
    # file format, so these are obviously synthetic rather than plausible.
    sqd_energy = hf_energy - 0.25
    gradient = [0.01, -0.02, 0.03, -0.04, 0.05, -0.06]
    corr = correlation_energy(sqd_energy, hf_energy)
    print(f"  stand-in correlation energy:   {corr:.9f} Hartree")

    with tempfile.TemporaryDirectory() as tmp:
        written = pathlib.Path(tmp) / "QUICK_job_PySCF_modified.out"
        update_quick_out(str(FIXTURE), str(written), sqd_energy, gradient, hf_energy, corr)
        print(f"\nwrote {written.name} in the format sander reads")

        # The check that matters: the energy has to survive the round trip, since
        # this file is the only thing the MD driver sees.
        recovered = extract_final_scf_energy(str(written))
        text = written.read_text()

        assert recovered == hf_energy, "Hartree-Fock energy did not survive"
        assert f"{sqd_energy:17.9f}" in text, "SQD energy not written"
        for value in gradient:
            assert f"{value:17.10f}" in text, f"gradient component {value} not written"

    print("round trip verified: energies and all gradient components read back")
    return 0


if __name__ == "__main__":
    sys.exit(main())
