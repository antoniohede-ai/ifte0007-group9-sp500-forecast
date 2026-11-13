# Model review and ranking (second pass, all authors)

Date: 11 Nov 2026. Protocol and its addendum were committed before the results they govern: [`PREREG.md`](PREREG.md).
Code: `run_review.py`, `lib.py`; raw outputs: `results/`; the first pass, which missed Layla's package, is kept in `results_pass1/`.
Every number below is read from `results/*.csv` by `make_review_md.py`.

## What was reviewed
| Author | Models |
|---|---|
| Jayen | no change; fixed drift; 1.72M search (best on the full sample, best on the first 70%); round-2 ensemble; semiconductor composite; ES futures anchor (full gap, 0.5 and 0.75 of the gap, plus Asia) |
| Antonio | mean, median, weighted-median and 5-year-median drift; median + 0.5 Asia (the agreed group model); his futures start (PR #6) on TradingView and on Bloomberg data; his 30 factor tests |
| Layla | her package's rule: median six-session return since 1990 plus the overnight futures move; her 16-factor screen |
| Mohamed | momentum, momentum + RSI, + SMA20, + VIX re-run at the six-session horizon; his 8 models on his own five-session window (ridge and random forest only there) |

The review changes no model.

## Headline ranking (clean models, coursework situation)
**Setup.** Forecast made at 07:00 New York for the S&P 500 close 6 sessions after the previous close, using only information available then.
Track A = the 187 Friday origins (Jan 2023 to Oct 2026), the real situation on Fri 13 Nov. Track W = all 925 weekday origins (more data, heavily overlapping outcomes).
"Unseen" = origins after 19 Aug 2025, the point where the search models' selection window ended. Errors are mean absolute % error (lower is better).
Rank = average of the four MAPE ranks (A all, A unseen, W all, W unseen); a gap under 0.005 pp counts as a tie.

| Rank | Model | By | A all | A unseen | W all | W unseen | Avg rank | Skill A all % | Skill W unseen % | t A | t W | |t|>=1.96 on both |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | M15 Layla: median (1990) + demeaned ES gap | Layla | 1.525 | 1.349 | 1.537 | 1.340 | 1.50 | 4.9 | 5.3 | 1.97 | 2.90 | yes |
| 2 | M16 Antonio PR6: median + demeaned ES gap | Antonio | 1.529 | 1.347 | 1.540 | 1.338 | 2.00 | 4.6 | 5.4 | 1.95 | 3.00 | no |
| 3 | M11 ES 07:00 level + median drift | Jayen | 1.532 | 1.349 | 1.541 | 1.340 | 3.25 | 4.4 | 5.3 | 1.87 | 2.90 | no |
| 4 | M13 ES 0.75 gap + median | Jayen | 1.528 | 1.368 | 1.542 | 1.344 | 4.25 | 4.7 | 5.0 | 2.27 | 3.12 | yes |
| 5 | M12 ES 0.5 gap + median | Jayen | 1.530 | 1.396 | 1.548 | 1.356 | 5.75 | 4.5 | 4.1 | 2.50 | 3.10 | yes |
| 6 | M6 Median + 0.5 Asia (group model) | Antonio | 1.542 | 1.448 | 1.564 | 1.385 | 8.00 | 3.8 | 2.0 | 2.23 | 2.57 | yes |
| 7 | M10 Median + semis/Asia composite | Jayen | 1.547 | 1.454 | 1.566 | 1.393 | 11.00 | 3.5 | 1.5 | 2.04 | 2.43 | yes |
| 8 | M19 Mohamed momentum+SMA20 (6 sessions) | Mohamed | 1.573 | 1.435 | 1.600 | 1.385 | 11.50 | 1.9 | 2.0 | 2.36 | 1.78 | no |
| 9 | M3 Median drift | Antonio | 1.556 | 1.460 | 1.572 | 1.392 | 12.50 | 3.0 | 1.6 | 1.82 | 2.22 | no |
| 10 | M4 Weighted-median drift | Antonio | 1.557 | 1.455 | 1.577 | 1.391 | 12.75 | 2.8 | 1.6 | 2.13 | 2.47 | yes |
| 11 | M5 Median drift, last 5y | Antonio | 1.556 | 1.479 | 1.566 | 1.398 | 13.25 | 2.9 | 1.1 | 1.12 | 1.55 | no |
| 12 | M8 Search best on first 70% | Jayen | 1.535 | 1.532 | 1.554 | 1.433 | 14.25 | 4.2 | -1.3 | 1.36 | 1.79 | no |
| 13 | M18 Mohamed momentum only (6 sessions) | Mohamed | 1.588 | 1.448 | 1.606 | 1.397 | 14.75 | 0.9 | 1.2 | 1.62 | 1.85 | no |
| 14 | M9 Round-2 ensemble | Jayen | 1.556 | 1.483 | 1.569 | 1.411 | 15.50 | 2.9 | 0.3 | 1.18 | 1.53 | no |
| 15 | M20 Mohamed momentum+VIX (6 sessions) | Mohamed | 1.590 | 1.452 | 1.607 | 1.399 | 16.50 | 0.8 | 1.1 | 1.47 | 1.62 | no |
| 16 | M2 Expanding mean drift | Antonio | 1.585 | 1.465 | 1.603 | 1.403 | 17.00 | 1.1 | 0.8 | 2.66 | 2.85 | yes |
| 17 | M0 No change | benchmark | 1.603 | 1.481 | 1.618 | 1.414 | 20.25 | 0.0 | 0.0 |  |  | no |

Not ranked (parameters chosen using the evaluation data):

| Model | By | Why not ranked | A all | A unseen | W all | W unseen |
|---|---|---|---|---|---|---|
| M1 Fixed drift +0.25% | Jayen | +0.25% was set after seeing the full sample (round 1) | 1.559 | 1.452 | 1.580 | 1.391 |
| M7 Search best (full sample) | Jayen | chosen on the full sample, including the unseen window | 1.548 | 1.477 | 1.553 | 1.400 |
| M14 ES gap + median + 0.5 Asia | Jayen | post-hoc combination, not planned | 1.525 | 1.351 | 1.541 | 1.346 |
| M17 Mohamed momentum+RSI (6 sessions) | Mohamed | Mohamed picked it as the winner of 11 on a window that overlaps the unseen part | 1.585 | 1.452 | 1.604 | 1.398 |

## Best model per author
| Author | Best clean model | Rank | A unseen MAPE | Skill A all % | Models in ranking |
|---|---|---|---|---|---|
| Layla | M15 Layla: median (1990) + demeaned ES gap | 1 | 1.349 | 4.9 | M15 |
| Antonio | M16 Antonio PR6: median + demeaned ES gap | 2 | 1.347 | 4.6 | M16, M6, M3, M4, M5, M2 |
| Jayen | M11 ES 07:00 level + median drift | 3 | 1.349 | 4.4 | M11, M13, M12, M10, M8, M9 |
| Mohamed | M19 Mohamed momentum+SMA20 (6 sessions) | 8 | 1.435 | 1.9 | M19, M18, M20 |

## Reading the ranking
- **Tier 1: the ES-anchored models (M15, M16, M11, M13, M12).** Layla's rule, Antonio's PR #6 rule and Jayen's three variants all start from the ES level at 07:00 and differ only in how the drift is estimated and whether the gap is shrunk or demeaned. Their skill versus no change is 4.4-4.9% (Friday, all), 5.7-9.0% (Friday, unseen) and 4.1-5.4% (weekday, unseen). The bootstrap intervals overlap almost completely. Of the 10 pairs, those with an unadjusted |t| above 1.96 are: all Fridays: M15 beats M11 (|t| 2.31); unseen Fridays: M15 beats M12 (|t| 2.15); unseen Fridays: M16 beats M13 (|t| 2.02); unseen Fridays: M16 beats M12 (|t| 2.39); unseen Fridays: M11 beats M12 (|t| 2.28); unseen Fridays: M13 beats M12 (|t| 2.53). No pair differs on either weekday sample. Reading this: the models that use the full gap (M15, M16, M11) are indistinguishable from each other; the half-gap model (M12) is worse than the full-gap ones on unseen Fridays, consistent with the measured slope of about 0.9 (futures gap passed through almost one-for-one); and Layla's M15 beats M11 on all Fridays, which can come only from demeaning the gap or from her drift definition (median since 1990). Counting 10 pairs over four samples, two or three such |t| values are expected by chance, so the order inside this tier is not reliable.
- **Tier 2: the group model and the drift models (M6, M3, M4, M5, M10, M2).** About 3% better than no change over the whole sample, 1-2% on the unseen part. Adding the Asia factor to the median (M6) beats the median alone by only 0.013 pp on the full Friday sample and 0.006 pp on unseen weekdays: the factor is not distinguishable from nothing, and the ES gap, which includes the same overnight news, makes it redundant.
- **Tier 3: Mohamed's models at six sessions (M19, M18, M20, M17).** The clean variants beat no change by 0.8-1.9% over all Fridays but trail plain median drift (M3, 3.0%) and the ES models by a wide margin. Over 24 years of Thursdays before 2025 they are *worse* than no change (Track B): the five-session result on his own window does not carry to the coursework horizon.
- **Tier 3b: search-derived models (M8, M9; M7 contaminated).** M8, the model with the lowest error on the first 70%, looks good on the full samples (1.535 on Fridays) only because they include its selection period; on unseen data it is **3.4% worse than no change** on Fridays and 1.3% worse on weekdays.
- **No change (M0)** ranks last.

## Is any of it distinguishable from luck?
White's reality check (adjusts for choosing the best of the clean models; stationary bootstrap, mean block 5, 2,000 resamples):
- A_all: best model M15 (Layla: median (1990) + demeaned ES gap); White reality-check p = 0.074 over 16 clean models
- W_all: best model M15 (Layla: median (1990) + demeaned ES gap); White reality-check p = 0.018 over 16 clean models
- W_oos: best model M16 (Antonio PR6: median + demeaned ES gap); White reality-check p = 0.110 over 16 clean models

Models below p = 0.05 after the adjustment:
- A_all: no model below p = 0.05
- W_all: M15 (Layla: median (1990) + demeaned ES gap) p=0.018; M16 (Antonio PR6: median + demeaned ES gap) p=0.020; M11 (ES 07:00 level + median drift) p=0.022; M13 (ES 0.75 gap + median) p=0.024; M12 (ES 0.5 gap + median) p=0.035; M8 (Search best on first 70%) p=0.048
- W_oos: no model below p = 0.05

The ES-anchored models reach significance on the 925-origin weekday sample (p 0.018-0.035) but not on the 187 Fridays alone (p 0.074-0.096) or on unseen weekdays alone (p 0.110-0.189). Of the non-ES models only M8 passes in a full sample, and that sample includes the period M8 was selected on. The group model M6 and Mohamed's models do not pass in any sample. With 16 clean models in the set the adjustment is harsher than in the first pass. Weekday outcomes overlap by 5 of 6 days, so a block of 5 may understate the dependence and the weekday p-values are, if anything, optimistic.

## Full metrics: Friday origins, all (n = 187)
Columns: MAPE, median error, RMSE (%), largest error, mean score out of 50 (brief), hit rate % (direction), bias % (negative = forecasts too low), skill vs no change %, Newey-West t vs no change and vs the best model, 90% bootstrap interval for MAPE.

| id | Model | n | MAPE | MedAE | RMSE | Max | Score | Hit | Bias | Skill% | t_vs_M0 | t_vs_best | 90% CI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M0 | No change | 187 | 1.603 | 1.445 | 2.118 | 12.20 | 42.044 | 0.0 | -0.360 | 0.000 |  | 1.929 | 1.431-1.783 |
| M1 | Fixed drift +0.25% | 187 | 1.559 | 1.294 | 2.096 | 12.48 | 42.272 | 62.6 | -0.111 | 2.749 | 2.402 | 1.099 | 1.381-1.748 |
| M2 | Expanding mean drift | 187 | 1.585 | 1.396 | 2.109 | 12.31 | 42.138 | 62.6 | -0.270 | 1.133 | 2.656 | 1.650 | 1.410-1.769 |
| M3 | Median drift | 187 | 1.556 | 1.238 | 2.096 | 12.60 | 42.292 | 62.6 | 0.001 | 2.954 | 1.822 | 1.066 | 1.373-1.751 |
| M4 | Weighted-median drift | 187 | 1.557 | 1.287 | 2.096 | 12.54 | 42.281 | 62.6 | -0.068 | 2.839 | 2.135 | 1.089 | 1.377-1.748 |
| M5 | Median drift, last 5y | 187 | 1.556 | 1.130 | 2.111 | 12.87 | 42.296 | 62.6 | 0.221 | 2.923 | 1.115 | 0.998 | 1.365-1.763 |
| M6 | Median + 0.5 Asia (group model) | 187 | 1.542 | 1.216 | 2.084 | 12.45 | 42.355 | 63.1 | -0.000 | 3.795 | 2.230 | 0.691 | 1.362-1.734 |
| M7 | Search best (full sample) | 187 | 1.548 | 1.240 | 2.084 | 12.75 | 42.335 | 61.5 | 0.100 | 3.448 | 1.362 | 0.581 | 1.361-1.751 |
| M8 | Search best on first 70% | 187 | 1.535 | 1.159 | 2.071 | 12.77 | 42.398 | 63.1 | 0.179 | 4.222 | 1.362 | 0.232 | 1.344-1.745 |
| M9 | Round-2 ensemble | 187 | 1.556 | 1.127 | 2.108 | 12.82 | 42.295 | 62.6 | 0.197 | 2.929 | 1.177 | 1.023 | 1.369-1.762 |
| M10 | Median + semis/Asia composite | 187 | 1.547 | 1.243 | 2.090 | 12.37 | 42.330 | 63.6 | 0.002 | 3.516 | 2.044 | 0.842 | 1.367-1.740 |
| M11 | ES 07:00 level + median drift | 187 | 1.532 | 1.168 | 2.073 | 12.50 | 42.406 | 62.6 | -0.005 | 4.419 | 1.867 | 0.846 | 1.343-1.739 |
| M12 | ES 0.5 gap + median | 187 | 1.530 | 1.234 | 2.074 | 12.55 | 42.416 | 64.7 | -0.002 | 4.523 | 2.495 | 0.293 | 1.348-1.727 |
| M13 | ES 0.75 gap + median | 187 | 1.528 | 1.190 | 2.071 | 12.52 | 42.429 | 63.6 | -0.003 | 4.689 | 2.265 | 0.224 | 1.342-1.729 |
| M14 | ES gap + median + 0.5 Asia | 187 | 1.525 | 1.211 | 2.070 | 12.35 | 42.438 | 62.6 | -0.006 | 4.868 | 1.929 |  | 1.338-1.727 |
| M15 | Layla: median (1990) + demeaned ES gap | 187 | 1.525 | 1.165 | 2.070 | 12.52 | 42.442 | 63.6 | 0.026 | 4.860 | 1.970 | 0.015 | 1.336-1.732 |
| M16 | Antonio PR6: median + demeaned ES gap | 187 | 1.529 | 1.185 | 2.070 | 12.47 | 42.419 | 62.6 | -0.012 | 4.584 | 1.948 | 0.528 | 1.342-1.737 |
| M17 | Mohamed momentum+RSI (6 sessions) | 187 | 1.585 | 1.412 | 2.107 | 12.21 | 42.136 | 55.6 | -0.263 | 1.137 | 1.707 | 1.635 | 1.404-1.772 |
| M18 | Mohamed momentum only (6 sessions) | 187 | 1.588 | 1.436 | 2.108 | 12.28 | 42.119 | 57.2 | -0.285 | 0.902 | 1.620 | 1.720 | 1.409-1.777 |
| M19 | Mohamed momentum+SMA20 (6 sessions) | 187 | 1.573 | 1.392 | 2.097 | 12.20 | 42.196 | 56.7 | -0.254 | 1.897 | 2.363 | 1.289 | 1.392-1.756 |
| M20 | Mohamed momentum+VIX (6 sessions) | 187 | 1.590 | 1.444 | 2.109 | 12.29 | 42.110 | 55.1 | -0.291 | 0.797 | 1.471 | 1.760 | 1.410-1.778 |

## Full metrics: Friday origins, unseen (after 19 Aug 2025)
| id | Model | n | MAPE | MedAE | RMSE | Max | Score | Hit | Bias | Skill% | t_vs_M0 | t_vs_best | 90% CI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M0 | No change | 55 | 1.481 | 1.390 | 1.810 | 4.23 | 42.594 | 0.0 | -0.213 | 0.000 |  | 2.282 | 1.208-1.764 |
| M1 | Fixed drift +0.25% | 55 | 1.452 | 1.405 | 1.802 | 3.99 | 42.740 | 60.0 | 0.037 | 1.966 | 0.927 | 2.417 | 1.177-1.736 |
| M2 | Expanding mean drift | 55 | 1.465 | 1.392 | 1.804 | 4.14 | 42.676 | 60.0 | -0.111 | 1.108 | 1.232 | 2.294 | 1.191-1.749 |
| M3 | Median drift | 55 | 1.460 | 1.347 | 1.810 | 4.08 | 42.698 | 60.0 | 0.144 | 1.404 | 0.479 | 2.764 | 1.186-1.745 |
| M4 | Weighted-median drift | 55 | 1.455 | 1.369 | 1.805 | 4.02 | 42.724 | 60.0 | 0.081 | 1.748 | 0.715 | 2.579 | 1.180-1.739 |
| M5 | Median drift, last 5y | 55 | 1.479 | 1.279 | 1.827 | 4.16 | 42.604 | 60.0 | 0.270 | 0.134 | 0.034 | 2.957 | 1.203-1.766 |
| M6 | Median + 0.5 Asia (group model) | 55 | 1.448 | 1.383 | 1.816 | 4.03 | 42.760 | 60.0 | 0.140 | 2.239 | 0.694 | 2.539 | 1.177-1.728 |
| M7 | Search best (full sample) | 55 | 1.477 | 1.338 | 1.813 | 4.20 | 42.616 | 61.8 | 0.194 | 0.293 | 0.074 | 2.120 | 1.190-1.767 |
| M8 | Search best on first 70% | 55 | 1.532 | 1.240 | 1.845 | 4.06 | 42.342 | 52.7 | 0.184 | -3.409 | -0.736 | 2.704 | 1.251-1.813 |
| M9 | Round-2 ensemble | 55 | 1.483 | 1.183 | 1.840 | 4.28 | 42.584 | 60.0 | 0.335 | -0.137 | -0.030 | 2.825 | 1.210-1.767 |
| M10 | Median + semis/Asia composite | 55 | 1.454 | 1.393 | 1.827 | 4.05 | 42.731 | 60.0 | 0.143 | 1.842 | 0.539 | 2.709 | 1.186-1.726 |
| M11 | ES 07:00 level + median drift | 55 | 1.349 | 1.124 | 1.729 | 3.87 | 43.257 | 69.1 | 0.166 | 8.952 | 2.189 | 0.407 | 1.083-1.623 |
| M12 | ES 0.5 gap + median | 55 | 1.396 | 1.261 | 1.760 | 3.89 | 43.020 | 61.8 | 0.155 | 5.744 | 1.737 | 2.395 | 1.126-1.678 |
| M13 | ES 0.75 gap + median | 55 | 1.368 | 1.179 | 1.742 | 3.88 | 43.161 | 69.1 | 0.161 | 7.649 | 2.069 | 2.022 | 1.098-1.643 |
| M14 | ES gap + median + 0.5 Asia | 55 | 1.351 | 1.114 | 1.745 | 3.96 | 43.245 | 72.7 | 0.163 | 8.794 | 1.986 | 0.224 | 1.078-1.624 |
| M15 | Layla: median (1990) + demeaned ES gap | 55 | 1.349 | 1.144 | 1.732 | 3.83 | 43.257 | 69.1 | 0.195 | 8.947 | 2.087 | 0.172 | 1.086-1.621 |
| M16 | Antonio PR6: median + demeaned ES gap | 55 | 1.347 | 1.099 | 1.726 | 3.89 | 43.263 | 69.1 | 0.144 | 9.030 | 2.282 |  | 1.081-1.624 |
| M17 | Mohamed momentum+RSI (6 sessions) | 55 | 1.452 | 1.418 | 1.805 | 4.35 | 42.741 | 52.7 | -0.095 | 1.988 | 1.615 | 1.991 | 1.165-1.742 |
| M18 | Mohamed momentum only (6 sessions) | 55 | 1.448 | 1.427 | 1.801 | 4.33 | 42.758 | 58.2 | -0.117 | 2.208 | 2.133 | 1.873 | 1.164-1.747 |
| M19 | Mohamed momentum+SMA20 (6 sessions) | 55 | 1.435 | 1.375 | 1.786 | 4.29 | 42.826 | 56.4 | -0.080 | 3.136 | 2.120 | 1.744 | 1.157-1.718 |
| M20 | Mohamed momentum+VIX (6 sessions) | 55 | 1.452 | 1.331 | 1.805 | 4.31 | 42.739 | 58.2 | -0.125 | 1.949 | 1.882 | 1.942 | 1.166-1.751 |

## Full metrics: all weekday origins, unseen
| id | Model | n | MAPE | MedAE | RMSE | Max | Score | Hit | Bias | Skill% | t_vs_M0 | t_vs_best | 90% CI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M0 | No change | 285 | 1.414 | 1.175 | 1.821 | 6.47 | 42.929 | 0.0 | -0.352 | 0.000 |  | 1.819 | 1.219-1.630 |
| M1 | Fixed drift +0.25% | 285 | 1.391 | 1.118 | 1.794 | 6.24 | 43.043 | 58.2 | -0.103 | 1.613 | 0.932 | 2.045 | 1.201-1.599 |
| M2 | Expanding mean drift | 285 | 1.403 | 1.115 | 1.807 | 6.39 | 42.987 | 58.2 | -0.251 | 0.825 | 1.171 | 1.873 | 1.210-1.612 |
| M3 | Median drift | 285 | 1.392 | 1.126 | 1.795 | 6.16 | 43.042 | 58.2 | 0.003 | 1.599 | 0.648 | 2.254 | 1.200-1.595 |
| M4 | Weighted-median drift | 285 | 1.391 | 1.103 | 1.794 | 6.21 | 43.045 | 58.2 | -0.059 | 1.641 | 0.810 | 2.145 | 1.201-1.596 |
| M5 | Median drift, last 5y | 285 | 1.398 | 1.103 | 1.804 | 6.12 | 43.008 | 58.2 | 0.125 | 1.124 | 0.343 | 2.296 | 1.211-1.604 |
| M6 | Median + 0.5 Asia (group model) | 285 | 1.385 | 1.120 | 1.790 | 6.22 | 43.073 | 58.2 | 0.004 | 2.039 | 0.805 | 2.057 | 1.196-1.589 |
| M7 | Search best (full sample) | 285 | 1.400 | 1.030 | 1.827 | 6.65 | 42.999 | 57.9 | 0.046 | 0.989 | 0.293 | 1.556 | 1.196-1.619 |
| M8 | Search best on first 70% | 285 | 1.433 | 1.122 | 1.856 | 6.61 | 42.837 | 49.8 | 0.026 | -1.304 | -0.377 | 2.339 | 1.233-1.650 |
| M9 | Round-2 ensemble | 285 | 1.411 | 1.141 | 1.810 | 6.01 | 42.947 | 58.2 | 0.193 | 0.253 | 0.067 | 2.450 | 1.226-1.613 |
| M10 | Median + semis/Asia composite | 285 | 1.393 | 1.125 | 1.803 | 6.31 | 43.036 | 57.5 | 0.010 | 1.514 | 0.580 | 2.287 | 1.204-1.600 |
| M11 | ES 07:00 level + median drift | 285 | 1.340 | 1.084 | 1.718 | 5.46 | 43.302 | 60.0 | 0.030 | 5.277 | 1.718 | 0.628 | 1.161-1.536 |
| M12 | ES 0.5 gap + median | 285 | 1.356 | 1.073 | 1.742 | 5.81 | 43.222 | 58.9 | 0.017 | 4.145 | 1.571 | 1.398 | 1.172-1.554 |
| M13 | ES 0.75 gap + median | 285 | 1.344 | 1.057 | 1.726 | 5.64 | 43.281 | 59.3 | 0.023 | 4.985 | 1.759 | 0.857 | 1.163-1.540 |
| M14 | ES gap + median + 0.5 Asia | 285 | 1.346 | 1.112 | 1.728 | 5.52 | 43.268 | 60.7 | 0.031 | 4.796 | 1.498 | 1.203 | 1.171-1.545 |
| M15 | Layla: median (1990) + demeaned ES gap | 285 | 1.340 | 1.088 | 1.717 | 5.42 | 43.301 | 60.4 | 0.060 | 5.267 | 1.625 | 0.288 | 1.164-1.536 |
| M16 | Antonio PR6: median + demeaned ES gap | 285 | 1.338 | 1.087 | 1.717 | 5.48 | 43.308 | 60.0 | 0.008 | 5.370 | 1.819 |  | 1.159-1.536 |
| M17 | Mohamed momentum+RSI (6 sessions) | 285 | 1.398 | 1.169 | 1.813 | 6.32 | 43.012 | 53.0 | -0.247 | 1.184 | 1.202 | 1.638 | 1.199-1.618 |
| M18 | Mohamed momentum only (6 sessions) | 285 | 1.397 | 1.156 | 1.803 | 6.20 | 43.015 | 54.0 | -0.262 | 1.227 | 1.458 | 1.594 | 1.200-1.616 |
| M19 | Mohamed momentum+SMA20 (6 sessions) | 285 | 1.385 | 1.151 | 1.807 | 6.37 | 43.073 | 55.1 | -0.230 | 2.037 | 1.589 | 1.294 | 1.185-1.607 |
| M20 | Mohamed momentum+VIX (6 sessions) | 285 | 1.399 | 1.159 | 1.804 | 6.20 | 43.006 | 53.7 | -0.268 | 1.099 | 1.342 | 1.640 | 1.202-1.618 |

(Friday in-sample, weekday all and the other tables are in `results/metrics_*.csv`.)

## Track B: long history, Thursday origins, no futures (2002-2026)
Models that need only S&P (and VIX for M20) data, over 1249 Thursday origins. Selection before 2025, holdout 2025-26. M15b is Layla's drift on its own: the median of all six-session returns since 1990.

| Model | Before 2025 MAPE | Skill % | t | 2025-26 MAPE | Skill %  | t  |
|---|---|---|---|---|---|---|
| M0 No change | 1.827 | 0.000 |  | 1.647 | 0.000 |  |
| M1 Fixed drift +0.25% | 1.802 | 1.393 | 3.35 | 1.634 | 0.799 | 0.53 |
| M2 Expanding mean drift | 1.832 | -0.250 | -0.92 | 1.639 | 0.463 | 0.75 |
| M3 Median drift | 1.807 | 1.140 | 2.49 | 1.645 | 0.132 | 0.06 |
| M4 Weighted-median drift | 1.812 | 0.831 | 1.87 | 1.638 | 0.543 | 0.31 |
| M5 Median drift, last 5y | 1.809 | 0.985 | 1.40 | 1.667 | -1.242 | -0.41 |
| M6 Median + 0.5 Asia (group model) | 1.812 | 0.837 | 1.66 | 1.640 | 0.407 | 0.19 |
| M15b Layla drift only: median (1990) | 1.800 | 1.506 | 2.58 | 1.647 | -0.027 | -0.01 |
| M17 Mohamed momentum+RSI (6 sessions) | 1.840 | -0.681 | -1.70 | 1.630 | 1.001 | 1.04 |
| M18 Mohamed momentum only (6 sessions) | 1.849 | -1.199 | -2.94 | 1.635 | 0.696 | 0.80 |
| M19 Mohamed momentum+SMA20 (6 sessions) | 1.838 | -0.555 | -1.28 | 1.619 | 1.679 | 1.45 |
| M20 Mohamed momentum+VIX (6 sessions) | 1.849 | -1.188 | -2.39 | 1.633 | 0.814 | 0.98 |

Years in which each model beat no change (out of 25): M1 16, M2 12, M3 14, M4 15, M5 11, M6 16, M15b 14, M17 12, M18 8, M19 12, M20 10.
- The drift models, the group model and Layla's drift help a little (about 1-1.5% before 2025) but not consistently: M6 beat no change in 16 of 25 years, the median drift in 14, Layla's drift in 14.
- **Mohamed's models are worse than no change before 2025** (skill -1.2% for momentum alone, t = -2.94; -0.7% with RSI), and only marginally better in 2025-26 (skill 0.7-1.7%, not significant), which is where his own window lies. This confirms Antonio's PR #6 finding (see the check on his t = -3.15).
- In the 2025-26 holdout no drift, Asia or momentum variant is distinguishable from no change (largest |t| 1.45).

## Track C: Mohamed's five-session models on his own window
His 109 forecasts, 2024-08-30 to 2026-10-27 (his 80/20 holdout). Not comparable in level with tracks A and W (5 sessions from a weekly origin, no 07:00 information); compare skill against each track's own no change. I also scored our drift models on his origins.

| Model | MAPE | Skill% | t_vs_M0 | MAPE 1st half | MAPE 2nd half | Hit | 90% CI |
|---|---|---|---|---|---|---|---|
| M0 | 1.594 | 0.00 |  | 1.846 | 1.347 | 0.0 | 1.295-1.960 |
| random_forest | 1.584 | 0.63 | 0.31 | 1.851 | 1.322 | 46.8 | 1.285-1.946 |
| momentum | 1.553 | 2.58 | 1.45 | 1.770 | 1.340 | 53.2 | 1.262-1.896 |
| momentum+RSI | 1.551 | 2.68 | 1.38 | 1.770 | 1.337 | 56.9 | 1.259-1.899 |
| momentum+SMA20 | 1.553 | 2.58 | 1.45 | 1.769 | 1.341 | 52.3 | 1.262-1.896 |
| momentum+VIX | 1.567 | 1.69 | 0.88 | 1.820 | 1.319 | 53.2 | 1.265-1.933 |
| ridge | 1.585 | 0.59 | 0.32 | 1.818 | 1.356 | 52.3 | 1.292-1.933 |
| training mean (theirs) | 1.581 | 0.80 | 0.57 | 1.803 | 1.363 | 54.1 | 1.284-1.940 |
| unchanged (theirs) | 1.594 | 0.00 |  | 1.846 | 1.347 | 0.0 | 1.295-1.960 |
| median drift (ours, 5d) | 1.583 | 0.70 | 0.41 | 1.798 | 1.372 | 54.1 | 1.283-1.943 |
| mean drift (ours, 5d) | 1.587 | 0.44 | 0.68 | 1.827 | 1.351 | 54.1 | 1.292-1.948 |
| fixed +0.21% (ours) | 1.583 | 0.71 | 0.62 | 1.811 | 1.359 | 54.1 | 1.285-1.941 |

- His momentum and momentum + RSI regressions have the lowest error (about 2.6% better than unchanged), but the improvement is not significant (t about 1.4) and sits in the first half of the window; in the second half all models are within 0.03 pp of unchanged.
- The random forest and ridge are no better than a training mean or our median drift (about 0.6-0.8% skill).
- His reported MAPEs reproduce exactly from the stored forecasts, and his stored actual levels match our closes (0 mismatches over 108 checkable targets).

## Track D: Bloomberg cross-check (short)
Antonio's Bloomberg 07:00 ES prices replace the TradingView gap. 121 daily origins, 2026-04-22 to 2026-10-22.

| id | Model | n | MAPE | Skill% | t_vs_M0 | t_vs_best | 90% CI |
|---|---|---|---|---|---|---|---|
| M0 | No change | 121 | 1.330 | 0.000 |  | 1.85 | 1.104-1.591 |
| M3 | Median drift | 121 | 1.308 | 1.618 | 0.41 | 2.78 | 1.102-1.559 |
| M6 | Median + 0.5 Asia (group model) | 121 | 1.297 | 2.472 | 0.63 | 2.47 | 1.084-1.551 |
| M11 | ES 07:00 level + median drift | 121 | 1.229 | 7.590 | 1.59 | 1.26 | 1.032-1.459 |
| M15 | Layla: median (1990) + demeaned ES gap | 121 | 1.228 | 7.685 | 1.52 | 0.67 | 1.030-1.456 |
| M16 | Antonio PR6: median + demeaned ES gap | 121 | 1.228 | 7.691 | 1.69 | 1.69 | 1.030-1.459 |
| M17 | Mohamed momentum+RSI (6 sessions) | 121 | 1.300 | 2.241 | 1.22 | 1.73 | 1.074-1.562 |
| M21 | Antonio median + demeaned Bloomberg gap | 121 | 1.221 | 8.199 | 1.85 |  | 1.022-1.449 |

- The gap from TradingView and from Bloomberg agree (correlation 0.9994, median difference 0.010 pp), so the ES result does not depend on the data source.
- On these 121 origins the ES models are 7.6-8.2% better than no change; none is significant on its own (short sample), and the Bloomberg version M21 is not distinguishable from the TradingView ones.
- Two origins are excluded for the Bloomberg gap only: 2026-06-22 (p 2026-06-18, last bar 09:29); 2026-09-21 (p 2026-09-18, last bar 09:29). On expiry day Bloomberg's "16:00" price is a 09:29 print of the expiring contract; TradingView is right on those days. If Antonio's test 31 includes them, its Bloomberg gaps are wrong on those two days.

## What the factor screens found
| Who | Tested | Passed own rule | Best t | Rule |
|---|---|---|---|---|
| Antonio (verdict.csv, selection window) | 19 | 0 | 1.32 | abs t >= 3.14 plus sign, sub-period and placebo rules |
| Layla (factor_screen.csv, preview build) | 16 | 0 | 1.77 | t >= 1.65 validation, sign match in 70% of origins, proxy t >= 0 |
| Jayen (1.72M search) | 1722240 | 0 |  | no model beats drift on unseen data (see REVIEW tiers) |

No author's screen finds a factor that passes its own rule. Layla's best candidate (VIX level) reaches t = 1.77 on validation and 0.87 on test; Antonio's best reaches 1.32. Mohamed's feature importances are spread evenly (the top feature carries 9%), which is what noise features look like. Three screens by different authors plus the 1.72M combinations agree: **the only signal that survives is the overnight futures move**.

## Error checks
Status counts: PASS 16, WARN 1.

| check | status | detail |
|---|---|---|
| drift-asia pytest suite | PASS | 26 passed, 48 warnings in 13.91s |
| GitHub CI on recent runs | PASS | review/model-ranking:success, feat/futures-model-review:success, feat/futures-model-review:success |
| S&P series ordered, no duplicate dates, no gaps over 4 days other than known market closures (11 Sep 2001, 2 Jan 2007 Ford mourning day, 29-30 Oct 2012 Hurricane Sandy) | PASS | 6748 closes 2000-01-03 to 2026-10-30; gaps over 4 days: {'2001-09-17': 7, '2007-01-03': 5, '2012-10-31': 5}; NaN 0. (Corrected 11 Nov: the first version allowed no gap over 4 days except 9/11 and wrongly flagged the 2007 and 2012 closures.) |
| ES file ordered, no duplicate timestamps | PASS | 22786 bars; spacing 1h 95.6%, 2h (daily break) 3.4% |
| ES 06:00 and 15:00 bars exist on S&P trading days | PASS | 06:00 bar 99.9%, 15:00 bar 99.2% of 961 days |
| ES 16:00 vs S&P close basis stable (timestamp alignment) | PASS | std of daily change in log(ES16/S&P) 0.0005 excluding 17 roll or jump days |
| Yahoo S&P closes equal the group workbook | WARN | 1718 common dates; 2 differ by more than 0.05: 2020-05-11 Yahoo 2930.19 vs workbook 2930.32; 2021-08-11 Yahoo 4442.41 vs workbook 4447.70. Both dates are outside the Jan 2023-Oct 2026 evaluation window and affect only the workbook-trained search models' training data. |
| Outcome is the close exactly 6 sessions after the previous close | PASS | calendar days between p and outcome: min 8, max 12 |
| Truncation test: drift and Asia forecasts unchanged when later data is removed | PASS | 6 random origins 2024-26; mismatches [] |
| Independent recomputation of M0-M3 forecasts and outcomes from the raw Yahoo file (own parsing, plain pandas) | PASS | max forecast difference 8.19e-12 index points, max outcome difference 0.00e+00, 925 origins |
| Jayen headline (best model) reproduces from numbers.json | PASS | mape 1.5412 hold 1.3978 naive_hold 1.4123 |
| COMPARISON.md claims: unseen 297 origins; no change 1.412, best search 1.398, fixed drift 1.390 | PASS | n 297, no change 1.4123, best search 1.3978, fixed drift 1.3905 |
| Antonio's tools/compare_jayen.py reruns to the stored output | PASS | identical |
| Public data snapshots match their SHA-256 manifest on this checkout | PASS | 13 manifest rows, 0 mismatches []. Found 11 Nov: on a Windows checkout git converted line endings and 7 CSV files (DGS2, DGS10, DFF, VIXCLS, BAMLH0A0HYM2, VIX3M, VIX_CBOE) failed verification (all match once CRLF is turned back into LF), which makes Antonio's load_raw stop for any factor using them. Fixed by .gitattributes (-text) on this branch; recommend merging it. |
| Layla's preview forecast reproduces from my implementation of her rule (m0 from her S&P file + her nowcast) | PASS | horizon 9 sessions (preview); m0 mine 0.5559% vs hers 0.5563%; forecast mine 7543.69 vs hers 7543.72. Agreement is to 0.03 index points, not exact (likely a one-observation boundary difference in her median). (First attempt used 6 sessions and failed: her preview horizon is 9, corrected.) |
| Antonio's PR #6 claim: Mohamed momentum+RSI at 6 sessions is worse than median drift over Thursdays before 2025 (his t = -3.15) | PASS | my t = -3.97 (n=1159; MAPE median 1.807%, momentum+RSI 1.840%). Not identical to his number: his RSI is Wilder-smoothed, Mohamed's PR #4 uses a simple 14-day average, which I follow. |
| ES gap from TradingView matches Bloomberg 07:00 prices on common days | PASS | n 121 of 123 common days, correlation 0.9994, median /difference/ 0.010 pp, max 0.040 pp, mean TV minus Bloomberg +0.0038 pp. Excluded because Bloomberg's 16:00 price is a stale 09:29 print of the expiring contract on expiry day (TradingView is correct there): ['2026-06-22 (p 2026-06-18, last bar 09:29)', '2026-09-21 (p 2026-09-18, last bar 09:29)']. First attempt without this exclusion failed (corr 0.971, two differences of 0.7-0.9 pp); these two days also sit in Antonio's Bloomberg-based test 31 if his sample includes them. |

The WARN is a data-quality finding about the group workbook, not about any forecast in the evaluation window: it has wrong S&P closes on 11 May 2020 and 11 Aug 2021 (the latter off by 5.3 points), which touch only the training data of the workbook-based search models.

## Changes between pass 1 and pass 2
- Models added: Layla's rule (M15), Antonio's PR #6 rule (M16), Mohamed at six sessions (M17-M20), the Bloomberg track and the factor-screen summary.
- The roll handling changed (deviation 5). It moved the ES models by a few thousandths of a point:

| Model | A all, pass 1 | A all, pass 2 | W unseen, pass 1 | W unseen, pass 2 |
|---|---|---|---|---|
| M0 No change | 1.607 | 1.603 | 1.418 | 1.414 |
| M3 Median drift | 1.558 | 1.556 | 1.394 | 1.392 |
| M6 Median + 0.5 Asia (group model) | 1.547 | 1.542 | 1.389 | 1.385 |
| M11 ES 07:00 level + median drift | 1.538 | 1.532 | 1.348 | 1.340 |
| M12 ES 0.5 gap + median | 1.535 | 1.530 | 1.361 | 1.356 |
| M13 ES 0.75 gap + median | 1.533 | 1.528 | 1.351 | 1.344 |

## Deviations from the protocol (logged, nothing hidden)
1. Track B starts in 2002 (first Thursday with 104 prior outcomes from 2000), not 2004 as `PREREG.md` said.
2. The S&P-gap check was first written with a 5-day limit and then with only the 9/11 exception; both wrongly flagged real closures (2 Jan 2007, 29-30 Oct 2012). The allow-list was corrected and the check rerun; the data were not changed.
3. A WARN status was added to the checks for a finding that is real but does not affect the evaluation window.
4. The first independent-recomputation check used workbook closes (history from 2020 only) and failed because Antonio's drift uses history from 2000. It was replaced by a recomputation from the raw Yahoo file, which agrees to 1e-11.
5. **Roll exclusion changed in pass 2.** Pass 1 and PR #5 dropped origins by calendar rule (the Tuesday after the Monday of expiry week). The Bloomberg cross-check showed that rule missed rolls on other days. Pass 2 also drops an origin whenever the ES-minus-cash basis steps by more than 0.3% between the two closes (5 further origins). PR #5's numbers carry the same weakness, to a similar small degree.
6. Layla's reproduction check first used a 6-session horizon and failed, because her preview ran at 9 sessions (cutoff 10 Nov); corrected. The tolerance is 0.05 index points because the match is 7543.69 against 7543.72, not exact.
7. The ES-versus-Bloomberg check first failed (correlation 0.971) because of two Bloomberg expiry-day prints; those two days are excluded and listed in the check.
8. A data-integrity problem was found and fixed on this branch: on a Windows checkout git converted line endings and 7 of 13 public data CSVs failed Antonio's SHA-256 verification. `.gitattributes` now marks the data folders as binary. Anyone on Windows needs it.
9. M17 is marked contaminated because Mohamed chose it from 11 candidates on a window overlapping the unseen part; his other three specifications are treated as clean.

## Limitations
- ES data cover 3.8 years; the unseen Friday sample is 55 origins. Gains of 5-9% on that sample have wide intervals (see the 90% columns).
- M1, M7, M14 and M17 are contaminated and not ranked. M6 and M10 were chosen on an earlier window that overlaps the first part of the evaluation period.
- Layla's demeaning uses an expanding mean of past gaps (about 0.05% a night) as a stand-in for her 48-day mean; her own backtest of the rule covers only 48 days and is not part of this ranking.
- Mohamed's ridge and random forest were not re-run at six sessions; they appear only on Track C.
- The roll-day exclusion is data-derived, not from the CME calendar. ES1! is not back-adjusted.
- Differences between the top models are far smaller than the bootstrap intervals; the ranking is a best estimate, not a verdict.
- The ES advantage depends on the 07:00 price being available before the cutoff; for the final forecast it needs a fresh export taken after 07:00 New York on 13 Nov.
- CME and Bloomberg data are licensed: the raw files are not in the repository (CME) or were used locally only (Bloomberg); only derived results are written here.
