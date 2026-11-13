# Model review and ranking: protocol (11 Nov 2026, written BEFORE any review result was computed)

Scope: every forecasting model in this repository or its open pull requests as of 11 Nov 2026
(`main`; PR #4 `codex/add-five-session-findings`, mderbala1; PR #5 `exp/es-futures-pr`; branch `exp/semis-factor`). The review changes no model.

## Models
| id | model | owner | parameters chosen on |
|---|---|---|---|
| M0 | no change | benchmark | none |
| M1 | fixed drift +0.25% | Jayen | judgement after round 1 (full sample seen) |
| M2 | expanding mean drift (Thursday outcomes) | Antonio | none |
| M3 | expanding median drift | Antonio | none (selection window 2003-24) |
| M4 | weighted-median drift | Antonio | none |
| M5 | median drift, last 5 years | Antonio | none |
| M6 | median drift + 0.5 x asia_overnight | Antonio | selection window before 2025 |
| M7 | best of the 1.72M search (ESI chg21 + Y2 level), engine as published | Jayen | FULL sample (contaminated) |
| M8 | search model with the best error on the first 70% of the daily origins | Jayen | first 70% only |
| M9 | round-2 candidate: LAD fit, median drift, tilt k=0.1, median of top 50 search models | Jayen | first 70% only |
| M10 | median drift + semiconductor/Asia composite (selection winner, dataset A, shrink 1.0) | Jayen | selection window before 2025 |
| M11 | ES 07:00 level x exp(median drift)  (B1) | Jayen | none |
| M12 | ES 0.5 gap + median drift (B3); M13: 0.75 gap (B4) | Jayen | none (fixed values) |
| M14 | ES gap + median drift + 0.5 asia (D1) | Jayen | post-hoc |
| T-C | mderbala1 models (momentum, +RSI, +SMA20, +VIX, ridge, random forests, training mean) | mderbala1 | their 80/20 split |

## Tracks (a model is only compared with others on the same origins)
- **A. Coursework situation.** Friday origins at 07:00 New York (n about 188), previous close p = Thursday, target = S&P close 6 sessions after p. M0-M14.
  In sample = origins whose p is before the first unseen origin of the 990-origin daily search window (the date where M7/M8's selection ended); out of sample = after.
- **W. Every weekday origin** (about 930), same definition. Robustness for A.
- **B. Long history.** Thursday origins 2004-2026, S&P and Asian data only (M0-M6, M10 excluded). Selection before 2025, holdout 2025-26.
- **C. mderbala1's window.** Their 109 weekly 5-session forecasts, Aug 2024 to Oct 2026, with their stored forecasts and, on the same origins, our drift models re-targeted to 5 sessions.
  Not comparable in level with A (different horizon); compared by skill against each track's own no-change.

## Metrics (all reported for every model and sample)
n, mean absolute % error (MAPE), median absolute % error, RMSE in %, largest error, mean score (brief: 50 - min(50, 5 x error)), hit rate (sign of forecast minus base vs sign of outcome minus base),
mean signed error (bias), skill vs no change (% reduction in MAPE), Newey-West t of the loss difference vs no change and vs the best model (lags 1 for Friday origins, 5 for weekday origins),
block-bootstrap 90% interval for MAPE (stationary bootstrap, mean block 5, 2,000 resamples, seed 1), White reality-check p-value (best model over no change, same bootstrap) for the clean model set.

## Ranking rule
1. Only models whose parameters were chosen without the out-of-sample origins are ranked as "clean". M1 and M7 are shown but marked contaminated; M7 is excluded from the headline rank.
2. Headline rank = average of four ranks: MAPE on track A all, A out of sample, W all, W out of sample. Ties within 0.005 pp of MAPE are reported as ties.
3. A model is "distinguishable from no change" only if |t| >= 1.96 on both A all-sample and W all-sample (one planned comparison per model; no multiplicity adjustment beyond the reality check).
4. Differences smaller than the bootstrap interval are called ties, not wins.

## Error checking (each reported PASS/FAIL, nothing hidden)
Repo test suite (pytest), CI status, data integrity (duplicates, ordering, gaps, holidays), S&P closes vs workbook, target alignment (outcome is exactly 6 sessions after p),
truncation (look-ahead) test for drift, Asia and futures forecasts at random origins, ES timestamp coverage (06:00 and 15:00 bars), independent recomputation of M0, M1 and M3 errors,
reproduction of published numbers (Jayen's headline, Antonio's compare_jayen, mderbala1's stored MAPEs), and a check of claims in `COMPARISON.md`.

---

# Addendum 1 (11 Nov 2026, written BEFORE the models below were run)

Reason: the first pass (commit 4c2623a, results kept in git history and in `results_pass1/`) missed Layla's package and ran Mohamed's models only on his own 5-session track.
The ranking rule, metrics and clean/contaminated logic are unchanged. The reality-check set simply gets larger (more models, so a harsher adjustment).

## Added models (all scored on tracks A and W)
| id | model | owner | parameters chosen on |
|---|---|---|---|
| M15 | Layla's rule: last close x exp(m0 + g - mean g), m0 = expanding median of ALL 6-session log returns known at the origin, S&P history from 1990 (her `gspc_daily.json`); g = ES 16:00 -> 07:00 NY gap; mean g = expanding mean of past g (min 50 observations, else 0), standing in for her 48-day mean overnight drift | Layla | none (her pre-registered rule; her factor screen found no factor) |
| M16 | Antonio's futures start "C": median drift (Thursday outcomes since 2000, his definition) + g - expanding mean g | Antonio (PR #6) | none |
| M17 | Mohamed momentum + RSI(14), re-run at 6 sessions: expanding OLS on Thursday pairs known at the origin, burn 104, his feature definitions (log 5-day momentum; RSI from 14-day simple average gain and loss) | Mohamed | his winner among 11 on a window overlapping the unseen part: marked NOT clean |
| M18 | Mohamed momentum only | Mohamed | none (fixed specification) |
| M19 | Mohamed momentum + SMA20 gap | Mohamed | none |
| M20 | Mohamed momentum + 5-session change in VIX | Mohamed | none |
Mohamed's ridge and random-forest models need his full 13-factor workbook set and his 80/20 protocol; they stay on Track C only (his stored forecasts), which is stated, not hidden.

## Added track D: Bloomberg cross-check (short, 133 daily origins, 21 Apr to 30 Oct 2026)
- Antonio's Bloomberg 07:00 ES prices (`data/raw/bbg-drop/01c_es1_0700_1600_ny.csv`) replace the TradingView gap: model M21 = median drift + (g_bbg - mean g_bbg), the same rule as M16 on a second data source.
- Check: correlation and size of difference between g from TradingView and g from Bloomberg on common days.
- Head-to-head on these origins for M0, M3, M6, M11, M15, M16, M17, M21.
- The Bloomberg file is licensed: used locally for the check, only derived statistics are written to the repository.

## Added factor-screen summaries (not ranked as models)
Antonio's 30 pre-registered tests (`results/verdict.csv`) and Layla's 16-factor screen (`outputs/preview/tables/factor_screen.csv` in her package) are summarised side by side with the 1.72M search and Mohamed's feature importance:
how many tested, how many passed each author's own hurdle, best t.

## Added checks
Reproduce Layla's preview forecast (7,543.72) from her inputs with my M15 implementation of her rule; reproduce Antonio's PR #6 claim that Mohamed's momentum + RSI at 6 sessions has t = -3.15 vs median drift over Thursdays 2002-24; ES gap from TradingView vs Bloomberg.

## Ranking-rule changes
None. Contaminated list becomes M1, M7, M14, M17. New headline rank uses all clean models of tracks A and W.
