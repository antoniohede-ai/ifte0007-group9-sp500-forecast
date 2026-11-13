# Model ranking and recommendation (10 Nov 2026)

Compares every model in this repo on the coursework's own terms: S&P 500 close 6 trading days ahead, mean absolute % error (MAPE), 0.5 marks lost per 0.1% of error. Sources:
- Each member's own results files.
- Antonio's re-runs: PR #6, `drift-asia/results/compare_mohamed.txt` and `futures_anchor.txt`.
- Jayen's futures test: PR #5, `drift-asia/futures/results/futures_results.md`.
- A new like-for-like check: `laila-package/code/compare_models.py`, output in `laila-package/outputs/extra/model_comparison.json`. It reads the Bloomberg 07:00 file in `drift-asia/data/raw/bbg-drop/` where it already sits and does not copy it.

## Recommendation
**Submit: median drift + the overnight futures move to the cutoff (07:00 New York), no factors, model frozen.** This is the model Layla's package implements and Antonio's test 31 adopted. It's the only change to "drift alone" that reliably lowers error, and the evidence comes from three independent tests on three data sources (Bloomberg, TradingView and Yahoo).

Use **Layla's package (PR #7)** to submit it. It is the only complete deliverable (report, 5 slides, evidence ZIP and a one-command final run). It reproduces exactly and passes its leak tests. The final run is already scheduled for 13 Nov after 12:00 UTC.

## Ranking
| Rank | Model | Who | Key evidence | Verdict |
|---|---|---|---|---|
| 1 | **Median drift + overnight futures (07:00 NY)** | Layla (pipeline), Antonio (test 31), Jayen (proposed, PR #5) | Bloomberg, 133 origins: 1.389% to 1.307% (t 2.50; Thursdays t 3.49). Same data re-checked here, 135 origins: 1.378% to 1.318%; Thursdays 1.528% to 1.383% (t 2.26). TradingView, 930 origins: 1.570% to 1.540% (t 2.04), slope 0.92. | **Use** |
| 1= | Same with fixed +0.25% drift | Jayen | Ties rank 1: with futures, 1.313% vs 1.318% (135 origins); over 2003-26 Thursdays, 1.760% vs 1.758% | Equivalent |
| 3 | Median drift + 0.5 x Asian overnight | Antonio (earlier) | Best of the no-futures models on the unseen window (1.386%), but adds nothing once futures are known (PR #5: corr 0.35 with the gap; PR #6: D vs C -0.006, t -0.61) | Subsumed by rank 1 |
| 4 | Drift alone (median or fixed) | all | Beats no change over 2003-26 Thursdays (1.758% vs 1.787%, t 2.60) | Fallback if the futures price is unavailable |
| 5 | Best of the 1.72M factor combinations (2Y level + surprise change) | Jayen | 1.398% unseen vs 1.390% fixed drift: lost to drift; selection bias from 1.72M trials | Report as exploration only |
| 6 | Momentum + RSI (machine learning, 80/20 split) | Mohamed | Worse than drift over 1,096 Thursdays 2002-24 (t -3.15) and worse than no change. Ties on 2025-26. With futures added it looked best on 133 recent days (1.286%), but that window is short and 22 years say otherwise | Robustness note only |
| 7 | No change | benchmark | 1.787% over 2003-26 Thursdays | Benchmark |
| - | 16-factor screen (yields, USD, gold, semis, surprises, CPI, PPI, VIX, trend...) | Layla | None passes a pre-registered out-of-sample bar. The best (VIX level, t 1.77) is contradicted by 2000-12 history (t -2.34) | Evidence of breadth |
| - | 30 pre-registered tests incl. Bloomberg factors | Antonio | None passes the hurdle (\|t\| 3.14) | Evidence of breadth |

## Which drift? It barely matters
Like-for-like, Thursday origins, drift only. Each estimate uses only returns known at the time.

| Drift estimate | 2003-26 (n = 1,208) | 2020-26 | Aug 2025-Oct 2026 (unseen) |
|---|---|---|---|
| Median since 1990 (Layla) | **1.758%** | **1.938%** | 1.551% |
| Median since 2000 (Antonio) | 1.763% (t -0.93) | 1.939% | 1.550% |
| Fixed +0.25% (Jayen) | 1.760% (t -0.46) | 1.943% | **1.537%** |
| Mean since 1990 | 1.767% | 1.951% | 1.538% |
| No drift | 1.787% (t -2.60) | 1.979% | 1.559% |

None of the drift choices differ significantly, and all beat no drift over the long run. **Keep the frozen choice (median since 1990).** It is marginally best over 23 years, and changing it now would be a rule change after seeing results. For the final run the alternatives would move the forecast by only about 0.05-0.15% (4-11 points).

**Why 7,598.08 (Layla) differs from 7,581.58 (Antonio's dry run) on 10 Nov.** Layla's preview targets 20 Nov from a Monday origin, so it uses a 9-session drift (+0.56%). Antonio's dry run applied the 6-session drift (+0.35%) to the same origin. For the real final (Thursday 12 Nov to Friday 20 Nov) both use 6 sessions, and the gap shrinks to about 0.05%, roughly 4 points.

## Caveats
- The futures evidence covers Apr-Oct 2026 (Bloomberg) and 2023-26 (TradingView). It is consistent across both, but short by stock-market standards.
- The test numbers from PRs #5 and #6 are quoted from those branches, so re-check them once they are merged.
- Accuracy is still mostly luck: a typical miss of 1.3-1.8% is about 6-9 marks. Nothing here changes that.
