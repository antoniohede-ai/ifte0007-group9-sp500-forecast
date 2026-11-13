# ES futures anchor: pre-registration (10 Nov 2026, written BEFORE any result was computed)

Status: exploratory, branch `exp/es-futures`. It does not change the agreed model.

## Data
`data/ES1_60min_TradingView_20261110.csv`: TradingView `ES1!` (CME E-mini S&P 500, continuous front month) hourly bars,
exported by Jayen from a Premium account on 10 Nov 2026, New York time with UTC offset. 22,785 bars,
2023-01-01 18:00 ET to 2026-11-10 11:00 ET. sha256 `c71a874cffe1de9ed2dd9b4caa1f4b30f673e2a46b46a07f666ee87fb72a8696`.
Licence: CME data via TradingView, used for coursework in a private repo; do not redistribute (see README note).
S&P 500 official closes: the repo's public GSPC snapshot (to 30 Oct 2026).

## Question
The cutoff is Fri 13 Nov 07:00 New York. Does starting from the level implied by ES at 07:00, instead of the S&P close of the
previous day, lower the 6-day-ahead error of the S&P close?

## Definitions
- Futures prices: ES(16:00) = close of the 15:00 bar; ES(07:00) = close of the 06:00 bar. Gap g = log ES(d, 07:00) - log ES(p, 16:00),
  p = previous S&P trading day. The futures-cash basis cancels in the ratio.
- Origin d at 07:00 New York; target = S&P close 5 trading days after d's close (6 after p's). Same horizon as the model.
- Roll days: any hourly bar-to-bar jump above 0.3% that is repeated as a contract-roll signature (found from the data) removes every origin whose
  gap window contains it. Counted and reported.
- Drift: expanding median of known 6-day log returns (outcome date on or before p), full S&P history from 2000.

## Forecasts compared (all run, none dropped)
| id | forecast |
|---|---|
| A0 | S&P(p) |
| A1 | S&P(p) x exp(drift)   [current model without the Asia factor] |
| B0 | S&P(p) x exp(g) |
| B1 | S&P(p) x exp(g + drift) |
| B2 | S&P(p) x exp(g + drift x 5/6) |
| B3 | S&P(p) x exp(0.5 g + drift) |
| B4 | S&P(p) x exp(0.75 g + drift) |

## Rules
- Primary sample: Friday origins (the real situation). Secondary: every weekday origin (overlapping, more data).
- Metric: mean absolute % error; mean score 50 - min(50, 5E); Newey-West t (2 lags) of the loss difference against A1 (positive = better).
- Unseen part: the last 30% of origins in time, reported beside the full sample. No parameter is tuned (B3, B4 are fixed values, not fitted).
- Also reported: OLS slope of the 6-day return on g (should be near 1 if the gap persists), correlation of g with asia_overnight.
- Hurdle: this is one primary comparison (B1 vs A1). Other rows are descriptive.
