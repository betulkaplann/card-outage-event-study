"""
power.py - how much data does the thesis need?

A Monte Carlo study: simulate many small datasets with different numbers of
stores and outages, estimate the backup effect in each, and record how
precise the estimate is.

Output per design (stores x outages):
  * se   : average standard error of b3 (the backup effect)
  * mde  : minimum detectable effect = 2.8 x se
           (the smallest effect found with 80% power at the 5% level)
  * bias : average estimate minus the true effect

Run:  python power.py   (about 2-3 minutes)   ->  data/power_results.csv
"""

import numpy as np
import pandas as pd

import analysis as an
import simulate


def small_design(n_stores, n_outages, seed, base_cfg=None):
    """A two-month dataset with n_outages national 3-hour outages, 10 days apart."""
    cfg = dict(base_cfg or simulate.load_config())
    dates = pd.date_range("2025-03-10", periods=n_outages, freq="10D")
    cfg.update(
        seed=seed,
        period={"start": "2025-03-01", "end": "2025-05-15"},
        stores=dict(cfg["stores"], n=n_stores),
        outages=[{"event": i + 1, "date": d.strftime("%Y-%m-%d"), "start_hour": 12,
                  "hours": 3, "scope": "National"} for i, d in enumerate(dates)],
    )
    return cfg


def one_run(n_stores, n_outages, seed, base_cfg=None):
    cfg = small_design(n_stores, n_outages, seed, base_cfg)
    df, _, _ = simulate.simulate(cfg)
    if df["has_backup"].nunique() < 2:            # need both groups
        return None
    df, _ = an.add_counterfactual(df)
    fit = an.did_regression(df)
    return fit.params["outage:backup"], fit.bse["outage:backup"]


def power_study(stores=(10, 20, 40, 60), outages=(1, 2, 4), reps=20, base_cfg=None):
    truth = simulate.true_effects(base_cfg or simulate.load_config())["retained_by_backup"]
    rows = []
    for n_s in stores:
        for n_o in outages:
            runs = [one_run(n_s, n_o, seed, base_cfg) for seed in range(reps)]
            runs = [r for r in runs if r is not None]
            est = np.array([r[0] for r in runs])
            se = np.array([r[1] for r in runs])
            rows.append({"stores": n_s, "outages": n_o, "runs": len(runs),
                         "se": se.mean(), "mde": 2.8 * se.mean(),
                         "bias": est.mean() - truth})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    res = power_study()
    simulate.DATA.mkdir(exist_ok=True)
    res.to_csv(simulate.DATA / "power_results.csv", index=False)
    print(res.round(4).to_string(index=False))
