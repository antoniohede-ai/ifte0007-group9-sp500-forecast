# SAMPLE inputs (labelled): the format of the restricted futures files

The two group futures tests cited in the report used **licensed intraday data that may not be redistributed**: Bloomberg ES1 1-minute bars (UCL terminal) and a TradingView / CME ES1! hourly export. The real files are not in this ZIP. The two files here are **samples in the same layout, built from public data**, so you can see the format and run your own code on it.

| File | Layout of | Rows | Built from |
|---|---|---|---|
| `SAMPLE_ES_hourly_TradingView_format.csv` | the TradingView ES1! export: `time` (New York time, stamped by the bar's **start**), `open`, `high`, `low`, `close` | 69 hourly bars, 3 Nov 18:00 to 6 Nov 17:00 (New York) | Yahoo Finance ES=F 5-minute bars (public), `data/raw_live/es_5m.json` of the 10 Nov snapshot, aggregated to hours |
| `SAMPLE_ES_0700_1600_Bloomberg_format.csv` | the Bloomberg table used by test 31: `date_new_york`, price at 07:00 and 16:00 New York and the start time of the bar used | 3 sessions, 4-6 Nov | The same Yahoo bars: the last 5-minute bar before each time (bar start 06:55 and 15:55; the real Bloomberg table uses 1-minute bars starting 06:59 and 15:59) |

**What these are not.** They are not Bloomberg or TradingView data, they are far too short to reproduce any reported statistic, and nothing in the forecast, the report tables or the group tests was computed from them. They were made on 13 Nov 2026 only to show the layout.

**What you can reproduce without the licensed data.** The statistics the report cites come from per-origin errors that contain no prices, and those are saved in this ZIP:

- `../futures_tradingview_930/recompute_from_origin_errors.py` rebuilds the 930-origin tables and the slope 0.92 (s.e. 0.16) from `origin_errors.csv`; every number matches `futures_results.md`.
- `../futures_bloomberg_test31/recompute_from_origin_errors.py` rebuilds test 31 (133 origins, 1.389% to 1.307%, t 2.50; Thursdays t 3.49) from `origin_errors_test31.csv`; every number matches `futures_anchor.txt` and `compare_mohamed.txt`.

Both need only numpy and pandas. They check the arithmetic from the errors onwards, not the construction of the errors from the licensed prices; that step is in `futures_anchor.py` and `run_futures.py`, which need the real files.
