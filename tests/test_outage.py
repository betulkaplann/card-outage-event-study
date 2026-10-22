"""Tests for the outage event study. Run with:  pytest -q"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # import project files

import analysis as an       # noqa: E402
import power                # noqa: E402
import simulate             # noqa: E402
from survey import analysis as sv   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def small_dataset(seed=0, **overrides):
    cfg = power.small_design(n_stores=20, n_outages=2, seed=seed)
    cfg.update(overrides)
    df, _, _ = simulate.simulate(cfg)
    df, _ = an.add_counterfactual(df)
    return cfg, df


def test_true_effects_follow_from_assumptions():
    cfg = simulate.load_config()
    t = simulate.true_effects(cfg)
    assert np.isclose(t["loss_without_backup"], -0.86 * 0.65)
    assert np.isclose(t["retained_by_backup"], 0.86 * 0.35)


def test_counterfactual_is_unbiased_in_normal_hours():
    _, df = small_dataset()
    normal = df[~df["disturbed"]]
    assert abs(normal["residual"].mean()) < 0.01


def average_estimate(seeds=range(10), **overrides):
    """Mean DiD estimate over several simulated datasets (one draw can be unlucky)."""
    est = []
    for seed in seeds:
        cfg, df = small_dataset(seed, **overrides)
        if df["has_backup"].nunique() == 2:
            est.append(an.did_regression(df).params["outage:backup"])
    return cfg, np.mean(est)


def test_did_recovers_the_true_backup_effect():
    cfg, est = average_estimate()
    assert abs(est - simulate.true_effects(cfg)["retained_by_backup"]) < 0.02


def test_did_is_robust_to_selection_on_store_size():
    cfg, est = average_estimate(backup={"share_of_stores": 0.5, "selection_on_size": 1.5})
    assert abs(est - simulate.true_effects(cfg)["retained_by_backup"]) < 0.02


def test_survey_calibration_returns_valid_config_keys():
    updates = sv.calibrate(sv.synthetic_responses(n=120))
    cfg = simulate.load_config(**updates)
    assert set(updates) <= set(cfg)
    assert abs(sum(cfg["payment_mix"].values()) - 1) < 0.01
    for group in cfg["switching_during_outage"].values():
        assert 0 <= sum(group.values()) <= 1


def test_outage_catalogue_template_contains_no_invented_events():
    template = pd.read_csv(ROOT / "templates" / "outage_catalogue_template.csv")
    assert len(template) == 0                     # rows only from cited public sources
    assert "source_url" in template.columns
