"""Recompute test 31's headline results from the saved per-origin errors, without the licensed Bloomberg prices.

    python recompute_from_origin_errors.py            # numpy and pandas only

`origin_errors_test31.csv` holds, for each of the 133 origins, the absolute percentage error (%) of five forecasts of the close six
sessions later: nochange; A = drift only; B = drift + 0.5 x Asia signal (the earlier group model); C = drift + overnight futures
move (the submitted model's form); D = C + 0.5 x Asia. It contains no Bloomberg prices: it was written by `futures_anchor.py`
(same folder) on the group's machine. Expected output: the n, errors, gains and t values on lines 4-7 of `futures_anchor.txt`
(C vs B), and the t values of C against drift alone (A) that the report cites (2.50 overall, 3.49 on Thursdays; `compare_mohamed.txt`).
The Newey-West code is copied from the group repository (drift-asia/model/walkforward.py).
"""
import pathlib

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
LAGS = 5


def nw_t(d, lags=2):
    d = pd.Series(d).dropna().values
    n = len(d)
    if n < 6:
        return float("nan")
    m = d.mean(); u = d - m
    v = u @ u / n
    for k in range(1, lags + 1):
        v += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / n
    return m / (v / n) ** 0.5 if v > 0 else float("nan")


def line(name, e):
    g = lambda x, z: (e[x] - e[z]).mean()
    t = lambda x, z: nw_t((e[x] - e[z]).values, LAGS)
    return (f"{name}: n={len(e)} | " + ", ".join(f"{c} {e[c].mean():.3f}%" for c in ["nochange", "A", "B", "C", "D"]) +
            f" | C vs B gain {g('B', 'C'):+.4f} t {t('B', 'C'):.2f}; D vs C gain {g('C', 'D'):+.4f} t {t('C', 'D'):.2f}"
            f" | C vs drift alone (A): {e.A.mean():.3f}% -> {e.C.mean():.3f}%, t {t('A', 'C'):.2f}")


def main():
    E = pd.read_csv(HERE / "origin_errors_test31.csv", parse_dates=["origin"]).set_index("origin")
    half = E.index[len(E) // 2]
    print(f"Origins {E.index[0].date()} to {E.index[-1].date()}; NW t with {LAGS} lags\n")
    for name, e in (("All origins", E), ("First half", E[E.index < half]), ("Second half", E[E.index >= half]), ("Thursday origins", E[E.thursday])):
        print(line(name, e))


if __name__ == "__main__":
    main()
