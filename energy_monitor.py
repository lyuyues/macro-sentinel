#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# energy_monitor.py  能源周期被动监控工具
#
# 定期获取油价/气价/能源股估值数据，计算买卖信号，生成周报，
# 触发 HIGH 信号时发送 macOS 原生通知。
#
# Usage:
#   python energy_monitor.py                          # 手动运行一次
#   python energy_monitor.py --tickers XOM,CVX,FCX    # 指定监控股票
#   python energy_monitor.py --check-only             # 只检查信号不保存文件
#   python energy_monitor.py --test-alert             # 测试 macOS 通知
#   python energy_monitor.py --install                # 安装 launchd 定时任务
#   python energy_monitor.py --uninstall              # 卸载 launchd 定时任务

import argparse
import csv
import os
import plistlib
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import yfinance as yf

# =======================================
#  Constants
# =======================================

DEFAULT_TICKERS = ["XOM", "CVX"]
COMMODITY_SYMBOLS = {
    "WTI": "CL=F",
    "Brent": "BZ=F",
    "NatGas": "NG=F",
}
BENCHMARK_SYMBOLS = {
    "XLE": "XLE",
    "SPY": "SPY",
}
OUTPUT_DIR = os.path.join("output", "energy_cycle")
PLIST_LABEL = "com.ai-stock.energy-monitor"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")

# Signal thresholds
SIGNALS_CONFIG = [
    # (id, indicator, buy_op, buy_thresh, sell_op, sell_thresh, severity)
    (1, "WTI_price",       "<",  45,    ">",  95,    "HIGH"),
    (2, "WTI_wow_pct",     "<",  -10,   None, None,  "MEDIUM"),
    (3, "WTI_wow_pct",     None, None,  ">",  10,    "MEDIUM"),
    (4, "XOM_pe",          ">",  30,    "<",  10,    "HIGH"),
    (5, "XOM_div_yield",   ">",  4.5,   "<",  2.5,   "HIGH"),
    (6, "XOM_dist_52w_low","<",  10,    None, None,  "MEDIUM"),
    (7, "XOM_dist_52w_high",None,None,  "<",  5,     "MEDIUM"),
    (8, "XLE_vs_SPY_1m",   "<",  -10,   ">",  15,    "LOW"),
    (9, "NatGas_price",    "<",  2.0,   ">",  8.0,   "LOW"),
]


# =======================================
#  Data Fetching
# =======================================

def fetch_commodity_prices(sleep_sec: float = 0.3) -> dict:
    """Fetch WTI, Brent, NatGas current prices + week/month/year changes."""
    result = {}
    for name, symbol in COMMODITY_SYMBOLS.items():
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period="1y")
            if hist.empty:
                result[name] = {"error": f"No data for {symbol}"}
                continue

            current = float(hist["Close"].iloc[-1])
            high_52w = float(hist["Close"].max())
            low_52w = float(hist["Close"].min())

            # Week-over-week change
            wow_pct = None
            if len(hist) >= 5:
                prev_week = float(hist["Close"].iloc[-6])
                if prev_week > 0:
                    wow_pct = (current - prev_week) / prev_week * 100

            # Month-over-month change
            mom_pct = None
            if len(hist) >= 22:
                prev_month = float(hist["Close"].iloc[-23])
                if prev_month > 0:
                    mom_pct = (current - prev_month) / prev_month * 100

            # Year-over-year change
            yoy_pct = None
            if len(hist) >= 250:
                prev_year = float(hist["Close"].iloc[0])
                if prev_year > 0:
                    yoy_pct = (current - prev_year) / prev_year * 100

            result[name] = {
                "price": current,
                "wow_pct": wow_pct,
                "mom_pct": mom_pct,
                "yoy_pct": yoy_pct,
                "high_52w": high_52w,
                "low_52w": low_52w,
            }
            time.sleep(sleep_sec)

        except Exception as e:
            result[name] = {"error": str(e)}

    return result


def fetch_stock_snapshot(ticker: str, sleep_sec: float = 0.3) -> dict:
    """Fetch key valuation metrics for a single stock."""
    result = {
        "ticker": ticker.upper(),
        "price": None,
        "pe": None,
        "forward_pe": None,
        "div_yield": None,
        "ev_ebitda": None,
        "high_52w": None,
        "low_52w": None,
        "market_cap": None,
        "name": None,
        "error": None,
    }
    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        if not info or info.get("regularMarketPrice") is None:
            raise ValueError(f"yfinance returned empty info for {ticker}")

        result["name"] = info.get("shortName") or info.get("longName")
        result["price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        result["pe"] = info.get("trailingPE")
        result["forward_pe"] = info.get("forwardPE")
        result["market_cap"] = info.get("marketCap")
        result["ev_ebitda"] = info.get("enterpriseToEbitda")

        # Dividend yield — yfinance may return as percentage (e.g. 2.72) or
        # decimal (e.g. 0.027) depending on version. Normalize to percentage.
        dy = info.get("dividendYield")
        if dy is not None:
            result["div_yield"] = dy if dy > 1 else dy * 100

        result["high_52w"] = info.get("fiftyTwoWeekHigh")
        result["low_52w"] = info.get("fiftyTwoWeekLow")

        time.sleep(sleep_sec)

    except Exception as e:
        result["error"] = str(e)

    return result


def fetch_benchmark_performance(sleep_sec: float = 0.3) -> dict:
    """Fetch XLE and SPY prices + 1-month relative performance."""
    result = {}
    prices_1m = {}

    for name, symbol in BENCHMARK_SYMBOLS.items():
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period="3mo")
            if hist.empty:
                result[name] = {"error": f"No data for {symbol}"}
                continue

            current = float(hist["Close"].iloc[-1])

            # 1-month return
            mom_return = None
            if len(hist) >= 22:
                prev_month = float(hist["Close"].iloc[-23])
                if prev_month > 0:
                    mom_return = (current - prev_month) / prev_month * 100

            result[name] = {
                "price": current,
                "mom_return_pct": mom_return,
            }
            prices_1m[name] = mom_return
            time.sleep(sleep_sec)

        except Exception as e:
            result[name] = {"error": str(e)}

    # XLE vs SPY relative 1-month performance
    xle_ret = prices_1m.get("XLE")
    spy_ret = prices_1m.get("SPY")
    if xle_ret is not None and spy_ret is not None:
        result["XLE_vs_SPY_1m_pct"] = xle_ret - spy_ret
    else:
        result["XLE_vs_SPY_1m_pct"] = None

    return result


def fetch_all_data(tickers: list, sleep_sec: float = 0.3) -> dict:
    """Aggregate all data into a single dict."""
    print("[INFO] Fetching commodity prices...")
    commodities = fetch_commodity_prices(sleep_sec)

    print("[INFO] Fetching benchmark data (XLE, SPY)...")
    benchmarks = fetch_benchmark_performance(sleep_sec)

    stocks = {}
    for t in tickers:
        print(f"[INFO] Fetching stock snapshot for {t}...")
        stocks[t.upper()] = fetch_stock_snapshot(t, sleep_sec)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "commodities": commodities,
        "benchmarks": benchmarks,
        "stocks": stocks,
    }


# =======================================
#  Signal Computation
# =======================================

def _get_indicator_value(data: dict, indicator: str) -> Optional[float]:
    """Extract indicator value from aggregated data."""
    commodities = data.get("commodities", {})
    stocks = data.get("stocks", {})
    benchmarks = data.get("benchmarks", {})

    if indicator == "WTI_price":
        wti = commodities.get("WTI", {})
        return wti.get("price")

    if indicator == "WTI_wow_pct":
        wti = commodities.get("WTI", {})
        return wti.get("wow_pct")

    if indicator == "NatGas_price":
        ng = commodities.get("NatGas", {})
        return ng.get("price")

    if indicator == "XOM_pe":
        xom = stocks.get("XOM", {})
        return xom.get("pe")

    if indicator == "XOM_div_yield":
        xom = stocks.get("XOM", {})
        return xom.get("div_yield")

    if indicator == "XOM_dist_52w_low":
        xom = stocks.get("XOM", {})
        price = xom.get("price")
        low = xom.get("low_52w")
        if price is not None and low is not None and low > 0:
            return (price - low) / low * 100
        return None

    if indicator == "XOM_dist_52w_high":
        xom = stocks.get("XOM", {})
        price = xom.get("price")
        high = xom.get("high_52w")
        if price is not None and high is not None and high > 0:
            return (high - price) / high * 100
        return None

    if indicator == "XLE_vs_SPY_1m":
        return benchmarks.get("XLE_vs_SPY_1m_pct")

    return None


def compute_signals(data: dict) -> list:
    """Compute all signals based on current data and thresholds.

    Returns list of dicts: {id, indicator, value, direction, threshold, severity, message}
    """
    signals = []

    for sig_id, indicator, buy_op, buy_thresh, sell_op, sell_thresh, severity in SIGNALS_CONFIG:
        value = _get_indicator_value(data, indicator)
        if value is None:
            continue

        # Check buy signal
        if buy_op is not None and buy_thresh is not None:
            triggered = False
            if buy_op == "<" and value < buy_thresh:
                triggered = True
            elif buy_op == ">" and value > buy_thresh:
                triggered = True

            if triggered:
                signals.append({
                    "id": sig_id,
                    "indicator": indicator,
                    "value": value,
                    "direction": "BUY",
                    "threshold": f"{buy_op}{buy_thresh}",
                    "severity": severity,
                    "message": _format_signal_message(indicator, value, "BUY", buy_op, buy_thresh),
                })

        # Check sell signal
        if sell_op is not None and sell_thresh is not None:
            triggered = False
            if sell_op == "<" and value < sell_thresh:
                triggered = True
            elif sell_op == ">" and value > sell_thresh:
                triggered = True

            if triggered:
                signals.append({
                    "id": sig_id,
                    "indicator": indicator,
                    "value": value,
                    "direction": "SELL",
                    "threshold": f"{sell_op}{sell_thresh}",
                    "severity": severity,
                    "message": _format_signal_message(indicator, value, "SELL", sell_op, sell_thresh),
                })

    return signals


def _format_signal_message(indicator: str, value: float, direction: str, op: str, threshold: float) -> str:
    """Create human-readable signal message."""
    labels = {
        "WTI_price": "WTI Oil Price",
        "WTI_wow_pct": "WTI Week-over-Week Change",
        "NatGas_price": "Natural Gas Price",
        "XOM_pe": "XOM P/E Ratio",
        "XOM_div_yield": "XOM Dividend Yield",
        "XOM_dist_52w_low": "XOM Distance from 52w Low",
        "XOM_dist_52w_high": "XOM Distance from 52w High",
        "XLE_vs_SPY_1m": "XLE vs SPY 1-Month Relative",
    }
    label = labels.get(indicator, indicator)

    units = {
        "WTI_price": "$",
        "NatGas_price": "$",
        "XOM_pe": "x",
        "XOM_div_yield": "%",
        "XOM_dist_52w_low": "%",
        "XOM_dist_52w_high": "%",
        "WTI_wow_pct": "%",
        "XLE_vs_SPY_1m": "%",
    }
    unit = units.get(indicator, "")
    prefix = "$" if unit == "$" else ""
    suffix = unit if unit != "$" else ""

    return f"{label}: {prefix}{value:.1f}{suffix} (threshold: {op}{threshold}{suffix} for {direction.lower()})"


# =======================================
#  Alerts (macOS Notification)
# =======================================

def send_macos_notification(title: str, message: str):
    """Send a native macOS notification via osascript."""
    # Escape double quotes for AppleScript
    safe_msg = message.replace('"', '\\"')
    safe_title = title.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}" sound name "Glass"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    except Exception as e:
        print(f"[WARN] Failed to send notification: {e}")


def send_alert(signals: list):
    """Filter HIGH severity signals and send macOS notification."""
    high_signals = [s for s in signals if s["severity"] == "HIGH"]
    if not high_signals:
        return

    lines = []
    for s in high_signals:
        icon = "\U0001f534" if s["direction"] == "SELL" else "\U0001f7e2"
        lines.append(f"{icon} {s['direction']}: {s['message']}")

    # macOS notification has limited text, keep it concise
    summary = f"{len(high_signals)} HIGH signal(s) triggered"
    detail = "; ".join(f"{s['direction']}:{s['indicator']}" for s in high_signals)

    send_macos_notification("Energy Monitor", f"{summary}: {detail}")
    print(f"[ALERT] Sent notification for {len(high_signals)} HIGH signal(s)")


# =======================================
#  Output: Weekly Snapshots CSV
# =======================================

def save_weekly_snapshot(data: dict, signals: list):
    """Append a row to weekly_snapshots.csv with current data."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, "weekly_snapshots.csv")

    commodities = data.get("commodities", {})
    stocks = data.get("stocks", {})
    benchmarks = data.get("benchmarks", {})

    wti = commodities.get("WTI", {})
    brent = commodities.get("Brent", {})
    natgas = commodities.get("NatGas", {})
    xom = stocks.get("XOM", {})
    cvx = stocks.get("CVX", {})
    xle = benchmarks.get("XLE", {})
    spy = benchmarks.get("SPY", {})

    signal_strs = [f"{s['direction']}:{s['indicator']}" for s in signals]

    row = {
        "Date": data["date"],
        "WTI": _fv(wti.get("price")),
        "Brent": _fv(brent.get("price")),
        "NatGas": _fv(natgas.get("price")),
        "WTI_WoW%": _fv(wti.get("wow_pct")),
        "XOM_Price": _fv(xom.get("price")),
        "XOM_PE": _fv(xom.get("pe")),
        "XOM_FwdPE": _fv(xom.get("forward_pe")),
        "XOM_DivYield%": _fv(xom.get("div_yield")),
        "XOM_52wHigh": _fv(xom.get("high_52w")),
        "XOM_52wLow": _fv(xom.get("low_52w")),
        "CVX_Price": _fv(cvx.get("price")),
        "CVX_PE": _fv(cvx.get("pe")),
        "CVX_DivYield%": _fv(cvx.get("div_yield") if isinstance(cvx, dict) else None),
        "XLE_Price": _fv(xle.get("price") if isinstance(xle, dict) else None),
        "SPY_Price": _fv(spy.get("price") if isinstance(spy, dict) else None),
        "XLE_vs_SPY_1m%": _fv(benchmarks.get("XLE_vs_SPY_1m_pct")),
        "Signal_Count": len(signals),
        "Signals": ";".join(signal_strs) if signal_strs else "",
    }

    fieldnames = list(row.keys())
    write_header = not os.path.exists(csv_path)

    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(f"[Saved] {csv_path}")


def _fv(val) -> str:
    """Format value for CSV."""
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{val:.2f}"
    return str(val)


# =======================================
#  Output: Weekly Markdown Report
# =======================================

def generate_weekly_report(data: dict, signals: list) -> str:
    """Generate a markdown weekly report."""
    date = data["date"]
    commodities = data.get("commodities", {})
    stocks = data.get("stocks", {})
    benchmarks = data.get("benchmarks", {})

    lines = []
    lines.append(f"# Energy Cycle Weekly Report - {date}")
    lines.append("")

    # Commodity Prices table
    lines.append("## Commodity Prices")
    lines.append("")
    lines.append("| Commodity | Price | WoW | MoM | YoY | 52w Range |")
    lines.append("|-----------|-------|-----|-----|-----|-----------|")

    for name in ["WTI", "Brent", "NatGas"]:
        c = commodities.get(name, {})
        if "error" in c:
            lines.append(f"| {name} | Error: {c['error']} | | | | |")
            continue
        price = f"${c.get('price', 0):.2f}" if c.get("price") else "N/A"
        wow = f"{c.get('wow_pct', 0):+.1f}%" if c.get("wow_pct") is not None else "N/A"
        mom = f"{c.get('mom_pct', 0):+.1f}%" if c.get("mom_pct") is not None else "N/A"
        yoy = f"{c.get('yoy_pct', 0):+.1f}%" if c.get("yoy_pct") is not None else "N/A"
        low = c.get("low_52w", 0)
        high = c.get("high_52w", 0)
        range_str = f"${low:.2f} - ${high:.2f}" if low and high else "N/A"
        lines.append(f"| {name} | {price} | {wow} | {mom} | {yoy} | {range_str} |")

    lines.append("")

    # Stock Snapshots table
    lines.append("## Stock Snapshots")
    lines.append("")
    lines.append("| Ticker | Price | P/E | Fwd P/E | Div Yield | EV/EBITDA | 52w Range |")
    lines.append("|--------|-------|-----|---------|-----------|-----------|-----------|")

    for ticker, s in sorted(stocks.items()):
        if s.get("error"):
            lines.append(f"| {ticker} | Error: {s['error']} | | | | | |")
            continue
        price = f"${s.get('price', 0):.2f}" if s.get("price") else "N/A"
        pe = f"{s.get('pe', 0):.1f}x" if s.get("pe") else "N/A"
        fwd_pe = f"{s.get('forward_pe', 0):.1f}x" if s.get("forward_pe") else "N/A"
        div_y = f"{s.get('div_yield', 0):.2f}%" if s.get("div_yield") is not None else "N/A"
        ev_ebitda = f"{s.get('ev_ebitda', 0):.1f}x" if s.get("ev_ebitda") else "N/A"
        low = s.get("low_52w", 0)
        high = s.get("high_52w", 0)
        range_str = f"${low:.2f} - ${high:.2f}" if low and high else "N/A"
        lines.append(f"| {ticker} | {price} | {pe} | {fwd_pe} | {div_y} | {ev_ebitda} | {range_str} |")

    lines.append("")

    # Benchmark performance
    lines.append("## Benchmark Performance")
    lines.append("")
    xle = benchmarks.get("XLE", {})
    spy = benchmarks.get("SPY", {})
    rel = benchmarks.get("XLE_vs_SPY_1m_pct")

    if isinstance(xle, dict) and "price" in xle:
        xle_mom = f"{xle.get('mom_return_pct', 0):+.1f}%" if xle.get("mom_return_pct") is not None else "N/A"
        lines.append(f"- **XLE**: ${xle['price']:.2f} (1m: {xle_mom})")
    if isinstance(spy, dict) and "price" in spy:
        spy_mom = f"{spy.get('mom_return_pct', 0):+.1f}%" if spy.get("mom_return_pct") is not None else "N/A"
        lines.append(f"- **SPY**: ${spy['price']:.2f} (1m: {spy_mom})")
    if rel is not None:
        lines.append(f"- **XLE vs SPY (1m)**: {rel:+.1f}%")

    lines.append("")

    # Signals section
    lines.append("## Signals")
    lines.append("")

    if not signals:
        lines.append("No signals triggered this week.")
    else:
        for s in signals:
            sev = s["severity"]
            direction = s["direction"]
            if sev == "HIGH":
                icon = "\U0001f534" if direction == "SELL" else "\U0001f7e2"
                label = f"{direction} SIGNAL"
            elif sev == "MEDIUM":
                icon = "\U0001f7e1"
                label = "CAUTION"
            else:
                icon = "\U0001f535"
                label = "NOTE"
            lines.append(f"- {icon} **{label}**: {s['message']}")

    lines.append("")

    # Cycle assessment
    lines.append("## Cycle Assessment")
    lines.append("")
    assessment = _assess_cycle(data, signals)
    lines.append(assessment)
    lines.append("")

    return "\n".join(lines)


def _assess_cycle(data: dict, signals: list) -> str:
    """Generate a brief cycle phase assessment based on signals and data."""
    commodities = data.get("commodities", {})
    stocks = data.get("stocks", {})

    wti_price = commodities.get("WTI", {}).get("price")
    xom_pe = stocks.get("XOM", {}).get("pe")
    xom_div = stocks.get("XOM", {}).get("div_yield")

    buy_count = sum(1 for s in signals if s["direction"] == "BUY")
    sell_count = sum(1 for s in signals if s["direction"] == "SELL")

    parts = []

    # Determine cycle phase
    if buy_count > sell_count and buy_count >= 2:
        parts.append("**Phase**: EARLY CYCLE / BOTTOM")
        parts.append("Multiple buy signals suggest energy sector is near cyclical lows.")
    elif sell_count > buy_count and sell_count >= 2:
        parts.append("**Phase**: LATE CYCLE / TOP")
        parts.append("Multiple sell signals suggest energy sector may be overvalued.")
    elif buy_count > 0 or sell_count > 0:
        parts.append("**Phase**: MID CYCLE / TRANSITION")
        parts.append("Mixed signals — sector in transition. Monitor closely.")
    else:
        parts.append("**Phase**: MID CYCLE / NEUTRAL")
        parts.append("No signals triggered. Sector appears fairly valued.")

    # Add context
    if wti_price is not None:
        if wti_price < 50:
            parts.append(f"Oil at ${wti_price:.0f} — below historical mid-cycle range.")
        elif wti_price > 85:
            parts.append(f"Oil at ${wti_price:.0f} — above historical mid-cycle range.")
        else:
            parts.append(f"Oil at ${wti_price:.0f} — within normal mid-cycle range ($50-85).")

    if xom_pe is not None:
        parts.append(f"XOM P/E at {xom_pe:.1f}x (cycle range: 8-35x).")

    if xom_div is not None:
        parts.append(f"XOM dividend yield at {xom_div:.2f}% (buy >4.5%, sell <2.5%).")

    return "\n".join(parts)


def save_weekly_report(report: str, date_str: str):
    """Save markdown report to output/energy_cycle/weekly_YYYY-MM-DD.md."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"weekly_{date_str}.md")
    with open(path, "w") as f:
        f.write(report)
    print(f"[Saved] {path}")


# =======================================
#  Scheduling: launchd
# =======================================

def install_launchd():
    """Generate and install a macOS launchd plist for weekly runs."""
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
            "Weekday": 0,  # Sunday
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
    print(f"     Schedule: Every Sunday at 10:00")
    print(f"     Log: {log_path}")
    print(f"     To verify: launchctl list | grep energy-monitor")


def uninstall_launchd():
    """Unload and remove launchd plist."""
    if os.path.exists(PLIST_PATH):
        subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)
        os.remove(PLIST_PATH)
        print(f"[OK] Uninstalled launchd job: {PLIST_LABEL}")
    else:
        print(f"[INFO] Plist not found: {PLIST_PATH}")


# =======================================
#  Main
# =======================================

def run(tickers: list, check_only: bool = False):
    """Main entry: fetch data, compute signals, generate outputs."""
    print(f"{'='*50}")
    print(f"Energy Cycle Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"{'='*50}")

    data = fetch_all_data(tickers)
    signals = compute_signals(data)

    # Print signals to console
    print(f"\n--- Signals ({len(signals)} triggered) ---")
    if not signals:
        print("  No signals triggered.")
    for s in signals:
        sev = s["severity"]
        icon = {"HIGH": "\U0001f534", "MEDIUM": "\U0001f7e1", "LOW": "\U0001f535"}[sev]
        print(f"  {icon} [{sev}] {s['direction']}: {s['message']}")

    if check_only:
        print("\n[--check-only] Skipping file output.")
        return

    # Save outputs
    save_weekly_snapshot(data, signals)
    report = generate_weekly_report(data, signals)
    save_weekly_report(report, data["date"])

    # Send alerts for HIGH signals
    send_alert(signals)

    print(f"\n{'='*50}")
    print("Done.")


def main():
    ap = argparse.ArgumentParser(
        description="Energy cycle passive monitoring tool"
    )
    ap.add_argument("--tickers", default=",".join(DEFAULT_TICKERS),
                    help=f"Comma-separated tickers to monitor (default: {','.join(DEFAULT_TICKERS)})")
    ap.add_argument("--check-only", action="store_true",
                    help="Only check signals, do not save files")
    ap.add_argument("--test-alert", action="store_true",
                    help="Send a test macOS notification and exit")
    ap.add_argument("--install", action="store_true",
                    help="Install macOS launchd weekly job")
    ap.add_argument("--uninstall", action="store_true",
                    help="Uninstall macOS launchd weekly job")
    args = ap.parse_args()

    if args.test_alert:
        send_macos_notification(
            "Energy Monitor (Test)",
            "This is a test notification from energy_monitor.py"
        )
        print("[OK] Test notification sent.")
        return

    if args.install:
        install_launchd()
        return

    if args.uninstall:
        uninstall_launchd()
        return

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        print("ERROR: No tickers specified.")
        sys.exit(1)

    run(tickers, check_only=args.check_only)


if __name__ == "__main__":
    main()
