"""Recompute the 930-origin futures test's headline tables from the saved per-origin file, without the licensed prices.

    python recompute_from_origin_errors.py            # run from anywhere; needs numpy and pandas only

`origin_errors.csv` (derived values only: no TradingView prices) has one row per weekday origin d with
  g      log gap, ES 16:00 New York to the next 07:00 New York          drift  median 6-session log return known at the origin
  y      realised 6-session log return                                   A0..B4 absolute percentage error (%) of each forecast
From these the script rebuilds the Friday and weekday tables (mean error, score, Newey-West t against A1) and the slope of
(y - drift) on g. The output should match `futures_results.md` line for line: that is the check.
The code of the statistics is copied from the group repository (drift-asia/model/walkforward.py, futures/run_futures.py).
"""
import pathlib

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
LABELS = {"A0": "S&P(p), no change", "A1": "S&P(p) x exp(drift)  [current model w/o Asia]", "B0": "S&P(p) x exp(g)", "B1": "S&P(p) x exp(g + drift)",
          "B2": "S&P(p) x exp(g + 5/6 drift)", "B3": "S&P(p) x exp(0.5 g + drift)", "B4": "S&P(p) x exp(0.75 g + drift)"}


def score(e_pct):
    return 50 - np.minimum(50, 0.5 * np.asarray(e_pct, dtype=float) / 0.1)       # brief: 0.5 marks per 0.1% of error


def nw_t(d, lags=2):
    d = pd.Series(d).dropna().values
    n = len(d)
    if n < 6:
        return np.nan
    m = d.mean(); u = d - m
    v = u @ u / n
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / n
    return m / np.sqrt(v / n) if v > 0 else np.nan


def nw_se_slope(x, y, lags=5):
    x, y = np.asarray(x), np.asarray(y)
    X = np.column_stack([np.ones(len(x)), x]); b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b; XtXi = np.linalg.inv(X.T @ X)
    S = (X * u[:, None]).T @ (X * u[:, None])
    for k in range(1, lags + 1):
        G = (X[k:] * u[k:, None]).T @ (X[:-k] * u[:-k, None]); S += (1 - k / (lags + 1)) * (G + G.T)
    V = XtXi @ S @ XtXi
    return b[1], float(np.sqrt(V[1, 1])), float(1 - (u @ u) / ((y - y.mean()) @ (y - y.mean())))


def main():
    R = pd.read_csv(HERE / "origin_errors.csv", parse_dates=["d"]).set_index("d")
    print(f"Origins: {len(R)} weekdays ({int((R.dow == 4).sum())} Fridays), {R.index[0].date()} to {R.index[-1].date()}\n")
    for title, S in (("PRIMARY: Friday origins", R[R.dow == 4]), ("SECONDARY: every weekday origin", R)):
        cut = S.index[int(len(S) * 0.7)]
        print(f"== {title}: n={len(S)}, unseen part from {cut.date()} (n={int((S.index >= cut).sum())}) ==")
        print(f"{'forecast':52s} {'MAE all':>8s} {'MAE unseen':>10s} {'score all':>9s} {'t vs A1 all':>11s} {'t vs A1 unseen':>14s}")
        for k, lab in LABELS.items():
            ea, eu = S[k], S[k][S.index >= cut]
            t_all = nw_t((S["A1"] - S[k]).values, 2) if k != "A1" else float("nan")
            t_un = nw_t((S["A1"][S.index >= cut] - eu).values, 2) if k != "A1" else float("nan")
            print(f"{k + ' ' + lab:52s} {ea.mean():8.4f} {eu.mean():10.4f} {score(ea).mean():9.3f} {t_all:11.2f} {t_un:14.2f}")
        print()
    S = R[R.dow == 4]
    b, se, r2 = nw_se_slope(R["g"], R["y"] - R["drift"])
    bf, sef, r2f = nw_se_slope(S["g"], S["y"] - S["drift"], lags=1)
    print("Gap g (ES 16:00 to next 07:00 New York, log):")
    print(f"  std {R.g.std():.4f}, mean |g| {R.g.abs().mean():.4f} (all weekdays); Fridays std {S.g.std():.4f}, mean |g| {S.g.abs().mean():.4f}")
    print(f"  6-day return minus drift regressed on g, all weekdays: slope {b:.2f} (NW se {se:.2f}), R2 {r2:.3f}")
    print(f"  same, Fridays only: slope {bf:.2f} (se {sef:.2f}), R2 {r2f:.3f}")


if __name__ == "__main__":
    main()
