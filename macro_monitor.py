#!/usr/bin/env python3
"""
macro_monitor.py — 宏观市场情绪监控工具

从 FRED 获取通胀、就业、金融条件等 15 个关键指标，
自动回答"该不该恐慌"的 5 个核心问题，
生成 Markdown 报告 + 终端彩色摘要 + macOS 通知。

Usage:
    python macro_monitor.py                  # 运行一次，保存报告
    python macro_monitor.py --check-only     # 只看终端，不保存
    python macro_monitor.py --test-alert     # 测试 macOS 通知
    python macro_monitor.py --install        # 安装 launchd (每月15号)
    python macro_monitor.py --uninstall      # 卸载 launchd
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

# 15 FRED series
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

# Five core questions
QUESTIONS = [
    {"id": 1, "short": "服务通胀粘性",     "long": "核心服务通胀是否仍在加速？"},
    {"id": 2, "short": "通胀预期锚定",     "long": "市场通胀预期是否脱锚？"},
    {"id": 3, "short": "工资-物价螺旋",    "long": "工资增速是否显著超过通胀？"},
    {"id": 4, "short": "失业恶化趋势",     "long": "劳动力市场是否快速恶化？"},
    {"id": 5, "short": "金融条件收紧",     "long": "金融条件是否异常收紧？"},
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
    """Fetch all 15 FRED series. Returns dict keyed by our short name."""
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

    return d


# ---------------------------------------------------------------------------
# Step 3: Five-Question Assessment Logic
# ---------------------------------------------------------------------------

def assess_q1_core_services(raw: dict, derived: dict) -> dict:
    """Q1: 核心服务通胀是否仍在加速？
    Checks: CPI Services 3-month annualized trend, shelter decomposition.
    """
    result = {"id": 1, "arrow": "→", "label": "不变", "color": "yellow",
              "key_data": "N/A", "detail": "数据不足"}

    svc_ann3m = derived.get("cpi_services_ann3m")
    shelter_ann3m = derived.get("cpi_shelter_ann3m")
    svc_yoy = derived.get("cpi_services_yoy")

    if svc_ann3m is None:
        return result

    # Latest YoY for context
    svc_yoy_latest = svc_yoy.dropna().iloc[-1] if svc_yoy is not None and not svc_yoy.dropna().empty else None

    parts = []
    if svc_yoy_latest is not None:
        parts.append(f"服务CPI YoY {svc_yoy_latest:.1f}%")
    parts.append(f"3M年化 {svc_ann3m:.1f}%")
    if shelter_ann3m is not None:
        parts.append(f"住房3M年化 {shelter_ann3m:.1f}%")

    result["key_data"] = ", ".join(parts)

    # Logic: 3M annualized > 4.5% = worsening, < 3.0% = improving
    if svc_ann3m > 4.5:
        result.update(arrow="↑", label="恶化", color="red",
                      detail=f"服务通胀3个月年化 {svc_ann3m:.1f}% 仍高于舒适区(>4.5%)")
    elif svc_ann3m < 3.0:
        result.update(arrow="↓", label="改善", color="green",
                      detail=f"服务通胀3个月年化 {svc_ann3m:.1f}% 已回落至3%以下")
    else:
        shelter_note = ""
        if shelter_ann3m is not None and shelter_ann3m < 3.0:
            shelter_note = "，住房分项已明显减速"
        result.update(arrow="→", label="不变", color="yellow",
                      detail=f"服务通胀3个月年化 {svc_ann3m:.1f}% 处于过渡区间{shelter_note}")

    return result


def assess_q2_inflation_expectations(raw: dict, derived: dict) -> dict:
    """Q2: 市场通胀预期是否脱锚？
    Checks: 5Y breakeven level and trend, 5Y5Y forward.
    """
    result = {"id": 2, "arrow": "→", "label": "不变", "color": "yellow",
              "key_data": "N/A", "detail": "数据不足"}

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

    parts.append(f"3M变化 {be5_delta:+.2f}pp")
    result["key_data"] = ", ".join(parts)

    # Anchored: 5Y BEI 2.0-2.5% is normal. >2.8% concerning. <1.5% deflation risk.
    fwd_latest = fwd.iloc[-1] if fwd is not None and not fwd.empty else None

    if be5_latest > 2.8 or (fwd_latest is not None and fwd_latest > 2.8):
        result.update(arrow="↑", label="恶化", color="red",
                      detail=f"通胀预期偏高(5Y BEI {be5_latest:.2f}%)，可能脱锚风险")
    elif be5_latest < 1.5:
        result.update(arrow="↓", label="恶化", color="red",
                      detail=f"通胀预期过低(5Y BEI {be5_latest:.2f}%)，暗示通缩担忧")
    elif 2.0 <= be5_latest <= 2.5 and abs(be5_delta) < 0.3:
        result.update(arrow="→", label="改善", color="green",
                      detail=f"通胀预期锚定良好(5Y BEI {be5_latest:.2f}%，波动小)")
    else:
        result.update(arrow="→", label="不变", color="yellow",
                      detail=f"通胀预期小幅偏离正常区间(5Y BEI {be5_latest:.2f}%)")

    return result


def assess_q3_wage_stickiness(raw: dict, derived: dict) -> dict:
    """Q3: 工资增速是否显著超过通胀？
    Checks: AHE YoY vs Core CPI YoY, ECI trend.
    """
    result = {"id": 3, "arrow": "→", "label": "不变", "color": "yellow",
              "key_data": "N/A", "detail": "数据不足"}

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

    parts = [f"工资YoY {ahe_latest:.1f}%", f"核心CPI YoY {cpi_latest:.1f}%",
             f"差值 {wage_cpi_gap:+.1f}pp"]
    if eci_yoy is not None and not eci_yoy.dropna().empty:
        eci_latest = eci_yoy.dropna().iloc[-1]
        parts.append(f"ECI YoY {eci_latest:.1f}%")

    result["key_data"] = ", ".join(parts)

    # Wage-price spiral: wage growth significantly > CPI → inflationary pressure
    # Gap > 1.5pp means wages clearly outpacing → could fuel inflation
    if wage_cpi_gap > 1.5:
        result.update(arrow="↑", label="恶化", color="red",
                      detail=f"工资增速({ahe_latest:.1f}%)显著超过通胀({cpi_latest:.1f}%)，"
                             f"工资-物价螺旋风险")
    elif wage_cpi_gap < -0.5:
        # Wages lagging inflation → real wage decline, demand risk
        result.update(arrow="↓", label="改善", color="green",
                      detail=f"工资增速({ahe_latest:.1f}%)低于通胀({cpi_latest:.1f}%)，"
                             f"通胀压力自然减弱")
    else:
        result.update(arrow="→", label="不变", color="yellow",
                      detail=f"工资与通胀大致平衡(差值{wage_cpi_gap:+.1f}pp)，暂无螺旋迹象")

    return result


def assess_q4_unemployment_trend(raw: dict, derived: dict) -> dict:
    """Q4: 劳动力市场是否快速恶化？
    Checks: UNRATE 3-month delta, ICSA acceleration (4wma vs 13wma), U-6 level.
    """
    result = {"id": 4, "arrow": "→", "label": "不变", "color": "yellow",
              "key_data": "N/A", "detail": "数据不足"}

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
        parts.append(f"3M变化 {unrate_3m:+.1f}pp")
    if icsa_accel is not None:
        parts.append(f"ICSA加速 {icsa_accel:+.0f}")

    result["key_data"] = ", ".join(parts)

    # Sahm rule inspired: 3-month UR rise > 0.5pp = recession signal
    # ICSA acceleration: 4wma > 13wma by >30K = deteriorating
    is_ur_rising = unrate_3m is not None and unrate_3m > 0.5
    is_icsa_accel = icsa_accel is not None and icsa_accel > 30000

    if is_ur_rising and is_icsa_accel:
        result.update(arrow="↑", label="恶化", color="red",
                      detail=f"失业率3个月上升{unrate_3m:+.1f}pp且初次申领加速，"
                             f"劳动力市场快速恶化")
    elif is_ur_rising or is_icsa_accel:
        result.update(arrow="↑", label="恶化", color="yellow",
                      detail=f"劳动力市场出现弱化信号("
                             f"{'UR↑' if is_ur_rising else 'ICSA↑'})")
    elif unrate_3m is not None and unrate_3m < -0.2:
        result.update(arrow="↓", label="改善", color="green",
                      detail=f"失业率持续下降(3M {unrate_3m:+.1f}pp)，市场强劲")
    else:
        result.update(arrow="→", label="不变", color="yellow",
                      detail=f"劳动力市场平稳(U-3 {ur_latest:.1f}%)")

    return result


def assess_q5_financial_conditions(raw: dict, derived: dict) -> dict:
    """Q5: 金融条件是否异常收紧？
    Checks: NFCI level, HY spread level + trend, yield curve.
    """
    result = {"id": 5, "arrow": "→", "label": "不变", "color": "yellow",
              "key_data": "N/A", "detail": "数据不足"}

    nfci = raw.get("nfci")
    hy = raw.get("hy_spread")
    yc = raw.get("yield_spread")
    hy_delta = derived.get("hy_spread_3m_delta")

    parts = []
    nfci_latest = None
    hy_latest = None
    yc_latest = None

    if nfci is not None and not nfci.empty:
        nfci_latest = nfci.iloc[-1]
        parts.append(f"NFCI {nfci_latest:+.2f}")
    if hy is not None and not hy.empty:
        hy_latest = hy.iloc[-1]
        parts.append(f"HY利差 {hy_latest * 100:.0f}bp")
    if yc is not None and not yc.empty:
        yc_latest = yc.iloc[-1]
        parts.append(f"10Y-2Y {yc_latest:+.2f}%")
    if hy_delta is not None:
        parts.append(f"HY 3M变化 {hy_delta * 100:+.0f}bp")

    if not parts:
        return result

    result["key_data"] = ", ".join(parts)

    # NFCI > 0 = tighter than average. > 0.5 = significantly tight.
    # HY spread > 5.0% (500bp) = stress. > 8.0% (800bp) = crisis. (FRED data in %)
    # Inverted yield curve (negative 10Y-2Y) = recession warning.
    stress_signals = 0

    if nfci_latest is not None and nfci_latest > 0.5:
        stress_signals += 1
    if hy_latest is not None and hy_latest > 5.0:
        stress_signals += 1
    if yc_latest is not None and yc_latest < -0.5:
        stress_signals += 1

    if stress_signals >= 2:
        result.update(arrow="↑", label="恶化", color="red",
                      detail=f"多个金融条件指标同时收紧({stress_signals}/3 触发)，市场压力显著")
    elif stress_signals == 1:
        result.update(arrow="↑", label="恶化", color="yellow",
                      detail=f"部分金融条件收紧(1/3 触发)，需关注")
    else:
        # Check if conditions are unusually loose
        is_loose = (nfci_latest is not None and nfci_latest < -0.5)
        if is_loose:
            result.update(arrow="↓", label="改善", color="green",
                          detail=f"金融条件宽松(NFCI {nfci_latest:+.2f})，市场流动性充裕")
        else:
            result.update(arrow="→", label="不变", color="yellow",
                          detail="金融条件处于正常范围")

    return result


def compute_overall_signal(q_results: list[dict]) -> dict:
    """Compute overall signal from 5 question results.
    Q1-Q3 focused: if none worsening = green; 1 worsening = yellow; 2+ = red.
    Q4-Q5 can escalate: if either is red, bump overall by one level.
    """
    inflation_qs = [r for r in q_results if r["id"] <= 3]
    market_qs = [r for r in q_results if r["id"] > 3]

    inflation_red = sum(1 for r in inflation_qs if r["color"] == "red")
    market_red = sum(1 for r in market_qs if r["color"] == "red")
    all_red = sum(1 for r in q_results if r["color"] == "red")

    if inflation_red == 0 and market_red == 0:
        signal = "green"
        emoji = "\U0001f7e2"  # 🟢
        label = "低风险"
        narrative = "通胀、就业和金融条件均未显示恶化信号，宏观环境有利。"
    elif all_red >= 3:
        signal = "red"
        emoji = "\U0001f534"  # 🔴
        label = "高风险"
        narrative = "多个维度同时恶化，宏观环境面临显著压力，建议提高防御性配置。"
    elif inflation_red >= 2 or (inflation_red >= 1 and market_red >= 1):
        signal = "red"
        emoji = "\U0001f534"  # 🔴
        label = "高风险"
        narrative = "通胀压力与市场压力叠加，宏观不确定性较高。"
    else:
        signal = "yellow"
        emoji = "\U0001f7e1"  # 🟡
        label = "中等风险"
        narrative = "部分指标出现警示信号，需密切跟踪变化方向。"

    return {
        "signal": signal,
        "emoji": emoji,
        "label": label,
        "narrative": narrative,
        "red_count": all_red,
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
                "label": f"{m['date']} ({'含 SEP' if m['sep'] else '无 SEP'}) — {days}天后",
            }

    return {"date": "TBD", "sep": False, "days": None, "label": "暂无已知会议日期"}


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
        # Pattern: | 1 | ... | ↑ 恶化 | ...
        pattern = r"\|\s*(\d)\s*\|[^|]+\|[^|]*\|\s*([↑↓→])\s+(改善|不变|恶化)\s*\|"
        for match in re.finditer(pattern, content):
            qid = int(match.group(1))
            arrow = match.group(2)
            label = match.group(3)
            color_map = {"改善": "green", "不变": "yellow", "恶化": "red"}
            prev[qid] = {"arrow": arrow, "label": label, "color": color_map.get(label, "yellow")}
    except Exception as e:
        print(f"  [WARN] Failed to parse previous report: {e}")

    return prev


def compute_change_label(prev_label: str | None, curr_label: str) -> str:
    """Compare previous vs current label, return change indicator."""
    if prev_label is None:
        return "—"
    if prev_label == curr_label:
        return "不变 —"

    severity = {"改善": 0, "不变": 1, "恶化": 2}
    prev_sev = severity.get(prev_label, 1)
    curr_sev = severity.get(curr_label, 1)

    if curr_sev < prev_sev:
        return "改善 \u2713"
    elif curr_sev > prev_sev:
        return "恶化 \u2717"
    return "不变 —"


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
        return "_数据不可用_\n"

    s = series.dropna().tail(n)
    if s.empty:
        return "_数据不可用_\n"

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

    # Title
    lines.append(f"# 宏观市场情绪监控 — {date_str}\n")

    # Fed meeting
    lines.append("## 下次美联储会议\n")
    if meeting["days"] is not None:
        sep_tag = " **\U0001f4ca 含经济预测摘要(SEP)**" if meeting["sep"] else ""
        lines.append(f"**{meeting['date']}** — {meeting['days']}天后{sep_tag}\n")
    else:
        lines.append(f"{meeting['label']}\n")

    # Five-question summary table
    lines.append("## 五问速览\n")
    lines.append("| # | 问题 | 上期 | 本期 | 变化 | 关键数据 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")

    for r in q_results:
        q = QUESTIONS[r["id"] - 1]
        prev = prev_summary.get(r["id"])
        prev_str = f"{prev['arrow']} {prev['label']}" if prev else "—"
        curr_str = f"{r['arrow']} {r['label']}"
        change = compute_change_label(prev["label"] if prev else None, r["label"])
        lines.append(f"| {r['id']} | {q['short']} | {prev_str} | {curr_str} | {change} | {r['key_data']} |")

    lines.append("")

    # Overall signal
    lines.append("## 综合判断\n")
    lines.append(f"**{overall['emoji']} {overall['label']}** ({overall['red_count']}/5 项恶化)\n")
    lines.append(f"{overall['narrative']}\n")

    # Detailed data sections
    lines.append("## 详细数据\n")

    # 1. Inflation
    lines.append("### 1. 通胀\n")

    lines.append("**核心 CPI (CPILFESL) — YoY%**\n")
    if "core_cpi_yoy" in derived:
        lines.append(_tail_table(derived["core_cpi_yoy"], fmt_func=lambda v: f"{v:.1f}%"))
    else:
        lines.append("_数据不可用_\n")

    lines.append("**服务 CPI (CUSR0000SAS) — YoY%**\n")
    if "cpi_services_yoy" in derived:
        lines.append(_tail_table(derived["cpi_services_yoy"], fmt_func=lambda v: f"{v:.1f}%"))
    else:
        lines.append("_数据不可用_\n")

    lines.append("**住房 CPI (CUSR0000SAH1) — YoY%**\n")
    if "cpi_shelter_yoy" in derived:
        lines.append(_tail_table(derived["cpi_shelter_yoy"], fmt_func=lambda v: f"{v:.1f}%"))
    else:
        lines.append("_数据不可用_\n")

    lines.append("**通胀预期**\n")
    if "breakeven_5y" in raw:
        be5 = raw["breakeven_5y"]
        be5_monthly = be5.resample("ME").last().dropna()
        lines.append(f"- 5Y Breakeven: {_fmt(be5.iloc[-1], 2)}")
    if "forward_5y5y" in raw:
        fwd = raw["forward_5y5y"]
        lines.append(f"- 5Y5Y Forward: {_fmt(fwd.iloc[-1], 2)}")
    lines.append("")

    # 2. Employment
    lines.append("### 2. 就业\n")

    lines.append("**失业率**\n")
    if "unrate" in raw:
        lines.append(_tail_table(raw["unrate"], fmt_func=lambda v: f"{v:.1f}%"))
    if "u6rate" in raw:
        lines.append(f"- U-6 (最新): {_fmt(raw['u6rate'].iloc[-1], 1)}\n")
    if "civpart" in raw:
        lines.append(f"- 劳动参与率 (最新): {_fmt(raw['civpart'].iloc[-1], 1)}\n")

    lines.append("**工资**\n")
    if "avg_hourly_earn_yoy" in derived:
        ahe = derived["avg_hourly_earn_yoy"].dropna()
        if not ahe.empty:
            lines.append(f"- 平均时薪 YoY: {_fmt(ahe.iloc[-1], 1)}")
    if "eci_wages_yoy" in derived:
        eci = derived["eci_wages_yoy"].dropna()
        if not eci.empty:
            lines.append(f"- ECI 工资成本 YoY: {_fmt(eci.iloc[-1], 1)}")
    lines.append("")

    lines.append("**初次申领失业金 (ICSA)**\n")
    if "jobless_claims" in raw:
        ic = raw["jobless_claims"]
        lines.append(f"- 最新: {_fmt(ic.iloc[-1], 0, '')}")
        if "icsa_4wma" in derived:
            ma4 = derived["icsa_4wma"].dropna()
            if not ma4.empty:
                lines.append(f"- 4周均线: {_fmt(ma4.iloc[-1], 0, '')}")
        if "icsa_13wma" in derived:
            ma13 = derived["icsa_13wma"].dropna()
            if not ma13.empty:
                lines.append(f"- 13周均线: {_fmt(ma13.iloc[-1], 0, '')}")
    lines.append("")

    # 3. Financial conditions
    lines.append("### 3. 金融条件\n")

    if "nfci" in raw:
        nfci = raw["nfci"]
        nfci_monthly = nfci.resample("ME").last().dropna()
        lines.append("**NFCI (芝加哥联储金融条件指数)**\n")
        lines.append(_tail_table(nfci_monthly, fmt_func=lambda v: f"{v:+.2f}"))

    if "hy_spread" in raw:
        lines.append(f"**高收益债利差**: {raw['hy_spread'].iloc[-1] * 100:.0f}bp ({raw['hy_spread'].iloc[-1]:.2f}%)\n")

    if "fed_funds" in raw:
        lines.append(f"**联邦基金利率**: {_fmt(raw['fed_funds'].iloc[-1], 2)}\n")

    if "yield_spread" in raw:
        lines.append(f"**10Y-2Y 利差**: {_fmt_signed(raw['yield_spread'].iloc[-1], 2, '%')}\n")

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

    print()
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  宏观市场情绪监控{RESET}")
    print(f"{'=' * 60}")

    # Fed meeting
    if meeting["days"] is not None:
        sep_note = " (含SEP)" if meeting["sep"] else ""
        print(f"\n  {CYAN}下次FOMC: {meeting['date']}{sep_note} — {meeting['days']}天后{RESET}")

    # Five questions
    print(f"\n  {BOLD}五问速览:{RESET}\n")
    for r in q_results:
        q = QUESTIONS[r["id"] - 1]
        c = color_map.get(r["color"], RESET)
        print(f"  {r['id']}. {q['short']:　<8s}  {c}{r['arrow']} {r['label']}{RESET}  {r['key_data']}")

    # Overall
    oc = color_map.get(overall["signal"], RESET)
    print(f"\n  {BOLD}综合: {oc}{overall['emoji']} {overall['label']}{RESET} ({overall['red_count']}/5 恶化)")
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
    title = f"宏观监控: {overall['emoji']} {overall['label']}"
    red_qs = [QUESTIONS[r["id"] - 1]["short"] for r in q_results if r["color"] == "red"]
    if red_qs:
        msg = f"恶化: {', '.join(red_qs)}"
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
        description="宏观市场情绪监控 — FRED 数据驱动的五问分析"
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
        send_macos_notification("宏观监控 (测试)", "这是一条来自 macro_monitor.py 的测试通知")
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
