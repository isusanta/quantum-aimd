"""Tests for the run configuration.

The configuration is where the device name and the sampling budget live, so these
tests pin down two properties the rest of the package depends on: there is no
default device, and per-step artifacts do not collide.
"""

from __future__ import annotations

import pytest

from quantum_aimd.config import BACKEND_ENV_VAR, RunConfig


def test_backend_is_required():
    """No default device: a result must never be attributed to a processor by accident."""
    with pytest.raises(ValueError, match="no backend given"):
        RunConfig(backend="")


def test_backend_can_come_from_the_environment(monkeypatch):
    monkeypatch.setenv(BACKEND_ENV_VAR, "some-device")
    config = RunConfig.from_mapping({})
    assert config.backend == "some-device"


def test_explicit_backend_beats_the_environment(monkeypatch):
    monkeypatch.setenv(BACKEND_ENV_VAR, "from-env")
    config = RunConfig.from_mapping({"backend": "explicit"})
    assert config.backend == "explicit"


@pytest.mark.parametrize(
    "field,value",
    [("shots", 0), ("batches", 0), ("score_iterations", 0)],
)
def test_nonsensical_sizes_are_rejected(field, value):
    with pytest.raises(ValueError):
        RunConfig(backend="device", **{field: value})


def test_unknown_keys_are_rejected_rather_than_ignored():
    """A typo in a config file should fail loudly, not run with a silent default."""
    with pytest.raises(ValueError, match="unknown configuration key"):
        RunConfig.from_mapping({"backend": "device", "shotz": 100})


def test_derived_quantities():
    config = RunConfig(backend="device", num_atoms=4, num_electrons_a=5, num_electrons_b=5)
    assert config.nelec == (5, 5)
    assert config.num_gradient_components == 12


def test_batch_artifacts_collide_without_a_step_and_not_with_one():
    """The reason per-frame wave functions were unavailable for the published runs."""
    without = RunConfig(backend="device")
    assert without.batch_artifact("c", 1, 2) == without.batch_artifact("c", 1, 2)

    first = RunConfig(backend="device", step=0).batch_artifact("c", 1, 2)
    second = RunConfig(backend="device", step=1).batch_artifact("c", 1, 2)
    assert first != second
    assert "step-0" in first and "step-1" in second


def test_yaml_round_trip(tmp_path):
    yaml = pytest.importorskip("yaml")
    path = tmp_path / "run.yaml"
    path.write_text(yaml.safe_dump({"backend": "device", "shots": 4096, "num_atoms": 5}))

    config = RunConfig.from_yaml(str(path))
    assert (config.backend, config.shots, config.num_atoms) == ("device", 4096, 5)
    assert config.to_mapping()["shots"] == 4096
