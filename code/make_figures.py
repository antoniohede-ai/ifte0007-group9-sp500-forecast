"""make_figures.py (v2) - workflow diagram, factor-screen chart, backtest chart, forecast fan.
    python code/make_figures.py --tag rehearsal --snapshot data/raw_live"""
import argparse
import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, load_daily, utc  # noqa: E402

INK, MUTED = "#1f2933", "#6b7280"
C = {"agent": "#1d4e89", "tool": "#2a7f62", "check": "#b45309", "human": "#7c3a8a", "data": "#52606d"}


def box(ax, x, y, w, h, text, color, fs=7.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc="white", ec=color, lw=1.6))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.22), w, 0.22, boxstyle="round,pad=0.0,rounding_size=0.05", fc=color, ec=color))
    title, *body = text.split("\n")
    ax.text(x + w / 2, y + h - 0.11, title, ha="center", va="center", color="white", fontsize=fs, fontweight="bold")
    ax.text(x + w / 2, y + (h - 0.22) / 2, "\n".join(body), ha="center", va="center", color=INK, fontsize=fs - 0.6, linespacing=1.25)


def arrow(ax, p, q, color=MUTED):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3, shrinkA=0, shrinkB=0))


def workflow(path, res):
    fig, ax = plt.subplots(figsize=(10.2, 5.2))
    ax.set_xlim(0, 10.2); ax.set_ylim(0, 5.4); ax.axis("off")
    td = pd.Timestamp(res["target_date"]); co = pd.Timestamp(res["cutoff_utc"])
    ax.text(0.05, 5.22, f"GOAL: one point forecast of the S&P 500 official close on {td.day} {td:%b %Y}, using only information available by the "
                        f"{co.day} {co:%b} {co:%H:%M} UTC cutoff", fontsize=8.4, fontweight="bold", color=INK, va="center")
    box(ax, 0.05, 3.55, 2.3, 1.2, "1 PERCEIVE (agent + tools)\nretrieve dated raw files: Yahoo SPX,\nVIX, ES futures; US Treasury; Cboe\ncheck; group workbook (helper);\nURL, time, SHA-256 logged", C["tool"])
    box(ax, 2.6, 3.55, 2.3, 1.2, "2 FREEZE + CUTOFF FILTER\nraw snapshot saved read-only;\na value enters only if its official\nclose / bar end <= cutoff;\nlast usable obs recorded", C["data"])
    box(ax, 5.15, 3.55, 2.3, 1.2, "3 CALCULATE (Python tool)\nscreen 16 candidate factors\nwalk-forward LAD regression\nbenchmarks B0, B1\nfutures overnight nowcast", C["tool"])
    box(ax, 7.7, 3.55, 2.45, 1.2, "4 AGENT DECISIONS\napply pre-registered rule:\nkeep only factors that beat drift;\nchoose kappa on validation only;\nwrite calculation trace", C["agent"])
    box(ax, 0.05, 1.75, 3.2, 1.3, "5 CHECKS (independent of step 3)\n(a) Yahoo / Cboe / workbook / Treasury\nreconciliation (b) second code path:\nstatsmodels, plain-Python median\n(c) leak test: corrupt post-cutoff\nbars, inputs must not change", C["check"])
    box(ax, 3.5, 1.75, 3.2, 1.3, "6 EVALUATE (chronological)\nweekly origins, h sessions ahead;\nvalidation block selects, later\ntest block untouched; long-history\ncorroboration; sensitivity;\nadverse scenarios; failures listed", C["tool"])
    box(ax, 6.95, 1.75, 3.2, 1.3, "7 HUMAN RESPONSIBILITY\neach member re-runs run_all.py, reads\nthe trace, checks the S&P DJI close,\napproves or vetoes; only the signed\nforecast record is submitted;\nno trading / execution", C["human"])
    box(ax, 0.05, 0.1, 10.1, 1.2, "8 OUTPUT (frozen before the 17:00 deadline)\nforecast_record.json (market, unit, target, cutoff, value) = report cover value  |  report PDF  |  slides  |  evidence ZIP + README\nAgent permissions: may read public data, run Python, write files.  May NOT trade, use post-cutoff data, or edit the forecast after approval.", C["data"], fs=7.8)
    for p, q in [((2.35, 4.15), (2.6, 4.15)), ((4.9, 4.15), (5.15, 4.15)), ((7.45, 4.15), (7.7, 4.15)), ((8.9, 3.55), (8.9, 3.05)),
                 ((3.25, 2.4), (3.5, 2.4)), ((6.7, 2.4), (6.95, 2.4)), ((1.6, 1.75), (1.6, 1.3)), ((5.1, 1.75), (5.1, 1.3)), ((8.5, 1.75), (8.5, 1.3))]:
        arrow(ax, p, q)
    arrow(ax, (6.3, 3.55), (5.6, 3.05), C["tool"])
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig)


def screen_and_backtest(res, out, path):
    scr = pd.DataFrame(res["screen"]).sort_values("t_valid")
    fig, axs = plt.subplots(1, 2, figsize=(10.4, 4.1), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axs[0]
    zaki = scr.source.str.startswith("Macro")
    colors = np.where(zaki, C["tool"], C["agent"])
    ax.barh(scr.label, scr.t_valid, color=colors, height=0.62)
    ax.scatter(scr.t_test, scr.label, marker="D", s=16, color=C["check"], zorder=5, label="test block (information only)")
    for x, ls in ((1.65, "--"), (2.33, ":")):
        ax.axvline(x, color=MUTED, ls=ls, lw=1)
    ax.axvline(0, color=INK, lw=0.8)
    ax.text(1.68, -0.9, "pass 1.65", fontsize=6.5, color=MUTED); ax.text(2.36, -0.9, "2.33", fontsize=6.5, color=MUTED)
    ax.set_title("Factor screen: does it beat median drift out of sample?\n(Diebold-Mariano t on validation block; teal = macro and cross-asset, blue = price/vol)", fontsize=8, color=INK)
    ax.tick_params(labelsize=6.8); ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    ax = axs[1]
    bt = pd.read_csv(out / "tables" / "backtest_origins.csv", parse_dates=["date"])
    ax.plot(bt.date, (bt.APE_B0 - bt.APE_final).cumsum(), color=C["agent"], lw=1.6, label="final vs B0 unchanged")
    ax.plot(bt.date, (bt.APE_B1 - bt.APE_final).cumsum(), color=C["tool"], lw=1.6, label="final vs B1 median drift")
    ax.axhline(0, color=MUTED, lw=0.8); ax.axvline(pd.Timestamp(res["windows"]["valid_end"]), color=C["check"], ls="--", lw=1)
    ax.set_title("Cumulative error reduction of the final model\n(% points of APE; above 0 = better)", fontsize=8, color=INK)
    ax.legend(fontsize=6.8, frameon=False); ax.tick_params(labelsize=6.8)
    for a_ in axs:
        for s in ("top", "right"):
            a_.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig)


def sensitivity(res, path):
    fs = pd.DataFrame(res["final_sensitivity"])
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.barh(fs.variant[::-1], fs.forecast[::-1], color=C["agent"], height=0.6)
    lo, hi = fs.forecast.min(), fs.forecast.max(); pad = max((hi - lo) * 0.5, 4)
    ax.set_xlim(lo - pad, hi + pad)
    for i, v in enumerate(fs.forecast[::-1]):
        ax.text(v, i, f" {v:,.1f}", va="center", fontsize=6.5, color=INK)
    ax.set_title("Final forecast under alternative assumptions (index points)", fontsize=8.5, color=INK); ax.tick_params(labelsize=6.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig)


def forecast_fan(res, snap, path):
    cutoff = utc(res["cutoff_utc"])
    s = load_daily(snap / "gspc_daily.json", cutoff, "16:00").iloc[-60:]
    full = load_daily(snap / "gspc_daily.json", utc("2100-01-01"), "16:00")
    tgt = pd.Timestamp(res["target_date"])
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.plot(s.index, s.values, color=C["agent"], lw=1.5, label="S&P 500 close (usable by cutoff)")
    ax.errorbar([tgt], [res["forecast_final"]], yerr=[[res["forecast_final"] - res["interval80"][0]], [res["interval80"][1] - res["forecast_final"]]],
                fmt="o", color=C["check"], capsize=4, label=f"forecast {res['forecast_final']:,.2f} (80% interval)")
    ax.plot([s.index[-1], tgt], [s.values[-1], res["forecast_final"]], color=C["check"], ls=":", lw=1)
    if res.get("realised_in_snapshot"):
        after = full[(full.index > s.index[-1]) & (full.index <= tgt)]
        ax.plot(after.index, after.values, color=C["human"], lw=1.2, ls="--", label="realised path (rehearsal only; not used)")
        ax.scatter([tgt], [res["realised_in_snapshot"]], marker="D", color=C["human"], zorder=5)
    ax.set_title("Forecast against recent index history", fontsize=9, color=INK); ax.legend(fontsize=6.5, frameon=False, loc="lower left"); ax.tick_params(labelsize=7)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", required=True); ap.add_argument("--snapshot", required=True)
    a = ap.parse_args()
    out = ROOT / "outputs" / a.tag
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    (out / "figures").mkdir(exist_ok=True)
    workflow(out / "figures" / "fig1_workflow.png", res)
    screen_and_backtest(res, out, out / "figures" / "fig2_screen_backtest.png")
    sensitivity(res, out / "figures" / "fig3_sensitivity.png")
    forecast_fan(res, ROOT / a.snapshot, out / "figures" / "fig4_forecast.png")
    print("figures written")
