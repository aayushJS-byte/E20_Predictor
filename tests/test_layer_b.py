from layer_b import physics_forecast as pf
from layer_b.dataset import TEST_YEARS, TRAIN_YEARS, feature_rows, observables
from sim.tank import TankParams, simulate
from sim.weather import synthetic


def test_train_test_years_disjoint():
    assert set(TRAIN_YEARS).isdisjoint(TEST_YEARS)
    assert max(TRAIN_YEARS) < min(TEST_YEARS)


def _run():
    w = synthetic("2024-06-01", "2024-07-31", seed=2).frame
    p = TankParams(seal="major", seed=1)
    tr, ev, led = simulate(w, p)
    run = type("R", (), {})()
    run.obs, run.trace, run.events, run.params, run.tank_id, run.year = observables(tr, ev, p), tr, ev, p, "t", "2024"
    return run


def test_features_use_only_past_observables():
    run = _run()
    rows = feature_rows(run, [500])
    # the only forward-looking inputs are the declared weather forecast columns
    leaked = [c for c in rows.columns if c.startswith("target") or c in ("margin_now_true", "onset_within_h", "separated_now")]
    from layer_b.dataset import FEATURES

    assert not set(FEATURES) & set(leaked)
    assert all(c.startswith("fcst_") or c == "horizon_h" or not c.startswith("fcst") for c in FEATURES)


def test_physics_forecast_shape_and_order():
    run = _run()
    i = 48 * 20
    n = pf.HORIZON_H * pf.STEPS_PER_H
    f = pf.forecast(run.obs, i, run.obs["t_fuel"][i + 1:i + 1 + n], run.obs["precip_mm"][i + 1:i + 1 + n])
    assert len(f["mid"]) == 72
    assert all(lo >= hi - 1e-12 for lo, hi in zip(f["lo"], f["hi"], strict=True))  # lo-ingress path keeps more margin


def test_time_to_zero():
    assert pf.time_to_zero([0.5, 0.25, -0.25]) == 2.5
    assert pf.time_to_zero([0.5, 0.4]) is None
