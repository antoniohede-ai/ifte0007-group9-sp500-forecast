"""extra_dukascopy.py - free long-history check of the overnight-futures nowcast using Dukascopy's USA500 index quotes.

Dukascopy's S&P 500 index CFD (USA500.IDX/USD) quotes almost 24 hours a day and has years of tick history on their public data feed.
For each US trading day D we keep only two prices (mid of bid/ask):
    close_D  : last quote before the US cash close (16:00 New York) on D
    cut_D'   : last quote at or before 12:00 UTC on the NEXT calendar weekday D'
so that   r_ovn(D') = ln(cut_D' / close_D)   is the same overnight window as the ES nowcast.  Raw ticks are NOT stored (terms of use unverified);
only the two extracted prices per day are saved (data/raw_live/dukascopy_usa500_points.csv, excluded from the submission ZIP).

    python code/extra_dukascopy.py fetch   --snapshot data/raw_live --start 2013-01-01 --workers 6
    python code/extra_dukascopy.py analyse --snapshot data/raw_live --cutoff 2026-11-10T13:45:00Z --h 6 --weekday 3 --from-tag preview
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import lzma
import pathlib
import struct
import sys
import time
import warnings
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, utc  # noqa: E402

warnings.filterwarnings("ignore")
NY = ZoneInfo("America/New_York"); UTC = dt.timezone.utc
URL = "https://datafeed.dukascopy.com/datafeed/USA500IDXUSD/{y}/{m:02d}/{d:02d}/{h:02d}h_ticks.bi5"
H = {"User-Agent": "Mozilla/5.0"}


def last_tick(when_hour_start: dt.datetime, sess: requests.Session):
    """Mid price (index points) and timestamp of the last tick in the hour file starting at `when_hour_start` (UTC)."""
    u = URL.format(y=when_hour_start.year, m=when_hour_start.month - 1, d=when_hour_start.day, h=when_hour_start.hour)   # month is zero-based in the feed
    for attempt in range(4):
        try:
            r = sess.get(u, headers=H, timeout=40)
            if r.status_code == 200:
                if not r.content:
                    return None
                raw = lzma.decompress(r.content)
                if len(raw) < 20:
                    return None
                ms, ask, bid, _, _ = struct.unpack(">IIIff", raw[-20:])
                return (ask + bid) / 2000.0, when_hour_start + dt.timedelta(milliseconds=ms)
            if r.status_code in (404, 403):
                return None
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    return "ERR"


def job(args):
    d, kind, hour_start = args
    sess = requests.Session()
    return d, kind, last_tick(hour_start, sess)


def fetch(a):
    snap = ROOT / a.snapshot
    from common import load_daily
    s = load_daily(snap / "gspc_daily.json", utc("2100-01-01"), "16:00")
    days = [d for d in s.index if d >= pd.Timestamp(a.start) and (a.only_weekday is None or d.weekday() == a.only_weekday)]
    outp = snap / "dukascopy_usa500_points.csv"
    done = pd.read_csv(outp, parse_dates=["date"]) if outp.exists() else pd.DataFrame(columns=["date", "kind", "price", "tick_utc"])
    done["date"] = pd.to_datetime(done["date"])
    have = set(zip(done.date.dt.strftime("%Y-%m-%d"), done.kind))
    jobs = []
    for d in days:
        dd = d.date()
        close_utc = dt.datetime(dd.year, dd.month, dd.day, 16, 0, tzinfo=NY).astimezone(UTC)
        hs = (close_utc - dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        if (str(dd), "close") not in have:
            jobs.append((str(dd), "close", hs))
        nxt = dd + dt.timedelta(days=1)
        if nxt.weekday() < 5 and (str(nxt), "cut") not in have and (nxt in {x.date() for x in days} or True):
            jobs.append((str(nxt), "cut", dt.datetime(nxt.year, nxt.month, nxt.day, 11, 0, tzinfo=UTC)))
    jobs = list({(j[0], j[1]): j for j in jobs}.values())
    print(f"{len(jobs)} hour files to fetch", flush=True)
    rows, n = [], 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for d, kind, res in ex.map(job, jobs):
            n += 1
            if res not in (None, "ERR"):
                rows.append({"date": d, "kind": kind, "price": res[0], "tick_utc": res[1].isoformat()})
            elif res == "ERR":
                rows.append({"date": d, "kind": kind, "price": np.nan, "tick_utc": "ERR"})
            if n % 500 == 0:
                print(f"  {n}/{len(jobs)}  {time.time()-t0:.0f}s", flush=True)
                pd.concat([done, pd.DataFrame(rows)]).to_csv(outp, index=False)
    pd.concat([done, pd.DataFrame(rows)]).drop_duplicates(["date", "kind"], keep="last").to_csv(outp, index=False)
    print("saved", outp, "errors:", sum(1 for r in rows if r["tick_utc"] == "ERR"))


def analyse(a):
    import run_model as rm
    snap = ROOT / a.snapshot; cutoff = utc(a.cutoff); out = ROOT / "outputs" / "extra"; out.mkdir(parents=True, exist_ok=True)
    pts = pd.read_csv(snap / "dukascopy_usa500_points.csv", parse_dates=["date"]).dropna(subset=["price"])
    pts = pts[pts.tick_utc != "ERR"]
    P, PL, Z, tsy, cov, yraw = rm.build_panel(snap, cutoff)
    spx = PL.spx
    close = pts[pts.kind == "close"].set_index("date").price; cut = pts[pts.kind == "cut"].set_index("date")
    # staleness guard: the quote used must be recent (market open) -- at most 15 minutes old at 12:00 UTC
    cut["age_min"] = [(pd.Timestamp(d).tz_localize("UTC") + pd.Timedelta(hours=12) - pd.Timestamp(t)).total_seconds() / 60 for d, t in zip(cut.index, cut.tick_utc)]
    cutp = cut[cut.age_min <= 15].price
    rows = []
    for D in close.index:
        D2 = D + pd.Timedelta(days=1)
        if D2 in cutp.index and D in spx.index and D2 in spx.index:
            rows.append({"date": D2, "r_ovn": np.log(cutp[D2] / close[D]), "R_day": np.log(spx[D2] / spx[D]), "VIX": PL.vix.get(D, np.nan)})
    d = pd.DataFrame(rows).set_index("date").sort_index()
    d = d[(d.r_ovn.abs() < 0.06)]
    res = {"n_days": int(len(d)), "first": str(d.index[0].date()), "last": str(d.index[-1].date()), "mean_overnight_drift_pct": float(100 * d.r_ovn.mean())}

    def reg(x):
        X = np.column_stack([np.ones(len(x)), x.r_ovn.values]); b = rm.ols(X, x.R_day.values); e = x.R_day.values - X @ b
        se = np.sqrt((e @ e / (len(x) - 2)) * np.linalg.inv(X.T @ X)[1, 1])
        return {"n": int(len(x)), "beta": float(b[1]), "se": float(se), "r2": float(1 - e @ e / ((x.R_day - x.R_day.mean()) ** 2).sum()),
                "beta_zero_intercept": float((x.r_ovn * x.R_day).sum() / (x.r_ovn ** 2).sum())}
    res["A_all"] = reg(d)
    for lab, lo, hi in (("2013-2019", "2013", "2019"), ("2020-2026", "2020", "2026")):
        res[f"A_{lab}"] = reg(d.loc[lo:hi])
    q = d.VIX.quantile([1 / 3, 2 / 3]).values
    res["A_calm_VIX<=%.0f" % q[0]] = reg(d[d.VIX <= q[0]]); res["A_stress_VIX>%.0f" % q[1]] = reg(d[d.VIX > q[1]])
    # agreement with ES over the overlap
    ncp = ROOT / "outputs" / a.from_tag / "tables" / "nowcast_check.csv"
    if ncp.exists():
        nc = pd.read_csv(ncp, parse_dates=["date"]).set_index("date")
        j = pd.concat([d.r_ovn, nc.r_ovn], axis=1, keys=["cfd", "es"], sort=True).dropna()
        res["overlap_with_ES"] = {"n": int(len(j)), "corr": float(j.corr().iloc[0, 1]), "slope_es_on_cfd": float(np.polyfit(j.cfd, j.es, 1)[0])}
    print(json.dumps({k: v for k, v in res.items() if k != "n_days"}, indent=1))

    # level test: six-session forecast, B1 (median drift) vs B1 + nowcast (beta = 1, mean overnight drift removed), weekly origins
    h, wd = a.h, a.weekday
    idx = PL.index; n = len(PL); lS = np.log(PL.spx.values)
    y = np.full(n, np.nan); y[:-h] = lS[h:] - lS[:-h]
    ebar = d.r_ovn.expanding().mean()      # only past overnight moves
    orig = [i for i in range(n) if idx[i] >= pd.Timestamp("2014-01-01") and idx[i].weekday() == wd and i + h <= n - 1 and (idx[i] + pd.Timedelta(days=1)) in d.index]
    orig = np.array(orig)
    S0, A = PL.spx.values[orig], PL.spx.values[orig + h]
    m0 = np.array([rm.m0_full(y, i, h) for i in orig])
    nowc = np.array([d.r_ovn[idx[i] + pd.Timedelta(days=1)] - ebar[idx[i]] if idx[i] in ebar.index else d.r_ovn[idx[i] + pd.Timedelta(days=1)] for i in orig])
    nowc = np.array([d.r_ovn[idx[i] + pd.Timedelta(days=1)] - ebar.loc[:idx[i] + pd.Timedelta(days=1)].iloc[-2 if len(ebar.loc[:idx[i] + pd.Timedelta(days=1)]) > 1 else -1] for i in orig])
    valid = np.array([idx[i] <= pd.Timestamp("2019-12-31") for i in orig])
    rows = []
    E0 = rm.level_err(S0, A, np.zeros(len(orig))); E1 = rm.level_err(S0, A, m0); E2 = rm.level_err(S0, A, m0 + nowc)
    E3 = rm.level_err(S0, A, nowc)
    for lab, mask in (("2014-2019", valid), ("2020-2026", ~valid), ("all", np.ones(len(orig), bool))):
        t1, p1 = rm.nw_t((E1 - E2)[mask]); t0, p0 = rm.nw_t((E0 - E2)[mask])
        rows.append({"block": lab, "n": int(mask.sum()), "MAPE_unchanged_%": float(E0[mask].mean()), "MAPE_drift_%": float(E1[mask].mean()),
                     "MAPE_drift_plus_nowcast_%": float(E2[mask].mean()), "score_gain_vs_drift": float((rm.score(E2) - rm.score(E1))[mask].mean()),
                     "DM_t_vs_drift": t1, "DM_p_vs_drift": p1, "DM_t_vs_unchanged": t0})
    tab = pd.DataFrame(rows); tab.to_csv(out / "dukascopy_levelforecast.csv", index=False); print(tab.round(4).to_string())
    res["level_test"] = rows
    (out / "dukascopy_results.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch"); f.add_argument("--snapshot", required=True); f.add_argument("--start", default="2013-01-01"); f.add_argument("--workers", type=int, default=2); f.add_argument("--only-weekday", type=int, default=None, help="0=Mon..4=Fri; 3 = Thursday origins only (the final run's weekday)")
    g = sub.add_parser("analyse"); g.add_argument("--snapshot", required=True); g.add_argument("--cutoff", required=True)
    g.add_argument("--h", type=int, default=6); g.add_argument("--weekday", type=int, default=3); g.add_argument("--from-tag", default="preview")
    a = ap.parse_args()
    fetch(a) if a.cmd == "fetch" else analyse(a)
