"""
simulate.py - SYNTHETIC hourly store sales with card-payment outages.

Purpose: test whether the thesis method recovers a KNOWN effect before it is
used on real data. All numbers come from config/assumptions.json, so they can
be replaced by calibrated values from public data and the merchant survey.

The simulated world (with the default assumptions)
  * 60 stores in 4 regions, open 09-21, every day of 2025
  * Normal payment mix: card 86%, account-to-account (Swish/QR) 8%, cash 6%
  * 5 card outages (national or regional, 2-4 hours)
  * Some stores have a BACKUP payment option (QR / account-to-account at the till)
  * During an outage, card customers switch method or leave:
        without backup: 20% switch to A2A, 15% to cash, 65% of card sales lost
        with backup   : 55% switch to A2A, 15% to cash, 30% of card sales lost
  * 10% of lost sales come back in the 2 hours after the outage

Run:  python simulate.py   ->  data/hourly_sales.csv, data/stores.csv, data/outages.csv
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CONFIG = ROOT / "config" / "assumptions.json"

# Shape of demand over the day and the week (relative to the average hour)
HOUR_PROFILE = {9: .5, 10: .7, 11: .9, 12: 1.2, 13: 1.1, 14: .9, 15: .9,
                16: 1.1, 17: 1.4, 18: 1.4, 19: 1.0, 20: .7}
WEEKDAY = {0: .9, 1: .9, 2: .95, 3: 1.0, 4: 1.15, 5: 1.25, 6: .85}


def load_config(path=CONFIG, **overrides):
    """Read the assumptions file. Keyword arguments replace top-level entries,
    e.g. load_config(seed=3) or load_config(stores={...})."""
    cfg = json.loads(Path(path).read_text())
    cfg.update(overrides)
    return cfg


def true_effects(cfg):
    """The effects the analysis should recover, as shares of normal total sales.

    loss_without_backup : sales change during an outage, store without backup
    retained_by_backup  : extra share of sales kept because of the backup
    """
    card = cfg["payment_mix"]["card"]
    kept_without = sum(cfg["switching_during_outage"]["without_backup"].values())
    kept_with = sum(cfg["switching_during_outage"]["with_backup"].values())
    return {"loss_without_backup": -card * (1 - kept_without),
            "retained_by_backup": card * (kept_with - kept_without)}


def make_stores(cfg, rng):
    """Store list. With selection_on_size > 0, bigger stores are more likely to
    have a backup - the kind of selection the thesis must handle."""
    s = cfg["stores"]
    n = s["n"]
    base = rng.lognormal(np.log(s["base_sales_sek_per_hour"]["median"]),
                         s["base_sales_sek_per_hour"]["log_sd"], n)
    size_z = (np.log(base) - np.log(base).mean()) / np.log(base).std()
    share = cfg["backup"]["share_of_stores"]
    logit = np.log(share / (1 - share)) + cfg["backup"]["selection_on_size"] * size_z
    p_backup = 1 / (1 + np.exp(-logit))
    return pd.DataFrame({
        "store_id": [f"S{i:02d}" for i in range(1, n + 1)],
        "region": rng.choice(s["regions"], n),
        "has_backup": rng.random(n) < p_backup,
        "base_sales": base,
    })


def simulate(cfg=None):
    """Return (hourly sales, stores, outages) as DataFrames."""
    cfg = cfg or load_config()
    rng = np.random.default_rng(cfg["seed"])
    stores = make_stores(cfg, rng)
    outages = pd.DataFrame(cfg["outages"])

    # ---- Calendar: one row per store and opening hour ---------------------
    days = pd.date_range(cfg["period"]["start"], cfg["period"]["end"], freq="D")
    hours = range(*cfg["stores"]["open_hours"])
    grid = pd.MultiIndex.from_product([stores["store_id"], days, hours],
                                      names=["store_id", "date", "hour"]).to_frame(index=False)
    df = grid.merge(stores, on="store_id")

    # Expected sales = store size x hour profile x weekday x season
    season = 1 + 0.10 * np.sin(2 * np.pi * (df["date"].dt.dayofyear - 80) / 365)
    season = season + np.where(df["date"].dt.month == 12, 0.25, 0)       # Christmas
    season = season + np.where((df["date"].dt.month == 11) & (df["date"].dt.day == 28), 0.40, 0)
    expected = (df["base_sales"] * df["hour"].map(HOUR_PROFILE)
                * df["date"].dt.dayofweek.map(WEEKDAY) * season)
    sd = cfg["noise_log_sd"]
    demand = expected * rng.lognormal(-sd ** 2 / 2, sd, len(df))   # noise with mean 1

    sales = {m: demand * share for m, share in cfg["payment_mix"].items()}
    switch = cfg["switching_during_outage"]

    # ---- Outages ----------------------------------------------------------
    df["event"], df["outage"], df["after"], df["rel_hour"] = 0, 0, 0, np.nan
    for o in outages.itertuples():
        same_day = df["date"] == pd.Timestamp(o.date)
        in_scope = same_day & ((o.scope == "National") | (df["region"] == o.scope))
        end = o.start_hour + o.hours
        during = in_scope & df["hour"].between(o.start_hour, end - 1)
        after = in_scope & df["hour"].between(end, end + 1)
        df.loc[in_scope, "event"] = o.event
        df.loc[in_scope, "rel_hour"] = df.loc[in_scope, "hour"] - o.start_hour
        df.loc[during, "outage"] = 1
        df.loc[after, "after"] = 1

        card = sales["card"][during]
        backup = df.loc[during, "has_backup"]
        to_a2a = np.where(backup, switch["with_backup"]["a2a"], switch["without_backup"]["a2a"]) * card
        to_cash = np.where(backup, switch["with_backup"]["cash"], switch["without_backup"]["cash"]) * card
        lost = card - to_a2a - to_cash
        sales["a2a"][during] += to_a2a
        sales["cash"][during] += to_cash
        sales["card"][during] = 0.0

        # Delayed purchases: part of the lost sales come back in the next 2 hours
        lost_by_store = pd.Series(lost.values, index=df.loc[during, "store_id"]).groupby(level=0).sum()
        catch = df.loc[after, "store_id"].map(lost_by_store).fillna(0) * cfg["catch_up_share"] / 2
        sales["card"][after] += catch

    for m in cfg["payment_mix"]:
        df[f"sales_{m}"] = sales[m].round(2)
    df["sales_total"] = df[[f"sales_{m}" for m in cfg["payment_mix"]]].sum(axis=1).round(2)
    cols = ["store_id", "region", "has_backup", "date", "hour", "event", "outage", "after",
            "rel_hour", "sales_card", "sales_a2a", "sales_cash", "sales_total"]
    return df[cols], stores.drop(columns="base_sales"), outages


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    hourly, stores, outages = simulate()
    hourly.to_csv(DATA / "hourly_sales.csv", index=False)
    stores.to_csv(DATA / "stores.csv", index=False)
    outages.to_csv(DATA / "outages.csv", index=False)
    print(f"Saved {len(hourly):,} store-hours, {len(stores)} stores, {len(outages)} outages")
