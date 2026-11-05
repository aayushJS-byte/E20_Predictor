import numpy as np
import pytest

from layer_a.conformity import decide
from layer_a.load import split_columns
from layer_a.pls import metrics
from layer_a.preprocess import ALS, SNV, SavGol, make_preprocessor


@pytest.fixture(scope="module")
def data():
    from layer_a.load import load

    return load()


def test_split_ids_disjoint(data):
    ids = {s: set(data.sample_id[data.split == s]) for s in ("train", "validation", "test")}
    assert ids["train"].isdisjoint(ids["test"])
    assert ids["validation"].isdisjoint(ids["test"])
    assert ids["train"].isdisjoint(ids["validation"])
    assert {len(v) for v in ids.values()} == {107, 36}


def test_no_duplicate_spectra_across_splits(data):
    def keys(s):
        return {x.tobytes() for x in data.X[data.split == s]}

    assert keys("test").isdisjoint(keys("train") | keys("validation"))


def test_spectral_columns_parsed():
    spec, tgt = split_columns(["400.0", "401.0", "Water Content", "Ethanol Content (%)"])
    assert spec == ["400.0", "401.0"] and tgt == ["Water Content", "Ethanol Content (%)"]


def test_targets_not_imputed(data):
    assert data.targets["Water Content"].isna().sum() == 15


def test_snv_and_savgol():
    X = np.random.default_rng(0).normal(size=(3, 50)) * 5 + 10
    Z = SNV().fit_transform(X)
    assert np.allclose(Z.mean(axis=1), 0) and np.allclose(Z.std(axis=1), 1)
    sm = SavGol(11, 2, 0).fit(X).transform(np.tile(np.arange(50.0), (2, 1)))
    assert np.allclose(sm[:, 5:-5], np.arange(50.0)[5:-5])  # SG preserves lines


def test_als_removes_linear_baseline():
    x = np.linspace(0, 1, 400)
    peak = np.exp(-((x - 0.5) / 0.01) ** 2) * 100
    y = peak + 500 + 300 * x
    out = ALS(lam=1e5, p=0.01).transform(y[None])[0]
    assert abs(np.median(out)) < 5 and out.max() > 80


def test_metrics_definitions():
    ref = np.array([1.0, 2.0, 3.0, 4.0])
    m = metrics(ref, ref + 0.5)
    assert m["bias"] == pytest.approx(0.5) and m["sep"] == pytest.approx(0.0) and m["rmsep"] == pytest.approx(0.5)


@pytest.mark.parametrize("pred,half,status", [(5, 1, "PASS"), (9.5, 1, "REVIEW"), (12, 1, "FAIL")])
def test_conformity_rule(pred, half, status):
    assert decide(pred, half, 0, 10, True) == status


def test_out_of_space_never_passes():
    assert decide(5, 1, 0, 10, False) == "REVIEW"


def test_pipeline_crop():
    wn = np.arange(400.0, 2301.0)
    pre = make_preprocessor("snv", "fingerprint 400-1800", wn).fit(np.ones((2, len(wn))) + np.arange(len(wn)))
    assert pre.transform(np.ones((1, len(wn))) + np.arange(len(wn))).shape[1] == 1401
