"""ES 07:00 New York anchor vs previous S&P close. Rules: futures/PREREG.md (committed before this ran)."""
import os, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from model import data, factors, walkforward as wf  # noqa: E402

OUT = ROOT / "futures" / "results"
ES = ROOT / "futures" / "data" / "ES1_60min_TradingView_20261110.csv"
H = 6
FORECASTS = {
    "A0 S&P(p), no change": None,
    "A1 S&P(p) x exp(drift)  [current model w/o Asia]": None,
    "B0 S&P(p) x exp(g)": None,
    "B1 S&P(p) x exp(g + drift)": None,
    "B2 S&P(p) x exp(g + 5/6 drift)": None,
    "B3 S&P(p) x exp(0.5 g + drift)": None,
    "B4 S&P(p) x exp(0.75 g + drift)": None,
}


def load_es():
    d = pd.read_csv(ES)
    d["t"] = pd.to_datetime(d["time"], utc=True).dt.tz_convert("America/New_York")
    d = d.set_index("t").sort_index()
    h = d.index.hour
    es16 = d.loc[h == 15, "close"]; es16.index = es16.index.tz_localize(None).normalize()
    es07 = d.loc[h == 6, "close"]; es07.index = es07.index.tz_localize(None).normalize()
    return d, es16[~es16.index.duplicated()], es07[~es07.index.duplicated()]


def roll_tuesdays(first, last):
    """Tuesday after the Monday (3rd Friday - 4 days) of Mar/Jun/Sep/Dec: the 18:00 Monday reopen carries the ES1! contract roll."""
    out = set()
    for y in range(first.year, last.year + 1):
        for m in (3, 6, 9, 12):
            fr = [x for x in pd.date_range(pd.Timestamp(y, m, 1), pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)) if x.weekday() == 4][2]
            out.add(fr - pd.Timedelta(days=3))   # Tuesday after the roll Monday
    return out


def nw_se_slope(x, y, lags=5):
    x, y = np.asarray(x), np.asarray(y)
    X = np.column_stack([np.ones(len(x)), x]); b = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ b; n = len(y); XtXi = np.linalg.inv(X.T @ X)
    S = (X * u[:, None]).T @ (X * u[:, None])
    for k in range(1, lags + 1):
        G = (X[k:] * u[k:, None]).T @ (X[:-k] * u[:-k, None]); S += (1 - k / (lags + 1)) * (G + G.T)
    V = XtXi @ S @ XtXi
    r2 = 1 - (u @ u) / ((y - y.mean()) @ (y - y.mean()))
    return b[1], float(np.sqrt(V[1, 1])), float(r2)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reg = factors.load_registry(ROOT / "factors.yaml")
    raw, _ = data.load_raw(ROOT / "data" / "public", reg["series"], {"GSPC", "N225", "HSI"})
    spx = raw["GSPC"].dropna()
    idx = spx.index
    lr = np.log(spx.values)
    N = len(idx)
    y6 = np.full(N, np.nan); y6[: N - H] = lr[H:] - lr[: N - H]
    d_es, es16, es07 = load_es()
    asia = next(f for f in reg["factors"] if f["name"] == "asia_overnight")
    F0, _ = factors.build_factors({"factors": [asia]}, data.align(raw, reg["series"], idx))
    rolls = roll_tuesdays(es07.index[0], es07.index[-1])

    rows, dropped = [], {"no futures price": 0, "roll window": 0}
    for i in range(1, N - H):
        d, p = idx[i], idx[i - 1]
        if d < es07.index[0] or p not in es16.index or d not in es07.index:
            if d >= es07.index[0]:
                dropped["no futures price"] += 1
            continue
        if d in rolls:
            dropped["roll window"] += 1
            continue
        g = np.log(es07[d] / es16[p])
        drift = float(np.median(y6[: i - 1 - H + 1]))      # outcomes known at p (position i-1): j <= i-1-H
        a = spx.iloc[i - 1 + H]
        base = spx.iloc[i - 1]
        row = dict(d=d, dow=d.weekday(), g=g, drift=drift, y=lr[i - 1 + H] - lr[i - 1], asia=F0["asia_overnight"].iloc[i - 1])
        for name, f in (("A0", 0.0), ("A1", drift), ("B0", g), ("B1", g + drift), ("B2", g + 5 / 6 * drift),
                        ("B3", 0.5 * g + drift), ("B4", 0.75 * g + drift)):
            row[name] = 100 * abs(base * np.exp(f) - a) / a
        rows.append(row)
    R = pd.DataFrame(rows).set_index("d")
    labels = list(FORECASTS)
    ids = ["A0", "A1", "B0", "B1", "B2", "B3", "B4"]
    L = [f"ES1! hourly bars {d_es.index[0]:%Y-%m-%d %H:%M} to {d_es.index[-1]:%Y-%m-%d %H:%M} ET, {len(d_es)} bars. S&P closes to {idx[-1].date()}.",
         f"Origins with a usable gap g: {len(R)} weekdays ({int((R.dow == 4).sum())} Fridays), {R.index[0].date()} to {R.index[-1].date()}. "
         f"Dropped: {dropped}. Roll Tuesdays excluded: {sorted(x.date().isoformat() for x in rolls if R.index[0] <= x <= R.index[-1])}", ""]
    for title, S in (("PRIMARY: Friday origins", R[R.dow == 4]), ("SECONDARY: every weekday origin", R)):
        cut = S.index[int(len(S) * 0.7)]
        L.append(f"== {title}: n={len(S)}, unseen part from {cut.date()} (n={int((S.index >= cut).sum())}) ==")
        L.append(f"{'forecast':52s} {'MAE all':>8s} {'MAE unseen':>10s} {'score all':>9s} {'t vs A1 all':>11s} {'t vs A1 unseen':>14s}")
        for k, lab in zip(ids, labels):
            ea, eu = S[k], S[k][S.index >= cut]
            t_all = wf.nw_t((S["A1"] - S[k]).values, 2) if k != "A1" else float("nan")
            t_un = wf.nw_t((S["A1"][S.index >= cut] - eu).values, 2) if k != "A1" else float("nan")
            L.append(f"{lab:52s} {ea.mean():8.4f} {eu.mean():10.4f} {wf.score(ea).mean():9.3f} {t_all:11.2f} {t_un:14.2f}")
        L.append("")
    S = R[R.dow == 4]
    b, se, r2 = nw_se_slope(R["g"], R["y"] - R["drift"])
    bf, sef, r2f = nw_se_slope(S["g"], S["y"] - S["drift"], lags=1)
    L += ["Gap g (ES 16:00 to next 07:00 New York, log):",
          f"  std {R.g.std():.4f}, mean |g| {R.g.abs().mean():.4f} (all weekdays); Fridays std {S.g.std():.4f}, mean |g| {S.g.abs().mean():.4f}",
          f"  6-day return minus drift regressed on g, all weekdays: slope {b:.2f} (NW se {se:.2f}), R2 {r2:.3f}",
          f"  same, Fridays only: slope {bf:.2f} (se {sef:.2f}), R2 {r2f:.3f}",
          f"  correlation of g with asia_overnight (Friday origins) {S.g.corr(S.asia):+.2f}; all weekdays {R.g.corr(R.asia):+.2f}", "",
          "Marks per 0.1 pp of error = 0.5 (brief): A1 -> B1 difference in mean error (Friday origins): "
          f"{(S.A1.mean() - S.B1.mean()):+.4f} pp = {(S.A1.mean() - S.B1.mean()) / 0.1 * 0.5:+.3f} marks."]
    text = "\n".join(L)
    (OUT / "futures_results.md").write_text(text)
    R.to_csv(OUT / "origin_errors.csv")
    print(text)


if __name__ == "__main__":
    main()
