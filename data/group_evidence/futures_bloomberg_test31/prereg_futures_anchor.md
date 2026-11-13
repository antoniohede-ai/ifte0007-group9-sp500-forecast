# Pre-registration: futures nowcast as the starting level (10 Nov 2026, before any result)

Prompted by Layla's preview (group repo `main` b597cc1, `evidence_preview.zip`): forecast = last close x exp(median drift + overnight ES move to the cutoff, less its mean). Her check used 48 days of Yahoo 5-minute ES. This test uses our longer Bloomberg table and is test 31 (budget raised 30 -> 31 by Antonio on 10 Nov; Bonferroni hurdle |t| >= 3.16).

## Definitions
- Overnight move for forecast day d: r_ovn(d) = log(ES at 07:00 New York on d / ES at 16:00 New York on the previous trading day). 07:00 New York = our 12:00 London cutoff.
- Sources: Bloomberg ES1 table `01c_es1_0700_1600_ny.csv` (21 Apr - 2 Nov 2026) first; Layla's Yahoo `ES=F` 5-minute bars (1 Sep - 10 Nov 2026; last bar at or before the time) only for days after 2 Nov. On the overlap both are computed and their agreement is reported, not used to choose.
- Drop a day when either end fails the bar-time rule (07:00 bar 06:59, 16:00 bar 15:59) or when the two ends straddle a quarterly expiry (first session after 18/19 Jun and after 18 Sep), or |r_ovn| > 4%.
- Mean overnight drift e(d) = mean of r_ovn over earlier days in the sample (0 until 20 days exist), so no look-ahead.

## Origins and models
Origin = close of the trading day before d; target = close 6 trading days after the origin; outcomes known up to the 9 Nov close. m = expanding median of known Thursday 6-day log returns since 2000; a = asia_overnight signal, both exactly as in the chosen model.
- B (current model): S x exp(m + 0.5 a)
- C (futures start): S x exp(m + r_ovn - e)
- D (both): S x exp(m + r_ovn - e + 0.5 a)
- A (drift only) and no change are reported for reference.

## Statistic and decision rule
- Primary: mean absolute % error gain of C over B on all origins, Newey-West t with 5 lags (overlapping 6-day windows). Thursday origins reported separately.
- C has no fitted parameter (the futures move enters one for one), so there is no in-sample selection to protect against. Adopt C as the live model if its gain over B is positive on the full sample and in both halves (split at the middle origin), and say plainly whether |t| reaches 3.16.
- Keep the Asia term on top (D) only if D beats C on the full sample and in both halves. Otherwise Asia stays as the long-history evidence for the overnight-news mechanism and leaves the live formula, because the futures move already contains it.
- If C is not adopted, the futures price stays a noon cross-check only (PLAN.md).
