"""extra_asia.py - free-data experiment: does Asian overnight information improve the forecast?

Asian cash markets (Tokyo, Hong Kong, Seoul, Sydney) close BEFORE the 12:00 UTC cutoff, so their move between the US close and the cutoff
is legitimate overnight information with decades of free history (Yahoo daily files).  Three tests:
  A  next-US-day relationship over 1997-2026: S&P close-to-close return on Asia's same-calendar-date return
  B  the six-session level forecast: walk-forward median regression of the deviation from drift on the Asia move (same protocol as the factor screen)
  C  incremental value over the ES overnight move on the ~48 days of 5-minute futures history (nowcast_check.csv)
Usage: python code/extra_asia.py --snapshot data/raw_live --cutoff 2026-11-10T13:45:00Z --h 6 --weekday 3 --from-tag preview
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
from common import ROOT, _yahoo_frame, utc  # noqa: E402

warnings.filterwarnings("ignore")
ASIA = {"n225": ("Asia/Tokyo", "15:00"), "hsi": ("Asia/Hong_Kong", "16:00"), "kospi": ("Asia/Seoul", "15:30"), "asx": ("Australia/Sydney", "16:00")}


def load_local(path, tz, hhmm, cutoff):
    df = _yahoo_frame(path)
    date = df["ts"].dt.tz_convert(tz).dt.tz_localize(None).dt.normalize()
    hh, mm = map(int, hhmm.split(":"))
    close_utc = (date + pd.Timedelta(hours=hh, minutes=mm)).dt.tz_localize(tz, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    return df.assign(date=date).loc[close_utc <= cutoff].drop_duplicates("date", keep="last").set_index("date")["close"].astype(float).sort_index()


def asia_returns(snap, cutoff):
    """Composite Asian log return per calendar date d (equal-weight mean over the markets that traded on d)."""
    rets = {}
    for k, (tz, hhmm) in ASIA.items():
        s = load_local(snap / f"{k}_daily.json", tz, hhmm, cutoff)
        rets[k] = np.log(s).diff()
    R = pd.DataFrame(rets)
    return R.mean(axis=1, skipna=True), R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True); ap.add_argument("--cutoff", required=True)
    ap.add_argument("--h", type=int, default=6); ap.add_argument("--weekday", type=int, default=3)
    ap.add_argument("--from-tag", default="preview")
    a = ap.parse_args()
    snap = ROOT / a.snapshot; cutoff = utc(a.cutoff); out = ROOT / "outputs" / "extra"; out.mkdir(parents=True, exist_ok=True)
    comp, R = asia_returns(snap, cutoff)
    P, PL, Z, tsy, cov, yraw = rm.build_panel(snap, cutoff)
    spx = PL.spx
    res = {"cutoff": a.cutoff, "markets": list(ASIA), "first_asia_date": str(comp.dropna().index[0].date())}

    # ---------------------------------------------------------------- A: next-day relationship
    d = pd.DataFrame({"S": spx})
    d["R"] = np.log(d.S).diff()
    d["asia"] = comp.reindex(d.index).values          # Asian session on the same calendar date as the US day
    d = d.loc["1997-01-01":].dropna()
    for lab, lo, hi in (("1997-2026", "1997", "2026"), ("1997-2012", "1997", "2012"), ("2013-2026", "2013", "2026")):
        x = d.loc[lo:hi]
        X = np.column_stack([np.ones(len(x)), x.asia.values]); b = rm.ols(X, x.R.values); e = x.R.values - X @ b
        se = np.sqrt((e @ e / (len(x) - 2)) * np.linalg.inv(X.T @ X)[1, 1])
        res[f"A_{lab}"] = {"n": int(len(x)), "beta": float(b[1]), "se": float(se), "r2": float(1 - e @ e / ((x.R - x.R.mean()) ** 2).sum())}
    print("A", json.dumps({k: v for k, v in res.items() if k.startswith("A_")}, indent=1))

    # ---------------------------------------------------------------- B: six-session level forecast
    h, wd = a.h, a.weekday
    idx = PL.index; n = len(PL); lS = np.log(PL.spx.values)
    y = np.full(n, np.nan); y[:-h] = lS[h:] - lS[:-h]
    # origin t (last US close) -> Asia session of the NEXT calendar day, before the cutoff
    nxt = pd.Series(comp.reindex(idx + pd.Timedelta(days=1)).values, index=idx)
    F = {"asia": nxt.fillna(0.0).values}
    orig = np.array([i for i in range(n) if idx[i] >= rm.L_START and idx[i].weekday() == wd and i + h <= n - 1])
    S0, A = PL.spx.values[orig], PL.spx.values[orig + h]
    m0 = np.array([rm.m0_full(y, i, h) for i in orig])
    valid = np.array([idx[i] <= rm.L_VALID_END for i in orig]); test = ~valid
    dev, sg = rm.walk_forward(F, ["asia"], y, h, orig, rm.MIN_TRAIN_L)
    ok = np.isfinite(dev)
    E1 = rm.level_err(S0, A, m0); Ea = rm.level_err(S0, A, m0 + np.where(ok, dev, 0))
    rows = []
    for lab, mask in (("validation 2000-2012", valid), ("test 2013-", test), ("all", np.ones(len(orig), bool))):
        m = mask & ok
        t, p = rm.nw_t((E1 - Ea)[m])
        rows.append({"block": lab, "n": int(m.sum()), "MAPE_drift_%": float(E1[m].mean()), "MAPE_drift_plus_asia_%": float(Ea[m].mean()),
                     "score_gain": float((rm.score(Ea) - rm.score(E1))[m].mean()), "DM_t": t, "DM_p": p})
    tabB = pd.DataFrame(rows); tabB.to_csv(out / "asia_levelforecast.csv", index=False); print(tabB.round(4).to_string())
    res["B"] = rows
    r = rm.fit_dev([F["asia"]], y, n - 1, h, rm.MIN_TRAIN_L)
    res["B_coef_per_sd_pct"] = float(100 * r[1][1]); res["B_asia_sd_pct"] = float(100 * r[3][0])

    # ---------------------------------------------------------------- C: incremental over ES on the 5-minute sample
    nc = pd.read_csv(ROOT / "outputs" / a.from_tag / "tables" / "nowcast_check.csv", parse_dates=["date"])
    nc["asia"] = comp.reindex(nc.date.values).values
    nc = nc.dropna(subset=["asia"])
    def fit(cols):
        X = np.column_stack([np.ones(len(nc))] + [nc[c].values for c in cols]); b = rm.ols(X, nc.R_day.values); e = nc.R_day.values - X @ b
        cov = (e @ e / (len(nc) - X.shape[1])) * np.linalg.inv(X.T @ X)
        return b, np.sqrt(np.diag(cov)), 1 - e @ e / ((nc.R_day - nc.R_day.mean()) ** 2).sum()
    b1, s1, r1 = fit(["r_ovn"]); b2, s2, r2 = fit(["r_ovn", "asia"]); b3, s3, r3 = fit(["asia"])
    res["C"] = {"n": int(len(nc)), "es_only": {"beta": float(b1[1]), "se": float(s1[1]), "r2": float(r1)},
                "asia_only": {"beta": float(b3[1]), "se": float(s3[1]), "r2": float(r3)},
                "both": {"beta_es": float(b2[1]), "se_es": float(s2[1]), "beta_asia": float(b2[2]), "se_asia": float(s2[2]), "r2": float(r2)}}
    print("C", json.dumps(res["C"], indent=1))
    (out / "asia_results.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
