"""
survey/analysis.py - analyse the merchant survey and turn it into model inputs.

The survey (questionnaire.md) is work package 2. This module:
    1. synthetic_responses() -> a SYNTHETIC test dataset with the survey's columns,
                                so the pipeline can be built before real answers exist
    2. describe()            -> key shares for the thesis' descriptive section
    3. adoption_logit()      -> what explains having a digital backup? (sub-question 2)
    4. calibrate()           -> model assumptions estimated from the answers, in the
                                same format as config/assumptions.json (feeds WP3)

Answer bands are coded as numbers; each band is replaced by its midpoint.
"""

import numpy as np
import pandas as pd

SECTORS = ["Grocery", "Fashion", "Electronics", "Pharmacy", "Restaurant", "Hotel", "Other"]

# Midpoints of the answer bands (Q3, Q8, Q10, Q11, Q14)
DAILY_SALES_SEK = {1: 5_000, 2: 30_000, 3: 125_000, 4: 300_000}   # Q3
SHARE_BAND = {1: 0.10, 2: 0.30, 3: 0.50, 4: 0.70, 5: 0.90}         # Q8, Q10
CAME_BACK = {0: 0.0, 1: 0.10, 2: 0.50, 3: 0.80}                    # Q11
WTP_SEK = {0: 0, 1: 1_000, 2: 3_500, 3: 7_500, 4: 12_500}          # Q14

COLUMNS = {
    "sector": "Q1", "size_band": "Q3 (1-4)", "stores_band": "Q4 (1-4)",
    "card_pct": "Q5", "a2a_pct": "Q5", "cash_pct": "Q5",
    "outages_band": "Q6 (0 = none ... 4 = more than 6)",
    "switched_band": "Q8 (1-5, empty if no outage)", "used_a2a": "Q9 (0/1)", "used_cash": "Q9 (0/1)",
    "left_band": "Q10 (1-5)", "came_back": "Q11 (0-3)",
    "has_a2a_backup": "Q12 Swish/QR (0/1)", "has_offline_card": "Q12 offline card (0/1)",
    "wtp_band": "Q14 (0-4)",
}


# ---------------------------------------------------------------------------
# 1. Synthetic test data
# ---------------------------------------------------------------------------
def synthetic_responses(n=150, seed=1):
    """SYNTHETIC answers for testing the pipeline. Not real survey data.

    Built-in relationships (so the analysis has something to find):
      * larger chains are more likely to have a digital backup
      * merchants with a backup report a higher share of customers switching
    """
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "sector": rng.choice(SECTORS, n, p=[.25, .2, .1, .05, .2, .1, .1]),
        "size_band": rng.choice([1, 2, 3, 4], n, p=[.3, .4, .2, .1]),
        "stores_band": rng.choice([1, 2, 3, 4], n, p=[.45, .3, .15, .1]),
        "outages_band": rng.choice([0, 1, 2, 3, 4], n, p=[.3, .3, .25, .1, .05]),
    })
    card = rng.normal(85, 5, n).clip(60, 98)
    a2a = rng.normal(9, 3, n).clip(1, 30)
    df["card_pct"], df["a2a_pct"], df["cash_pct"] = card, a2a, (100 - card - a2a).clip(0)

    logit = -1.2 + 0.6 * (df["stores_band"] - 2) + 0.3 * (df["size_band"] - 2) + 0.2 * df["outages_band"]
    df["has_a2a_backup"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    df["has_offline_card"] = (rng.random(n) < 0.15 + 0.1 * df["has_a2a_backup"]).astype(int)

    had_outage = df["outages_band"] > 0
    switched = np.where(df["has_a2a_backup"] == 1, rng.choice([2, 3, 4, 5], n, p=[.1, .3, .4, .2]),
                        rng.choice([1, 2, 3], n, p=[.4, .45, .15]))
    df["switched_band"] = np.where(had_outage, switched, np.nan)
    df["left_band"] = np.where(had_outage, (6 - switched).clip(1, 5), np.nan)
    df["used_a2a"] = np.where(had_outage, (rng.random(n) < 0.4 + 0.5 * df["has_a2a_backup"]).astype(int), np.nan)
    df["used_cash"] = np.where(had_outage, (rng.random(n) < 0.6).astype(int), np.nan)
    df["came_back"] = np.where(had_outage, rng.choice([0, 1, 2, 3], n, p=[.3, .5, .15, .05]), np.nan)
    df["wtp_band"] = rng.choice([0, 1, 2, 3, 4], n, p=[.25, .3, .25, .15, .05])
    return df


# ---------------------------------------------------------------------------
# 2. Descriptive statistics
# ---------------------------------------------------------------------------
def describe(resp):
    """Key shares and averages for the thesis' descriptive section."""
    had = resp["outages_band"] > 0
    out = {
        "respondents": len(resp),
        "had at least one outage (24 months)": had.mean(),
        "have Swish/QR backup": resp["has_a2a_backup"].mean(),
        "have offline card payments": resp["has_offline_card"].mean(),
        "customers switching, with backup": resp.loc[had & (resp.has_a2a_backup == 1), "switched_band"].map(SHARE_BAND).mean(),
        "customers switching, without backup": resp.loc[had & (resp.has_a2a_backup == 0), "switched_band"].map(SHARE_BAND).mean(),
        "median willingness to pay (SEK/store/year)": resp["wtp_band"].map(WTP_SEK).median(),
    }
    return pd.Series(out)


# ---------------------------------------------------------------------------
# 3. Adoption model
# ---------------------------------------------------------------------------
def adoption_logit(resp):
    """Logit of having a Swish/QR backup on size, chain size, outage experience
    and sector, with robust standard errors. Returns (fit, average marginal effects)."""
    import statsmodels.formula.api as smf

    fit = smf.logit("has_a2a_backup ~ size_band + stores_band + outages_band + C(sector)",
                    data=resp).fit(disp=False, cov_type="HC1")
    ame = fit.get_margeff(at="overall").summary_frame()
    return fit, ame


# ---------------------------------------------------------------------------
# 4. Calibration: survey -> config/assumptions.json
# ---------------------------------------------------------------------------
def calibrate(resp):
    """Estimate model assumptions from the answers.

    Switching shares are split between A2A and cash in proportion to how many
    merchants report each method being used (Q9). Returns a dict whose keys
    match config/assumptions.json, ready for simulate.load_config(**updates).
    """
    had = resp[resp["outages_band"] > 0]
    mix = resp[["card_pct", "a2a_pct", "cash_pct"]].mean()
    mix = (mix / mix.sum()).round(3)

    def switching(group):
        switched = group["switched_band"].map(SHARE_BAND).mean()
        a2a_w, cash_w = group["used_a2a"].mean(), group["used_cash"].mean()
        a2a_share = a2a_w / (a2a_w + cash_w) if (a2a_w + cash_w) > 0 else 0.5
        return {"a2a": round(float(switched * a2a_share), 3),
                "cash": round(float(switched * (1 - a2a_share)), 3)}

    fit, _ = adoption_logit(resp)
    size_sd = resp["size_band"].std()
    return {
        "payment_mix": {"card": float(mix["card_pct"]), "a2a": float(mix["a2a_pct"]),
                        "cash": float(mix["cash_pct"])},
        "switching_during_outage": {"without_backup": switching(had[had.has_a2a_backup == 0]),
                                    "with_backup": switching(had[had.has_a2a_backup == 1])},
        "catch_up_share": round(float(had["came_back"].map(CAME_BACK).mean()), 3),
        "backup": {"share_of_stores": round(float(resp["has_a2a_backup"].mean()), 3),
                   # log-odds per 1 standard deviation of store size
                   "selection_on_size": round(float(fit.params["size_band"] * size_sd), 3)},
    }
