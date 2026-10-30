"""
analysis.py - estimate lost sales during card outages and the value of a backup.

Method (in the spirit of Mäder, Meyer, Nacht & Gatica-Perez 2026, SNB WP 2026-12):
    1. Counterfactual: what would sales have been WITHOUT the outage?
       A fixed-effects model of log sales, estimated on normal hours only:
           log(sales_sdh) = store_s + day_d + weekday-x-hour_wh + e
       The day effect is identified from unaffected stores/hours on the same
       day, so special days (Black Friday) are handled automatically.
    2. Residual = actual / counterfactual - 1  (e.g. -0.55 = 55% below normal)
    3. Event study: average residual by hour relative to the outage start,
       for stores with and without a backup payment option.
    4. Difference-in-differences regression with store-clustered standard errors.
"""

import numpy as np
import pandas as pd

FE_COLS = ["store_id", "date", "wh"]


# ---------------------------------------------------------------------------
# 1. Counterfactual: high-dimensional fixed effects
# ---------------------------------------------------------------------------
def fit_fixed_effects(df, y="log_sales", fe=FE_COLS, iterations=50, tol=1e-8):
    """Estimate additive fixed effects by alternating projections.

    With 60 stores x 365 days x 84 weekday-hours we would need ~500 dummy
    columns. Instead we repeat: for each FE group, take the group mean of
    what is still unexplained. This converges to the OLS solution
    (the same idea used by Stata's reghdfe).
    """
    resid = df[y] - df[y].mean()
    effects = {f: pd.Series(0.0, index=df[f].unique()) for f in fe}
    for _ in range(iterations):
        change = 0.0
        for f in fe:
            update = resid.groupby(df[f]).mean()
            effects[f] = effects[f].add(update, fill_value=0)
            resid = resid - df[f].map(update).values
            change = max(change, update.abs().max())
        if change < tol:
            break
    return {"const": df[y].mean(), "effects": effects, "sigma2": resid.var()}


def predict_fixed_effects(model, df):
    """Counterfactual sales in SEK. exp(sigma^2/2) corrects for the fact that
    exp(E[log y]) is below E[y] (log-normal 'smearing' correction)."""
    log_pred = model["const"] + sum(df[f].map(model["effects"][f]).fillna(0)
                                    for f in model["effects"])
    return np.exp(log_pred + model["sigma2"] / 2)


def add_counterfactual(df):
    """Fit on normal hours and predict all hours.

    Normal hours = not during an outage and not in the 2 hours after it
    (columns `outage` and `after`), so delayed purchases do not leak into
    the counterfactual.
    """
    df = df.copy()
    df["wh"] = df["date"].dt.dayofweek.astype(str) + "_" + df["hour"].astype(str)
    df["log_sales"] = np.log(df["sales_total"])
    disturbed = (df["outage"] == 1) | (df["after"] == 1)
    model = fit_fixed_effects(df.loc[~disturbed])
    df["counterfactual"] = predict_fixed_effects(model, df)
    df["residual"] = df["sales_total"] / df["counterfactual"] - 1
    df["disturbed"] = disturbed
    return df, model


# ---------------------------------------------------------------------------
# 2. Event study
# ---------------------------------------------------------------------------
def event_study(df, window=(-5, 7)):
    """Average residual by hour relative to outage start, by backup group.

    Confidence intervals: residuals are first averaged per store, then the
    standard error is computed across stores (= clustering by store).
    """
    ev = df[df["rel_hour"].between(*window)]
    per_store = ev.groupby(["has_backup", "rel_hour", "store_id"])["residual"].mean()
    out = per_store.groupby(level=[0, 1]).agg(["mean", "std", "count"])
    out["se"] = out["std"] / np.sqrt(out["count"])
    out["lo"], out["hi"] = out["mean"] - 1.96 * out["se"], out["mean"] + 1.96 * out["se"]
    return out.reset_index()


# ---------------------------------------------------------------------------
# 3. Difference-in-differences
# ---------------------------------------------------------------------------
def did_regression(df):
    """On the outage days, for affected stores:

        residual = b0 + b1*outage + b2*backup + b3*(outage x backup)
                      + b4*after + b5*(after x backup) + e

      b1 = sales change during the outage for stores WITHOUT backup
      b3 = extra sales retained BECAUSE of the backup (the effect of interest)
      b4, b5 = delayed purchases in the 2 hours after, kept apart so they do
               not contaminate the comparison hours
    Standard errors are clustered by store.
    """
    import statsmodels.formula.api as smf

    sample = df[df["rel_hour"].notna()].copy()        # outage days, affected stores
    sample["backup"] = sample["has_backup"].astype(int)
    fit = smf.ols("residual ~ outage * backup + after * backup", data=sample).fit(
        cov_type="cluster", cov_kwds={"groups": sample["store_id"]})
    return fit


def naive_comparison(df):
    """What a simple comparison would say: average sales per store-hour during
    outages, backup stores vs others, with no counterfactual. Biased when
    backup stores differ (e.g. are bigger) - shown as a warning example."""
    out = df[df["outage"] == 1]
    means = out.groupby("has_backup")["sales_total"].mean()
    return means.get(True, np.nan) / means.get(False, np.nan) - 1


def value_of_backup(df, fit, cfg):
    """Insurance value of a backup per store and year (gross profit, SEK).

    value = b3 x normal sales per outage hour x outage hours per store-year x margin
    """
    outage_rows = df[df["outage"] == 1]
    stores = df["store_id"].nunique()
    hours_per_store = len(outage_rows) / stores
    s_bar = outage_rows["counterfactual"].mean()
    b3 = fit.params["outage:backup"]
    margin = cfg["economics"]["gross_margin"]
    cost = cfg["economics"]["backup_cost_sek_per_store_year"]
    value = b3 * s_bar * hours_per_store * margin
    return {"outage hours per store-year": hours_per_store,
            "normal sales per outage hour (SEK)": s_bar,
            "share retained by backup (b3)": b3,
            "value per store-year (SEK gross profit)": value,
            "assumed cost per store-year (SEK)": cost,
            "break-even outage hours per year": cost / (b3 * s_bar * margin)}


def method_decomposition(df):
    """Where did card customers go during the outage? Compare each payment
    method with its normal share of counterfactual sales (store-specific)."""
    normal = df[~df["disturbed"]]
    shares = normal.groupby("store_id")[["sales_card", "sales_a2a", "sales_cash"]].sum()
    shares = shares.div(shares.sum(axis=1), axis=0)
    out = df[df["outage"] == 1].copy()
    rows = []
    for backup, g in out.groupby("has_backup"):
        cf = g["counterfactual"]
        row = {"group": "With backup" if backup else "Without backup"}
        for m in ["card", "a2a", "cash"]:
            expected = cf * g["store_id"].map(shares[f"sales_{m}"])
            row[f"{m}: change vs normal (% of normal total sales)"] = (
                (g[f"sales_{m}"] - expected).sum() / cf.sum())
        row["total change"] = (g["sales_total"] - cf).sum() / cf.sum()
        rows.append(row)
    return pd.DataFrame(rows).set_index("group")


# ---------------------------------------------------------------------------
# 5. Placebo test: fake outage dates
# ---------------------------------------------------------------------------
def placebo_did(df, outages, shifts=(-21, -14, -7, 7, 14, 21)):
    """Run the same DiD on days WITHOUT an outage.

    Each real outage is moved k days (k = 7, 14, 21 keeps the same weekday),
    with the same hours and the same stores. Nothing happened on those days,
    so b3 should be close to zero. If it is not, the method finds effects
    that are not there (for example from weekday or store patterns).

    df      : output of add_counterfactual
    outages : the outage table returned by simulate.simulate
    Returns one row per shift: b3, standard error, 95% CI and p-value.
    """
    real_days = set(pd.to_datetime(outages["date"]))
    rows = []
    for k in shifts:
        fake = df.drop(columns=["outage", "after", "rel_hour"]).copy()
        fake["outage"], fake["after"], fake["rel_hour"] = 0, 0, np.nan
        for o in outages.itertuples():
            day = pd.Timestamp(o.date) + pd.Timedelta(days=k)
            if day in real_days:                     # never use a real outage day
                continue
            in_scope = (fake["date"] == day) & ((o.scope == "National") | (fake["region"] == o.scope))
            end = o.start_hour + o.hours
            fake.loc[in_scope, "rel_hour"] = fake.loc[in_scope, "hour"] - o.start_hour
            fake.loc[in_scope & fake["hour"].between(o.start_hour, end - 1), "outage"] = 1
            fake.loc[in_scope & fake["hour"].between(end, end + 1), "after"] = 1
        if fake["outage"].sum() == 0:                # shift falls outside the data
            continue
        fit = did_regression(fake)
        lo, hi = fit.conf_int().loc["outage:backup"]
        rows.append({"shift (days)": k, "b3": fit.params["outage:backup"],
                     "se": fit.bse["outage:backup"], "lo": lo, "hi": hi,
                     "p-value": fit.pvalues["outage:backup"]})
    return pd.DataFrame(rows)
