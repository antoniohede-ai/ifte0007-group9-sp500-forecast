"""common.py - shared helpers: raw-snapshot parsing and the information-cutoff filter.

Every function that touches data takes an explicit `cutoff` (tz-aware UTC Timestamp). Nothing observed
after the cutoff can enter the model: daily bars are admitted only once their *official close time* has
passed, and intraday bars only once the bar has *ended*.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
NY = "America/New_York"

# NYSE full-day closures that fall inside the horizons used here (Q4 2026). Source: NYSE holiday calendar.
NYSE_HOLIDAYS = pd.to_datetime(["2026-11-26", "2026-12-25"])


def utc(ts: str) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _yahoo_frame(path: pathlib.Path) -> pd.DataFrame:
    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    res = raw["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True)
    q = res["indicators"]["quote"][0]
    return pd.DataFrame({"ts": ts, "close": q["close"]}).dropna()


def load_daily(path: pathlib.Path, cutoff: pd.Timestamp, close_hhmm: str) -> pd.Series:
    """Daily close series indexed by New York session date; a bar is kept only if its close time <= cutoff."""
    df = _yahoo_frame(path)
    local = df["ts"].dt.tz_convert(NY)
    df["date"] = local.dt.tz_localize(None).dt.normalize()
    hh, mm = map(int, close_hhmm.split(":"))
    close_local = df["date"] + pd.Timedelta(hours=hh, minutes=mm)
    close_utc = close_local.dt.tz_localize(NY, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    keep = close_utc <= cutoff
    s = df.loc[keep].drop_duplicates("date", keep="last").set_index("date")["close"].astype(float)
    return s.sort_index()


def load_es(path: pathlib.Path, cutoff: pd.Timestamp) -> pd.Series:
    """ES futures 5-minute close, indexed by the bar END time (UTC); bars that end after the cutoff are dropped."""
    df = _yahoo_frame(path)
    df["end"] = df["ts"] + pd.Timedelta(minutes=5)
    df = df[df["end"] <= cutoff]
    return df.set_index("end")["close"].astype(float).sort_index()


ZAKI_SHEETS = {"spx": "S&P 500", "vix": "VIX", "y2": "US 2Y YIELDS", "y10": "US 10Y YIELDS", "cpi": "US CPI", "ppi": "US PPI",
               "usd": "USD Index", "esi": "US Economic Surprise Index", "semi": "BBG US Listed Semiconductors", "gold": "Gold"}
# time at which each workbook series is treated as published (conservative; daily series stamped at the New York session date)
ZAKI_CLOSE = {"spx": "16:00", "vix": "16:15", "y2": "17:00", "y10": "17:00", "usd": "17:00", "esi": "17:00", "semi": "16:00", "gold": "17:00"}
MONTHLY_LAG_DAYS = 16      # CPI/PPI for month m are treated as known 16 days after month-end (BLS releases fall about 10-15 days after)


def load_zaki(path, cutoff: pd.Timestamp) -> dict:
    """Return {key: Series} from Zaki's workbook, keeping only observations published at or before `cutoff`."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out = {}
    for key, sheet in ZAKI_SHEETS.items():
        rows = [(r[0], r[1]) for r in wb[sheet].iter_rows(min_row=2, values_only=True) if r[0] is not None and r[1] is not None]
        s = pd.Series({pd.Timestamp(d).normalize(): float(v) for d, v in rows}).sort_index()
        if key in ("cpi", "ppi"):
            avail = (s.index + pd.offsets.MonthEnd(0) + pd.Timedelta(days=MONTHLY_LAG_DAYS)).tz_localize(NY).tz_convert("UTC")
        else:
            hh, mm = map(int, ZAKI_CLOSE[key].split(":"))
            avail = (s.index + pd.Timedelta(hours=hh, minutes=mm)).tz_localize(NY, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
        out[key] = s[(avail <= cutoff)]
    wb.close()
    return out


def load_treasury(path, cutoff: pd.Timestamp) -> pd.DataFrame:
    """US Treasury par yields (columns '2 Yr', '10 Yr'); a row is admitted from 17:00 ET of its date."""
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.drop_duplicates("Date").set_index("Date").sort_index()
    avail = (df.index + pd.Timedelta(hours=17)).tz_localize(NY, ambiguous="NaT", nonexistent="NaT").tz_convert("UTC")
    return df.loc[avail <= cutoff, ["2 Yr", "10 Yr"]].astype(float)


def sessions_between(last_obs: pd.Timestamp, target_date: pd.Timestamp) -> int:
    """Number of NYSE sessions after `last_obs` up to and including `target_date`."""
    days = pd.bdate_range(last_obs + pd.Timedelta(days=1), target_date)
    days = days[~days.isin(NYSE_HOLIDAYS)]
    return len(days)


def load_manifest(snapshot: pathlib.Path) -> dict:
    return json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))


def news_known(items, cutoff: pd.Timestamp) -> list:
    """News items published by the cutoff. An item dated before the cutoff day counts; one dated on the cutoff day only
    with a "time_utc" at or before the cutoff (a same-day item without a time is left out). Scheduled events are excluded."""
    day = str(cutoff.date()); out = []
    for i in items:
        if "Scheduled" in i["event"] or "Target day" in i["event"]:
            continue
        if i["date"] < day or (i["date"] == day and i.get("time_utc") and pd.Timestamp(i["time_utc"]) <= cutoff):
            out.append(i)
    return out
