import numpy as np
import pytest

from sim.tank import Mulberry32, TankParams, segment_height, segment_volume, simulate
from sim.weather import synthetic

WEATHER = synthetic("2024-06-01", "2024-08-31", seed=1).frame
CASES = [
    TankParams(),
    TankParams(seal="major"),
    TankParams(seal="major", drain_out=True),
    TankParams(seal="minor", wet_tanker_probability=0.9, seed=4, rh_offset=20, swing_scale=2.0),
]


@pytest.mark.parametrize("p", CASES)
def test_water_mass_balance_closes(p):
    _, _, led = simulate(WEATHER, p)
    stored = led["stored_end"] - led["stored_start"]
    assert led["water_in"] - led["water_out"] == pytest.approx(stored, abs=1e-6)
    assert abs(led["imbalance"]) < 1e-6


@pytest.mark.parametrize("p", CASES)
def test_margin_nonpositive_iff_lower_phase(p):
    tr, _, _ = simulate(WEATHER, p)
    sep = tr["lower_water_kg"].to_numpy() > 0
    assert np.all(tr["margin"].to_numpy()[sep] <= 0)
    assert np.all(tr["margin"].to_numpy()[~sep] > 0)


def test_runs_are_reproducible():
    a, ea, _ = simulate(WEATHER, TankParams(seal="major", seed=9))
    b, eb, _ = simulate(WEATHER, TankParams(seal="major", seed=9))
    assert a.equals(b) and ea == eb


def test_breathing_alone_cannot_separate():
    tr, ev, _ = simulate(WEATHER, TankParams(wet_tanker_probability=0.0))
    assert not any(e["type"] == "separation_onset" for e in ev)
    assert tr["ingress_vapour_kg"].resample("D").sum().max() < 1.0  # well under 1 kg/day


def test_drain_out_never_hurts():
    _, ev_off, _ = simulate(WEATHER, TankParams(seal="major"))
    _, ev_on, _ = simulate(WEATHER, TankParams(seal="major", drain_out=True))
    first = lambda ev: next((e["step"] for e in ev if e["type"] == "separation_onset"), 10**9)  # noqa: E731
    assert first(ev_on) >= first(ev_off)


def test_segment_geometry_inverts():
    for v in (0.001, 0.05, 1.0, 5.0):
        h = segment_height(v, 1.25, 4.0)
        assert segment_volume(h, 1.25, 4.0) == pytest.approx(v, rel=1e-6)


def test_prng_matches_reference_mulberry32():
    # values from the canonical JavaScript mulberry32(1)
    r = Mulberry32(1)
    assert [r.random() for _ in range(3)] == [0.6270739405881613, 0.002735721180215478, 0.5274470399599522]
