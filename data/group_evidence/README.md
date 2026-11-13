# Group evidence: the tests the report cites but this package does not recompute

The report cites four pieces of the group's wider work (`data/group_tests.json`). Two of them use licensed
intraday futures data that may not be redistributed, so the raw inputs are **not** in this ZIP. This folder
holds what can be shared: the plan written before each test, the code, and the saved outputs, copied unchanged
from the group repository (`drift-asia/`) on 10 Nov 2026. Nothing here is a forecast input.

| Folder | Cited in the report as | What is here | Raw input (not included) |
|---|---|---|---|
| `futures_bloomberg_test31/` | Bloomberg 07:00 New York test, 133 origins, 1.389% to 1.307% (t 2.50; Thursdays t 3.49) | `prereg_futures_anchor.md` (plan), `futures_anchor.py` (code), `futures_anchor.txt` and `.json` (output), `compare_mohamed.txt` (the t values against drift alone), `drift_choice.txt` | Bloomberg ES1 Index 1-minute bars, UCL terminal, exported 3 Nov 2026 |
| `futures_tradingview_930/` | 930-origin test, slope 0.92 (s.e. 0.16) | `PREREG.md`, `run_futures.py`, `futures_results.md`, `compare_asia.md`, `origin_errors.csv` (derived per-day gaps and errors only) | TradingView ES1! hourly export (CME data), 22,786 bars, 2 Jan 2023 to 10 Nov 2026; SHA-256 in `README.md` there |
| `factor_tests_30/` | 30 pre-registered tests, none passed | `factors.yaml` (definitions fixed before results), `verdict.md`, `verdict.csv`, `placebo.txt` | Public data (Yahoo, FRED, Cboe, French) plus Bloomberg series for 6 of the factors |
| `model_review/` and `MODEL_RANKING.md` | Like-for-like ranking of every model | `PREREG.md`, `REVIEW.md` | As above |

## Format of the restricted inputs (description; labelled samples in `sample_inputs/`)

- Bloomberg table used by test 31, one row per session: `date_new_york`, `ES1 Index|price_at_0700_NY`,
  `last_bar_start_NY_used_0700`, `ES1 Index|price_at_1600_NY`, `last_bar_start_NY_used_1600`. A row is used only
  when the two bar times are 06:59 and 15:59 and the two ends are on the same contract.
- Bloomberg bars: `bar_start_utc`, `bar_start_new_york`, `ES1 Index|LAST_PRICE (bar close)`, `ES1 Index|VOLUME`.
- TradingView export: hourly ES1! bars in New York time (open, high, low, close).

## What a marker can and cannot rerun

- **Can, from this ZIP alone:** the submitted forecast and everything in the report's tables
  (`python code/run_all.py --final`). The futures price it uses is the public Yahoo ES=F series in `data/raw_final/`.
- **Can, from saved derived values (no licensed prices needed):** the statistics the report cites for both futures tests.
  `futures_tradingview_930/recompute_from_origin_errors.py` rebuilds the 930-origin tables and the slope 0.92 (s.e. 0.16) from
  `origin_errors.csv`; `futures_bloomberg_test31/recompute_from_origin_errors.py` rebuilds test 31 (133 origins, 1.389% to 1.307%,
  t 2.50; Thursdays t 3.49) from `origin_errors_test31.csv`. Each reproduces the saved results line for line (numpy and pandas only).
  `origin_errors_test31.csv` was written by `futures_anchor.py` on the group's machine on 13 Nov 2026 and holds percentage errors only.
- **Cannot without the licensed files:** build those per-origin errors from the prices (`futures_anchor.py`, `run_futures.py`).
  Layout samples built from public data are in `sample_inputs/` (labelled SAMPLE; not the licensed data and too short to
  reproduce anything). Honest reading: test 31 did not reach its pre-set hurdle of |t| 3.16 (t 2.31 against drift + Asia,
  2.50 against drift alone); the futures start was adopted under the pre-set rule of a positive gain overall and
  in both halves.
