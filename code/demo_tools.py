"""demo_tools.py - small, fast, read-only tools the demo agent can call (each takes a few seconds, prints a few lines).

    python code/demo_tools.py record                 which record, which data, what the cutoff removed, brief's rules
    python code/demo_tools.py recompute              separate recalculation of drift, futures move and forecast
    python code/demo_tools.py check                  runs code/independent_check.py and summarises it
    python code/demo_tools.py data spx|es            the raw observations either side of the cutoff
    python code/demo_tools.py explain <item>         how a number is defined, with its inputs and where it is in the code
                                                     items: drift, futures, overnight, cutoff, forecast, check
    python code/demo_tools.py whatif <change> ...    one or more changes; prints the forecast they would give
        drift=median | median:<year> | mean | mean:<year> | none | fixed | <x>%     (<x>% = expected return over the horizon)
        futures=none | HH:MM            (New York time on the cutoff morning, at or before the cutoff)
        overnight=12utc | 07:00 | none  (clock time for the average overnight move that is subtracted)
        close=<index points>            (a different last official close, e.g. if S&P DJI differs from Yahoo)

Read-only: never writes the forecast record. Uses only the frozen snapshot (no internet).
--tag defaults to final if outputs/final exists, otherwise preview.
Parsing is deliberately separate from run_model.py (own reading of the raw Yahoo files), so a match is a real check.
If the run used manually entered futures prices (Bloomberg backup, es_source = manual), those prices are used.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
NY = "America/New_York"
HOLIDAYS = pd.to_datetime(["2026-11-26", "2026-12-25"])      # NYSE closures inside the horizons used here
BRIEF_CUTOFF_UTC = "12:00"                                     # brief: 12:00 London = 12:00 UTC = 07:00 New York
# preset shortcuts used by the page's buttons; any value in the grammar above is accepted too
WHATIF = {
    "drift=2000": "median drift from 2000 instead of 1990",
    "drift=mean": "mean drift instead of median",
    "drift=fixed": "fixed +0.25% per 6 sessions",
    "drift=none": "no drift (unchanged centre)",
    "futures=none": "no overnight futures move",
    "futures=06:00": "futures read one hour earlier (06:00 New York)",
    "futures=05:00": "futures read two hours earlier (05:00 New York)",
    "overnight=07:00": "average overnight move measured at 07:00 New York every day, instead of 12:00 UTC",
}
OPT_RE = re.compile(r"^(drift=(median|mean|none|fixed|(median|mean):(19[5-9]\d|20[0-2]\d)|\d{4}|-?\d+(\.\d+)?%)"
                    r"|futures=(none|\d{1,2}:\d{2})|overnight=(12utc|07:00|none)|close=\d{3,5}(\.\d{1,2})?)$")


# ---------------------------------------------------------------------------------------------- data
def ctx(tag):
    tag = tag or ("final" if (ROOT / "outputs" / "final" / "forecast_record.json").exists() else "preview")
    out = ROOT / "outputs" / tag
    snap = ROOT / ("data/raw_final" if tag == "final" else "data/raw_live")
    rec_path = out / "forecast_record.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    R = json.loads((out / "results.json").read_text(encoding="utf-8"))
    cut = pd.Timestamp(rec["information_cutoff_utc"]).tz_convert("UTC")
    return dict(tag=tag, out=out, snap=snap, rec=rec, rec_path=rec_path, R=R, cut=cut, target=pd.Timestamp(R["target_date"]))


def chart(path):
    r = json.loads(path.read_text(encoding="utf-8"))["chart"]["result"][0]
    return pd.Series(r["indicators"]["quote"][0]["close"], index=pd.to_datetime(r["timestamp"], unit="s", utc=True)).dropna()


def spx_series(c, cut=None):
    cut = cut if cut is not None else c["cut"]
    s = chart(c["snap"] / "gspc_daily.json")
    s.index = s.index.tz_convert(NY).normalize().tz_localize(None)
    close_utc = (s.index + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC")
    dropped = s[close_utc > cut]
    s = s[close_utc <= cut].copy()
    corr = ROOT / "data" / "price_corrections.json"
    if corr.exists():
        for d, v in json.loads(corr.read_text(encoding="utf-8")).get("spx", {}).items():
            if pd.Timestamp(d) in s.index:
                s.loc[pd.Timestamp(d)] = v
    return s, dropped


def es_all(c):
    p = c["snap"] / "es_5m.json"
    if not p.exists():
        return None
    es = chart(p)
    es.index = es.index + pd.Timedelta(minutes=5)            # index = bar END: a bar is usable only once it has ended
    return es


def es_series(c):
    es = es_all(c)
    if es is None:
        return None, 0
    return es[es.index <= c["cut"]], int((es.index > c["cut"]).sum())


def es_at(es, t):
    s = es[es.index <= t]
    return (float(s.iloc[-1]), s.index[-1]) if len(s) else (np.nan, None)


def horizon(last, target):
    days = pd.bdate_range(last + pd.Timedelta(days=1), target)
    return int((~days.isin(HOLIDAYS)).sum())


def drift(s, h, start=None, how="median"):
    x = s[s.index >= pd.Timestamp(start)] if start else s
    lr = np.log(x.shift(-h) / x).dropna()
    return float(np.median(lr) if how == "median" else lr.mean())


def ny16(d):
    return (pd.Timestamp(d) + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC")


def overnight_mean(s, es, cut, read="12utc", shift_h=0.0):
    """Mean overnight move: previous trading day's 16:00 New York -> read time on the next trading day, up to the cutoff.
    read = "12utc" (the pipeline: 12:00 UTC, i.e. 08:00 New York in summer) or "07ny"; shift_h moves the read time earlier."""
    r = []
    for dprev, d in zip(s.index[:-1], s.index[1:]):
        t = ((pd.Timestamp(d.date()).tz_localize("UTC") + pd.Timedelta(hours=12)) if read == "12utc" else
             (pd.Timestamp(d.date()) + pd.Timedelta(hours=7)).tz_localize(NY).tz_convert("UTC")) - pd.Timedelta(hours=shift_h)
        if t > cut or t < es.index[0] or ny16(dprev) < es.index[0]:
            continue
        x = np.log(es_at(es, t)[0] / es_at(es, ny16(dprev))[0])
        if abs(x) <= 0.04:
            r.append(x)
    return float(np.mean(r)), len(r)


def parts(c, read_shift_h=0.0, e_read="12utc"):
    s, dropped = spx_series(c)
    S, last = float(s.iloc[-1]), s.index[-1]
    h = horizon(last, c["target"])
    nc = c["R"].get("nowcast", {})
    es, n_after = es_series(c)
    if nc.get("es_source") == "manual" and read_shift_h == 0:
        # Bloomberg backup: the run used two prices typed in by a member; use them, and the run's average overnight move
        p0, p1 = float(nc["es_close_prev_session"]), float(nc["es_at_cutoff"])
        t0, t1 = "16:00 New York (manual entry)", f"cutoff ({nc.get('es_bar_end_used', 'manual')})"
        e, n_e = float(nc["mean_overnight_drift_pct"]) / 100, nc.get("n_days_validation", 0)
        src = "manual"
    else:
        p0, t0 = es_at(es, ny16(last))
        p1, t1 = es_at(es, c["cut"] - pd.Timedelta(hours=read_shift_h))
        e, n_e = overnight_mean(s, es, c["cut"], e_read, read_shift_h)
        src = "yahoo"
    return dict(s=s, S=S, last=last, h=h, p0=p0, t0=t0, p1=p1, t1=t1, g=np.log(p1 / p0), e=e, n_e=n_e,
                m0=drift(s, h), dropped=dropped, n_after=n_after, src=src, es=es)


def f2(x):
    return f"{x:,.2f}"


def ok(a, b, tol):
    return "MATCH" if abs(a - b) <= tol else f"DIFFERS by {a - b:+.4f}"


def nyt(t):
    return t.tz_convert(NY).strftime("%a %d %b %H:%M New York") if hasattr(t, "tz_convert") else str(t)


# ---------------------------------------------------------------------------------------------- commands
def cmd_record(c):
    rec, p = c["rec"], parts(c)
    sha = hashlib.sha256(c["rec_path"].read_bytes()).hexdigest()
    man = json.loads((c["snap"] / "manifest.json").read_text(encoding="utf-8"))
    files = man["files"]
    files = files if isinstance(files, list) else [dict(name=k, **v) for k, v in files.items()]
    got = {f["name"]: f.get("retrieved_utc", man.get("retrieved_utc")) for f in files if f["name"] in ("gspc_daily.json", "es_5m.json")}
    print(f"Record ({c['tag']}): forecast {f2(rec['forecast'])}, status '{rec.get('status', '')}', sha256 {sha[:12]}...")
    print(f"Target: {rec['target']}. Cutoff in the record: {c['cut']:%a %d %b %Y %H:%M} UTC ({c['cut'].tz_convert(NY):%H:%M} New York).")
    rule = "MATCH" if f"{c['cut']:%H:%M}" == BRIEF_CUTOFF_UTC else f"DIFFERS: the brief's cutoff is {BRIEF_CUTOFF_UTC} UTC (07:00 New York)"
    print(f"  brief's rule, cutoff at {BRIEF_CUTOFF_UTC} UTC: {rule}")
    print(f"Snapshot retrieved: S&P {got.get('gspc_daily.json')}, futures {got.get('es_5m.json')} (after the cutoff, so later rows are dropped).")
    print(f"Last usable S&P close: {p['last']:%a %d %b} = {f2(p['S'])}; later daily rows dropped: {len(p['dropped'])}. Horizon h = {p['h']} sessions.")
    if "last_usable_close" in rec:
        print(f"  record's last close {f2(rec['last_usable_close'])} vs raw file {f2(p['S'])}: {ok(rec['last_usable_close'], p['S'], 0.005)}")
    if p["src"] == "manual":
        print(f"Futures used: MANUAL ENTRY {f2(p['p0'])} -> {f2(p['p1'])} ({p['t1']}); Yahoo bars not used for the forecast.")
    else:
        print(f"Futures used: {f2(p['p0'])} at {nyt(p['t0'])} (cash close) -> {f2(p['p1'])} at {nyt(p['t1'])} (last bar ended by the cutoff); {p['n_after']} later bars dropped.")


def cmd_recompute(c):
    R, rec, p = c["R"], c["rec"], parts(c)
    nc = R["nowcast"]
    F = p["S"] * np.exp(p["m0"] + p["g"] - p["e"])
    print(f"Separate recalculation from the raw files (not run_model.py), tag {c['tag']}:")
    print(f"  last close     {f2(p['S'])}  vs pipeline {f2(R['last_close'])}: {ok(p['S'], R['last_close'], 0.005)}")
    print(f"  drift (median {p['h']}-session return since {p['s'].index[0].year})  {100 * p['m0']:.4f}%  vs {R['m0_pct']:.4f}%: {ok(100 * p['m0'], R['m0_pct'], 1e-4)}")
    print(f"  futures move ({p['src']})  {100 * p['g']:+.4f}%  vs {nc['overnight_return_pct']:+.4f}%: {ok(100 * p['g'], nc['overnight_return_pct'], 1e-4)}")
    print(f"  average overnight move ({p['n_e']} nights, read at 12:00 UTC)  {100 * p['e']:.4f}%  vs {nc['mean_overnight_drift_pct']:.4f}%: {ok(100 * p['e'], nc['mean_overnight_drift_pct'], 1e-4)}")
    print(f"  forecast {f2(p['S'])} x exp({100 * p['m0']:.4f}% {100 * (p['g'] - p['e']):+.4f}%) = {f2(F)}  vs record {f2(rec['forecast'])}: {ok(F, rec['forecast'], 0.01)}")
    print(f"  for comparison: no change {f2(p['S'])}; drift only {f2(p['S'] * np.exp(p['m0']))}")


def cmd_check(c):
    r = subprocess.run([sys.executable, str(ROOT / "code" / "independent_check.py"), "--snapshot", str(c["snap"].relative_to(ROOT)), "--tag", c["tag"]],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"independent_check.py FAILED (exit {r.returncode}):\n{r.stdout[-800:]}{r.stderr[-800:]}")
        return
    k = json.loads((c["out"] / "independent_check.json").read_text(encoding="utf-8"))
    print(f"independent_check.py (second code path + leak test), tag {c['tag']}: PASS_ALL = {k['PASS_ALL']}")
    print(f"  drift matches {k.get('m0_matches')}, futures nowcast matches {k.get('nowcast_matches')}, last close matches {k.get('last_close_matches')}, "
          f"forecast recomputed {f2(k.get('forecast_recomputed', float('nan')))} matches record {k.get('forecast_matches_record')}")
    nleak = sum(v.get("bars_corrupted", 0) for kk, v in k.items() if kk.startswith("leak_") and isinstance(v, dict))
    print(f"  leak test: {nleak} post-cutoff values corrupted on purpose, inputs unchanged = {k.get('leak_test_pass')}")
    # independent_check.py compares with results.json (it runs before build_report.py writes forecast_record.json)
    res_f, rec_f = c["R"]["forecast_final"], c["rec"]["forecast"]
    print(f"  note: that check compares with results.json ({f2(res_f)}), not the signed record; forecast_record.json says {f2(rec_f)}: {ok(rec_f, res_f, 0.005)}")


def cmd_data(c, which):
    if which == "spx":
        full = chart(c["snap"] / "gspc_daily.json")
        full.index = full.index.tz_convert(NY).normalize().tz_localize(None)
        print(f"S&P 500 daily closes (Yahoo ^GSPC), a close counts once 16:00 New York has passed; cutoff {c['cut']:%d %b %H:%M} UTC:")
        for d, v in full.tail(6).items():
            used = ny16(d) <= c["cut"]
            print(f"  {d:%a %d %b}  {f2(v)}  {'used' if used else 'AFTER CUTOFF, dropped'}")
    elif which == "es":
        es = es_all(c)
        if es is None:
            print("No futures file in this snapshot (manual Bloomberg entry used instead)."); return
        win = es[(es.index > c["cut"] - pd.Timedelta(minutes=30)) & (es.index <= c["cut"] + pd.Timedelta(minutes=15))]
        print(f"E-mini futures 5-minute bars (Yahoo ES=F) around the cutoff ({c['cut'].tz_convert(NY):%H:%M} New York); time = bar end:")
        for t, v in win.items():
            print(f"  {t.tz_convert(NY):%a %d %b %H:%M}  {f2(v)}  {'used' if t <= c['cut'] else 'AFTER CUTOFF, dropped'}")
        _, last = spx_series(c)[0].iloc[-1], spx_series(c)[0].index[-1]
        p0, t0 = es_at(es, ny16(last))
        print(f"  previous cash close: bar ending {nyt(t0)} = {f2(p0)}")
    else:
        print("Choose: data spx | data es")


def cmd_explain(c, item):
    R, rec = c["R"], c["rec"]
    nc = R.get("nowcast", {})

    def where(fname, pattern):
        p = ROOT / "code" / fname
        if not p.exists():
            return f"code/{fname}"
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(pattern, line):
                return f"code/{fname}:{i}"
        return f"code/{fname}"
    text = {
        "drift": (f"Median of all past h-session log returns of the S&P 500 since 1990, using only returns already finished at the cutoff. "
                  f"h = {R.get('h_sessions')} sessions here; value {R['m0_pct']:.4f}%. Chosen over the mean because the score rewards being close "
                  f"(the median minimises absolute error). Code: {where('run_model.py', r'm0 = m0_full')}."),
        "futures": (f"log(ES at the cutoff / ES at 16:00 New York on the last close day), same front-month contract. Here {nc.get('es_close_prev_session')} -> "
                    f"{nc.get('es_at_cutoff')} = {nc.get('overnight_return_pct', float('nan')):+.4f}% (source: {nc.get('es_source', 'yahoo')}). "
                    f"Code: {where('run_model.py', r'r_now = ')}."),
        "overnight": (f"The average overnight move (16:00 New York -> 12:00 UTC, every pair of trading days in the futures file before the cutoff) is "
                      f"subtracted so only news, not the usual drift, enters. Value {nc.get('mean_overnight_drift_pct', float('nan')):.4f}% over "
                      f"{nc.get('n_days_validation')} nights. Note 12:00 UTC is 08:00 New York in summer. Code: {where('run_model.py', r'e_bar = ')}."),
        "cutoff": (f"Brief: every input must be available by Fri 13 Nov 2026 12:00 UTC (07:00 New York). This record's cutoff: {rec['information_cutoff_utc']}. "
                   f"A daily close counts once 16:00 New York has passed; a 5-minute bar once it has ended. Code: {where('common.py', r'def .*cutoff|cutoff')}."),
        "forecast": (f"Forecast = last close x exp(drift + futures move - average overnight move) = {f2(R['last_close'])} x exp({R['m0_pct']:.4f}% "
                     f"{nc.get('nowcast_adjustment_pct', float('nan')):+.4f}%) = {f2(R['forecast_final'])}. No factor enters (model frozen, kappa 0); "
                     f"no hand adjustment. Code: {where('run_model.py', r'forecast_final')}."),
        "check": (f"independent_check.py rebuilds the drift and futures nowcast in plain Python, re-runs the median regression with statsmodels, and "
                  f"corrupts every post-cutoff value to prove the inputs do not change. It compares with results.json because it runs before "
                  f"build_report.py writes forecast_record.json. Code: {where('independent_check.py', r'PASS_ALL')}."),
    }
    print(text.get(item, "Choose: explain drift | futures | overnight | cutoff | forecast | check"))


def cmd_whatif(c, opts):
    bad = [o for o in opts if not OPT_RE.match(o)]
    if not opts or bad:
        print(f"Not understood: {' '.join(bad) or '(nothing)'}. Use one or more of: drift=median|median:<year>|mean|mean:<year>|none|fixed|<x>% ; "
              "futures=none|HH:MM ; overnight=12utc|07:00|none ; close=<points>. Presets: " + ", ".join(WHATIF))
        return
    p = parts(c)
    base = p["S"] * np.exp(p["m0"] + p["g"] - p["e"])
    S, m, g, e, notes = p["S"], p["m0"], p["g"], p["e"], []
    for o in opts:
        k, v = o.split("=", 1)
        if k == "drift":
            if v == "none":
                m = 0.0; notes.append("no drift")
            elif v == "fixed":
                m = 0.0025 * p["h"] / 6; notes.append("fixed +0.25% per 6 sessions")
            elif v.endswith("%"):
                m = float(v[:-1]) / 100; notes.append(f"expected return {v} over the horizon")
            else:
                how, _, yr = v.partition(":")
                if how.isdigit():
                    how, yr = "median", how
                m = drift(p["s"], p["h"], f"{yr}-01-01" if yr else None, how); notes.append(f"{how} drift since {yr or p['s'].index[0].year}")
        elif k == "futures":
            if v == "none":
                g = e = 0.0; notes.append("no futures move")
            else:
                hh, mm = map(int, v.split(":"))
                read = (pd.Timestamp(c["cut"].tz_convert(NY).date()) + pd.Timedelta(hours=hh, minutes=mm)).tz_localize(NY).tz_convert("UTC")
                shift = (c["cut"] - read).total_seconds() / 3600
                if shift < 0 or shift > 12:
                    print(f"futures={v}: must be at or before the cutoff ({c['cut'].tz_convert(NY):%H:%M} New York) and within 12 hours of it."); return
                if p["es"] is None:
                    print("futures=HH:MM needs the Yahoo futures file; this run used manual prices."); return
                q = parts(c, read_shift_h=shift)
                g, e = q["g"], q["e"]
                notes.append(f"futures read at {v} New York ({f2(q['p1'])}); average overnight move re-measured {shift:.2f} h earlier ({100 * q['e']:.4f}%)")
        elif k == "overnight":
            if v == "none":
                e = 0.0; notes.append("average overnight move not subtracted")
            elif v == "07:00":
                if p["es"] is None:
                    print("overnight=07:00 needs the Yahoo futures file."); return
                e, n7 = overnight_mean(p["s"], p["es"], c["cut"], "07ny"); notes.append(f"average overnight move at 07:00 New York ({100 * e:.4f}%, {n7} nights)")
            else:
                notes.append("average overnight move at 12:00 UTC (as submitted)")
        elif k == "close":
            S = float(v); notes.append(f"last close {f2(S)} instead of {f2(p['S'])}")
    F = S * np.exp(m + g - e)
    print(f"What if: {'; '.join(notes)}")
    print(f"  close {f2(S)}, drift {100 * m:.3f}% (was {100 * p['m0']:.3f}%), futures nowcast {100 * (g - e):+.3f}% (was {100 * (p['g'] - p['e']):+.3f}%)")
    rec_f = c["rec"]["forecast"]
    print(f"  forecast {f2(F)} vs this tool's baseline recalculation {f2(base)}: {F - base:+.2f} points ({100 * (F / base - 1):+.2f}%).")
    print(f"  the record says {f2(rec_f)}{'' if abs(rec_f - base) < 0.01 else ' (DIFFERS from the baseline recalculation)'}; the record is not changed.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["record", "recompute", "check", "data", "explain", "whatif"])
    ap.add_argument("args", nargs="*", help="for data: spx|es; for explain: an item; for whatif: one or more changes")
    ap.add_argument("--tag", choices=["final", "preview", "rehearsal"])
    a = ap.parse_args()
    c = ctx(a.tag)
    if a.cmd == "record":
        cmd_record(c)
    elif a.cmd == "recompute":
        cmd_recompute(c)
    elif a.cmd == "check":
        cmd_check(c)
    elif a.cmd == "data":
        cmd_data(c, a.args[0] if a.args else "")
    elif a.cmd == "explain":
        cmd_explain(c, a.args[0] if a.args else "")
    else:
        cmd_whatif(c, a.args)


if __name__ == "__main__":
    main()
