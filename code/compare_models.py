"""compare_models.py - like-for-like comparison of the group's leading model choices on identical data.

The group's models all reduce to  forecast = S_t x exp(drift + overnight futures move), differing in the drift estimate:
    median of 6-session returns since 1990 (Layla) | since 2000 (Antonio) | fixed +0.25% (Jayen) | mean since 1990 | none
Part 1: long history, Thursday origins 2003-2026, drift only (no intraday futures exist that far back).
Part 2: Apr-Oct 2026, every origin with a Bloomberg 07:00 New York futures price (group repo file 01c_es1_0700_1600_ny.csv,
        Bloomberg data - read locally, never copied), each drift with and without the futures move.
All estimates use only returns already realised at each origin.  Error = mean absolute % vs the close 6 sessions later.

    python code/compare_models.py --snapshot data/raw_live --bbg "<repo>/drift-asia/data/raw/bbg-drop/01c_es1_0700_1600_ny.csv"
"""
import argparse
import json
import pathlib
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_model as rm  # noqa: E402
from common import ROOT, utc  # noqa: E402

warnings.filterwarnings("ignore")
H = 6


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot", required=True); ap.add_argument("--bbg", required=True)
    ap.add_argument("--cutoff", default="2026-11-10T12:00:00Z")
    a = ap.parse_args()
    P, PL, Z, tsy, cov, yraw = rm.build_panel(ROOT / a.snapshot, utc(a.cutoff))
    idx, S = PL.index, PL.spx.values; n = len(S); lS = np.log(S)
    y = np.full(n, np.nan); y[:-H] = lS[H:] - lS[:-H]
    i2000 = int(np.searchsorted(idx, pd.Timestamp("2000-01-01")))

    def drifts(o):
        v = y[: o - H + 1]; v = v[np.isfinite(v)]; w = y[i2000: o - H + 1]; w = w[np.isfinite(w)]
        return {"Median since 1990 (Layla)": float(np.median(v)), "Median since 2000 (Antonio)": float(np.median(w)),
                "Fixed +0.25% (Jayen)": 0.0025, "Mean since 1990": float(np.mean(v)), "No drift (unchanged)": 0.0}

    def table(rows, ref="Median since 1990 (Layla)"):
        df = pd.DataFrame(rows)
        out = []
        for m in df.columns.drop(["date", "S0", "A"]):
            E = 100 * np.abs(df.S0 * np.exp(df[m]) - df.A) / df.A
            Er = 100 * np.abs(df.S0 * np.exp(df[ref]) - df.A) / df.A
            t, p = rm.nw_t((Er - E).values, lag_=5) if m != ref else (np.nan, np.nan)
            out.append({"model": m, "n": int(len(df)), "MAPE_%": float(E.mean()), "mean_score": float(rm.score(E.values).mean()), "t_vs_ref": t})
        return pd.DataFrame(out)

    res = {}
    # ---------------------------------------------------------------- part 1: long history, drift only
    rows = []
    for o in range(n):
        if idx[o] >= pd.Timestamp("2003-01-01") and idx[o].weekday() == 3 and o + H <= n - 1:
            rows.append({"date": idx[o], "S0": S[o], "A": S[o + H], **drifts(o)})
    d1 = pd.DataFrame(rows)
    res["part1"] = {}
    for lab, lo, hi in (("2003-2026 all", "2003", "2026"), ("2003-2012", "2003", "2012"), ("2013-2019", "2013", "2019"), ("2020-2026", "2020", "2026"),
                        ("Aug 2025-Oct 2026 (group's unseen window)", "2025-08-15", "2026")):
        sub_ = d1[(d1.date >= lo) & (d1.date <= (hi + "-12-31" if len(hi) == 4 else hi))]
        tb = table(sub_.to_dict("records")); res["part1"][lab] = tb.to_dict("records")
        print(f"\nPART 1  Thursdays {lab}"); print(tb.round(4).to_string(index=False))

    # ---------------------------------------------------------------- part 2: Bloomberg 07:00 futures window
    b = pd.read_csv(a.bbg, parse_dates=["date_new_york"]).set_index("date_new_york")
    p07, p16 = b["ES1 Index|price_at_0700_NY"], b["ES1 Index|price_at_1600_NY"]
    gs = []
    rows2 = []
    for o in range(n):
        d = idx[o]
        if d not in p16.index or o + H > n - 1:
            continue
        nxt = idx[o + 1]
        if nxt not in p07.index or pd.isna(p07[nxt]) or pd.isna(p16[d]):
            continue
        g = float(np.log(p07[nxt] / p16[d]))
        if abs(g) > 0.04:          # roll guard
            continue
        e = float(np.mean(gs)) if gs else 0.0     # mean overnight drift from PAST days only
        gs.append(g)
        dr = drifts(o)
        r = {"date": d, "S0": S[o], "A": S[o + H]}
        for k, v in dr.items():
            r[k] = v
            r[k + " + futures"] = v + (g - e)
        rows2.append(r)
    d2 = pd.DataFrame(rows2)
    res["part2"] = {}
    for lab, sub_ in (("all origins", d2), ("Thursday origins", d2[d2.date.dt.weekday == 3])):
        tb = table(sub_.to_dict("records")); res["part2"][lab] = tb.to_dict("records")
        print(f"\nPART 2  Bloomberg 07:00 window {d2.date.min().date()} to {d2.date.max().date()}, {lab}"); print(tb.round(4).to_string(index=False))
    out = ROOT / "outputs" / "extra"; out.mkdir(parents=True, exist_ok=True)
    (out / "model_comparison.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
