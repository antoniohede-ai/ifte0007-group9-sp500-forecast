"""run_model.py (v2) - factor SEARCH on macro and market data, pre-registered selection, walk-forward validation, final forecast.

Deterministic: reads only the saved snapshot (data/raw_*/), applies the information cutoff, writes outputs/<tag>/.

    python code/run_model.py --snapshot data/raw_live --cutoff 2026-10-30T12:00:00Z --target 2026-11-06 --tag rehearsal
    python code/run_model.py --snapshot data/raw_final --cutoff 2026-11-13T12:00:00Z --target 2026-11-20 --tag final

PROTOCOL (fixed before results were inspected; see agent/AGENT_INSTRUCTIONS.md)
  y        = ln(S[t+h] / S[t]),  h = NYSE sessions from the last observed close to the target close
  B0       unchanged price;  B1 = expanding median h-session return (all history to the origin)
  Candidates (15, each with an economic sign fixed in advance) are screened one at a time by walk-forward median
  (LAD) regression: forecast deviation from B1 = b * z.  Score = Diebold-Mariano t of (B1 error - candidate error) on
  the VALIDATION block of weekly origins.  A factor is eligible only if (i) its fitted sign matches the mechanism,
  (ii) t >= 1.65 and, where a long-history proxy exists (2000-2012 validation), the proxy does not contradict it
  (t >= 0), else t >= 2.33.  At most two eligible factors with the highest t and |corr| < 0.7 enter the model.
  mu       = m0 + kappa * (b . z),   kappa in {0, .25, .5, .75, 1} chosen on the validation block only
  nowcast  = ES futures return, 16:00 ET close -> cutoff, less its mean overnight drift
  forecast = S_t * exp(mu + nowcast)
The loss for fitting and selection is the assignment's own: absolute % level error (conditional median is optimal).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import warnings
from math import erf, sqrt

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import NY, ROOT, load_daily, load_es, load_treasury, load_zaki, sessions_between, utc  # noqa: E402

warnings.filterwarnings("ignore")

KAPPA_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
M_START, M_VALID_END = pd.Timestamp("2018-01-01"), pd.Timestamp("2021-12-31")     # macro-sample screening blocks (workbook now reaches back to 2015)
L_START, L_VALID_END = pd.Timestamp("2000-01-01"), pd.Timestamp("2012-12-31")     # long-history proxy blocks
MIN_TRAIN_M, MIN_TRAIN_L = 350, 1500

# name: (label, source, expected sign, formula)
META = {
    "mom252": ("252-day trend", "S&P 500 close", +1, "ln(S_t / S_t-252)"),
    "rev5": ("5-day reversal", "S&P 500 close", -1, "ln(S_t / S_t-5)"),
    "vrp": ("Variance risk premium", "VIX, S&P 500", +1, "VIX_t^2 - RV21_t^2"),
    "dvix5": ("5-day VIX change", "VIX", -1, "VIX_t - VIX_t-5"),
    "dd252": ("Drawdown from 1-year high", "S&P 500 close", -1, "ln(S_t / max S over 252d) <= 0"),
    "d2y20": ("2Y yield 20-day change", "Macro: US 2Y Treasury yield", -1, "y2_t - y2_t-20 (pp)"),
    "d10y20": ("10Y yield 20-day change", "Macro: US 10Y Treasury yield", -1, "y10_t - y10_t-20 (pp)"),
    "slope": ("Curve slope 10Y-2Y", "Macro: 2Y and 10Y yields", +1, "y10_t - y2_t (pp)"),
    "usd20": ("USD 20-day return", "Macro: US dollar index", -1, "ln(USD_t / USD_t-20)"),
    "gold20": ("Gold 20-day return", "Macro: gold", -1, "ln(Gold_t / Gold_t-20)"),
    "semirel20": ("Semiconductors vs S&P 500", "Macro: US semiconductor index", +1, "20d log return of semis minus 20d log return of S&P"),
    "esi": ("Economic surprise level", "Macro: US economic surprise index", +1, "ESI_t"),
    "desi20": ("Economic surprise 20-day change", "Macro: US economic surprise index", +1, "ESI_t - ESI_t-20"),
    "dcpi63": ("CPI inflation change (3m)", "Macro: US CPI y/y", -1, "CPI_yoy_t - CPI_yoy_t-63 sessions"),
    "dppi63": ("PPI inflation change (3m)", "Macro: US PPI y/y", -1, "PPI_yoy_t - PPI_yoy_t-63 sessions"),
    "vixlvl": ("VIX level (fear premium)", "VIX", +1, "VIX_t"),
}
PRICE = {"mom252", "rev5", "vrp", "dvix5", "dd252", "vixlvl"}
PROXY = {"d10y20", "slope", "usd20", "gold20", "semirel20"} | PRICE      # candidates with a long-history (1990/2000-) series to corroborate
MACRO_COLS = {"d2y20": ["y2"], "d10y20": ["y10"], "slope": ["y10", "y2"], "usd20": ["usd"], "gold20": ["gold"], "semirel20": ["semi"],
              "esi": ["esi"], "desi20": ["esi"], "dcpi63": ["cpi"], "dppi63": ["ppi"]}
ZAKI_SOURCE_OF = {"y2": "US 2Y yield", "y10": "US 10Y yield", "usd": "USD index", "gold": "gold", "semi": "BBG US semis",
                  "esi": "Economic Surprise Index", "cpi": "US CPI", "ppi": "US PPI"}


# ----------------------------------------------------------------------------------------------- estimation
def lad(X: np.ndarray, y: np.ndarray, iters: int = 80) -> np.ndarray:
    """Least-absolute-deviations (median) regression by IRLS with normal equations."""
    b = np.linalg.solve(X.T @ X, X.T @ y)
    for _ in range(iters):
        w = 1.0 / np.maximum(np.abs(y - X @ b), 1e-4)
        Xw = X * w[:, None]
        nb = np.linalg.solve(X.T @ Xw, Xw.T @ y)
        if np.max(np.abs(nb - b)) < 1e-8:
            return nb
        b = nb
    return b


def ols(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def lag(a: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    out[k:] = a[:-k]
    return out


def price_features(P: pd.DataFrame, L: int = 252, rvw: int = 21) -> dict:
    lS = np.log(P.spx.values); V = P.vix.values
    ret = np.r_[np.nan, np.diff(lS)]
    rv = pd.Series(ret).rolling(rvw).std().values * np.sqrt(252) * 100
    F = {"mom252": lS - lag(lS, L), "rev5": lS - lag(lS, 5), "vrp": V ** 2 - rv ** 2, "dvix5": V - lag(V, 5), "vixlvl": V.copy(),
         "dd252": lS - pd.Series(lS).rolling(252).max().values, "_rv": rv}
    return F


def macro_features(P: pd.DataFrame, F: dict) -> dict:
    g = lambda c: P[c].values
    lS = np.log(P.spx.values)
    F["d2y20"] = g("y2") - lag(g("y2"), 20); F["d10y20"] = g("y10") - lag(g("y10"), 20); F["slope"] = g("y10") - g("y2")
    F["usd20"] = np.log(g("usd")) - lag(np.log(g("usd")), 20); F["gold20"] = np.log(g("gold")) - lag(np.log(g("gold")), 20)
    ls = np.log(g("semi")); F["semirel20"] = (ls - lag(ls, 20)) - (lS - lag(lS, 20))
    F["esi"] = g("esi"); F["desi20"] = g("esi") - lag(g("esi"), 20)
    F["dcpi63"] = g("cpi") - lag(g("cpi"), 63); F["dppi63"] = g("ppi") - lag(g("ppi"), 63)
    return F


def long_features(PL: pd.DataFrame) -> dict:
    F = price_features(PL)
    g = lambda c: PL[c].values
    lS = np.log(g("spx"))
    F["d10y20"] = g("tnx") - lag(g("tnx"), 20); F["slope"] = g("tnx") - g("irx")
    F["usd20"] = np.log(g("dxy")) - lag(np.log(g("dxy")), 20); F["gold20"] = np.log(g("goldf")) - lag(np.log(g("goldf")), 20)
    ls = np.log(g("sox")); F["semirel20"] = (ls - lag(ls, 20)) - (lS - lag(lS, 20))
    return F


def m0_full(y: np.ndarray, o: int, h: int) -> float:
    v = y[: o - h + 1]
    return float(np.median(v[np.isfinite(v)]))


def fit_dev(cols: list, y: np.ndarray, o: int, h: int, min_train: int, window: int | None = None, loss=lad):
    """Fit on rows whose target was realised by origin o; return (dev, coefs, mean, std, n_rows). dev = b . z_o (no intercept)."""
    hi = o - h
    lo = 0 if window is None else max(0, hi - window)
    X = np.column_stack(cols)
    rows = np.arange(lo, hi + 1)
    ok = np.isfinite(X[rows]).all(axis=1) & np.isfinite(y[rows])
    rows = rows[ok]
    if len(rows) < min_train or not np.isfinite(X[o]).all():
        return None
    Xt = X[rows]; mu_, sd_ = Xt.mean(0), Xt.std(0)
    sd_ = np.where(sd_ < 1e-12, 1.0, sd_)
    Z = (Xt - mu_) / sd_
    b = loss(np.column_stack([np.ones(len(Z)), Z]), y[rows])
    zo = (X[o] - mu_) / sd_
    return float(zo @ b[1:]), b, mu_, sd_, len(rows), zo


def walk_forward(F, names, y, h, origins, min_train, window=None, loss=lad):
    cols = [F[n] for n in names]
    dev, sgn_ = [], []
    for o in origins:
        r = fit_dev(cols, y, o, h, min_train, window, loss)
        dev.append(np.nan if r is None else r[0]); sgn_.append(np.nan if r is None else np.sign(r[1][1]))
    return np.array(dev), np.array(sgn_)


# ----------------------------------------------------------------------------------------------- metrics
def level_err(S0, A, mu):
    return 100 * np.abs(S0 * np.exp(mu) - A) / A


def score(E):
    return 50 - np.minimum(50, 5 * E)


def nw_t(d, lag_=1):
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 10:
        return np.nan, np.nan
    dm = d - d.mean(); v = dm @ dm / n
    for k in range(1, lag_ + 1):
        v += 2 * (1 - k / (lag_ + 1)) * (dm[k:] @ dm[:-k] / n)
    t = d.mean() / np.sqrt(v / n)
    return float(t), float(2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2)))))


# ----------------------------------------------------------------------------------------------- data panel
def build_panel(snap: pathlib.Path, cutoff: pd.Timestamp):
    spx_y = load_daily(snap / "gspc_daily.json", cutoff, "16:00")
    vix_y = load_daily(snap / "vix_daily.json", cutoff, "16:15")
    zpath = snap / "zaki_data.xlsx"
    # The supporting workbook is OPTIONAL and never a forecast input: it only feeds cross-checks and the macro candidates of the screen.
    Z = load_zaki(zpath, cutoff) if zpath.exists() else None
    # model inputs are public data only: Yahoo, with a short list of known-bad Yahoo values replaced by the Cboe value
    spx, vix = spx_y.copy(), vix_y.copy()
    corr = json.loads((ROOT / "data" / "price_corrections.json").read_text(encoding="utf-8"))
    for s_, key in ((spx, "spx"), (vix, "vix")):
        for d_, v_ in corr[key].items():
            if pd.Timestamp(d_) in s_.index:
                s_.loc[pd.Timestamp(d_)] = v_
    P = pd.DataFrame({"spx": spx}); P["vix"] = vix.reindex(P.index).ffill()
    tsy = load_treasury(snap / "treasury_yields.csv", cutoff)
    px = {"usd": load_daily(snap / "dxy_daily.json", cutoff, "17:00"), "gold": load_daily(snap / "gold_daily.json", cutoff, "17:00"),
          "semi": load_daily(snap / "sox_daily.json", cutoff, "16:00")}
    ext = {}
    for k in ("y2", "y10", "usd", "gold", "semi", "esi", "cpi", "ppi"):
        s = Z[k].copy() if Z is not None else pd.Series(dtype=float); added = 0
        if Z is None:                                   # no workbook: public proxies only (Treasury, Yahoo); surprise index/CPI/PPI unavailable
            proxy0 = {"y2": tsy["2 Yr"], "y10": tsy["10 Yr"]}.get(k, px.get(k))
            s = proxy0.copy() if proxy0 is not None else s
            ext[k] = (s, 0)
            P[k] = s.reindex(P.index, method="ffill", limit=6) if len(s) else np.nan
            continue
        proxy = {"y2": tsy["2 Yr"], "y10": tsy["10 Yr"]}.get(k, px.get(k))
        if proxy is not None and len(s) and proxy.index[-1] > s.index[-1]:
            d0 = proxy.index[proxy.index <= s.index[-1]][-1]; new = proxy[proxy.index > s.index[-1]]
            if k in ("y2", "y10"):
                add = s.iloc[-1] + (new - proxy[d0])
            else:
                add = s.iloc[-1] * new / proxy[d0]
            s = pd.concat([s, add]); added = len(add)
        ext[k] = (s, added)
        P[k] = s.reindex(P.index, method="ffill", limit=6) if k not in ("cpi", "ppi") else s.reindex(P.index, method="ffill", limit=75)
    # long-history proxy panel (Yahoo only) used for robustness screening
    PL = pd.DataFrame({"spx": spx}); PL["vix"] = vix.reindex(PL.index).ffill()      # same override applied
    for k, f_, hhmm in (("tnx", "tnx_daily.json", "17:00"), ("irx", "irx_daily.json", "17:00"), ("dxy", "dxy_daily.json", "17:00"),
                        ("goldf", "gold_daily.json", "17:00"), ("sox", "sox_daily.json", "16:00")):
        PL[k] = load_daily(snap / f_, cutoff, hhmm).reindex(PL.index, method="ffill", limit=6)
    cov = {k: {"workbook_last": (str(Z[k].index[-1].date()) if Z is not None and len(Z[k]) else None), "extended_obs": v[1],
               "last_used": (str(v[0].index[-1].date()) if len(v[0]) else None)} for k, v in ext.items()}
    return P, PL, Z, tsy, cov, {"spx": spx_y, "vix": vix_y}


# ----------------------------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True); ap.add_argument("--cutoff", required=True)
    ap.add_argument("--target", required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--allow-stale", action="store_true", help="carry forward stale workbook series (preview runs only)")
    ap.add_argument("--allow-factor-entry", action="store_true", help="let a factor that passes the screen enter the model (OFF: the model is frozen)")
    ap.add_argument("--es-manual", nargs=2, type=float, metavar=("ES_1600_PREV", "ES_CUTOFF"),
                    help="backup if Yahoo has no usable bars: ES (front month, e.g. Bloomberg ESZ6) at 16:00 NY on the last close day and at the cutoff")
    ap.add_argument("--es-manual-source", default="", help="required with --es-manual: where and when the two prices were read")
    a = ap.parse_args()
    snap = ROOT / a.snapshot
    out = ROOT / "outputs" / a.tag
    (out / "tables").mkdir(parents=True, exist_ok=True); (out / "figures").mkdir(parents=True, exist_ok=True)
    cutoff, target = utc(a.cutoff), pd.Timestamp(a.target)

    P, PL, Z, tsy, cov, yraw = build_panel(snap, cutoff)
    if a.es_manual and not a.es_manual_source:
        raise SystemExit("--es-manual needs --es-manual-source (where and when the prices were read)")
    es = load_es(snap / "es_5m.json", cutoff) if (snap / "es_5m.json").exists() or not a.es_manual else None
    dates = P.index; n = len(P); S = P.spx.values; logS = np.log(S); V = P.vix.values
    last = dates[-1]; o = n - 1
    h = sessions_between(last, target); wd = last.weekday()
    print(f"cutoff {cutoff}  last close {last.date()} = {S[-1]:.2f}  VIX {V[-1]:.2f}  h = {h}  weekday {wd}")
    y = np.full(n, np.nan); y[:-h] = logS[h:] - logS[:-h]
    nL = len(PL); ylong = np.full(nL, np.nan); lSL = np.log(PL.spx.values); ylong[:-h] = lSL[h:] - lSL[:-h]

    # ------------------------------------------------------------------ data reconciliation (three independent comparisons)
    chk = pd.read_csv(snap / "check_cboe_spx.csv"); chk["DATE"] = pd.to_datetime(chk["DATE"]); chk = chk.set_index("DATE")["SPX"]; chk = chk[chk.index <= last]
    j = pd.concat([yraw["spx"], chk], axis=1, keys=["yahoo", "cboe"], sort=True).dropna(); rel = (j.yahoo / j.cboe - 1).abs() * 100
    d0 = rel.idxmax(); prev = chk.index[chk.index.get_loc(d0) - 1]
    dc = {"yahoo_vs_cboe_days": int(len(j)), "yahoo_vs_cboe_over_0.05pct": int((rel > 0.05).sum()), "yahoo_vs_cboe_max_pct": float(rel.max()),
          "yahoo_vs_cboe_max_date": str(d0.date()), "cboe_repeats_prior_day_on_max": bool(abs(chk[d0] - chk[prev]) < 1e-6),
          "last_close_used": float(S[-1]), "last_close_cboe": float(chk.iloc[-1]) if chk.index[-1] == last else None}
    cv = pd.read_csv(snap / "check_cboe_vix.csv"); cv["DATE"] = pd.to_datetime(cv["DATE"]); cv = cv.set_index("DATE")["CLOSE"]
    corr = json.loads((ROOT / "data" / "price_corrections.json").read_text(encoding="utf-8"))
    vj = pd.concat([yraw["vix"], cv], axis=1, keys=["y", "c"], sort=True).dropna(); vdiff = (vj.y - vj.c).abs()
    dc.update({"yahoo_vs_cboe_vix_over_0.05": int((vdiff > 0.05).sum()), "corrections_applied": int(sum(len(v) for k, v in corr.items() if k in ("spx", "vix")))})
    if Z is not None:      # optional cross-check against the supporting workbook (never an input to the forecast)
        zs = pd.concat([Z["spx"], yraw["spx"]], axis=1, keys=["z", "y"], sort=True).dropna(); zr = (zs.z / zs.y - 1).abs() * 100
        zz = pd.concat([Z["spx"], chk], axis=1, keys=["z", "c"], sort=True).dropna(); zzr = (zz.z / zz.c - 1).abs() * 100
        zv = pd.concat([Z["vix"], yraw["vix"]], axis=1, keys=["z", "y"], sort=True).dropna(); zvd = (zv.z - zv.y).abs()
        zvc = pd.concat([Z["vix"], cv], axis=1, keys=["z", "c"], sort=True).dropna(); zvcd = (zvc.z - zvc.c).abs()
        zy = pd.concat([Z["y2"], tsy["2 Yr"]], axis=1, keys=["z", "t"], sort=True).dropna(); zy10 = pd.concat([Z["y10"], tsy["10 Yr"]], axis=1, keys=["z", "t"], sort=True).dropna()
        dc.update({"workbook_spx_vs_yahoo_over_0.05pct": int((zr > 0.05).sum()), "workbook_spx_vs_yahoo_dates": [str(d.date()) for d in zr[zr > 0.05].index],
                   "workbook_spx_vs_cboe_over_0.05pct": int((zzr > 0.05).sum()),
                   "workbook_vix_vs_yahoo_over_0.05": int((zvd > 0.05).sum()), "workbook_vix_vs_yahoo_dates": [str(d.date()) for d in zvd[zvd > 0.05].index],
                   "workbook_vix_vs_cboe_over_0.05": int((zvcd > 0.05).sum()),
                   "workbook_2y_vs_treasury_median_abs_bp": float(100 * (zy.z - zy.t).abs().median()), "workbook_10y_vs_treasury_median_abs_bp": float(100 * (zy10.z - zy10.t).abs().median())})

    # ------------------------------------------------------------------ factor SCREEN
    F = macro_features(P, price_features(P)); FL = long_features(PL)
    names = [k for k in META]
    orig_m = np.array([i for i in range(n) if dates[i] >= M_START and dates[i].weekday() == wd and i + h <= n - 1])
    valid_m = np.array([dates[i] <= M_VALID_END for i in orig_m]); test_m = ~valid_m
    S0m, Am = S[orig_m], S[orig_m + h]
    m0m = np.array([m0_full(y, i, h) for i in orig_m])
    E_B0m = level_err(S0m, Am, np.zeros(len(orig_m))); E_B1m = level_err(S0m, Am, m0m)
    orig_l = np.array([i for i in range(nL) if PL.index[i] >= L_START and PL.index[i].weekday() == wd and i + h <= nL - 1])
    valid_l = np.array([PL.index[i] <= L_VALID_END for i in orig_l]); test_l = ~valid_l
    S0l, Al = PL.spx.values[orig_l], PL.spx.values[orig_l + h]
    m0l = np.array([m0_full(ylong, i, h) for i in orig_l])
    E_B1l = level_err(S0l, Al, m0l)

    devs, rows = {}, []
    for nm in names:
        dev, sg = walk_forward(F, [nm], y, h, orig_m, MIN_TRAIN_M if nm in MACRO_COLS else MIN_TRAIN_L)
        devs[nm] = dev
        E = level_err(S0m, Am, m0m + np.where(np.isfinite(dev), dev, 0.0))
        ok = np.isfinite(dev)
        tv, pv = nw_t((E_B1m - E)[valid_m & ok]); tt, pt = nw_t((E_B1m - E)[test_m & ok])
        r = {"factor": nm, "label": META[nm][0], "source": META[nm][1], "expected_sign": META[nm][2],
             "fitted_sign_share_pos": float(np.nanmean(sg[valid_m & ok] > 0)) if (valid_m & ok).any() else np.nan,
             "n_valid": int((valid_m & ok).sum()), "t_valid": tv, "t_test": tt,
             "score_gain_valid": float((score(E) - score(E_B1m))[valid_m & ok].mean()) if (valid_m & ok).any() else np.nan,
             "score_gain_test": float((score(E) - score(E_B1m))[test_m & ok].mean()) if (test_m & ok).any() else np.nan}
        if nm in PROXY:
            devl, _ = walk_forward(FL, [nm], ylong, h, orig_l, MIN_TRAIN_L)
            El = level_err(S0l, Al, m0l + np.where(np.isfinite(devl), devl, 0.0)); okl = np.isfinite(devl)
            r["t_long_valid"], _ = nw_t((E_B1l - El)[valid_l & okl]); r["t_long_test"], _ = nw_t((E_B1l - El)[test_l & okl])
        else:
            r["t_long_valid"] = r["t_long_test"] = np.nan
        rows.append(r)
        print(f"  screened {nm:10s} t_valid {tv:6.2f}  t_test {tt:6.2f}  long_valid {r['t_long_valid']:6.2f}")
    scr = pd.DataFrame(rows)

    def eligible(r):
        sign_ok = (r.expected_sign > 0 and r.fitted_sign_share_pos > 0.7) or (r.expected_sign < 0 and r.fitted_sign_share_pos < 0.3)
        if not np.isfinite(r.t_valid) or not sign_ok:
            return False
        if np.isfinite(r.t_long_valid):
            return r.t_valid >= 1.65 and r.t_long_valid >= 0.0
        return r.t_valid >= 2.33
    scr["eligible"] = scr.apply(eligible, axis=1)
    # selection: highest t, at most two, pairwise |corr| < 0.7 (on the training sample used at the last origin)
    sel = []
    for nm in scr[scr.eligible].sort_values("t_valid", ascending=False).factor:
        if len(sel) == 2:
            break
        ok = True
        for s_ in sel:
            m = np.isfinite(F[nm]) & np.isfinite(F[s_])
            if m.sum() > 100 and abs(np.corrcoef(F[nm][m], F[s_][m])[0, 1]) >= 0.7:
                ok = False
        if ok:
            sel.append(nm)
    rule_sel = list(sel)
    scr["passes_rule"] = scr.factor.isin(rule_sel)
    if not a.allow_factor_entry:          # FROZEN MODEL (group decision, 10 Nov): the screen is reported, never acted on
        sel = []
    scr["selected"] = scr.factor.isin(sel)
    scr.to_csv(out / "tables" / "factor_screen.csv", index=False)
    print("RULE WOULD SELECT:", rule_sel or "none", "| FACTOR ENTRY:", "on" if a.allow_factor_entry else "off (frozen)", "| USED:", sel or "drift + nowcast only")

    # staleness guard: a selected factor must be covered up to the cutoff
    stale = []
    for nm in sel:
        for c in MACRO_COLS.get(nm, []):
            lastobs = P[c].last_valid_index()
            lag_s = sessions_between(lastobs, last) if lastobs is not None and lastobs < last else 0
            if lag_s > 2:
                stale.append({"factor": nm, "series": ZAKI_SOURCE_OF[c], "last_obs": str(lastobs.date()), "sessions_stale": int(lag_s)})
    if stale and not a.allow_stale:
        raise SystemExit(f"STOP: selected factor(s) rely on workbook data that ends before the cutoff: {stale}. Refresh those series in the supporting workbook "
                         f"through {last.date()} and re-run (or pass --allow-stale for a labelled preview).")

    # ------------------------------------------------------------------ model evaluation with the selected factors
    if sel:
        dev_sel, _ = walk_forward(F, sel, y, h, orig_m, MIN_TRAIN_M)
    else:
        dev_sel = np.zeros(len(orig_m))
    ok = np.isfinite(dev_sel)
    kap_rows = []
    for k in KAPPA_GRID:
        E = level_err(S0m, Am, m0m + k * np.where(ok, dev_sel, 0))
        kap_rows.append({"kappa": k, "valid_MAPE_%": E[valid_m & ok].mean(), "test_MAPE_%": E[test_m & ok].mean(),
                         "valid_score": score(E[valid_m & ok]).mean(), "test_score": score(E[test_m & ok]).mean()})
    kap = pd.DataFrame(kap_rows).set_index("kappa"); kap.to_csv(out / "tables" / "kappa_selection.csv")
    kappa = float(kap["valid_MAPE_%"].idxmin()) if sel else 0.0
    mu_final_bt = m0m + kappa * np.where(ok, dev_sel, 0)
    E_F = level_err(S0m, Am, mu_final_bt)
    # also the best single screened factor as a named comparator, and the all-candidate "kitchen sink" (trend+VRP) from v1
    dev_v1, _ = walk_forward(F, ["mom252", "vrp"], y, h, orig_m, MIN_TRAIN_L)
    E_v1 = level_err(S0m, Am, m0m + np.where(np.isfinite(dev_v1), dev_v1, 0))
    top = scr.sort_values("t_valid", ascending=False).iloc[0].factor
    E_top = level_err(S0m, Am, m0m + np.where(np.isfinite(devs[top]), devs[top], 0.0))
    models = {"B0 unchanged": E_B0m, "B1 median drift": E_B1m, f"Best-ranked candidate alone ({META[top][0]})": E_top, "Trend + VRP (earlier design)": E_v1,
              ("Final: drift + " + " + ".join(META[s][0] for s in sel)) if sel else "Final: median drift": E_F}
    perf = []
    for blk, mask in (("validation", valid_m), ("test", test_m), ("all", np.ones(len(orig_m), bool))):
        for nm, E in models.items():
            t0, p0 = (np.nan, np.nan) if nm.startswith("B0") else nw_t((E_B0m - E)[mask])
            t1, p1 = (np.nan, np.nan) if nm.startswith(("B0", "B1")) else nw_t((E_B1m - E)[mask])
            perf.append({"block": blk, "model": nm, "n": int(mask.sum()), "MAPE_%": E[mask].mean(), "median_APE_%": np.median(E[mask]),
                         "mean_score": score(E[mask]).mean(), "worst_APE_%": E[mask].max(), "DM_t_vs_B0": t0, "DM_p_vs_B0": p0, "DM_t_vs_B1": t1, "DM_p_vs_B1": p1})
    perf = pd.DataFrame(perf); perf.to_csv(out / "tables" / "performance.csv", index=False)
    final_name = list(models)[-1]
    # OOS R2 of final vs B1 (log-return MSE) on the test block
    lr = np.log(Am / S0m)
    r2 = 100 * (1 - ((lr - mu_final_bt)[test_m] ** 2).sum() / ((lr - m0m)[test_m] ** 2).sum())
    bt = pd.DataFrame({"date": dates[orig_m], "S0": S0m, "A": Am, "VIX0": V[orig_m], "m0": m0m, "dev": dev_sel, "F_final": S0m * np.exp(mu_final_bt),
                       "APE_final": E_F, "APE_B0": E_B0m, "APE_B1": E_B1m})
    bt.to_csv(out / "tables" / "backtest_origins.csv", index=False)
    worst = bt.sort_values("APE_final", ascending=False).head(6); worst.to_csv(out / "tables" / "worst_errors.csv", index=False)

    # ------------------------------------------------------------------ final fit on all information up to the cutoff
    m0 = m0_full(y, o, h)
    if sel:
        dev_now, b, mcol, scol, nrow, zo = fit_dev([F[s_] for s_ in sel], y, o, h, MIN_TRAIN_M)
    else:
        dev_now, b, mcol, scol, nrow, zo = 0.0, np.array([m0]), np.array([]), np.array([]), 0, np.array([])
    mu_final = m0 + kappa * dev_now
    contrib = {s_: float(kappa * b[1 + i] * zo[i]) for i, s_ in enumerate(sel)}
    x_now = {s_: float(F[s_][o]) for s_ in sel}

    # ------------------------------------------------------------------ ES nowcast and its validation
    ny_close = lambda d: (pd.Timestamp(d) + pd.Timedelta(hours=16)).tz_localize(NY).tz_convert("UTC")
    def es_at(t):
        s = es[es.index <= t]
        return (float(s.iloc[-1]), s.index[-1]) if len(s) else (np.nan, None)
    nrows = []
    for i in (range(1, n) if es is not None else []):
        d, dprev = dates[i], dates[i - 1]
        t12 = pd.Timestamp(d.date()).tz_localize("UTC") + pd.Timedelta(hours=12)
        if t12 > cutoff or t12 < es.index[0] or ny_close(dprev) < es.index[0]:
            continue
        p0_, _ = es_at(ny_close(dprev)); p1_, _ = es_at(t12)
        r_ovn = np.log(p1_ / p0_)
        if abs(r_ovn) > 0.04:
            continue
        nrows.append({"date": d, "i": i, "r_ovn": r_ovn, "R_day": logS[i] - logS[i - 1]})
    nc = pd.DataFrame(nrows, columns=["date", "i", "r_ovn", "R_day"])
    if len(nc) >= 20:
        e_bar = float(nc.r_ovn.mean())
    else:  # no usable Yahoo history: mean overnight move from the group's Bloomberg test (07:00 NY, 138 days)
        e_bar = float(json.loads((ROOT / "data" / "group_evidence" / "futures_bloomberg_test31" / "futures_anchor.json").read_text())["e_all"])
    if len(nc) >= 20:
        X = np.column_stack([np.ones(len(nc)), nc.r_ovn.values.astype(float)]); bb = ols(X, nc.R_day.values.astype(float)); res_ = nc.R_day.values - X @ bb
        cov_ = (res_ @ res_ / (len(nc) - 2)) * np.linalg.inv(X.T @ X)
        beta, se_beta = float(bb[1]), float(np.sqrt(cov_[1, 1])); r2n = float(1 - res_ @ res_ / ((nc.R_day - nc.R_day.mean()) ** 2).sum())
    else:  # no Yahoo history (Bloomberg backup only): the validation stats are not recomputed
        beta = se_beta = r2n = None
    lev = []
    for _, r_ in nc.iterrows():
        j_ = int(r_.i) + h - 1
        if j_ <= n - 1:
            A_ = S[j_]; F0 = S[int(r_.i) - 1]
            lev.append({"APE_unchanged": 100 * abs(F0 - A_) / A_, "APE_nowcast": 100 * abs(F0 * np.exp(r_.r_ovn - e_bar) - A_) / A_})
    lev = pd.DataFrame(lev, columns=["APE_unchanged", "APE_nowcast"]); nc.to_csv(out / "tables" / "nowcast_check.csv", index=False)
    if a.es_manual:
        p0_, p1_ = a.es_manual; t1_ = f"manual: {a.es_manual_source}"
    else:
        (p0_, t0_), (p1_, t1_) = es_at(ny_close(last)), es_at(cutoff)
        # the two bars must be the ones ending at 16:00 NY and at the cutoff; a stale bar would silently move the forecast
        stale = [f"{lab} bar ends {t}" for lab, t, want in (("close", t0_, ny_close(last)), ("cutoff", t1_, cutoff))
                 if t is None or want - t > pd.Timedelta(minutes=10)]
        if stale and a.tag == "final":
            raise SystemExit("ES bars missing or stale (" + "; ".join(map(str, stale)) + "). Re-fetch, or use the Bloomberg backup: "
                             "--es-manual <ES 16:00 NY> <ES at cutoff> --es-manual-source '<terminal, ticker, times>'")
        if stale:
            print("WARNING: stale ES bar(s):", stale)
    r_now = float(np.log(p1_ / p0_)); nowcast = r_now - e_bar
    nowcast_info = {"es_close_prev_session": p0_, "es_at_cutoff": p1_, "es_bar_end_used": str(t1_), "es_source": "manual" if a.es_manual else "yahoo", "overnight_return_pct": 100 * r_now,
                    "mean_overnight_drift_pct": 100 * e_bar, "nowcast_adjustment_pct": 100 * nowcast, "n_days_validation": int(len(nc)),
                    "beta_cash_on_overnight": beta, "beta_se": se_beta, "r2": r2n, "level_n": int(len(lev)),
                    "level_MAPE_unchanged": float(lev.APE_unchanged.mean()) if len(lev) else None, "level_MAPE_nowcast": float(lev.APE_nowcast.mean()) if len(lev) else None}
    F_final = S[o] * np.exp(mu_final + nowcast)

    # ------------------------------------------------------------------ prediction interval (long-history B1 residuals scaled by VIX)
    zres = np.log(Al / (S0l * np.exp(m0l))) / (PL.vix.values[orig_l] / 100 * np.sqrt(h / 252))
    q10, q90 = np.quantile(zres[np.isfinite(zres)], [0.10, 0.90])
    sig_now = V[o] / 100 * np.sqrt(h / 252)
    ci = (F_final * np.exp(q10 * sig_now), F_final * np.exp(q90 * sig_now))

    # ------------------------------------------------------------------ sensitivity of the final forecast: drift choice and futures timing
    def nowcast_at(hh, mm=0):
        """Nowcast measured at hh:mm UTC on the cutoff date (must not be after the cutoff), with its own mean overnight drift."""
        if es is None:  # Bloomberg backup without Yahoo bars: no timing variants
            return None
        rr = []
        for i in range(1, n):
            d, dprev = dates[i], dates[i - 1]
            t_ = pd.Timestamp(d.date()).tz_localize("UTC") + pd.Timedelta(hours=hh, minutes=mm)
            if t_ > cutoff or t_ < es.index[0] or ny_close(dprev) < es.index[0]:
                continue
            r_ = np.log(es_at(t_)[0] / es_at(ny_close(dprev))[0])
            if abs(r_) <= 0.04:
                rr.append(r_)
        tc = cutoff.normalize() + pd.Timedelta(hours=hh, minutes=mm)
        if tc > cutoff or not rr:
            return None
        return float(np.log(es_at(tc)[0] / p0_) - np.mean(rr))
    yv = y[: o - h + 1]; dv_ = dates[: o - h + 1]
    drifts = {"Final: median since 1990": m0, "Median since 2000": float(np.nanmedian(yv[dv_ >= "2000-01-01"])),
              "Fixed +0.25% per 6 sessions": 0.0025 * h / 6, "Mean since 1990": float(np.nanmean(yv)), "No drift (unchanged centre)": 0.0}
    fs = []
    for lab, m_ in drifts.items():
        fs.append({"variant": lab, "group": "drift", "mu_pct": 100 * m_, "nowcast_pct": 100 * nowcast, "forecast": float(S[o] * np.exp(m_ + nowcast))})
    ctime = cutoff.tz_convert("UTC")
    for hh, mm in ((ctime.hour - 1, ctime.minute), (ctime.hour - 2, ctime.minute)):
        nv = nowcast_at(hh, mm)
        if nv is not None:
            ny_t = (cutoff.normalize() + pd.Timedelta(hours=hh, minutes=mm)).tz_convert(NY)
            fs.append({"variant": f"Futures read at {hh:02d}:{mm:02d} UTC ({ny_t:%H:%M} New York)", "group": "timing", "mu_pct": 100 * m0, "nowcast_pct": 100 * nv,
                       "forecast": float(S[o] * np.exp(m0 + nv))})
    fs.append({"variant": "No futures nowcast", "group": "timing", "mu_pct": 100 * m0, "nowcast_pct": 0.0, "forecast": float(S[o] * np.exp(m0))})
    fs = pd.DataFrame(fs); fs.to_csv(out / "tables" / "final_sensitivity.csv", index=False)

    # ------------------------------------------------------------------ scenarios: shock the last observation and re-score the model
    def scenario(label, shocks):
        P2 = P.copy(); row = P2.iloc[-1].copy()
        row["spx"] = row["spx"] * np.exp(shocks.get("spx", 0)); row["vix"] = shocks.get("vix", row["vix"])
        for c, dlt in (("y2", "dy2"), ("y10", "dy10")):
            row[c] = row[c] + shocks.get(dlt, 0)
        for c in ("usd", "gold", "semi"):
            row[c] = row[c] * np.exp(shocks.get(c, 0))
        row.name = P2.index[-1] + pd.Timedelta(days=1); P2.loc[row.name] = row
        F2 = macro_features(P2, price_features(P2)); i2 = len(P2) - 1
        dv = sum(b[1 + i] * ((F2[s_][i2] - mcol[i]) / scol[i]) for i, s_ in enumerate(sel)) if sel else 0.0
        mu_ = m0 + kappa * dv
        return {"scenario": label, "spx_shock_pct": 100 * shocks.get("spx", 0), "vix": float(row["vix"]), "mu_pct": 100 * mu_,
                "base_index": float(row["spx"]), "forecast": float(row["spx"] * np.exp(mu_))}
    scen = pd.DataFrame([
        scenario("Relief: index +2%, VIX 17, 2Y -10bp, semis +5%", {"spx": 0.02, "vix": 17.0, "dy2": -0.10, "semi": 0.05}),
        scenario("Adverse A: AI/chip rout continues (index -4%, VIX 30, semis -10%)", {"spx": -0.04, "vix": 30.0, "semi": -0.10}),
        scenario("Adverse B: hawkish shock (index -3%, VIX 27, 2Y +20bp, 10Y +15bp, USD +1.5%)", {"spx": -0.03, "vix": 27.0, "dy2": 0.20, "dy10": 0.15, "usd": 0.015})])
    scen.to_csv(out / "tables" / "scenarios.csv", index=False)

    # ------------------------------------------------------------------ record
    ptest = perf[perf.block == "test"].set_index("model"); pval = perf[perf.block == "validation"].set_index("model")
    res = {
        "tag": a.tag, "market": "S&P 500 price index (SPX)", "unit": "index points",
        "target": f"{target.date()} official close (16:00 America/New_York)", "cutoff_utc": str(cutoff), "target_date": str(target.date()),
        "last_close_date": str(last.date()), "last_close": float(S[o]), "vix_last": float(V[o]), "h_sessions": int(h), "origin_weekday": int(wd),
        "selected": sel, "rule_selected": rule_sel, "factor_entry": "on" if a.allow_factor_entry else "off (frozen)", "labels": {s_: META[s_][0] for s_ in sel}, "formulas": {s_: META[s_][3] for s_ in sel}, "sources": {s_: META[s_][1] for s_ in sel},
        "expected_sign": {s_: META[s_][2] for s_ in sel},
        "kappa": kappa, "coef_per_sd_pct": {s_: 100 * float(b[1 + i]) for i, s_ in enumerate(sel)}, "z_now": {s_: float(zo[i]) for i, s_ in enumerate(sel)},
        "x_now": x_now, "contrib_pct": {k: 100 * v for k, v in contrib.items()}, "train_rows": int(nrow),
        "m0_pct": 100 * m0, "dev_unshrunk_pct": 100 * dev_now, "mu_final_pct": 100 * mu_final,
        "nowcast": nowcast_info, "forecast_model_only": float(S[o] * np.exp(mu_final)), "forecast_final": round(float(F_final), 2),
        "interval80": [round(float(ci[0]), 2), round(float(ci[1]), 2)], "discretionary_adjustment_pct": 0.0,
        "features_context": {"rv21_pct": float(F["_rv"][o]), "mom252_pct": 100 * float(F["mom252"][o]), "rev5_pct": 100 * float(F["rev5"][o]),
                             "dd252_pct": 100 * float(F["dd252"][o]), "vrp": float(F["vrp"][o])},
        "windows": {"macro_start": str(M_START.date()), "valid_end": str(M_VALID_END.date()), "n_origins": int(len(orig_m)), "n_valid": int(valid_m.sum()),
                    "n_test": int(test_m.sum()), "first_origin": str(dates[orig_m[0]].date()), "last_origin": str(dates[orig_m[-1]].date()),
                    "long_valid_n": int(valid_l.sum()), "long_test_n": int(test_l.sum())},
        "screen": scr.replace({np.nan: None}).to_dict("records"), "n_candidates": len(names),
        "perf_test": ptest.reset_index().replace({np.nan: None}).to_dict("records"), "perf_valid": pval.reset_index().replace({np.nan: None}).to_dict("records"),
        "final_model_name": final_name, "oos_r2_final_vs_B1_test_pct": float(r2), "kappa_table": kap.reset_index().to_dict("records"),
        "final_sensitivity": fs.to_dict("records"), "scenarios": scen.to_dict("records"), "data_checks": dc, "coverage": cov, "stale": stale,
        "worst_errors": worst.assign(date=worst.date.astype(str)).to_dict("records"),
        "package_versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
    }
    full = load_daily(snap / "gspc_daily.json", utc("2100-01-01"), "16:00")
    if target in full.index:
        A_ = float(full.loc[target]); res["realised_in_snapshot"] = A_
        res["rehearsal_APE_%"] = 100 * abs(F_final - A_) / A_; res["rehearsal_APE_unchanged_%"] = 100 * abs(S[o] - A_) / A_
        res["rehearsal_APE_B1_%"] = 100 * abs(S[o] * np.exp(m0) - A_) / A_
    (out / "results.json").write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    trace = [{"step": "last close S_t", "value": S[o]}, {"step": "median h-session return m0 (all history) (%)", "value": 100 * m0}]
    for s_ in sel:
        trace.append({"step": f"factor {s_}: {META[s_][0]} raw {x_now[s_]:.4f}, z {zo[sel.index(s_)]:.2f}, contribution after kappa (%)", "value": 100 * contrib[s_]})
    trace += [{"step": f"expected return = m0 + kappa({kappa}) x factor fit (%)", "value": 100 * mu_final},
              {"step": "futures nowcast adjustment (%)", "value": 100 * nowcast}, {"step": "discretionary adjustment (%)", "value": 0.0},
              {"step": "FINAL forecast", "value": round(float(F_final), 2)}]
    pd.DataFrame(trace).to_csv(out / "tables" / "calculation_trace.csv", index=False)
    print(json.dumps({k: res[k] for k in ["selected", "kappa", "forecast_final", "interval80", "mu_final_pct", "z_now", "contrib_pct"]}, indent=1))
    print(scr[["factor", "t_valid", "t_test", "t_long_valid", "eligible", "selected"]].round(2).to_string())
    print(perf[perf.block != "all"].round(3).to_string()); print(kap.round(3).to_string()); print(fs.round(2).to_string()); print(scen.round(1).to_string())
    print(json.dumps(nowcast_info, indent=1, default=float)); print({k: res.get(k) for k in ["realised_in_snapshot", "rehearsal_APE_%", "rehearsal_APE_unchanged_%", "rehearsal_APE_B1_%"]})


if __name__ == "__main__":
    main()
