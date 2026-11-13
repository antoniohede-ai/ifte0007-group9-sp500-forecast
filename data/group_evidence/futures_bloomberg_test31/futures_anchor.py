"""Test 31 (pre-registered in notes/prereg_futures_anchor.md, commit 3c588e9): futures nowcast as the starting level.

B = S exp(m + 0.5 a) (current model); C = S exp(m + r_ovn - e) (futures start); D = C + 0.5 a; A = drift only.
r_ovn(d) = log(ES 07:00 NY on d / ES 16:00 NY on the previous trading day). Bloomberg ES1 (01c) to 2 Nov,
Layla's Yahoo ES=F 5-minute bars after 2 Nov; both on the overlap for an agreement check only.
"""
import json

import numpy as np
import pandas as pd

from model import data, factors, walkforward as wf

HURDLE, LAGS, LAST = 3.16, 5, "2026-11-09"
DROP = {"2026-06-22", "2026-09-21"}  # first session after the June and September expiries (ends on different contracts)

reg = factors.load_registry("factors.yaml")
asia = next(f for f in reg["factors"] if f["name"] == "asia_overnight")
raw, _ = data.load_raw("data/public", reg["series"], {"GSPC"} | set(asia["series"]))
spx = raw["GSPC"].dropna().loc[:LAST]
F, _ = factors.build_factors({"factors": [asia]}, data.align(raw, reg["series"], spx.index))
idx = spx.index
y = wf.target_series(spx).values
thu = np.asarray(idx.day_of_week == wf.ORIGIN_DOW)
X = F[["asia_overnight"]].values.astype(float)

# Bloomberg 07:00 and 16:00 ES1 prices (bar-time rule: 06:59 and 15:59 bars only)
b = pd.read_csv("data/raw/bbg-drop/01c_es1_0700_1600_ny.csv", parse_dates=["date_new_york"]).set_index("date_new_york")
p07 = b["ES1 Index|price_at_0700_NY"].where(b.last_bar_start_NY_used_0700 == "06:59")
p16 = b["ES1 Index|price_at_1600_NY"].where(b.last_bar_start_NY_used_1600 == "15:59")

# Yahoo ES=F 5-minute bars (timestamps are bar starts): price at T = close of the bar starting at T - 5 min
j = json.load(open("data/raw/laila/es_5m.json"))["chart"]["result"][0]
yb = pd.Series(j["indicators"]["quote"][0]["close"], index=pd.to_datetime(j["timestamp"], unit="s", utc=True).tz_convert("America/New_York")).dropna()


def yahoo_at(day, hhmm):
    t = pd.Timestamp(f"{day.date()} {hhmm}").tz_localize("America/New_York") - pd.Timedelta(minutes=5)
    return float(yb[t]) if t in yb.index else np.nan


rows = []
for i in range(1, len(idx)):
    d, prev = idx[i], idx[i - 1]
    if str(d.date()) in DROP:
        continue
    rb = np.log(p07.get(d, np.nan) / p16.get(prev, np.nan))
    ry = np.log(yahoo_at(d, "07:00") / yahoo_at(prev, "16:00"))
    r = rb if d <= pd.Timestamp("2026-11-02") else ry
    if np.isfinite(r) and abs(r) <= 0.04:
        rows.append(dict(d=d, p=i - 1, r_ovn=r, r_bbg=rb, r_yahoo=ry))
R = pd.DataFrame(rows).set_index("d")
R["e"] = R.r_ovn.expanding().mean().shift(1).where(np.arange(len(R)) >= 20, 0.0).fillna(0.0)

cand = np.flatnonzero(thu & ~np.isnan(y))
out = []
for d, row in R.iterrows():
    p = int(row.p)
    if p + wf.H > len(idx) - 1:
        continue
    known = cand[cand <= p - wf.H]
    m = wf.drift_at(y[known], "median")
    fit = wf.fit_at(p, y, X, thu, wf.H)
    a = fit["signal"] if fit else np.nan
    S, A_ = spx.iloc[p], spx.iloc[p + wf.H]
    fc = dict(nochange=S, A=S * np.exp(m), B=S * np.exp(m + 0.5 * a), C=S * np.exp(m + row.r_ovn - row.e),
              D=S * np.exp(m + row.r_ovn - row.e + 0.5 * a))
    out.append(dict(origin=idx[p], thursday=bool(thu[p]), **{k: 100 * abs(v - A_) / A_ for k, v in fc.items()}))
E = pd.DataFrame(out).set_index("origin").dropna()


def line(name, e):
    t = lambda x, z: wf.nw_t((e[x] - e[z]).values, lags=LAGS)
    g = lambda x, z: (e[x] - e[z]).mean()
    return (f"{name}: n={len(e)} | " + ", ".join(f"{c} {e[c].mean():.3f}%" for c in ["nochange", "A", "B", "C", "D"]) +
            f" | C vs B gain {g('B', 'C'):+.4f} t {t('B', 'C'):.2f}; D vs C gain {g('C', 'D'):+.4f} t {t('C', 'D'):.2f}")


half = E.index[len(E) // 2]
L = ["Test 31: futures start (pre-registered, notes/prereg_futures_anchor.md). Errors: mean absolute % vs the close 6 trading days after the origin.",
     f"Origins {E.index[0].date()} to {E.index[-1].date()}; overnight moves: Bloomberg to 2 Nov, Yahoo after. NW t with {LAGS} lags; hurdle |t| >= {HURDLE}.", "",
     line("All origins", E), line("First half", E[E.index < half]), line("Second half", E[E.index >= half]),
     line("Thursday origins", E[E.thursday]), ""]
ov = R[["r_bbg", "r_yahoo"]].dropna()
L.append(f"Bloomberg vs Yahoo overnight move on the overlap: n={len(ov)}, correlation {ov.corr().iloc[0, 1]:.3f}, "
         f"median abs difference {100 * (ov.r_bbg - ov.r_yahoo).abs().median():.3f} pts of %, max {100 * (ov.r_bbg - ov.r_yahoo).abs().max():.3f}")
nd = pd.Series({d: np.log(spx.iloc[int(r.p) + 1] / spx.iloc[int(r.p)]) for d, r in R.iterrows() if int(r.p) + 1 < len(idx)})
Z = pd.concat([R.r_ovn, nd.rename("R_day")], axis=1).dropna()
beta = np.polyfit(Z.r_ovn, Z.R_day, 1)[0]
L.append(f"Next cash-day return on the overnight move: n={len(Z)}, slope {beta:.2f}, correlation {Z.corr().iloc[0, 1]:.2f} (Layla, 48 Yahoo days: slope 1.17, R2 0.26)")
gC, gD = [(E[a] - E[c]) for a, c in (("B", "C"), ("C", "D"))]
halves = lambda g: (g.mean() > 0) and (g[g.index < half].mean() > 0) and (g[g.index >= half].mean() > 0)
L += ["", f"Decision rule: adopt C if its gain over B is positive overall and in both halves -> {halves(gC)}; "
          f"keep Asia on top (D) if D beats C overall and in both halves -> {halves(gD)}; C passes |t| >= {HURDLE}: {abs(wf.nw_t(gC.values, lags=LAGS)) >= HURDLE}"]
L.append(f"Mean overnight move over all {len(R)} days (the e used live): {100 * R.r_ovn.mean():.4f}%")
text = "\n".join(L) + "\n"
open("results/futures_anchor.txt", "w").write(text)
json.dump({"e_all": float(R.r_ovn.mean()), "n_days": len(R), "first_day": str(R.index[0].date()), "last_day": str(R.index[-1].date())},
          open("results/futures_anchor.json", "w"), indent=1)
print(text)
