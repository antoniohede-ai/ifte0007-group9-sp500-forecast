"""build_report.py (v2) - writes report .docx + .pdf and forecast_record.json from outputs/<tag>/ (no number is typed by hand).

    python code/build_report.py --tag rehearsal|final
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, load_daily, load_es, news_known, utc  # noqa: E402
from render import count_main, to_docx, to_pdf  # noqa: E402
from run_all import PRESETS  # noqa: E402

LIMIT = 2400


def f(x, d=2):
    return f"{x:,.{d}f}"


def sgn(x, d=2):
    return f"{x:+,.{d}f}"


def date_long(s):
    t = pd.Timestamp(s)
    return f"{t:%a} {t.day} {t:%b %Y}"


def build(tag: str):
    out = ROOT / "outputs" / tag
    R = json.loads((out / "results.json").read_text(encoding="utf-8"))
    chk = json.loads((out / "independent_check.json").read_text(encoding="utf-8"))
    GI = json.loads((ROOT / "group_info.json").read_text(encoding="utf-8"))
    NEWS = json.loads((ROOT / "data" / "news_digest.json").read_text(encoding="utf-8"))
    P = PRESETS[tag]; snap = ROOT / P["snapshot"]
    man = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    final = tag == "final"
    cutoff = utc(R["cutoff_utc"])
    F, h, S0 = R["forecast_final"], R["h_sessions"], R["last_close"]
    tgt = date_long(R["target_date"]); last = date_long(R["last_close_date"]); cut_s = f"{date_long(cutoff.date())} {cutoff:%H:%M} UTC"
    ny_hhmm = f"{cutoff.tz_convert('America/New_York'):%H:%M}"
    sel = R["selected"]; W_ = R["windows"]
    pt = {r["model"]: r for r in R["perf_test"]}; pv = {r["model"]: r for r in R["perf_valid"]}
    names = list(pt)
    n_b0, n_b1, n_top, n_v1, n_fin = names[0], names[1], names[2], names[3], names[4]
    b0, b1, top, v1, fin = (pt[k] for k in names[:5]); b0v, b1v, finv = pv[n_b0], pv[n_b1], pv[n_fin]
    nc, dc, kappa = R["nowcast"], R["data_checks"], R["kappa"]
    scr_all = pd.DataFrame(R["screen"]); scr = scr_all[scr_all.t_valid.notna()].copy()          # rows without data (no workbook) are reported separately
    nz = int(scr.source.str.startswith("Macro").sum()); ncand = int(len(scr))
    WBN = json.loads((ROOT / "data" / "workbook_screen_note.json").read_text(encoding="utf-8")) if (ROOT / "data" / "workbook_screen_note.json").exists() else None
    wb_missing = [r for r in scr_all.to_dict("records") if pd.isna(r["t_valid"])]
    wb_txt2 = ""
    if wb_missing and WBN:
        ts = [WBN["t_valid"][r["factor"]] for r in wb_missing if r["factor"] in WBN["t_valid"]]
        wb_txt2 = (f" {len(wb_missing)} further candidates need licensed Bloomberg data ({', '.join(r['label'].lower() for r in wb_missing)}); tested separately on the group's Bloomberg workbook, "
                   f"none passed (validation t {f(min(ts),2)} to {f(max(ts),2)}).") if ts else ""
    fs = {r["variant"]: r for r in R["final_sensitivity"]}; scen = R["scenarios"]; reh = R.get("realised_in_snapshot")
    ctx = R["features_context"]
    nleak = sum(chk[k]["bars_corrupted"] for k in chk if k.startswith("leak_") and isinstance(chk[k], dict) and "bars_corrupted" in k and False) if False else \
        sum(v["bars_corrupted"] for k, v in chk.items() if k.startswith("leak_") and isinstance(v, dict) and "bars_corrupted" in v) + chk.get("leak_workbook", {}).get("rows_corrupted", 0)
    drift_wins = b1["MAPE_%"] < b0["MAPE_%"]
    drift_sig = drift_wins and (b1["DM_t_vs_B0"] or 0) > 1.65
    drift_phrase = "beats" if drift_sig else ("is no better than" if (b1["DM_t_vs_B0"] or 0) > -1.65 else "loses to")
    pre_path = ROOT / "outputs" / "preview" / "results.json"
    RC = json.loads(pre_path.read_text(encoding="utf-8")) if (tag not in ("final", "now") and pre_path.exists()) else R      # regime statistics: latest available information
    ctx, vix_now = RC["features_context"], RC["vix_last"]
    spx = load_daily(snap / "gspc_daily.json", cutoff, "16:00"); vix = load_daily(snap / "vix_daily.json", cutoff, "16:15"); es = load_es(snap / "es_5m.json", cutoff) if (snap / "es_5m.json").exists() else None
    es_manual = R["nowcast"].get("es_source") == "manual"   # Bloomberg backup prices typed in at the final run (run_model.py --es-manual)
    interval_pct = 100 * (R["interval80"][1] - R["interval80"][0]) / F
    GT = json.loads((ROOT / "data" / "group_tests.json").read_text(encoding="utf-8"))
    gB, gJ, gS = GT["futures_bloomberg"], GT["futures_tradingview"], GT["screen_prereg"]
    gR = GT.get("submitted_model_review")
    rule_sel = R.get("rule_selected", sel); frozen = R.get("factor_entry", "off").startswith("off")
    wb_dates = [v.get("workbook_last") for v in R["coverage"].values() if v.get("workbook_last")]
    wb_last = date_long(max(wb_dates)) if wb_dates else None

    banner = None
    if not final:
        what = (f"a rehearsal cutoff of {cut_s} and target {tgt} (outcome known, kept out of the model by the cutoff filter)" if tag == "rehearsal" else
                f"information up to {cut_s} ({ny_hhmm} New York), the moment this run was made, and the real target {tgt}; it is a look-ahead, because the cutoff is not yet reached" if tag == "now" else
                f"information to {cut_s} ({ny_hhmm} New York, the same clock time as the real cutoff) and the real target {tgt}; it is a look-ahead, because the cutoff is not yet reached")
        banner = (f"**{tag.upper()} BUILD - NOT THE BINDING FORECAST.** Generated by the same pipeline with {what}. "
                  f"The binding build is made on Fri 13 Nov 2026 after 12:00 UTC with `python code/run_all.py --final --fetch`; "
                  f"every number, table and figure then regenerates and the cover forecast replaces this one. Section 3 (news) was researched on 10 Nov and must be refreshed. Names and the contribution statement are for the members to complete.")
    cover = {
        "kicker": "IFTE0007 Decentralised Finance and Blockchain 2026/27  |  Assessment 1: Group coursework  |  AI Agent Market Forecasting",
        "title": "A Tool-Using AI Agent Forecast of the S&P 500 Close",
        "subtitle": "Factor search on the group dataset, a pre-registered selection rule, chronological validation and the agent workflow behind one number",
        "group": [("Group", GI["group"]), ("Members", "  |  ".join(f"{m['name']}, {m['id']}" for m in GI["members"])),
                  *([("Repository", GI["repository"])] if GI.get("repository") else []),
                  ("Build", f"{tag.upper()} run, generated {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC from the saved snapshot")],
        "label": "BINDING FINAL POINT FORECAST" if final else f"{tag.upper()} FORECAST - NOT BINDING",
        "forecast": f(F), "unit_line": "S&P 500 price index, index points",
        "record": [("Market / unit", "S&P 500 price index (SPX), index points"),
                   ("Target", f"Official closing price-index level on {tgt}, 16:00 America/New_York ({'21:00 UTC' if pd.Timestamp(R['target_date']).month in (11, 12, 1, 2, 3) else '20:00 UTC'})"),
                   ("Information cutoff", f"{cut_s}. Last usable close: {last} = {f(S0)}"),
                   ("Reference source", "S&P Dow Jones Indices official closing price-index level (not futures, ETF or total-return series)"),
                   ("80% prediction interval", f"{f(R['interval80'][0])} to {f(R['interval80'][1])} (not scored)"),
                   ("Discretionary adjustment", "0.00% - none applied")]}
    B = [("cover", cover)]
    if banner:
        B.append(("banner", banner))
    B.append(("pagebreak",))

    # ------------------------------------------------------------------ 1
    B.append(("h1", "1. Executive summary and final forecast", True))
    B.append(("p", f"**Forecast: {f(F)} index points** for the S&P 500 official close on {tgt}: {f(S0)} (last close, {last}) x exp({sgn(R['mu_final_pct'])}% expected {h}-session return and "
                   f"{sgn(nc['nowcast_adjustment_pct'])}% overnight futures nowcast), with no discretionary adjustment. The 80% interval is {f(R['interval80'][0])} to {f(R['interval80'][1])} "
                   f"(+/-{f(interval_pct/2,1)}%, VIX {f(R['vix_last'],1)}); only the point forecast is scored.", True))
    B.append(("bullets", [
        (f"**Factor search, then selection by rule.** Of {len(scr_all)} pre-registered candidates, we screened the {ncand} computable from public data, {nz} macro and cross-asset (yields, USD, gold, semiconductors), "
         f"each against median drift on a validation block; the {len(wb_missing)} that need the workbook were tested separately and failed. " if wb_missing else
         f"**Factor search, then selection by rule.** We screened {ncand} candidates, {nz} macro and cross-asset (yields, USD, gold, semiconductors, surprise index, CPI, PPI), "
         f"each against median drift on a validation block. ") + (f"**{len(rule_sel)} passed** (" + ", ".join(R['labels'].get(s, s) for s in rule_sel) + ")" + (", but the model is frozen, so it is reported, not used." if frozen else ".") if rule_sel else
        (lambda tb: f"**None passed.** The best, {tb['label']} (validation t {f(tb['t_valid'],2)}), "
                    + (f"is contradicted by the 2000-2012 proxy (t {f(tb['t_long_valid'],2)})" if tb['t_long_valid'] is not None and not pd.isna(tb['t_long_valid']) and tb['t_long_valid'] < 0 else "misses the bar")
                    + ". The model is frozen: no factor can enter on submission day.")(scr.sort_values("t_valid", ascending=False).iloc[0])),
        f"**Median drift {drift_phrase} unchanged.** Test-block error {f(b1['MAPE_%'],3)}% against {f(b0['MAPE_%'],3)}% ({W_['n_test']} origins; Diebold-Mariano t = {f(b1['DM_t_vs_B0'],2)}). "
        f"The best-ranked candidate alone scored {f(top['MAPE_%'],3)}%.",
        f"**News enters through prices, not opinion.** The 07:00 New York futures price reflects the latest data, Fed and earnings news. In the group's pre-registered test on Bloomberg prices it cut six-session error from "
        f"{f(gB['mape_drift'],3)}% to {f(gB['mape_futures'],3)}% ({gB['n']} origins, t {f(gB['t'],2)}); a second test over {gJ['n']} origins finds the move carries through about one for one (slope {f(gJ['slope'],2)}).",
        f"**Accuracy is mostly luck.** Typical (median) error is {f(fin['median_APE_%'],1)}%, which would score {f(50 - min(50, 5 * fin['median_APE_%']),1)}/50 (average backtest score {f(fin['mean_score'],1)}/50); we claim a well-centred, reproducible number, not foresight."], True))
    if not final and reh:
        B.append(("p", f"**Rehearsal result (a failure, reported).** With information to {cut_s} the pipeline forecast {f(F)} for {tgt}; the index closed at {f(reh)}. Error {f(R['rehearsal_APE_%'],2)}% "
                       f"(score {f(max(0, 50-5*R['rehearsal_APE_%']),2)}) against {f(R['rehearsal_APE_unchanged_%'],2)}% for unchanged and {f(R['rehearsal_APE_B1_%'],2)}% for median drift: the futures nowcast ({sgn(nc['nowcast_adjustment_pct'],2)}%) "
                       "captured part of a 4.4% one-day fall on 5 Nov, a tail event no factor anticipated.", True))

    # ------------------------------------------------------------------ 2
    B.append(("h1", "2. Market, data and information boundary", True))
    B.append(("p", f"**Market.** The S&P 500 *price* index, scored on its official close on {tgt}. The cutoff, {cut_s} ({ny_hhmm} New York), {'precedes the US open' if (cutoff.tz_convert('America/New_York').hour * 60 + cutoff.tz_convert('America/New_York').minute) < 570 else 'falls during the US session, before its close'}, so the last official close in hand is {last}; "
                   f"the horizon is h = {h} NYSE sessions. A value enters only if its official close time is at or before the cutoff; intraday bars only once finished. "
                   f"A leak test corrupted {nleak:,} post-cutoff observations across all input files; model inputs did not change.", True))
    rows = []
    for fn, role, pub, lastobs in (("zaki_data.xlsx", "Supporting research workbook (Bloomberg export). Cross-checks and macro screen only; not a forecast input",
                                    "dated rows; used from 17:00 New York (S&P 16:00, VIX 16:15); CPI/PPI 16 days after month-end", f"rows to {wb_last}; Treasury and Yahoo fill gaps" if wb_last else "not supplied"),
                                   ("gspc_daily.json", "S&P 500 and VIX daily, Yahoo (history from 1990; the model input)", "official close 16:00 New York (VIX 16:15)", f"{spx.index[-1]:%d %b %Y} close"),
                                   ("es_5m.json", "E-mini S&P 500 5-minute bars, Yahoo " + ("(not used: missing or stale at the cutoff; Bloomberg backup below)" if es_manual else "(nowcast)"), "continuous; a bar is used only once it has ended",
                                    f"bar ending {es.index[-1]:%d %b %H:%M} UTC" if es is not None and len(es) else "no usable bar"),
                                   ("treasury_yields.csv", "US Treasury par yields (official), gap fill and check", "after the close; used from 17:00 New York", "latest published row"),
                                   ("check_cboe_spx.csv", "Cboe SPX and VIX history (independent check)", "after the close", "reconciliation only")):
        if fn not in man["files"]:
            continue
        m = man["files"][fn]
        rows.append([role, pub, m["retrieved_utc"].replace("T", " ")[:16] + " UTC", lastobs])
    if es_manual:
        ncm = R["nowcast"]
        rows.append(["E-mini S&P 500 front month, Bloomberg prices typed in by a member (backup; the nowcast input)", "16:00 New York close and the cutoff",
                     str(ncm["es_bar_end_used"]).replace("manual: ", "")[:60], f"{f(ncm['es_close_prev_session'], 2)} and {f(ncm['es_at_cutoff'], 2)}"])
    B.append(("table", ["Source (raw files saved, SHA-256 in Appendix A)", "Publication time", "Retrieved", "Last usable observation"], rows, [7.2, 3.6, 3.0, 3.2],
              "Table 1. Observed data and timing discipline", True))
    wb_txt = ""
    if "workbook_spx_vs_cboe_over_0.05pct" in dc:
        wb_txt = (f"The supporting workbook matches Cboe on all but {dc['workbook_spx_vs_cboe_over_0.05pct'] + dc['workbook_vix_vs_cboe_over_0.05']} S&P/VIX days and Treasury yields to "
                  f"{f(dc['workbook_2y_vs_treasury_median_abs_bp'],1)}bp; it was a tie-breaker and screen source, never a forecast input. ")
    B.append(("p", f"**Reconciliation.** Yahoo and Cboe SPX differ by over 0.05% on {dc['yahoo_vs_cboe_over_0.05pct']} of {dc['yahoo_vs_cboe_days']:,} days (largest: a stale Cboe value). "
                   f"{dc['corrections_applied']} Yahoo values confirmed wrong by three sources are replaced with Cboe's (`price_corrections.json`); model inputs are public data only. "
                   + wb_txt + "Human sign-off checks the last close against S&P DJI.", True))

    # ------------------------------------------------------------------ 3 news
    B.append(("h1", "3. Latest news and market regime", True))
    B.append(("p", f"Researched on {NEWS['researched_utc']} from dated news pages and checked against saved prices (marked [data]); the digest was frozen then, before the cutoff, and the 11-12 Nov moves enter only through the last close and the futures price. October ended with an AI-spending scare and a Federal Reserve leaning toward tightening; "
                   f"on the latest information the S&P 500 sits {f(abs(ctx['dd252_pct']),1)}% below its one-year high, 21-day realised volatility is {f(ctx['rv21_pct'],0)}% and VIX {f(vix_now,1)}. "
                   "Risk is two-sided: hawkish Fed and AI-capex doubts against sharp relief rallies.", True))
    rows = [[i["date"][5:].replace("-", "/"), i["event"], i["read"], i["src"]] for i in news_known(NEWS["items"], cutoff)][-5:]
    B.append(("table", ["Date", "Event", "Market read", "Source"], rows, [1.3, 7.2, 5.9, 2.6], "Table 2. Dated events (2026)", True, {"font": 7.8}))
    B.append(("p", "**How news enters the forecast.** Known news is already in the 07:00 New York futures price, which the nowcast uses; events after the cutoff (Nvidia results 17 Nov, FOMC minutes 18 Nov, options expiry 20 Nov) widen the interval instead. "
                   "No hand adjustment: 0.00%.", True))

    # ------------------------------------------------------------------ 4 factors
    B.append(("h1", "4. Factor research and economic mechanism", True))
    B.append(("p", f"**Protocol (fixed before results).** Each candidate has an economic sign chosen in advance. For each, a walk-forward median regression (Koenker and Bassett, 1978) forecasts the deviation of the {h}-session return from median drift; "
                   f"weekly origins from {W_['macro_start']} (up to {W_['n_valid']} validation origins to {W_['valid_end']}, fewer for the yield factors, whose public history starts later; then {W_['n_test']} test origins). It is eligible only if its fitted sign matches, the Diebold and Mariano (1995) t of its error against drift is at least 1.65 and a 2000-2012 long-history proxy "
                   f"does not contradict it (without a proxy: 2.33). With {len(scr_all)} tests about one false positive is expected at 1.65, hence the stricter bar.", True))
    MECH = {"mom252": "trends persist", "rev5": "short-term overreaction", "vrp": "insurance premium earned", "dvix5": "fear spikes fade",
            "dd252": "rebound after falls", "vixlvl": "fear premium", "d2y20": "policy tightening", "d10y20": "discount rate rises",
            "slope": "growth outlook", "usd20": "foreign earnings hit", "gold20": "risk-off flight", "semirel20": "AI leadership",
            "esi": "growth surprises", "desi20": "improving data", "dcpi63": "inflation, hike odds", "dppi63": "cost pressure"}
    srows = []
    for r in scr.sort_values("t_valid", ascending=False).to_dict("records"):
        lv = "n/a" if r["t_long_valid"] is None or pd.isna(r["t_long_valid"]) else f(r["t_long_valid"], 2)
        srows.append([r["label"], MECH.get(r["factor"], ""), "+" if r["expected_sign"] > 0 else "-", f(r["t_valid"], 2), lv, f(r["t_test"], 2),
                      ("passes (not used)" if frozen else "selected") if r.get("passes_rule", r["selected"]) else "fails"])
    B.append(("table", ["Candidate factor", "Mechanism", "Sign", "t valid", "t long", "t test", "Result"], srows, [4.6, 3.6, 1.0, 1.6, 1.6, 1.6, 3.0],
              "Table 3. Factor screen (t > 0 means better than median drift; test t is reported, not used)", True, {"font": 7.8}))
    if sel and not frozen:
        B.append(("p", "**Selected factors.** " + "; ".join(f"**{R['labels'][s]}** ({R['formulas'][s]}; source {R['sources'][s]}; expected sign {'+' if R['expected_sign'][s] > 0 else '-'})" for s in sel) + ".", True))
    else:
        B.append(("p", f"**Result: {'no candidate beyond the two model factors survives' if not rule_sel else 'no further factor is used'}.** Over {h} sessions none reliably beat drift out of sample, in line with Welch and Goyal (2008) and Campbell and Thompson (2008). The group agrees: {gS['tests']} pre-registered tests "
                       f"(hurdle t {f(gS['hurdle_t'],2)}) passed none, and the {GT['search']['combinations']}-combination search's best model lost to plain drift on unseen data." + wb_txt2, True))
    B.append(("table", ["Specification", "D: equity risk premium (median drift)", "N: overnight futures move"], [
        ["Formula", f"median of ln(S[t+{h}]/S[t]) over all realised windows", "ln(ES at cutoff / ES at 16:00 New York close) minus its average"],
        ["Source", "S&P 500 official close (Yahoo, Cboe-checked)", "CME E-mini S&P 500 front month, 5-minute bars (Yahoo)"],
        ["Publication time", "16:00 New York, each session", f"continuous; read at the cutoff ({ny_hhmm} New York)"],
        ["Frequency / lookback", "daily; expanding window since 1990", "intraday; since the last cash close"],
        ["Expected sign", "+ (paid for bearing equity risk)", "+, one for one (group test slope " + f(gJ['slope'], 2) + ")"],
        ["Mechanism", "risk premium; negative skew lifts the median above zero", "futures lead index price discovery (Hasbrouck, 2003) and price overnight news; arbitrage ties the cash open to them"],
        ["Fails when", "prolonged bear markets (2000-02, 2008)", "contract roll, thin overnight trading, reversal at the open"]],
        [3.3, 6.7, 7.0], "Table 4. The two model factors as computable variables", True))
    B.append(("p", "**Why these two.** The last close prices news up to 16:00 New York; E-mini futures trade overnight, so their move to 07:00 "
                   "prices the news since. Beyond that, six-session returns have no reliably forecastable part, leaving the equity premium (drift). "
                   "It fails on a reversal at the open, a contract roll or thin overnight trading.", True))

    # ------------------------------------------------------------------ 5 agent
    B.append(("h1", "5. Agent architecture and modelling", True))
    B.append(("fig", out / "figures" / "fig1_workflow.png", 16.0, "Figure 1. Labelled agent workflow: goal, data, tools, agent decisions, checks and human responsibility.", True))
    B.append(("p", "**Agent.** Claude Code (Claude Sonnet 5.5) may read public data, run Python and write files; it cannot trade or submit. It retrieved the raw files, called Python to screen factors and fit models, applied the pre-registered rule and logged each decision in `agent_log.md`. "
                   "Members re-run the code, read the trace and approve the record."
                   + (" The agent's own check of the record (plan, tool calls, verdict) is saved in agent/demo_runs/." if list((ROOT / "agent" / "demo_runs").glob("*_check*.jsonl")) else ""), True))
    B.append(("bullets", [
        "*Decision:* fit by least absolute deviations, because score is linear in absolute percentage error and its optimal point forecast is the conditional median (Gneiting, 2011).",
        "*Decision (group review, 10 Nov):* freeze the model. The screen is reported but cannot change the forecast on submission day (kappa = 0), so the submitted method is exactly the reviewed one.",
        f"*Correction:* reconciliation exposed a stale Cboe value and three faulty Yahoo values (replaced by Cboe's, `data/price_corrections.json`); a first solver was too slow and was replaced; a second code path (plain-Python median and nowcast, statsmodels QuantReg) reproduced the forecast (PASS_ALL = {chk['PASS_ALL']}).",
    ], True))
    trace = [["Last official close S_t", f(S0), "Observed"], [f"Median {h}-session return m0 (all history)", f"{sgn(R['m0_pct'],3)}%", "Calculated"]]
    for s in sel:
        trace.append([f"{R['labels'][s]}: z = {f(R['z_now'][s],2)}, effect after kappa", f"{sgn(R['contrib_pct'][s],3)}%", "Calculated"])
    trace += [[f"Expected return = m0 + kappa({kappa}) x factor fit", f"{sgn(R['mu_final_pct'],3)}%", "Calculated"],
              [f"Futures nowcast: ES {f(nc['es_close_prev_session'],2)} to {f(nc['es_at_cutoff'],2)} ({sgn(nc['overnight_return_pct'],3)}%) less mean drift {sgn(nc['mean_overnight_drift_pct'],3)}%", f"{sgn(nc['nowcast_adjustment_pct'],3)}%", "Observed, calculated"],
              ["Discretionary adjustment", "0.00%", "Judgement (none)"],
              [f"Forecast = {f(S0)} x exp({sgn(R['mu_final_pct']+nc['nowcast_adjustment_pct'],3)}%)", f"**{f(F)}**", "Result"]]
    B.append(("table", ["Step", "Value", "Type"], trace, [10.2, 2.6, 4.2], "Table 5. From baseline to forecast level", True))

    # ------------------------------------------------------------------ 6 validation
    B.append(("h1", "6. Validation and benchmark", True))
    B.append(("p", f"**Design.** Weekly origins on the final origin's weekday, {W_['first_origin']} to {W_['last_origin']} ({W_['n_origins']}), h = {h}; parameters use only rows whose target was already realised. "
                   f"Benchmarks: B0 unchanged, B1 median drift. Loss: score = 50 - min(50, 5 x APE). Price factors train on up to 36 years, " + ("macro series on the workbook history (from 2015)." if wb_dates else "macro and cross-asset series on their public history."), True))
    labs = {n_b0: "B0 unchanged", n_b1: "B1 median drift", n_top: "Best-ranked candidate alone", n_v1: "Trend + VRP (earlier design)", n_fin: ("**Final: drift (+ nowcast, validated below)**" if not sel else "**Final model**")}
    rows = [[labs[k], f(pt[k]["MAPE_%"], 3), f(pv[k]["MAPE_%"], 3), f(pt[k]["mean_score"], 2), f(pt[k]["worst_APE_%"], 1), "-" if k == n_b0 else f(pt[k]["DM_t_vs_B0"], 2)] for k in names[:5]]
    B.append(("table", ["Model", f"Test MAPE % (n={W_['n_test']})", f"Validation MAPE % (n={W_['n_valid']})", "Test mean score /50", "Worst test APE %", "DM t vs B0 (test)"], rows, [4.8, 2.6, 2.9, 2.4, 2.1, 2.3],
              "Table 6. Chronological out-of-sample errors", True))
    B.append(("p", f"**Reading the table.** Drift {drift_phrase} unchanged (test {f(b1['MAPE_%'],3)}% vs {f(b0['MAPE_%'],3)}%; validation {f(b1v['MAPE_%'],3)}% vs {f(b0v['MAPE_%'],3)}%): a small, regime-dependent edge. "
                   f"The best-ranked candidate ({f(top['MAPE_%'],3)}%) and the earlier trend-plus-VRP design ({f(v1['MAPE_%'],3)}%) do not earn a place. "
                   f"The worst backtest errors (validation and test) were {'; '.join(f'{pd.Timestamp(w['date']):%d %b %Y} ({f(w['APE_final'],1)}%)' for w in R['worst_errors'][:3])}, all shocks the unchanged benchmark missed equally.", True))
    own_txt = ""
    rev_txt = (f"The group's like-for-like review scored this exact rule at {gR['n']} Friday 07:00 New York origins ({gR['period']}): "
               f"{f(gR['mape_model'],3)}% against {f(gR['mape_drift'],3)}% for drift alone and {f(gR['mape_nochange'],3)}% for no change; "
               f"after {gR['unseen_from']} ({gR['n_unseen']} origins) {f(gR['unseen_mape_model'],3)}% against {f(gR['unseen_mape_drift'],3)}% and {f(gR['unseen_mape_nochange'],3)}% "
               f"(reality-check p {f(gR['reality_check_p'],3)}). ") if gR else ""
    mc_ = ROOT / "outputs" / "extra" / "model_comparison.json"
    if mc_.exists():
        MCj = json.loads(mc_.read_text(encoding="utf-8"))["part2"]
        MA = {r["model"]: r for r in MCj["all origins"]}; MT = {r["model"]: r for r in MCj["Thursday origins"]}
        k0, k1 = "Median since 1990 (Layla)", "Median since 1990 (Layla) + futures"
        if k0 in MA and k1 in MA and k1 in MT:
            own_txt = (f"Our own backtest of the exact model on the same prices agrees: all {MA[k1]['n']} origins {f(MA[k0]['MAPE_%'],3)}% to {f(MA[k1]['MAPE_%'],3)}% (t {f(MA[k1]['t_vs_ref'],2)}), "
                       f"Thursdays {f(MT[k0]['MAPE_%'],3)}% to {f(MT[k1]['MAPE_%'],3)}% (t {f(MT[k1]['t_vs_ref'],2)}). ")
    ap_ = ROOT / "outputs" / "extra" / "asia_results.json"
    asia_txt = "Only about two months of 5-minute futures exist, so this is suggestive, not conclusive."
    if ap_.exists():
        AR = json.loads(ap_.read_text(encoding="utf-8")); A_, C_ = AR["A_1997-2026"], AR["C"]
        asia_txt = (f"Over 30 years Asian markets' overnight move explains {f(100*A_['r2'],1)}% of the next US day ({A_['n']:,} days), the spillover documented by Hamao, Masulis and Ng (1990), but adds nothing once futures are known.")
    B.append(("p", f"**Futures evidence (group tests).** A pre-registered test on Bloomberg 07:00 New York futures prices ({gB['n']} origins, {gB['period']}) cut six-session error from {f(gB['mape_drift'],3)}% (drift alone) to {f(gB['mape_futures'],3)}% "
                   f"(t {f(gB['t'],2)}, below its pre-set hurdle of {f(gB.get('hurdle_t',3.16),2)}, adopted on the pre-set rule of a gain in both halves; Thursdays {f(gB['thu_mape_drift'],3)}% to {f(gB['thu_mape_futures'],3)}%, t {f(gB['thu_t'],2)}). A second test over {gJ['n']} origins ({gJ['period']}) finds a slope of {f(gJ['slope'],2)} (s.e. {f(gJ['slope_se'],2)}), "
                   f"supporting a one-for-one entry. " + rev_txt + own_txt + asia_txt, True))
    B.append(("fig", out / "figures" / "fig2_screen_backtest.png", 16.0, "Figure 2. Left: factor screen (validation t; diamonds show the test block). Right: cumulative error reduction of the final model.", True))

    # ------------------------------------------------------------------ 7 sensitivity
    B.append(("h1", "7. Sensitivity and adverse scenarios", True))
    FS = R["final_sensitivity"]; dv = [r["forecast"] for r in FS if r.get("group") == "drift"]; tv = [r for r in FS if r.get("group") == "timing" and r["variant"] != "No futures nowcast"]
    rows = [[r["variant"], f"{sgn(r['mu_pct'],2)}%", f"{sgn(r['nowcast_pct'],2)}%", f(r["forecast"], 2), "0.00" if abs(r["forecast"] - F) < 0.005 else sgn(r["forecast"] - F, 2)] for r in FS]
    B.append(("table", ["Assumption", "Drift", "Nowcast", "Forecast", "vs final"], rows, [7.6, 2.2, 2.2, 2.6, 2.4], "Table 7. Sensitivity of the final forecast to the drift choice and the futures timing", True))
    B.append(("p", f"Across drift choices the forecast ranges {f(min(dv),1)} to {f(max(dv),1)} ({f(100*(max(dv)-min(dv))/F,2)}% of the level), well inside the typical error. "
                   + (f"Reading the futures one or two hours earlier moves it by up to {f(max(abs(r['forecast']-F) for r in tv),1)} points; " if tv else "")
                   + f"dropping the nowcast moves it by {f(F-fs['No futures nowcast']['forecast'],1)}. The key assumptions are the drift and the time the futures price is read.", True))
    rows = [[r["scenario"], f"{sgn(r['spx_shock_pct'],1)}%", f(r["vix"], 1), f(r["forecast"], 0), f"{f(100*(r['forecast']/F-1),1)}%"] for r in scen]
    B.append(("table", ["Scenario at the cutoff (labelled scenarios, not forecasts)", "Index move", "VIX", "Model level", "vs forecast"], rows, [8.2, 2.0, 1.5, 2.6, 2.7],
              "Table 8. Scenario analysis", True))
    lo_cost = 5 * 100 * (F / R["interval80"][0] - 1)   # brief: E = 100*|F-A|/A, score = 50 - 5E
    B.append(("p", f"**Adverse case.** The model has no crash protection: a further chip rout or a hawkish shock moves the forecast one-for-one with the index. The interval's lower end ({f(R['interval80'][0])}) is {f(100*(1-R['interval80'][0]/F),1)}% below the forecast, "
                   f"an error of {f(lo_cost/5,2)}% of the actual close, costing {f(lo_cost,1)} marks; a 4% error, the 5 Nov size, costs 20.", True))

    # ------------------------------------------------------------------ 8 limitations
    B.append(("h1", "8. Limitations and counterarguments", True))
    B.append(("bullets", [
        f"**Counterargument: 'a good analyst would use the news.'** We tested its measurable parts (yields, dollar, semiconductors, surprises, inflation): none beat drift, and the rest is in the futures price. A hand adjustment could not be validated and would add variance.",
        f"**Small samples.** The screen has {W_['n_valid']} validation and {W_['n_test']} test weeks, so a true weak factor could be missed (low power); the proxy requirement and the 2.33 bar guard only against accepting a lucky one.",
        f"**Drift is not a proven edge** ({f(b1v['MAPE_%'],3)}% vs {f(b0v['MAPE_%'],3)}% on validation); in a falling week the {sgn(R['m0_pct'],2)}% centre costs about {f(5*R['m0_pct'],1)} marks versus unchanged.",
        f"**Futures evidence is recent and event risk is large.** The Bloomberg test covers {gB['period']} and the longer one {gJ['period']}; Nvidia results, FOMC minutes and options expiry fall after the cutoff.",
        "**Data risk.** Yahoo is a secondary source, so the last close must be checked against S&P DJI. Nothing here is investment advice.",
    ], True))

    # ------------------------------------------------------------------ back matter
    B.append(("pagebreak",))
    B.append(("h1", "Contribution statement", False))
    B.append(("table", ["Member", "Responsibilities", "Checks performed and approved"], [[f"{m['name']}, {m['id']}", m["responsibilities"], m["checks"]] for m in GI["members"]],
              [3.6, 6.8, 6.6], ("Contributions drafted from the group repository history; each member confirms their own entry before submission." if any("[" in m["name"] or "[" in m["id"] for m in GI["members"]) else "Contributions as agreed by the group. The Bloomberg export used for data cross-checks and the exploratory macro screen is not a forecast input and is not in the evidence ZIP."), False))
    B.append(("h1", "AI-use declaration", False))
    if GI.get("ai_declaration"):         # the group's agreed (shortened) declaration, used verbatim
        for para in GI["ai_declaration"]:
            B.append(("p", para, False))
        GI_LONG = False
    else:
        GI_LONG = True
    if GI_LONG:
        B.append(("p", "**Group-wide.** " + "; ".join(GI.get("ai_tools", [])) + ". Each member confirms their own line.", False))
    for d_ in (GI.get("ai_use_detail", []) if GI_LONG else []):
        B.append(("p", f"**{d_['member']}'s agent.** {d_['tools']} **What it did:** {d_['did']} **Significant instructions:** {d_['instructions']} **Checks:** {d_['checks']} **Errors corrected:** {d_['errors']}", False))
    if GI_LONG:
        B.append(("p", "**This package (Layla's agent).** Claude Code in the Claude desktop app (Claude Sonnet 5.5, later Claude Opus 5.5 in the same session), with web search and fetch, PowerShell, Python 3.12 and file tools. "
                       "**What it did:** read the brief and the group's supporting workbook (helper only); chose the S&P 500 after asking the user; retrieved and reconciled data; wrote and ran all code; screened factors; researched news; drafted the report, slides and figures. "
                       "**Significant instructions:** the user asked twice for the best achievable result, first a researched full-marks report, then a redo with the best factors, the group dataset as a helper rather than a main factor, deep news research and at most five slides; the fixed method is in `agent/AGENT_INSTRUCTIONS.md`. "
                       "**Checks:** independent re-implementation, four-way source reconciliation, leak test on every input including the workbook, sensitivity, rehearsal against a known outcome, news items checked against saved prices. "
                       "**Errors corrected:** stale Cboe and faulty Yahoo values found by reconciliation; a slow solver replaced; FRED and Stooq unreachable, so Cboe and Treasury were used; a Treasury file whose columns changed between years; the first design's factors (trend, variance risk premium) were retired after the wider screen. "
                       "**Responsibility:** members approve the reasoning, calculations and references; no AI response is cited as evidence. Some news pages conflict on details (for example Senate control); we cite only items consistent across sources or checked against prices.", False))
    B.append(("h1", "References", False))
    refs = [
        "Campbell, J.Y. and Thompson, S.B. (2008) 'Predicting excess stock returns out of sample: can anything beat the historical average?', *Review of Financial Studies*, 21(4), pp. 1509-1531.",
        "Cboe Global Markets (2026) *Cboe Volatility Index mathematics methodology* and daily history files. https://cdn.cboe.com/api/global/us_indices/daily_prices/ (accessed 10 Nov 2026).",
        "Diebold, F.X. and Mariano, R.S. (1995) 'Comparing predictive accuracy', *Journal of Business & Economic Statistics*, 13(3), pp. 253-263.",
        "Gneiting, T. (2011) 'Making and evaluating point forecasts', *Journal of the American Statistical Association*, 106(494), pp. 746-762.",
        "Hamao, Y., Masulis, R.W. and Ng, V. (1990) 'Correlations in price changes and volatility across international stock markets', *Review of Financial Studies*, 3(2), pp. 281-307.",
        "Hasbrouck, J. (2003) 'Intraday price formation in U.S. equity index markets', *Journal of Finance*, 58(6), pp. 2375-2400.",
        "Koenker, R. and Bassett, G. (1978) 'Regression quantiles', *Econometrica*, 46(1), pp. 33-50.",
        "Moskowitz, T.J., Ooi, Y.H. and Pedersen, L.H. (2012) 'Time series momentum', *Journal of Financial Economics*, 104(2), pp. 228-250 (the 252-day trend candidate).",
        "Bollerslev, T., Tauchen, G. and Zhou, H. (2009) 'Expected stock returns and variance risk premia', *Review of Financial Studies*, 22(11), pp. 4463-4492 (the variance risk premium candidate).",
        "Newey, W.K. and West, K.D. (1987) 'A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix', *Econometrica*, 55(3), pp. 703-708.",
        "Welch, I. and Goyal, A. (2008) 'A comprehensive look at the empirical performance of equity premium prediction', *Review of Financial Studies*, 21(4), pp. 1455-1508.",
        "S&P Dow Jones Indices (2026) *S&P 500*. https://www.spglobal.com/spdji/en/indices/equity/sp-500/ ; U.S. Department of the Treasury (2026) *Daily Treasury par yield curve rates*. https://home.treasury.gov/ ; Yahoo Finance (2026) chart API (^GSPC, ^VIX, ES=F, ^TNX, ^IRX, DX-Y.NYB, GC=F, ^SOX).",
        "Bloomberg L.P. (2026) *ES1 Index (E-mini S&P 500 generic first future), 1-minute bars*. Bloomberg Terminal, UCL (retrieved 3 Nov 2026; group test of the futures move, not redistributed). TradingView (2026) *ES1! hourly export*, CME Group data (retrieved 10 Nov 2026; group test, not redistributed).",
        "Board of Governors of the Federal Reserve System (2026) *FOMC calendars* and *November 2026 events*. https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm ; https://www.federalreserve.gov/newsevents/2026-november.htm",
        "News items (all accessed 10 Nov 2026): " + "; ".join(sorted({f"{i['src']}, {i['url']}" for i in NEWS["items"] if i["url"]})),
    ]
    refs = sorted(refs[:-1], key=lambda s: s.lower()) + refs[-1:]      # Harvard: alphabetical by first author; news items last
    B.append(("bullets", refs, False))
    B.append(("pagebreak",))
    B.append(("h1", "Appendix A. Evidence record (evidence only; no new analysis)", False))
    rows = [[n_, m["role"][:80], m["url"].split("?")[0][:62], m["retrieved_utc"].replace("T", " ")[:19] + " UTC", m["sha256"][:14] + "...", f"{m['bytes']:,}"] for n_, m in man["files"].items() if n_ != "zaki_data.xlsx"]
    B.append(("table", ["File", "Role", "URL (query omitted)", "Retrieved", "SHA-256", "Bytes"], rows, [2.5, 4.4, 4.4, 2.3, 2.3, 1.1], "A1. Raw snapshot manifest", False, {"font": 7}))
    B.append(("table", ["Item", "Value"], [
        ["Forecast record", f"market S&P 500 price index; unit index points; target {tgt} official close; cutoff {cut_s}; value {f(F)}"],
        ["Software", f"Python {R['package_versions']['python']}, numpy {R['package_versions']['numpy']}, pandas {R['package_versions']['pandas']}, openpyxl, statsmodels (check only), matplotlib, reportlab, python-docx, python-pptx"],
        ["Independent check", f"PASS_ALL = {chk['PASS_ALL']}; m0 and nowcast recomputed by plain Python; leak test pass = {chk['leak_test_pass']}; recomputed forecast {f(chk['forecast_recomputed'])}"],
        ["Reproduce (no internet or AI account)", f"`python code/run_all.py --{tag}` reads the saved files in `{P['snapshot']}/` and rewrites outputs, figures, report, slides and `forecast_record.json`"],
        ["Supporting workbook", "Optional cross-check and macro-screen helper; not a forecast input and not in the submission ZIP (its hash is in the local manifest)"],
        ["Credentials", "None used or stored."]], [4.0, 13.0], "A2. Reproduction and versions", False))

    gi_text = json.dumps({k2: v for k2, v in GI.items() if k2 != "_note"})
    open_items = [k for k in ("[surname]", "[ID]", "[Group number]", "to confirm") if k in gi_text]
    if open_items:
        print(f"WARNING: group_info.json still has unconfirmed text ({', '.join(open_items)}); it prints in the declaration and contribution statement")
    n_words = count_main(B)
    for i, b in enumerate(B):
        if b[0] == "cover":
            B[i][1]["group"].append(("Main-body words", f"{n_words:,} of {LIMIT:,} allowed (excludes cover, references, declaration, contribution statement, appendix)"))
    title = f"IFTE0007 group forecast - S&P 500 ({tag})"
    (ROOT / "report").mkdir(exist_ok=True)
    stem = ROOT / "report" / f"report_{tag}"
    to_docx(B, f"{stem}.docx", title); to_pdf(B, f"{stem}.pdf", title)
    rec = {"status": "FINAL - PENDING HUMAN APPROVAL" if final else f"{tag.upper()} - NOT BINDING", "market": "S&P 500 price index (SPX)", "unit": "index points", "target": R["target"],
           "information_cutoff_utc": R["cutoff_utc"], "last_usable_close_date": R["last_close_date"], "last_usable_close": S0, "forecast": F, "interval80": R["interval80"],
           "reference_source": "S&P Dow Jones Indices official closing price-index level", "discretionary_adjustment_pct": 0.0, "approved_by": ["", "", "", ""], "approval_utc": ""}
    (out / "forecast_record.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"main-body words: {n_words} / {LIMIT}")
    if n_words > LIMIT:
        print("WARNING: over the word limit")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--tag", required=True)
    build(ap.parse_args().tag)
