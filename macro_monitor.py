#!/usr/bin/env python3
"""
macro_monitor.py — Macro Market Sentiment Monitor

Fetches 19 key indicators from FRED (inflation, employment, financial
conditions, leading indicators) and automatically answers 6 core questions
about macro risk. Generates a Markdown report + terminal color summary
+ macOS notification.

Usage:
    python macro_monitor.py                  # Run once, save report
    python macro_monitor.py --check-only     # Terminal only, no save
    python macro_monitor.py --test-alert     # Test macOS notification
    python macro_monitor.py --install        # Install launchd (15th monthly)
    python macro_monitor.py --uninstall      # Uninstall launchd
"""

import argparse
import glob
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from io import StringIO

import numpy as np
import pandas as pd
import requests

try:
    from fredapi import Fred

    HAS_FREDAPI = True
except ImportError:
    HAS_FREDAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "macro_monitor")

PLIST_LABEL = "com.ai-stock.macro-monitor"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")

# 19 FRED series
FRED_SERIES = {
    "core_cpi":        {"id": "CPILFESL",          "freq": "monthly",    "desc": "Core CPI (ex food & energy)"},
    "cpi_services":    {"id": "CUSR0000SAS",        "freq": "monthly",    "desc": "CPI Services"},
    "cpi_shelter":     {"id": "CUSR0000SAH1",       "freq": "monthly",    "desc": "CPI Shelter"},
    "breakeven_5y":    {"id": "T5YIE",              "freq": "daily",      "desc": "5-Year Breakeven Inflation"},
    "forward_5y5y":    {"id": "T5YIFR",             "freq": "daily",      "desc": "5Y5Y Forward Inflation Expectation"},
    "avg_hourly_earn": {"id": "CES0500000003",      "freq": "monthly",    "desc": "Avg Hourly Earnings (Private)"},
    "eci_wages":       {"id": "ECIWAG",             "freq": "quarterly",  "desc": "Employment Cost Index - Wages"},
    "unrate":          {"id": "UNRATE",             "freq": "monthly",    "desc": "Unemployment Rate (U-3)"},
    "u6rate":          {"id": "U6RATE",             "freq": "monthly",    "desc": "Unemployment Rate (U-6)"},
    "civpart":         {"id": "CIVPART",            "freq": "monthly",    "desc": "Labor Force Participation Rate"},
    "jobless_claims":  {"id": "ICSA",               "freq": "weekly",     "desc": "Initial Jobless Claims"},
    "nfci":            {"id": "NFCI",               "freq": "weekly",     "desc": "Chicago Fed National Financial Conditions Index"},
    "fed_funds":       {"id": "DFF",                "freq": "daily",      "desc": "Effective Federal Funds Rate"},
    "yield_spread":    {"id": "T10Y2Y",             "freq": "daily",      "desc": "10Y-2Y Treasury Spread"},
    "hy_spread":       {"id": "BAMLH0A0HYM2",      "freq": "daily",      "desc": "ICE BofA US High Yield Spread"},
    "consumer_sent":   {"id": "UMCSENT",            "freq": "monthly",    "desc": "U. Michigan Consumer Sentiment"},
    "recession_prob":  {"id": "RECPROUSM156N",      "freq": "monthly",    "desc": "Smoothed Recession Probability"},
    "vix":             {"id": "VIXCLS",              "freq": "daily",      "desc": "CBOE Volatility Index (VIX)"},
    "mfg_ip":          {"id": "IPMAN",               "freq": "monthly",    "desc": "Manufacturing Industrial Production"},
}

# Fed meeting dates (2025-2026) with SEP (Summary of Economic Projections) flags
FED_MEETINGS = [
    {"date": "2025-01-29", "sep": False},
    {"date": "2025-03-19", "sep": True},
    {"date": "2025-05-07", "sep": False},
    {"date": "2025-06-18", "sep": True},
    {"date": "2025-07-30", "sep": False},
    {"date": "2025-09-17", "sep": True},
    {"date": "2025-10-29", "sep": False},
    {"date": "2025-12-17", "sep": True},
    {"date": "2026-01-28", "sep": False},
    {"date": "2026-03-18", "sep": True},
    {"date": "2026-04-29", "sep": False},
    {"date": "2026-06-17", "sep": True},
    {"date": "2026-07-29", "sep": False},
    {"date": "2026-09-16", "sep": True},
    {"date": "2026-10-28", "sep": False},
    {"date": "2026-12-16", "sep": True},
]

# Six core questions
QUESTIONS = [
    {"id": 1, "short": "Services Sticky", "long": "Is core services inflation still accelerating?"},
    {"id": 2, "short": "Expect. Anchor",  "long": "Are inflation expectations unanchored?"},
    {"id": 3, "short": "Wage-Price",      "long": "Is wage growth significantly outpacing inflation?"},
    {"id": 4, "short": "Unemployment",     "long": "Is the labor market deteriorating rapidly?"},
    {"id": 5, "short": "Fin. Conditions",  "long": "Are financial conditions abnormally tight?"},
    {"id": 6, "short": "Econ. Momentum",   "long": "Are leading indicators showing weakening momentum?"},
]

# ---------------------------------------------------------------------------
# Step 2: Data Fetching Layer
# ---------------------------------------------------------------------------

def _fetch_fred_csv(series_id: str, start: str, end: str) -> pd.Series | None:
    """Fetch a FRED series via the public CSV endpoint (no API key needed)."""
    url = f"{FRED_CSV_URL}?id={series_id}&cosd={start}&coed={end}"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  [WARN] CSV fetch {series_id}: HTTP {r.status_code}")
            return None
        df = pd.read_csv(StringIO(r.text))
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna()
        if df.empty:
            return None
        return df.set_index("date")["value"]
    except Exception as e:
        print(f"  [WARN] CSV fetch {series_id}: {e}")
        return None


def _fetch_fred_api(series_id: str, start: str, end: str) -> pd.Series | None:
    """Fetch a FRED series via fredapi (requires FRED_API_KEY)."""
    if not HAS_FREDAPI:
        return None
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return None
    try:
        fred = Fred(api_key=api_key)
        s = fred.get_series(series_id, observation_start=start, observation_end=end)
        s = s.dropna()
        if s.empty:
            return None
        s.index.name = "date"
        s.name = "value"
        return s
    except Exception as e:
        print(f"  [WARN] API fetch {series_id}: {e}")
        return None


def fetch_fred_series(series_id: str, start: str, end: str) -> pd.Series | None:
    """Fetch a FRED series: try API first, fall back to CSV."""
    s = _fetch_fred_api(series_id, start, end)
    if s is not None and not s.empty:
        return s
    return _fetch_fred_csv(series_id, start, end)


def fetch_all_series(lookback_years: int = 3) -> dict[str, pd.Series]:
    """Fetch all 19 FRED series. Returns dict keyed by our short name."""
    today = date.today()
    start = (today - timedelta(days=lookback_years * 365)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    raw = {}
    for key, cfg in FRED_SERIES.items():
        print(f"  Fetching {key} ({cfg['id']})...", end=" ")
        s = fetch_fred_series(cfg["id"], start, end)
        if s is not None and not s.empty:
            raw[key] = s
            print(f"OK ({len(s)} obs)")
        else:
            print("FAILED")
        time.sleep(0.5)  # rate limit
    return raw


def _pct_change_mom(s: pd.Series) -> pd.Series:
    """Month-over-month percent change for index-level series."""
    return s.pct_change() * 100


def _pct_change_yoy(s: pd.Series, periods: int = 12) -> pd.Series:
    """Year-over-year percent change."""
    return s.pct_change(periods=periods) * 100


def _annualized_3m(s: pd.Series) -> float | None:
    """Annualized 3-month rate of change for a monthly index."""
    if len(s) < 4:
        return None
    recent = s.iloc[-4:]  # 4 values → 3 MoM changes
    cumulative = recent.iloc[-1] / recent.iloc[0] - 1
    return ((1 + cumulative) ** 4 - 1) * 100  # annualize


def compute_derived_metrics(raw: dict) -> dict:
    """Compute derived metrics from raw series."""
    d = {}

    # CPI MoM and YoY
    for key in ["core_cpi", "cpi_services", "cpi_shelter"]:
        if key in raw:
            d[f"{key}_mom"] = _pct_change_mom(raw[key])
            d[f"{key}_yoy"] = _pct_change_yoy(raw[key])
            d[f"{key}_ann3m"] = _annualized_3m(raw[key])

    # Wage YoY
    if "avg_hourly_earn" in raw:
        d["avg_hourly_earn_yoy"] = _pct_change_yoy(raw["avg_hourly_earn"])

    # ECI quarterly change (annualized)
    if "eci_wages" in raw:
        d["eci_wages_yoy"] = _pct_change_yoy(raw["eci_wages"], periods=4)

    # ICSA moving averages
    if "jobless_claims" in raw:
        ic = raw["jobless_claims"]
        d["icsa_4wma"] = ic.rolling(4).mean()
        d["icsa_13wma"] = ic.rolling(13).mean()
        # Acceleration: 4wma vs 13wma
        if len(ic) >= 13:
            d["icsa_accel"] = d["icsa_4wma"].iloc[-1] - d["icsa_13wma"].iloc[-1]

    # Unemployment change speed (3-month delta)
    if "unrate" in raw and len(raw["unrate"]) >= 4:
        d["unrate_3m_delta"] = raw["unrate"].iloc[-1] - raw["unrate"].iloc[-4]

    # HY spread change (3-month)
    if "hy_spread" in raw and len(raw["hy_spread"]) >= 63:
        d["hy_spread_3m_delta"] = raw["hy_spread"].iloc[-1] - raw["hy_spread"].iloc[-63]

    # Consumer sentiment 3-month delta
    if "consumer_sent" in raw and len(raw["consumer_sent"]) >= 4:
        d["consumer_sent_3m_delta"] = raw["consumer_sent"].iloc[-1] - raw["consumer_sent"].iloc[-4]

    # Manufacturing IP YoY and 3-month delta
    if "mfg_ip" in raw:
        d["mfg_ip_yoy"] = _pct_change_yoy(raw["mfg_ip"])
        if len(raw["mfg_ip"]) >= 4:
            d["mfg_ip_3m_delta"] = _pct_change_yoy(raw["mfg_ip"], periods=3)

    # VIX 20-day moving average (smooth daily volatility)
    if "vix" in raw and len(raw["vix"]) >= 20:
        d["vix_20d_avg"] = raw["vix"].rolling(20).mean()

    return d


# ---------------------------------------------------------------------------
# Step 3: Five-Question Assessment Logic
# ---------------------------------------------------------------------------

def assess_q1_core_services(raw: dict, derived: dict) -> dict:
    """Q1: Is core services inflation still accelerating?
    Checks: CPI Services 3-month annualized trend, shelter decomposition.
    """
    result = {"id": 1, "arrow": "→", "label": "Flat", "color": "yellow",
              "key_data": "N/A", "detail": "Insufficient data"}

    svc_ann3m = derived.get("cpi_services_ann3m")
    shelter_ann3m = derived.get("cpi_shelter_ann3m")
    svc_yoy = derived.get("cpi_services_yoy")

    if svc_ann3m is None:
        return result

    # Latest YoY for context
    svc_yoy_latest = svc_yoy.dropna().iloc[-1] if svc_yoy is not None and not svc_yoy.dropna().empty else None

    parts = []
    if svc_yoy_latest is not None:
        parts.append(f"Svc CPI YoY {svc_yoy_latest:.1f}%")
    parts.append(f"3M ann. {svc_ann3m:.1f}%")
    if shelter_ann3m is not None:
        parts.append(f"Shelter 3M ann. {shelter_ann3m:.1f}%")

    result["key_data"] = ", ".join(parts)

    # Logic: 3M annualized > 4.5% = worsening, < 3.0% = improving
    if svc_ann3m > 4.5:
        result.update(arrow="↑", label="Worsening", color="red",
                      detail=f"Services inflation 3M annualized {svc_ann3m:.1f}% still above comfort zone (>4.5%)")
    elif svc_ann3m < 3.0:
        result.update(arrow="↓", label="Improving", color="green",
                      detail=f"Services inflation 3M annualized {svc_ann3m:.1f}% has fallen below 3%")
    else:
        shelter_note = ""
        if shelter_ann3m is not None and shelter_ann3m < 3.0:
            shelter_note = "; shelter component decelerating notably"
        result.update(arrow="→", label="Stable", color="yellow",
                      detail=f"Services inflation 3M annualized {svc_ann3m:.1f}% in transition zone{shelter_note}")

    return result


def assess_q2_inflation_expectations(raw: dict, derived: dict) -> dict:
    """Q2: Are inflation expectations unanchored?
    Checks: 5Y breakeven level and trend, 5Y5Y forward.
    """
    result = {"id": 2, "arrow": "→", "label": "Flat", "color": "yellow",
              "key_data": "N/A", "detail": "Insufficient data"}

    be5 = raw.get("breakeven_5y")
    fwd = raw.get("forward_5y5y")

    if be5 is None or be5.empty:
        return result

    be5_latest = be5.iloc[-1]
    # 3-month ago
    be5_3m = be5.iloc[-63] if len(be5) >= 63 else be5.iloc[0]
    be5_delta = be5_latest - be5_3m

    parts = [f"5Y BEI {be5_latest:.2f}%"]
    if fwd is not None and not fwd.empty:
        fwd_latest = fwd.iloc[-1]
        parts.append(f"5Y5Y Fwd {fwd_latest:.2f}%")

    parts.append(f"3M chg {be5_delta:+.2f}pp")
    result["key_data"] = ", ".join(parts)

    # Anchored: 5Y BEI 2.0-2.5% is normal. >2.8% concerning. <1.5% deflation risk.
    fwd_latest = fwd.iloc[-1] if fwd is not None and not fwd.empty else None

    if be5_latest > 2.8 or (fwd_latest is not None and fwd_latest > 2.8):
        result.update(arrow="↑", label="Worsening", color="red",
                      detail=f"Inflation expectations elevated (5Y BEI {be5_latest:.2f}%), possible unanchoring")
    elif be5_latest < 1.5:
        result.update(arrow="↓", label="Worsening", color="red",
                      detail=f"Inflation expectations too low (5Y BEI {be5_latest:.2f}%), deflation concerns")
    elif 2.0 <= be5_latest <= 2.5 and abs(be5_delta) < 0.3:
        result.update(arrow="→", label="Improving", color="green",
                      detail=f"Inflation expectations well-anchored (5Y BEI {be5_latest:.2f}%, low volatility)")
    else:
        result.update(arrow="→", label="Stable", color="yellow",
                      detail=f"Inflation expectations slightly outside normal range (5Y BEI {be5_latest:.2f}%)")

    return result


def assess_q3_wage_stickiness(raw: dict, derived: dict) -> dict:
    """Q3: Is wage growth significantly outpacing inflation?
    Checks: AHE YoY vs Core CPI YoY, ECI trend.
    """
    result = {"id": 3, "arrow": "→", "label": "Flat", "color": "yellow",
              "key_data": "N/A", "detail": "Insufficient data"}

    ahe_yoy = derived.get("avg_hourly_earn_yoy")
    cpi_yoy = derived.get("core_cpi_yoy")
    eci_yoy = derived.get("eci_wages_yoy")

    if ahe_yoy is None or cpi_yoy is None:
        return result

    ahe_latest = ahe_yoy.dropna().iloc[-1] if not ahe_yoy.dropna().empty else None
    cpi_latest = cpi_yoy.dropna().iloc[-1] if not cpi_yoy.dropna().empty else None

    if ahe_latest is None or cpi_latest is None:
        return result

    wage_cpi_gap = ahe_latest - cpi_latest

    parts = [f"Wages YoY {ahe_latest:.1f}%", f"Core CPI YoY {cpi_latest:.1f}%",
             f"Gap {wage_cpi_gap:+.1f}pp"]
    if eci_yoy is not None and not eci_yoy.dropna().empty:
        eci_latest = eci_yoy.dropna().iloc[-1]
        parts.append(f"ECI YoY {eci_latest:.1f}%")

    result["key_data"] = ", ".join(parts)

    # Wage-price spiral: wage growth significantly > CPI → inflationary pressure
    # Gap > 1.5pp means wages clearly outpacing → could fuel inflation
    if wage_cpi_gap > 1.5:
        result.update(arrow="↑", label="Worsening", color="red",
                      detail=f"Wage growth ({ahe_latest:.1f}%) significantly outpacing inflation "
                             f"({cpi_latest:.1f}%), wage-price spiral risk")
    elif wage_cpi_gap < -0.5:
        # Wages lagging inflation → real wage decline, demand risk
        result.update(arrow="↓", label="Improving", color="green",
                      detail=f"Wage growth ({ahe_latest:.1f}%) below inflation ({cpi_latest:.1f}%), "
                             f"inflation pressure easing naturally")
    else:
        result.update(arrow="→", label="Stable", color="yellow",
                      detail=f"Wages and inflation roughly balanced (gap {wage_cpi_gap:+.1f}pp), no spiral signs")

    return result


def assess_q4_unemployment_trend(raw: dict, derived: dict) -> dict:
    """Q4: Is the labor market deteriorating rapidly?
    Checks: UNRATE 3-month delta, ICSA acceleration (4wma vs 13wma), U-6 level.
    """
    result = {"id": 4, "arrow": "→", "label": "Flat", "color": "yellow",
              "key_data": "N/A", "detail": "Insufficient data"}

    unrate = raw.get("unrate")
    u6 = raw.get("u6rate")
    icsa_accel = derived.get("icsa_accel")
    unrate_3m = derived.get("unrate_3m_delta")

    if unrate is None or unrate.empty:
        return result

    ur_latest = unrate.iloc[-1]
    parts = [f"U-3 {ur_latest:.1f}%"]
    if u6 is not None and not u6.empty:
        parts.append(f"U-6 {u6.iloc[-1]:.1f}%")
    if unrate_3m is not None:
        parts.append(f"3M chg {unrate_3m:+.1f}pp")
    if icsa_accel is not None:
        parts.append(f"ICSA accel {icsa_accel:+.0f}")

    result["key_data"] = ", ".join(parts)

    # Sahm rule inspired: 3-month UR rise > 0.5pp = recession signal
    # ICSA acceleration: 4wma > 13wma by >30K = deteriorating
    is_ur_rising = unrate_3m is not None and unrate_3m > 0.5
    is_icsa_accel = icsa_accel is not None and icsa_accel > 30000

    if is_ur_rising and is_icsa_accel:
        result.update(arrow="↑", label="Worsening", color="red",
                      detail=f"Unemployment rose {unrate_3m:+.1f}pp in 3M with claims accelerating, "
                             f"labor market deteriorating rapidly")
    elif is_ur_rising or is_icsa_accel:
        result.update(arrow="↑", label="Worsening", color="yellow",
                      detail=f"Labor market showing weakness "
                             f"({'UR rising' if is_ur_rising else 'claims rising'})")
    elif unrate_3m is not None and unrate_3m < -0.2:
        result.update(arrow="↓", label="Improving", color="green",
                      detail=f"Unemployment declining (3M {unrate_3m:+.1f}pp), labor market strong")
    else:
        result.update(arrow="→", label="Stable", color="yellow",
                      detail=f"Labor market stable (U-3 {ur_latest:.1f}%)")

    return result


def assess_q5_financial_conditions(raw: dict, derived: dict) -> dict:
    """Q5: Are financial conditions abnormally tight?
    Checks: NFCI level, HY spread level + trend, yield curve, VIX.
    """
    result = {"id": 5, "arrow": "→", "label": "Flat", "color": "yellow",
              "key_data": "N/A", "detail": "Insufficient data"}

    nfci = raw.get("nfci")
    hy = raw.get("hy_spread")
    yc = raw.get("yield_spread")
    vix = raw.get("vix")
    hy_delta = derived.get("hy_spread_3m_delta")
    vix_20d = derived.get("vix_20d_avg")

    parts = []
    nfci_latest = None
    hy_latest = None
    yc_latest = None
    vix_latest = None
    vix_20d_latest = None

    if nfci is not None and not nfci.empty:
        nfci_latest = nfci.iloc[-1]
        parts.append(f"NFCI {nfci_latest:+.2f}")
    if hy is not None and not hy.empty:
        hy_latest = hy.iloc[-1]
        parts.append(f"HY Spread {hy_latest * 100:.0f}bp")
    if yc is not None and not yc.empty:
        yc_latest = yc.iloc[-1]
        parts.append(f"10Y-2Y {yc_latest:+.2f}%")
    if vix is not None and not vix.empty:
        vix_latest = vix.iloc[-1]
        parts.append(f"VIX {vix_latest:.1f}")
        if vix_20d is not None and not vix_20d.dropna().empty:
            vix_20d_latest = vix_20d.dropna().iloc[-1]
            parts.append(f"VIX 20d avg {vix_20d_latest:.1f}")
    if hy_delta is not None:
        parts.append(f"HY 3M chg {hy_delta * 100:+.0f}bp")

    if not parts:
        return result

    result["key_data"] = ", ".join(parts)

    # NFCI > 0 = tighter than average. > 0.5 = significantly tight.
    # HY spread > 5.0% (500bp) = stress. > 8.0% (800bp) = crisis. (FRED data in %)
    # Inverted yield curve (negative 10Y-2Y) = recession warning.
    # VIX > 30 = elevated fear. VIX 20d avg > 25 = sustained high volatility.
    stress_signals = 0

    if nfci_latest is not None and nfci_latest > 0.5:
        stress_signals += 1
    if hy_latest is not None and hy_latest > 5.0:
        stress_signals += 1
    if yc_latest is not None and yc_latest < -0.5:
        stress_signals += 1
    if vix_latest is not None and (vix_latest > 30 or (vix_20d_latest is not None and vix_20d_latest > 25)):
        stress_signals += 1

    if stress_signals >= 2:
        result.update(arrow="↑", label="Worsening", color="red",
                      detail=f"Multiple financial conditions tightening ({stress_signals}/4 triggered), significant market stress")
    elif stress_signals == 1:
        result.update(arrow="↑", label="Worsening", color="yellow",
                      detail=f"Partial financial tightening (1/4 triggered), monitor closely")
    else:
        # Check if conditions are unusually loose
        is_loose = (nfci_latest is not None and nfci_latest < -0.5)
        if is_loose:
            result.update(arrow="↓", label="Improving", color="green",
                          detail=f"Financial conditions loose (NFCI {nfci_latest:+.2f}), ample liquidity")
        else:
            result.update(arrow="→", label="Stable", color="yellow",
                          detail="Financial conditions within normal range")

    return result


def assess_q6_economic_momentum(raw: dict, derived: dict) -> dict:
    """Q6: Are leading indicators showing weakening momentum?
    Checks: Consumer Sentiment, Manufacturing IP, Recession Probability.
    """
    result = {"id": 6, "arrow": "→", "label": "Flat", "color": "yellow",
              "key_data": "N/A", "detail": "Insufficient data"}

    cs = raw.get("consumer_sent")
    rp = raw.get("recession_prob")
    mfg_yoy = derived.get("mfg_ip_yoy")
    cs_3m = derived.get("consumer_sent_3m_delta")

    parts = []
    deteriorating = 0
    details = []

    # Consumer Sentiment
    if cs is not None and not cs.empty:
        cs_latest = cs.iloc[-1]
        parts.append(f"Sentiment {cs_latest:.1f}")
        if cs_latest < 60 and cs_3m is not None and cs_3m < -10:
            deteriorating += 1
            details.append(f"Consumer sentiment depressed ({cs_latest:.0f}) and down {cs_3m:.0f} over 3M")
        elif cs_3m is not None:
            parts[-1] += f" (3M {cs_3m:+.1f})"

    # Manufacturing IP YoY
    if mfg_yoy is not None and not mfg_yoy.dropna().empty:
        mfg_latest = mfg_yoy.dropna().iloc[-1]
        parts.append(f"Mfg IP YoY {mfg_latest:.1f}%")
        if mfg_latest < 0:
            deteriorating += 1
            details.append(f"Manufacturing output contracting (YoY {mfg_latest:.1f}%)")

    # Recession Probability
    if rp is not None and not rp.empty:
        rp_latest = rp.iloc[-1]
        parts.append(f"Recess. Prob {rp_latest:.0f}%")
        if rp_latest > 30:
            deteriorating += 1
            details.append(f"Recession probability elevated ({rp_latest:.0f}%)")

    if not parts:
        return result

    result["key_data"] = ", ".join(parts)

    if deteriorating >= 2:
        result.update(arrow="↑", label="Worsening", color="red",
                      detail=f"Multiple leading indicators deteriorating ({deteriorating}/3): " + "; ".join(details))
    elif deteriorating == 1:
        result.update(arrow="↑", label="Worsening", color="yellow",
                      detail=f"Some leading indicators weakening: {details[0]}")
    else:
        result.update(arrow="→", label="Improving", color="green",
                      detail="Leading indicators normal, economic momentum stable")

    return result


def compute_overall_signal(q_results: list[dict]) -> dict:
    """Compute overall signal from 6 question results.
    Q1-Q3 inflation + Q6 momentum = macro group.
    Q4-Q5 = market group.
    red_count >= 3 out of 6 = high risk.
    """
    macro_qs = [r for r in q_results if r["id"] <= 3 or r["id"] == 6]
    market_qs = [r for r in q_results if r["id"] in (4, 5)]

    macro_red = sum(1 for r in macro_qs if r["color"] == "red")
    market_red = sum(1 for r in market_qs if r["color"] == "red")
    all_red = sum(1 for r in q_results if r["color"] == "red")
    total = len(q_results)

    if macro_red == 0 and market_red == 0:
        signal = "green"
        emoji = "\U0001f7e2"  # 🟢
        label = "Low Risk"
        narrative = "Inflation, employment, financial conditions, and leading indicators show no deterioration. Macro environment is favorable."
    elif all_red >= 3:
        signal = "red"
        emoji = "\U0001f534"  # 🔴
        label = "High Risk"
        narrative = "Multiple dimensions deteriorating simultaneously. Consider increasing defensive allocation."
    elif macro_red >= 2 or (macro_red >= 1 and market_red >= 1):
        signal = "red"
        emoji = "\U0001f534"  # 🔴
        label = "High Risk"
        narrative = "Inflation/momentum pressure compounded by market stress. Elevated macro uncertainty."
    else:
        signal = "yellow"
        emoji = "\U0001f7e1"  # 🟡
        label = "Medium Risk"
        narrative = "Some warning signals detected. Monitor closely for directional changes."

    return {
        "signal": signal,
        "emoji": emoji,
        "label": label,
        "narrative": narrative,
        "red_count": all_red,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Step 4: Fed Calendar + Previous Report Comparison
# ---------------------------------------------------------------------------

def get_next_fed_meeting(today: date | None = None) -> dict:
    """Find the next upcoming Fed meeting, calculate days until, mark SEP."""
    if today is None:
        today = date.today()

    for m in FED_MEETINGS:
        mdate = datetime.strptime(m["date"], "%Y-%m-%d").date()
        if mdate >= today:
            days = (mdate - today).days
            return {
                "date": m["date"],
                "sep": m["sep"],
                "days": days,
                "label": f"{m['date']} ({'with SEP' if m['sep'] else 'no SEP'}) — {days} days",
            }

    return {"date": "TBD", "sep": False, "days": None, "label": "No upcoming meeting date known"}


def find_previous_report() -> str | None:
    """Find the most recent macro report file before today."""
    pattern = os.path.join(OUTPUT_DIR, "macro_report_*.md")
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    # Return the latest one (could be today's or older)
    return files[-1]


def parse_previous_summary(path: str) -> dict:
    """Parse the five-question summary table from a previous report.
    Returns dict mapping question ID -> {arrow, label, color}.
    """
    prev = {}
    if not path or not os.path.exists(path):
        return prev

    try:
        with open(path, "r") as f:
            content = f.read()

        # Look for table rows: | N | question | arrow label | ...
        # Supports both English (Better/Flat/Worse) and legacy Chinese labels
        pattern = r"\|\s*(\d)\s*\|[^|]+\|[^|]*\|\s*([↑↓→])\s+(Improving|Stable|Worsening|Better|Flat|Worse|改善|不变|恶化)\s*\|"
        for match in re.finditer(pattern, content):
            qid = int(match.group(1))
            arrow = match.group(2)
            label = match.group(3)
            color_map = {"Improving": "green", "Stable": "yellow", "Worsening": "red",
                         "Better": "green", "Flat": "yellow", "Worse": "red",
                         "改善": "green", "不变": "yellow", "恶化": "red"}
            prev[qid] = {"arrow": arrow, "label": label, "color": color_map.get(label, "yellow")}
    except Exception as e:
        print(f"  [WARN] Failed to parse previous report: {e}")

    return prev


def compute_change_label(prev_label: str | None, curr_label: str) -> str:
    """Compare previous vs current label, return change indicator."""
    if prev_label is None:
        return "—"
    if prev_label == curr_label:
        return "Unchanged —"

    severity = {"Improving": 0, "Stable": 1, "Worsening": 2,
                "Better": 0, "Flat": 1, "Worse": 2,
                "改善": 0, "不变": 1, "恶化": 2}
    prev_sev = severity.get(prev_label, 1)
    curr_sev = severity.get(curr_label, 1)

    if curr_sev < prev_sev:
        return "Improved \u2713"
    elif curr_sev > prev_sev:
        return "Deteriorated \u2717"
    return "Unchanged —"


# ---------------------------------------------------------------------------
# Step 5: Output Layer
# ---------------------------------------------------------------------------

def _fmt(val, decimals: int = 1, suffix: str = "%") -> str:
    """Format a numeric value with sign, decimals, and suffix."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    if decimals == 0:
        return f"{val:,.0f}{suffix}"
    return f"{val:.{decimals}f}{suffix}"


def _fmt_signed(val, decimals: int = 2, suffix: str = "") -> str:
    """Format with explicit sign."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:+.{decimals}f}{suffix}"


def _tail_table(series: pd.Series, n: int = 6, fmt_func=None) -> str:
    """Generate a markdown table showing the last n values of a series."""
    if series is None or series.empty:
        return "_Data unavailable_\n"

    s = series.dropna().tail(n)
    if s.empty:
        return "_Data unavailable_\n"

    dates = [d.strftime("%Y-%m") if hasattr(d, "strftime") else str(d) for d in s.index]
    if fmt_func:
        vals = [fmt_func(v) for v in s.values]
    else:
        vals = [f"{v:.2f}" for v in s.values]

    header = "| " + " | ".join(dates) + " |"
    sep = "| " + " | ".join(["---"] * len(dates)) + " |"
    row = "| " + " | ".join(vals) + " |"
    return f"{header}\n{sep}\n{row}\n"


def generate_report(raw: dict, derived: dict, q_results: list[dict],
                    overall: dict, prev_summary: dict, meeting: dict,
                    date_str: str) -> str:
    """Generate the full Markdown report."""
    lines = []
    total = overall.get("total", len(q_results))

    # Title
    lines.append(f"# Macro Market Sentiment Monitor — {date_str}\n")

    # Fed meeting
    lines.append("## Next Fed Meeting\n")
    if meeting["days"] is not None:
        sep_tag = " **\U0001f4ca with Summary of Economic Projections (SEP)**" if meeting["sep"] else ""
        lines.append(f"**{meeting['date']}** — {meeting['days']} days away{sep_tag}\n")
    else:
        lines.append(f"{meeting['label']}\n")

    # Six-question summary table
    lines.append("## Six-Question Dashboard\n")
    lines.append("| # | Question | Previous | Current | Change | Key Data |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    for r in q_results:
        q = QUESTIONS[r["id"] - 1]
        curr_str = r["label"]
        prev = prev_summary.get(r["id"])
        prev_str = prev["label"] if prev else "—"
        change = compute_change_label(prev["label"] if prev else None, r["label"])
        lines.append(f"| {r['id']} | {q['short']} | {prev_str} | {curr_str} | {change} | {r['key_data']} |")

    lines.append("")

    # Overall signal
    lines.append("## Overall Assessment\n")
    lines.append(f"**{overall['emoji']} {overall['label']}** ({overall['red_count']}/{total} deteriorating)\n")
    lines.append(f"{overall['narrative']}\n")

    # Detailed data sections
    lines.append("## Detailed Data\n")

    # 1. Inflation
    lines.append("### 1. Inflation\n")

    lines.append("**Core CPI (CPILFESL) — YoY%**\n")
    if "core_cpi_yoy" in derived:
        lines.append(_tail_table(derived["core_cpi_yoy"], fmt_func=lambda v: f"{v:.1f}%"))
    else:
        lines.append("_Data unavailable_\n")

    lines.append("**Services CPI (CUSR0000SAS) — YoY%**\n")
    if "cpi_services_yoy" in derived:
        lines.append(_tail_table(derived["cpi_services_yoy"], fmt_func=lambda v: f"{v:.1f}%"))
    else:
        lines.append("_Data unavailable_\n")

    lines.append("**Shelter CPI (CUSR0000SAH1) — YoY%**\n")
    if "cpi_shelter_yoy" in derived:
        lines.append(_tail_table(derived["cpi_shelter_yoy"], fmt_func=lambda v: f"{v:.1f}%"))
    else:
        lines.append("_Data unavailable_\n")

    lines.append("**Inflation Expectations**\n")
    if "breakeven_5y" in raw:
        be5 = raw["breakeven_5y"]
        lines.append(f"- 5Y Breakeven: {_fmt(be5.iloc[-1], 2)}")
    if "forward_5y5y" in raw:
        fwd = raw["forward_5y5y"]
        lines.append(f"- 5Y5Y Forward: {_fmt(fwd.iloc[-1], 2)}")
    lines.append("")

    # 2. Employment
    lines.append("### 2. Employment\n")

    lines.append("**Unemployment Rate**\n")
    if "unrate" in raw:
        lines.append(_tail_table(raw["unrate"], fmt_func=lambda v: f"{v:.1f}%"))
    if "u6rate" in raw:
        lines.append(f"- U-6 (latest): {_fmt(raw['u6rate'].iloc[-1], 1)}\n")
    if "civpart" in raw:
        lines.append(f"- Labor Force Participation (latest): {_fmt(raw['civpart'].iloc[-1], 1)}\n")

    lines.append("**Wages**\n")
    if "avg_hourly_earn_yoy" in derived:
        ahe = derived["avg_hourly_earn_yoy"].dropna()
        if not ahe.empty:
            lines.append(f"- Avg Hourly Earnings YoY: {_fmt(ahe.iloc[-1], 1)}")
    if "eci_wages_yoy" in derived:
        eci = derived["eci_wages_yoy"].dropna()
        if not eci.empty:
            lines.append(f"- ECI Wages YoY: {_fmt(eci.iloc[-1], 1)}")
    lines.append("")

    lines.append("**Initial Jobless Claims (ICSA)**\n")
    if "jobless_claims" in raw:
        ic = raw["jobless_claims"]
        lines.append(f"- Latest: {_fmt(ic.iloc[-1], 0, '')}")
        if "icsa_4wma" in derived:
            ma4 = derived["icsa_4wma"].dropna()
            if not ma4.empty:
                lines.append(f"- 4-week MA: {_fmt(ma4.iloc[-1], 0, '')}")
        if "icsa_13wma" in derived:
            ma13 = derived["icsa_13wma"].dropna()
            if not ma13.empty:
                lines.append(f"- 13-week MA: {_fmt(ma13.iloc[-1], 0, '')}")
    lines.append("")

    # 3. Financial conditions
    lines.append("### 3. Financial Conditions\n")

    if "nfci" in raw:
        nfci = raw["nfci"]
        nfci_monthly = nfci.resample("ME").last().dropna()
        lines.append("**NFCI (Chicago Fed National Financial Conditions Index)**\n")
        lines.append(_tail_table(nfci_monthly, fmt_func=lambda v: f"{v:+.2f}"))

    if "hy_spread" in raw:
        lines.append(f"**HY Spread**: {raw['hy_spread'].iloc[-1] * 100:.0f}bp ({raw['hy_spread'].iloc[-1]:.2f}%)\n")

    if "fed_funds" in raw:
        lines.append(f"**Fed Funds Rate**: {_fmt(raw['fed_funds'].iloc[-1], 2)}\n")

    if "yield_spread" in raw:
        lines.append(f"**10Y-2Y Spread**: {_fmt_signed(raw['yield_spread'].iloc[-1], 2, '%')}\n")

    if "vix" in raw:
        vix = raw["vix"]
        vix_20d = derived.get("vix_20d_avg")
        vix_str = f"**VIX**: {vix.iloc[-1]:.1f}"
        if vix_20d is not None and not vix_20d.dropna().empty:
            vix_str += f" (20-day avg: {vix_20d.dropna().iloc[-1]:.1f})"
        lines.append(f"{vix_str}\n")

    lines.append("")

    # 4. Leading Indicators
    lines.append("### 4. Leading Indicators\n")

    if "consumer_sent" in raw:
        lines.append("**U. Michigan Consumer Sentiment**\n")
        lines.append(_tail_table(raw["consumer_sent"], fmt_func=lambda v: f"{v:.1f}"))

    if "mfg_ip" in raw and "mfg_ip_yoy" in derived:
        lines.append("**Manufacturing Industrial Production — YoY%**\n")
        lines.append(_tail_table(derived["mfg_ip_yoy"], fmt_func=lambda v: f"{v:.1f}%"))

    if "recession_prob" in raw:
        rp = raw["recession_prob"]
        lines.append(f"**Smoothed Recession Probability**: {rp.iloc[-1]:.1f}%\n")

    lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"_Generated by macro_monitor.py on {date_str}_\n")

    return "\n".join(lines)


def save_report(report: str, date_str: str):
    """Save the markdown report to output/macro_monitor/."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"macro_report_{date_str}.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"[Saved] {path}")


def print_terminal_summary(q_results: list[dict], overall: dict, meeting: dict):
    """Print a colorful terminal summary using ANSI codes."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"

    color_map = {"red": RED, "yellow": YELLOW, "green": GREEN}

    total = overall.get("total", len(q_results))

    print()
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Macro Market Sentiment Monitor{RESET}")
    print(f"{'=' * 60}")

    # Fed meeting
    if meeting["days"] is not None:
        sep_note = " (with SEP)" if meeting["sep"] else ""
        print(f"\n  {CYAN}Next FOMC: {meeting['date']}{sep_note} — {meeting['days']} days{RESET}")

    # Six questions
    print(f"\n  {BOLD}Dashboard:{RESET}\n")
    for r in q_results:
        q = QUESTIONS[r["id"] - 1]
        c = color_map.get(r["color"], RESET)
        print(f"  {r['id']}. {q['short']:<16s}  {c}{r['arrow']} {r['label']}{RESET}  {r['key_data']}")

    # Overall
    oc = color_map.get(overall["signal"], RESET)
    print(f"\n  {BOLD}Overall: {oc}{overall['emoji']} {overall['label']}{RESET} ({overall['red_count']}/{total} deteriorating)")
    print(f"  {overall['narrative']}")
    print(f"\n{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Step 6: Infrastructure
# ---------------------------------------------------------------------------

def send_macos_notification(title: str, message: str):
    """Send a native macOS notification via osascript."""
    safe_msg = message.replace('"', '\\"')
    safe_title = title.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}" sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except Exception as e:
        print(f"[WARN] Failed to send notification: {e}")


def should_alert(overall: dict, prev_summary: dict) -> bool:
    """Determine if we should send a macOS notification.
    Alert when overall signal is red, or when it changed from a previous state.
    """
    if overall["signal"] == "red":
        return True
    if not prev_summary:
        return False
    # Alert if any question changed to red that wasn't before
    return overall["red_count"] >= 2


def send_alert(overall: dict, q_results: list[dict]):
    """Build and send a macOS notification."""
    title = f"Macro Monitor: {overall['emoji']} {overall['label']}"
    red_qs = [QUESTIONS[r["id"] - 1]["short"] for r in q_results if r["color"] == "red"]
    if red_qs:
        msg = f"Deteriorating: {', '.join(red_qs)}"
    else:
        msg = overall["narrative"]
    # Truncate for notification
    if len(msg) > 120:
        msg = msg[:117] + "..."
    send_macos_notification(title, msg)


def install_launchd():
    """Install a macOS launchd plist to run monthly on the 15th at 10:00."""
    script_path = os.path.abspath(__file__)
    python_path = shutil.which("python3") or sys.executable
    log_path = os.path.abspath(os.path.join(OUTPUT_DIR, "monitor.log"))
    working_dir = os.path.dirname(script_path)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    plist = {
        "Label": PLIST_LABEL,
        "ProgramArguments": [python_path, script_path],
        "WorkingDirectory": working_dir,
        "StartCalendarInterval": {
            "Day": 15,
            "Hour": 10,
            "Minute": 0,
        },
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
        "RunAtLoad": False,
    }

    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "load", PLIST_PATH], check=True)
    print(f"[OK] Installed launchd job: {PLIST_LABEL}")
    print(f"     Plist: {PLIST_PATH}")
    print(f"     Schedule: Every 15th of the month at 10:00")
    print(f"     Log: {log_path}")


def uninstall_launchd():
    """Unload and remove launchd plist."""
    if os.path.exists(PLIST_PATH):
        subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
        os.remove(PLIST_PATH)
        print(f"[OK] Uninstalled launchd job: {PLIST_LABEL}")
    else:
        print(f"[INFO] Plist not found: {PLIST_PATH}")


def run(check_only: bool = False):
    """Main orchestration function."""
    today_str = date.today().strftime("%Y-%m-%d")

    print(f"\n[macro_monitor] {today_str}")
    print("-" * 40)

    # 1. Fetch data
    print("\n[1/4] Fetching FRED data...")
    raw = fetch_all_series()

    if not raw:
        print("[ERROR] No data fetched. Check network/API key.")
        sys.exit(1)

    # 2. Compute derived metrics
    print("\n[2/4] Computing derived metrics...")
    derived = compute_derived_metrics(raw)

    # 3. Run five-question assessment
    print("\n[3/4] Assessing macro conditions...")
    q_results = [
        assess_q1_core_services(raw, derived),
        assess_q2_inflation_expectations(raw, derived),
        assess_q3_wage_stickiness(raw, derived),
        assess_q4_unemployment_trend(raw, derived),
        assess_q5_financial_conditions(raw, derived),
        assess_q6_economic_momentum(raw, derived),
    ]
    overall = compute_overall_signal(q_results)

    # 4. Fed calendar + previous report
    meeting = get_next_fed_meeting()

    prev_path = find_previous_report()
    prev_summary = {}
    if prev_path:
        # Don't compare with today's report if it exists
        if today_str not in os.path.basename(prev_path):
            prev_summary = parse_previous_summary(prev_path)
            print(f"  Previous report: {os.path.basename(prev_path)}")
        elif len(sorted(glob.glob(os.path.join(OUTPUT_DIR, "macro_report_*.md")))) > 1:
            # Use second-to-last
            files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "macro_report_*.md")))
            if len(files) >= 2:
                prev_summary = parse_previous_summary(files[-2])
                print(f"  Previous report: {os.path.basename(files[-2])}")

    # Terminal output
    print_terminal_summary(q_results, overall, meeting)

    # 5. Save report
    if not check_only:
        print("[4/4] Generating report...")
        report = generate_report(raw, derived, q_results, overall,
                                 prev_summary, meeting, today_str)
        save_report(report, today_str)

        # Alert
        if should_alert(overall, prev_summary):
            send_alert(overall, q_results)
    else:
        print("[4/4] Check-only mode, skipping save.")

    print("\n[Done]")


def main():
    ap = argparse.ArgumentParser(
        description="Macro Market Sentiment Monitor — FRED-driven six-question analysis"
    )
    ap.add_argument("--check-only", action="store_true",
                    help="Only print terminal summary, do not save report")
    ap.add_argument("--test-alert", action="store_true",
                    help="Send a test macOS notification and exit")
    ap.add_argument("--install", action="store_true",
                    help="Install macOS launchd monthly job (15th at 10:00)")
    ap.add_argument("--uninstall", action="store_true",
                    help="Uninstall macOS launchd job")
    args = ap.parse_args()

    if args.test_alert:
        send_macos_notification("Macro Monitor (Test)", "This is a test notification from macro_monitor.py")
        print("[OK] Test notification sent.")
        return

    if args.install:
        install_launchd()
        return

    if args.uninstall:
        uninstall_launchd()
        return

    run(check_only=args.check_only)


if __name__ == "__main__":
    main()
