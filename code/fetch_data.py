"""fetch_data.py - download dated raw snapshots (Yahoo, Cboe, US Treasury) and freeze Zaki's workbook; write a manifest
(URL, retrieval time, SHA-256). Run once, at/after the information cutoff, then treat the folder as read-only.
Reproduction by a marker does NOT need this script: run_model.py works from the saved files alone.

    python code/fetch_data.py --out data/raw_final --zaki "Zaki's data.xlsx"
    python code/fetch_data.py --out data/agent_demo --quick      # only what the demo agent needs (3 files, a few seconds)
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import pathlib
import shutil
import time

import requests

UA = {"User-Agent": "Mozilla/5.0"}
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?{q}"
FULL = "period1=631152000&period2={now}&interval=1d&events=history"
TSY = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all"
       "?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
SOURCES = {
    "gspc_daily.json": (YAHOO.format(sym="%5EGSPC", q=FULL), "S&P 500 price index daily close (Yahoo Finance chart API, ^GSPC)"),
    "vix_daily.json": (YAHOO.format(sym="%5EVIX", q=FULL), "Cboe VIX daily close (Yahoo, ^VIX)"),
    "es_5m.json": (YAHOO.format(sym="ES%3DF", q="range=60d&interval=5m"), "E-mini S&P 500 front-month future, 5-minute bars (Yahoo, ES=F)"),
    "tnx_daily.json": (YAHOO.format(sym="%5ETNX", q=FULL), "10-year Treasury yield, % (Yahoo, ^TNX) - long-history proxy for robustness"),
    "irx_daily.json": (YAHOO.format(sym="%5EIRX", q=FULL), "13-week T-bill yield, % (Yahoo, ^IRX) - long-history proxy for robustness"),
    "dxy_daily.json": (YAHOO.format(sym="DX-Y.NYB", q=FULL), "US Dollar Index (Yahoo, DX-Y.NYB) - proxy / gap fill for the supporting USD series"),
    "gold_daily.json": (YAHOO.format(sym="GC%3DF", q=FULL), "Gold front-month future (Yahoo, GC=F) - proxy / gap fill for the supporting gold series"),
    "sox_daily.json": (YAHOO.format(sym="%5ESOX", q=FULL), "PHLX Semiconductor index (Yahoo, ^SOX) - proxy / gap fill for the supporting semiconductor series"),
    "n225_daily.json": (YAHOO.format(sym="%5EN225", q=FULL), "Nikkei 225 daily close (Yahoo, ^N225) - Asian overnight information"),
    "hsi_daily.json": (YAHOO.format(sym="%5EHSI", q=FULL), "Hang Seng daily close (Yahoo, ^HSI) - Asian overnight information"),
    "kospi_daily.json": (YAHOO.format(sym="%5EKS11", q=FULL), "KOSPI daily close (Yahoo, ^KS11) - Asian overnight information"),
    "asx_daily.json": (YAHOO.format(sym="%5EAXJO", q=FULL), "ASX 200 daily close (Yahoo, ^AXJO) - Asian overnight information"),
    "check_cboe_spx.csv": ("https://cdn.cboe.com/api/global/us_indices/daily_prices/SPX_History.csv", "INDEPENDENT CHECK: Cboe published SPX daily history"),
    "check_cboe_vix.csv": ("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv", "INDEPENDENT CHECK: Cboe published VIX daily history"),
}


QUICK = ("gspc_daily.json", "es_5m.json", "check_cboe_spx.csv")      # S&P 500 closes, futures bars, Cboe reconciliation


def _rec(manifest, out, name, url, role, content):
    (out / name).write_bytes(content)
    manifest["files"][name] = {"url": url, "role": role, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                               "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    print(f"saved {name}: {len(content):,} bytes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw_live")
    ap.add_argument("--zaki", default=None, help="path to Zaki's data workbook (frozen copy is stored next to the raw files)")
    ap.add_argument("--only", nargs="*", default=None, help="fetch only these file names and merge them into the existing manifest")
    ap.add_argument("--quick", action="store_true", help="fetch only gspc_daily.json, es_5m.json and check_cboe_spx.csv into a fresh manifest (used by the demo agent)")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.quick:
        a.only = list(QUICK)
        if not (out / "manifest.json").exists():
            (out / "manifest.json").write_text(json.dumps({"retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "files": {}}), encoding="utf-8")
    now = int(time.time())
    manifest = {"retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "files": {}}
    if a.only:
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        manifest["retrieved_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    for name, (url, role) in SOURCES.items():
        if a.only and name not in a.only:
            continue
        url = url.replace("{now}", str(now))
        r = requests.get(url, headers=UA, timeout=90); r.raise_for_status()
        _rec(manifest, out, name, url, role, r.content)
    if a.only:
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return
    # US Treasury par yield curve (official), 2020 to now, used for the 2Y/10Y gap fill and as a check on the workbook
    import io
    import pandas as pd
    parts = []
    for y in range(2020, dt.date.today().year + 1):     # the column set changes between years, so parse each year separately
        r = requests.get(TSY.format(y=y), headers=UA, timeout=90); r.raise_for_status()
        parts.append(pd.read_csv(io.StringIO(r.text))[["Date", "2 Yr", "10 Yr"]])
    tsy = pd.concat(parts).drop_duplicates("Date")
    _rec(manifest, out, "treasury_yields.csv", TSY.format(y="2020-" + str(dt.date.today().year)), "US Treasury daily par yield curve (official); 2 Yr and 10 Yr columns", tsy.to_csv(index=False).encode("utf-8"))
    if a.zaki:
        src = glob.glob(a.zaki)[0]
        shutil.copyfile(src, out / "zaki_data.xlsx")
        c = (out / "zaki_data.xlsx").read_bytes()
        _rec(manifest, out, "zaki_data.xlsx", "local file: Bloomberg export ('Last Price' sheets)", "Supporting workbook (helper only, not a forecast input): S&P 500, VIX, 2Y/10Y yields, CPI, PPI, USD index, Citi surprise index, semiconductors, gold", c)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
