# Agent instructions (as given to the tool-using agent) - version 2, 10 Nov 2026

**Agent used:** Claude Code (Claude desktop app, Code tab), model `claude-sonnet-5-5`, with PowerShell, Python 3.12, file read/write, web search and web fetch. A human group member supervised the session.

## Research goal
Produce ONE numerical forecast of the **S&P 500 price index official closing level on Friday 20 November 2026** (S&P Dow Jones Indices, index points, 16:00 America/New_York), using only information available by the **information cutoff Friday 13 November 2026, 12:00 UTC**. Find the factors that genuinely predict it, using public data plus, as a HELPER only (never a forecast input, never shipped), the group's supporting workbook (`Zaki's data.xlsx`: yields, CPI, PPI, USD, surprise index, semiconductors, gold), research the latest news, and report the most accurate point forecast that the evidence supports. Compare with benchmarks over chronological origins, test sensitivity, and report failures honestly.

## Data boundary
* Allowed: public market data (model inputs); the supporting workbook as a helper for the screen and cross-checks only; public market data retrieved over HTTPS and saved as raw files with URL, retrieval time and SHA-256 (`code/fetch_data.py`); dated news pages (context only).
* Every observation is admitted only if its official publication time is **<=** the cutoff (SPX 16:00 ET, VIX 16:15 ET, other daily series 17:00 ET, CPI/PPI 16 days after month-end, intraday bars only once finished). Enforced in `code/common.py` and tested (`code/independent_check.py`, leak test incl. the workbook).
* Not allowed: the realised 20 Nov value, any price or news dated after the cutoff, ETFs or futures as a *target substitute* (ES futures are an *input* to the overnight nowcast), any forecast copied from an analyst or an AI answer, memory of past index levels used as data.

## Permitted tools
Read the workbook and public web pages/APIs; run Python (numpy, pandas, statsmodels, openpyxl, matplotlib, reportlab, python-docx, python-pptx); write files in the evidence package. **Not permitted:** trading or account access, paid APIs, entering credentials, changing the forecast after human approval.

## Pre-registered method (fixed before any result was inspected)
1. Target `y = ln(S[t+h]/S[t])`, h = NYSE sessions from the last observed close to the target close (h = 6 for the final run).
2. Benchmarks: B0 unchanged; B1 expanding median h-session return (all history).
3. **Candidate factors (16), each with an economic sign fixed in advance:** 252-day trend (+), 5-day reversal (-), variance risk premium (+), 5-day VIX change (-), drawdown from the 1-year high (-), VIX level (+), 2Y yield 20-day change (-), 10Y yield 20-day change (-), 10Y-2Y slope (+), USD 20-day return (-), gold 20-day return (-), semiconductors-minus-S&P 20-day return (+), economic surprise index level (+) and 20-day change (+), CPI inflation 3-month change (-), PPI inflation 3-month change (-).
4. **Screen:** one factor at a time, walk-forward least-absolute-deviations (median) regression on rows whose target was already realised at each origin; forecast = m0 + b.z. Weekly origins on the final origin's weekday from 2018-01 (validation to 2021-12, test after; widened from 2022-01/2024-06 on 10 Nov when the supporting workbook was extended back to 2015, before any result on the new data was seen). Score = Diebold-Mariano t (Newey-West, 1 lag) of B1's absolute % error minus the factor model's.
5. **Eligibility:** fitted sign matches the mechanism in >70% of origins; t >= 1.65 on validation and, where a long-history proxy exists (2000-2012 validation), proxy t >= 0; otherwise t >= 2.33. At most two eligible factors with |corr| < 0.7 enter. If none qualifies, the model is median drift plus nowcast. **The rule is not to be relaxed after seeing results.**
6. mu = m0 + kappa x (factor fit), kappa in {0, .25, .5, .75, 1} chosen on the validation block only.
7. Overnight nowcast from ES futures (16:00 ET close -> cutoff), less the sample's mean overnight drift. News enters only through this price and through the interval width; **no discretionary adjustment (0.00%)**.
8. Loss for fitting and selection is the assignment's own: absolute percentage level error (the conditional median is optimal).

## Required behaviour
* State why each approach was chosen, record tool inputs/outputs in `agent_log.md`, and log every correction.
* Reconcile sources; report disagreements instead of choosing the convenient value.
* Never fabricate data, references or results; where a news item is contradicted across sources, hedge it or leave it out.
* Stop and report if the cutoff filter, the independent check or a coverage check fails (a selected factor whose workbook series ends before the cutoff stops the run: refresh it or run without the workbook).
* End by writing `forecast_record.json`; a human must approve it before it is copied to the report cover.

## Human responsibility
Members run `python code/run_all.py --final --fetch` (optionally `--zaki "<path>"` to widen the screen), read `outputs/final/tables/calculation_trace.csv`, confirm `independent_check.json` shows `PASS_ALL = true`, check the S&P DJI close, refresh `data/news_digest.json` (items dated before the cutoff only) and sign the forecast record. The agent never submits anything.

## Amendment after group review (10 Nov 2026, before the final run)
* **The model is frozen.** The factor screen is still run and reported, but no factor can enter the forecast on submission day (`--allow-factor-entry` is off; kappa = 0). Reason: the brief asks for a frozen method, and an unreviewed refit on the day is a risk (Antonio's review, group repo PR #6).
* **Futures evidence** in the report cites the group's two pre-registered tests (Bloomberg 07:00 New York prices, 133 origins; TradingView, 930 origins) in place of the 48-day check, which is kept as a secondary check. Their data are not redistributed.
* **Preview builds** use the cutoff's clock time (12:00 UTC = 07:00 New York).
