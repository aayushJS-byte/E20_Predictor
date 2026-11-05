import numpy as np
import pytest

from common.config import iter_entries, value
from common.physics import pct_vv_to_mg_per_kg, tolerance_kg, water_tolerance_wt_pct


@pytest.mark.parametrize("ethanol", [5, 10, 15, 20, 25])
def test_tolerance_curve_monotonic_in_temperature(ethanol):
    t = np.linspace(-20, 50, 300)
    w = water_tolerance_wt_pct(t, ethanol)
    assert np.all(np.diff(w) > 0)
    assert np.all(w > 0)


def test_tolerance_increases_with_ethanol():
    for t in (-10, 0, 15, 30, 45):
        w = [water_tolerance_wt_pct(t, e) for e in (5, 10, 15, 20, 25)]
        assert np.all(np.diff(w) > 0)


def test_literature_cross_checks():
    # EPA (Korotney 1995): E10 holds ~0.5 % v/v at 60 F
    vv = water_tolerance_wt_pct(15.6, 10) * value("physical", "density_e20") / value("physical", "density_water")
    assert abs(vv - value("water_tolerance", "e10_check_point")) < 0.1
    # Haq & Ali (1990): E25 at 0 C holds 1.78-1.88 % mass
    lo, hi = value("water_tolerance", "haq_e25_0c_check_point")
    assert lo - 0.1 < water_tolerance_wt_pct(0, 25) < hi + 0.1


def test_tolerance_kg_matches_wt_pct():
    w = water_tolerance_wt_pct(25, 20) / 100
    m_w = tolerance_kg(25, 1000.0, 20)
    assert m_w / (1000.0 + m_w) == pytest.approx(w)


def test_spec_limits_are_distinct_quantities():
    neat = value("spec", "absolute_alcohol_max_water")          # % v/v in neat ethanol
    blend = value("spec", "e20_max_water_content")              # % v/v in E20
    assert neat != blend
    assert pct_vv_to_mg_per_kg(blend) < 1e4 * water_tolerance_wt_pct(-15, 20)


def test_every_constant_has_a_source_and_label():
    labels = {"STANDARD", "LITERATURE VALUE", "PHYSICAL CONSTANT", "ASSUMPTION", "DESIGN CHOICE"}
    n = 0
    for key, e in iter_entries():
        n += 1
        assert e.get("source"), key
        assert e.get("label") in labels, key
        if e["label"] == "ASSUMPTION":
            assert "ASSUMPTION" in e["source"], key
    assert n > 30


def test_measured_tolerance_dataset():
    from validation.tolerance_data import all_measurements

    df = all_measurements()
    assert len(df) == 33
    assert set(df.source) == {"johansen2009", "korotney1995", "haq1990"}
    e10 = df[df.source == "korotney1995"]
    # the EPA memo's text: E10 holds ~0.5 % v/v at 60 F; the extracted curve must agree
    at60 = e10.iloc[(e10.temp_c - 15.56).abs().argmin()]
    assert abs(at60.water_vol_pct - 0.5) < 0.05
    assert (df.water_wt_pct > 0).all()


def test_correlation_is_conservative_near_e20():
    from validation.tolerance_data import johansen

    j = johansen()
    near = j[(j.ethanol_vol_pct > 15) & (j.ethanol_vol_pct < 25)]
    pred = water_tolerance_wt_pct(near.temp_c.to_numpy(), near.ethanol_vol_pct.to_numpy())
    assert np.all(pred <= near.water_wt_pct.to_numpy())  # under-predicts tolerance -> earlier warnings
