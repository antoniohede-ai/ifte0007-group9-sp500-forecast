"""independent_check.py (v2) - re-derives the final forecast by a DIFFERENT code path and tests the information cutoff.

  1. median six-session return m0 rebuilt with plain-Python loops from the raw Yahoo JSON (own date handling)
  2. overnight futures nowcast rebuilt from the raw 5-minute bars (own timezone logic), including the mean-drift term
  3. if factors were selected: median regression by statsmodels QuantReg (interior point) on the pipeline's features
  4. leak test: every Yahoo bar and every workbook row published after the cutoff is corrupted; loaded inputs must be unchanged
  5. arithmetic of the forecast chain re-added by hand
Usage: python code/independent_check.py --snapshot data/raw_live --tag rehearsal
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import shutil
import statistics
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, load_daily, load_es, load_zaki, utc  # noqa: E402

NY = ZoneInfo("America/New_York")


def raw_daily(path, cutoff_utc, hh, mm):
    r = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))["chart"]["result"][0]
    out = {}
    for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]):
        if c is None:
            continue
        d = dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).astimezone(NY).date()
        if dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=NY).astimezone(dt.timezone.utc) <= cutoff_utc:
            out[d] = c
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--snapshot", required=True); ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    out = ROOT / "outputs" / a.tag; snap = ROOT / a.snapshot
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    cutoff = dt.datetime.fromisoformat(res["cutoff_utc"].replace("Z", "+00:00"))
    h = res["h_sessions"]; checks = {}

    # 1 -- m0 from scratch
    spx = raw_daily(snap / "gspc_daily.json", cutoff, 16, 0)
    corr = json.loads((ROOT / "data" / "price_corrections.json").read_text(encoding="utf-8"))["spx"]     # known-bad Yahoo values -> Cboe value
    for d_, v_ in corr.items():
        dd = dt.date.fromisoformat(d_)
        if dd in spx:
            spx[dd] = float(v_)
    days = sorted(spx); S = [spx[d] for d in days]; n = len(S); lS = [math.log(x) for x in S]; o = n - 1
    checks["last_close_matches"] = abs(S[-1] - res["last_close"]) < 1e-6
    checks["last_obs_date_matches"] = days[-1].isoformat() == res["last_close_date"]
    y = [lS[i + h] - lS[i] for i in range(0, o - h + 1)]
    m0 = statistics.median(y)
    checks["m0_pct_recomputed"] = 100 * m0
    checks["m0_matches"] = abs(100 * m0 - res["m0_pct"]) < 1e-8

    # 2 -- nowcast from raw bars (or from the two recorded prices when the Bloomberg backup was used)
    manual = res["nowcast"].get("es_source") == "manual"
    esf = snap / "es_5m.json"
    r = json.loads(esf.read_text(encoding="utf-8"))["chart"]["result"][0] if esf.exists() else {"timestamp": [], "indicators": {"quote": [{"close": []}]}}
    bars = sorted((dt.datetime.fromtimestamp(t, tz=dt.timezone.utc) + dt.timedelta(minutes=5), c)
                  for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None)
    def at(t):
        v = [c for e, c in bars if e <= t]
        return v[-1] if v else None
    def ny_close(d):
        return dt.datetime(d.year, d.month, d.day, 16, 0, tzinfo=NY).astimezone(dt.timezone.utc)
    ovn = []
    for i in range(1, n):
        d, dp = days[i], days[i - 1]
        t12 = dt.datetime(d.year, d.month, d.day, 12, 0, tzinfo=dt.timezone.utc)
        if not bars or t12 > cutoff or t12 < bars[0][0] or ny_close(dp) < bars[0][0]:
            continue
        r_ = math.log(at(t12) / at(ny_close(dp)))
        if abs(r_) <= 0.04:
            ovn.append(r_)
    e_bar = sum(ovn) / len(ovn) if len(ovn) >= 20 else json.loads((ROOT / "data" / "group_evidence" / "futures_bloomberg_test31" / "futures_anchor.json").read_text())["e_all"]
    if manual:  # Bloomberg backup: recompute from the two recorded prices
        now = math.log(res["nowcast"]["es_at_cutoff"] / res["nowcast"]["es_close_prev_session"]) - e_bar
    else:
        now = math.log(at(cutoff) / at(ny_close(days[-1]))) - e_bar
    checks["nowcast_source"] = "manual (Bloomberg backup)" if manual else "yahoo 5-minute bars"
    checks["nowcast_pct_recomputed"] = 100 * now
    checks["nowcast_matches"] = abs(100 * now - res["nowcast"]["nowcast_adjustment_pct"]) < 1e-8
    checks["nowcast_sample_days"] = len(ovn)

    # 3 -- QuantReg cross-check if factors were selected
    if res["selected"]:
        import statsmodels.api as sm
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import run_model as rm
        P, PL, Z, tsy, cov, _ = rm.build_panel(snap, utc(res["cutoff_utc"]))
        F = rm.macro_features(P, rm.price_features(P)); oo = len(P) - 1
        yy = np.full(len(P), np.nan); lP = np.log(P.spx.values); yy[:-h] = lP[h:] - lP[:-h]
        cols = np.column_stack([F[s] for s in res["selected"]]); rows = [i for i in range(0, oo - h + 1) if np.isfinite(cols[i]).all() and np.isfinite(yy[i])]
        Xt = cols[rows]; mu_, sd_ = Xt.mean(0), Xt.std(0); Z_ = sm.add_constant((Xt - mu_) / sd_)
        fit = sm.QuantReg(yy[rows], Z_).fit(q=0.5, max_iter=5000, p_tol=1e-9)
        dev = float(fit.params[1:] @ ((cols[oo] - mu_) / sd_))
        mu_q = m0 + res["kappa"] * dev
        checks["quantreg_mu_pct"] = 100 * mu_q; checks["quantreg_mu_diff_pp"] = abs(100 * mu_q - res["mu_final_pct"])
    else:
        checks["quantreg_mu_diff_pp"] = 0.0; checks["quantreg_note"] = "no factor selected: expected return is the median drift m0"

    # 4 -- leak test
    ok = True
    for name, hh, mm in (("gspc_daily.json", 16, 0), ("vix_daily.json", 16, 15), ("es_5m.json", 0, 0)):
        if not (snap / name).exists() and name == "es_5m.json" and manual:  # Bloomberg backup with no Yahoo file: nothing to leak
            checks["leak_es_5m.json"] = "no file (manual Bloomberg prices recorded in results.json)"; continue
        raw = json.loads((snap / name).read_text(encoding="utf-8")); rr = raw["chart"]["result"][0]
        q = rr["indicators"]["quote"][0]; cnt = 0
        for k, t in enumerate(rr["timestamp"]):
            if t >= cutoff.timestamp() - 1 and q["close"][k] is not None:
                q["close"][k] *= 3.0; cnt += 1
        tmp = out / f"_leak_{name}"; tmp.write_text(json.dumps(raw), encoding="utf-8")
        ld = (lambda p: load_es(p, utc(res["cutoff_utc"]))) if name.startswith("es") else (lambda p: load_daily(p, utc(res["cutoff_utc"]), f"{hh:02d}:{mm:02d}"))
        same = bool(np.array_equal(ld(snap / name).values, ld(tmp).values)); tmp.unlink(); ok &= same
        checks[f"leak_{name}"] = {"bars_corrupted": cnt, "inputs_unchanged": same}
    if (snap / "zaki_data.xlsx").exists():          # optional supporting workbook: still must not leak
        import openpyxl
        wb = openpyxl.load_workbook(snap / "zaki_data.xlsx"); cut_ts = pd.Timestamp(res["cutoff_utc"]); cnt = 0
        for ws in wb.worksheets:
            for row in ws.iter_rows(min_row=2):
                d = row[0].value
                if d is not None and row[1].value is not None and pd.Timestamp(d).normalize() + pd.Timedelta(hours=16) >= cut_ts.tz_convert(NY).tz_localize(None):
                    row[1].value = float(row[1].value) * 3.0; cnt += 1
        tmpx = out / "_leak_zaki.xlsx"; wb.save(tmpx)
        za, zb = load_zaki(snap / "zaki_data.xlsx", utc(res["cutoff_utc"])), load_zaki(tmpx, utc(res["cutoff_utc"]))
        same = all(np.array_equal(za[k].values, zb[k].values) for k in za); tmpx.unlink(); ok &= same
        checks["leak_workbook"] = {"rows_corrupted": cnt, "inputs_unchanged": same}
    checks["leak_test_pass"] = bool(ok)

    # 5 -- arithmetic
    Fr = res["last_close"] * math.exp(res["mu_final_pct"] / 100 + res["nowcast"]["nowcast_adjustment_pct"] / 100)
    checks["forecast_recomputed"] = round(Fr, 2); checks["forecast_matches_record"] = abs(round(Fr, 2) - res["forecast_final"]) < 0.015
    checks["PASS_ALL"] = bool(checks["last_close_matches"] and checks["last_obs_date_matches"] and checks["m0_matches"] and checks["nowcast_matches"]
                              and checks["leak_test_pass"] and checks["forecast_matches_record"] and checks["quantreg_mu_diff_pp"] < 0.05)
    (out / "independent_check.json").write_text(json.dumps(checks, indent=2, default=float), encoding="utf-8")
    print(json.dumps(checks, indent=2, default=float))


if __name__ == "__main__":
    main()
