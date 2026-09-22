"""Tests for QUICK input and output handling.

These run offline with no quantum or chemistry dependency, which is the point of
keeping the parsing in its own module: the file format is where a silent error
would corrupt a trajectory, so it is the part that most needs testing.
"""

from __future__ import annotations

import pathlib

import pytest

from quantum_aimd.io.quick import (
    correlation_energy,
    extract_final_scf_energy,
    get_charges,
    get_coords,
    read_data_between_keywords,
    read_mm_charges,
    update_quick_out,
)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "quick_job_minimal.out"


def test_point_charges_are_read_with_positions_and_magnitudes():
    coords, charges = read_mm_charges(str(FIXTURE))
    assert coords.shape == (3, 3)
    assert charges.shape == (3,)
    assert charges[1] == pytest.approx(0.6791)
    assert coords[0].tolist() == pytest.approx([-4.1, -3.4, -7.9])


def test_raw_reader_keeps_the_trailing_blank_row():
    """The ``[:-1]`` convention in ported code depends on this.

    QUICK leaves a blank line before DISTANCE MATRIX. If the raw reader silently
    dropped it, callers that slice off the last element would discard a real
    charge instead, quietly changing the embedding.
    """
    rows = read_data_between_keywords(str(FIXTURE))
    assert rows[-1] == []
    assert len(rows) == 4  # three charges plus the blank row
    assert len(rows[:-1]) == 3


def test_coords_and_charges_split_a_row_the_way_the_solver_expects():
    rows = [[1.0, 2.0, 3.0, -0.5]]
    assert get_coords(rows) == [[1.0, 2.0, 3.0]]
    assert get_charges(rows) == [[-0.5]]


def test_final_scf_energy_is_the_last_cycle_before_convergence():
    assert extract_final_scf_energy(str(FIXTURE)) == pytest.approx(-10.25)


def test_missing_scf_table_raises_rather_than_returning_zero(tmp_path):
    empty = tmp_path / "no_scf.out"
    empty.write_text(" TOTAL ENERGY         =       -1.000000000\n")
    with pytest.raises(ValueError, match="no SCF energy table"):
        extract_final_scf_energy(str(empty))


def test_correlation_energy_is_the_difference():
    assert correlation_energy(-10.5, -10.25) == pytest.approx(-0.25)


def test_update_writes_energy_and_gradient_that_read_back(tmp_path):
    out = tmp_path / "modified.out"
    gradient = [0.01, -0.02, 0.03, -0.04, 0.05, -0.06]
    update_quick_out(str(FIXTURE), str(out), -10.5, gradient, -10.25, -0.25)
    text = out.read_text()

    # The energy block is what the MD driver reads back for the step.
    assert "PySCF METHOD = CASCI" in text
    assert f" CORR ENERGY          ={-0.25:17.9f}" in text
    assert f" TOTAL ENERGY         ={-10.5:17.9f}" in text
    # The inserted HF line must appear exactly once, not duplicate a template line.
    assert text.count(" HF ENERGY            =") == 1

    # Every gradient component must land in the analytical-gradient block, in
    # order, with the coordinate columns untouched.
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if "ANALYTICAL GRADIENT" in line)
    for offset, value in enumerate(gradient):
        row = lines[start + offset + 4]
        assert row.endswith(f"{value:17.10f}")
        assert row.lstrip().startswith(f"{offset // 3 + 1}{'XYZ'[offset % 3]}")


def test_update_refuses_a_template_without_the_blocks(tmp_path):
    broken = tmp_path / "broken.out"
    broken.write_text("nothing useful here\n")
    with pytest.raises(ValueError, match="TOTAL ENERGY"):
        update_quick_out(str(broken), str(tmp_path / "out.out"), -1.0, [], -1.0, 0.0)


def test_no_point_charges_gives_empty_arrays(tmp_path):
    """A gas-phase step has no MM charges, and must not raise."""
    vacuum = tmp_path / "vacuum.out"
    vacuum.write_text(" -- EXTERNAL POINT CHARGES: (X,Y,Z,Q) --\n\n -- DISTANCE MATRIX -- :\n")
    coords, charges = read_mm_charges(str(vacuum))
    assert coords.shape == (0, 3)
    assert charges.shape == (0,)
