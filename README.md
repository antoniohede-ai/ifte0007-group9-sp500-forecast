# IFTE0007 group coursework (group 9): S&P 500 forecast, evidence package

**Start here.** This ZIP lets you check one forecast and reproduce it from the saved inputs, without our accounts, without internet and without an AI subscription.

| Final forecast record | |
|---|---|
| Status | FINAL - APPROVED BY ALL FOUR MEMBERS |
| Market and unit | S&P 500 price index (SPX), index points |
| Target | 2026-11-20 official close (16:00 America/New_York) |
| Information cutoff | 2026-11-13 12:00:00+00:00 UTC |
| Last usable close | 2026-11-12 = 7,592.40 |
| **Forecast** | **7,637.84** |
| Reference source | S&P Dow Jones Indices official closing price-index level |
| Discretionary adjustment | 0.00% |
| Approved by | Layla Ahmed, Antonio Herrera Despradel, Jayen Rughani, Mohamed Derbala at 2026-11-13T15:05:55Z |
| Record | `outputs/final/forecast_record.json`, SHA-256 71ae56994c3f... |


The same value is on the cover of the report (`report/`). It was calculated with information available by **Fri 13 Nov 2026 12:00 UTC** (07:00 New York) only: every input carries its publication time and anything later is excluded by the code and tested. The snapshot was downloaded at 14:29 UTC, after the cutoff, because the 5-minute futures bar ending at 07:00 New York exists only once the cutoff has passed; the filter keeps the bar ending at 12:00 UTC and drops the later ones (the leak test corrupts them and the inputs do not change).

## Check it in three steps

Python 3.12 or later, and `pip install -r requirements.txt` (versions tested are listed in that file). Run from this folder.

| Step | Command | Time | What you see |
|---|---|---|---|
| 1. Recalculate the number | `python code/demo_tools.py recompute` | about 3 s | A separate recalculation from the raw files (needs only numpy and pandas). Each line ends MATCH or DIFFERS against the record: last close, drift, futures move, overnight average, forecast |
| 2. Independent check | `python code/independent_check.py --snapshot data/raw_final --tag final` | about 3 s | `PASS_ALL = true` if the second code path (plain Python plus statsmodels) reproduces the forecast and the leak test passes: every value published after the cutoff is corrupted on purpose and the inputs must not change |
| 3. Rebuild everything | `python code/run_all.py --final` | about 10 min | Rewrites `outputs/final/`, figures, report, slides and `forecast_record.json` from the saved files only, and writes `agent/run_transcript_final.txt` |

Step 3 overwrites files in this folder, so run it in a copy. The rehearsal (cutoff 30 Oct, target 6 Nov, outcome known) is kept as saved outputs in `outputs/rehearsal/`; its raw inputs are not in this ZIP, so it is evidence rather than something to rebuild.

## Where each brief requirement is

| The brief asks for | Where |
|---|---|
| Frozen data snapshot | `data/raw_final/`: raw files with source URL, retrieval time and SHA-256 in `manifest.json` |
| Dated sources, publication time, last usable observation | Report Table 1 and Appendix A; `outputs/final/results.json` |
| Calculation files | `code/` (`run_model.py` is the model; `common.py` holds the cutoff filter); `outputs/final/tables/calculation_trace.csv` is the step-by-step calculation |
| Agent instructions: goal, data boundary, permitted tools, method fixed in advance | `agent/AGENT_INSTRUCTIONS.md` |
| Agent decisions, tool inputs and outputs, corrections | `agent/agent_log.md` (in order) and `agent/run_transcript_final.txt` (the full run) |
| An independent check | `code/independent_check.py`, result in `outputs/final/independent_check.json` |
| Human approval | `approved_by` in `outputs/final/forecast_record.json`; contribution statement in the report |
| Labelled workflow diagram | `outputs/final/figures/fig1_workflow.png` (also Figure 1 in the report) |
| Benchmark, chronological validation, sensitivity, adverse scenario | Report sections 6 and 7; `outputs/final/tables/` |
| Labelled sample inputs where redistribution is restricted | `data/group_evidence/sample_inputs/` (layout samples) and the two `recompute_from_origin_errors.py` scripts (cited tests from saved derived values) |
| Software versions | `requirements.txt` and the table below |
| Final forecast record | `outputs/final/forecast_record.json` |
| Report and slides | `report/` |

## Watch the agent work (optional, no account needed)

`python code/demo_ui.py`, then open http://127.0.0.1:8765 and choose **Replay**. It plays back saved runs of the research agent (Claude Code) checking the forecast: its plan, the tools it chooses, what each returns, its reasoning and its recommendation. Each replay shows when it was recorded; runs dated before 13 Nov used the earlier 10 Nov preview data and show a different forecast. A live run needs Claude Code signed in and uses **Frozen** mode by default: the agent works only on the saved snapshot in `data/raw_final/` with no internet, as the brief asks (*demonstrate the agent using frozen inputs*). The optional Demo and Full modes pull fresh public data; Full is a non-binding look-ahead. `agent/DEMO_README.md` explains all of this. The agent's tools are `code/demo_tools.py` (read-only; it never changes the record).

## What the method does

Forecast = last official close x exp(median six-session return since 1990 + overnight E-mini futures move to 07:00 New York, less the average overnight move). The agent first screened 16 pre-registered candidate factors (yields, dollar, gold, semiconductors, surprise index, CPI, PPI, price and volatility measures) one at a time against median drift in a walk-forward test. A factor could enter only by beating drift out of sample on a validation block and not being contradicted by a long-history proxy; the rule is in `agent/AGENT_INSTRUCTIONS.md` and was not relaxed. None qualified, so the model is median drift plus the futures move. It was frozen after a group review: the screen is reported but cannot change the forecast on submission day. No discretionary adjustment (0.00%).

## What is not in this ZIP, and why

- **Licensed data.** Two group tests behind the report's futures evidence used Bloomberg and TradingView prices that cannot be redistributed. `data/group_evidence/` holds their plans, code and saved results. Two short scripts there (`recompute_from_origin_errors.py` in each futures folder) rebuild the cited statistics from saved per-origin errors, which contain no prices, and match the saved results line for line. `data/group_evidence/sample_inputs/` has labelled samples, built from public data, of the layout of the restricted files; its README says what they are and are not. The forecast itself uses public data only (Yahoo Finance, Cboe, US Treasury), all in `data/raw_final/`.
- **The group's supporting workbook** (a Bloomberg export): a helper for cross-checks only, not a forecast input, so a rebuild from this ZIP matches every table exactly.
- **Credentials:** none are used or stored.

## Tested environments

| | Python | numpy | pandas | statsmodels |
|---|---|---|---|---|
| Package author's machine (as recorded 10 Nov) | 3.12.10 | 2.5.4 | 3.1.0 | 0.15.0 |
| Clean rebuild from the repository, 13 Nov 2026 | 3.14.0 | 2.3.4 | 2.3.3 | 0.14.5 |
| **Submitted final build**, 13 Nov 2026 (fresh install from `requirements.txt`) | 3.13.2 | 2.5.4 | 3.1.1 | 0.15.0 |

Both gave the same forecast, drift and futures move, and `PASS_ALL = true`. Both: matplotlib 3.11.2, reportlab 5.1.0, python-docx 1.2.0, python-pptx 1.0.2. The clean rebuild also used openpyxl 3.1.5, pillow 13.0.0 and requests 2.32.5. The full list is in `requirements.txt`.

## Contents

| Path | What it is |
|---|---|
| `code/run_all.py` | One command that reproduces every number, table, figure, the report and the slides |
| `code/run_model.py`, `code/common.py` | Source reconciliation, factor screen, selection rule, walk-forward validation, nowcast, final forecast, sensitivity, scenarios; raw-file parsing and the information-cutoff filter |
| `code/independent_check.py` | Second code path and leak test |
| `code/fetch_data.py` | How the snapshot was downloaded (not needed to reproduce) |
| `code/make_figures.py`, `build_report.py`, `build_slides.py`, `render.py` | Figures, report (.docx and .pdf), 6-slide deck (5 for the 7-minute talk, 1 for the live agent demo in the questions) and speaker script |
| `code/extra_asia.py`, `extra_dukascopy.py`, `compare_models.py` | Side experiments and the model comparison cited in the report |
| `code/demo_tools.py`, `demo_ui.py`, `demo_ui.html` | The agent demo: its read-only tools and the local page |
| `agent/` | Instructions, log, run transcripts, demo prompts and saved demo runs |
| `outputs/final/` | `results.json`, `tables/*.csv`, `figures/`, `independent_check.json`, `forecast_record.json` |
| `outputs/rehearsal/` | Rehearsal against a known outcome (quoted on slide 5) and its run transcript in `agent/` |
| `report/` | Submitted report, slides and speaker script |
| `data/` | Frozen snapshot (`raw_final/`), group tests and evidence, dated news digest, price corrections |
| `group_info.json` | Members, contributions and AI-use statements, used to build the report |
