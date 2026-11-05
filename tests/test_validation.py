import pytest

from validation.ftir import composition


@pytest.mark.parametrize("name,eth,fam", [
    ("PRF40-E20", 20.0, "PRF + ethanol (Foong)"), ("TERF91-30-60", 60.0, "TRF + ethanol (Foong)"),
    ("TE10", 10.0, "toluene + ethanol (Foong)"), ("H30E5", 5.0, "heptane/isooctane + ethanol (Truedsson)"),
    ("T6", 12.5, "4-component + ethanol (Truedsson)"), ("isooctane", 0.0, "ethanol-free hydrocarbons"),
    ("ethanol-REP2", 100.0, "neat ethanol"),
])
def test_ftir_composition_parsing(name, eth, fam):
    assert composition(name) == (eth, fam)


def test_other_alcohols_excluded():
    assert composition("methanol") is None and composition("IPA") is None


def test_bootstrap_alerts_bounds():
    from layer_b.models import bootstrap_alerts

    pt = {f"t{i}": {"incidents": 1, "caught": i % 2, "leads": [10.0] if i % 2 else [], "act": 2, "act_true": i % 2} for i in range(20)}
    ci = bootstrap_alerts(pt, n=300)
    lo, hi = ci["incident_recall"]
    assert 0 <= lo <= 0.5 <= hi <= 1
