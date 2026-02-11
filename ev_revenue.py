#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ev_revenue.py  EV/Revenue 对比估值工具
#
# 用同行公司的 EV/Revenue 中位数，乘以目标公司的收入，推算隐含公允价值。
# 适合尚未盈利、FCF 为负的高增长公司（如 NBIS、IREN 等）。
#
# Usage:
#   python ev_revenue.py --ticker IREN --peers MARA,CLSK,HUT,CORZ,RIOT
#   python ev_revenue.py --ticker NBIS --peers GOOGL,MSFT,AMZN --forward

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# =======================================
#  数据获取：单个公司的 EV/Revenue 指标
# =======================================

def fetch_peer_metrics(ticker: str, sleep_sec: float = 0.3) -> dict:
    """获取单个公司的 EV/Revenue 相关指标。

    优先用 yfinance .info（TTM 数据），失败则 fallback 到 SEC EDGAR。
    """
    result = {
        "ticker": ticker.upper(),
        "name": None,
        "sector": None,
        "revenue": None,
        "ev": None,
        "market_cap": None,
        "price": None,
        "shares": None,
        "debt": None,
        "cash": None,
        "ev_revenue": None,
        "ev_ebitda": None,
        "ebitda": None,
        "gross_margin": None,
        "net_margin": None,
        "fcf_margin": None,
        "revenue_growth": None,
        "forward_revenue": None,
        "ev_forward_revenue": None,
        "data_source": None,
        "error": None,
    }

    # --- Try yfinance first ---
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        info = tk.info

        if not info or info.get("regularMarketPrice") is None:
            raise ValueError("yfinance returned empty info")

        result["name"] = info.get("shortName") or info.get("longName")
        result["sector"] = info.get("sector")
        result["revenue"] = info.get("totalRevenue")
        result["ev"] = info.get("enterpriseValue")
        result["market_cap"] = info.get("marketCap")
        result["price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        result["shares"] = info.get("sharesOutstanding")
        result["debt"] = info.get("totalDebt")
        result["cash"] = info.get("totalCash")
        result["ebitda"] = info.get("ebitda")

        # Margins
        result["gross_margin"] = info.get("grossMargins")
        result["net_margin"] = info.get("profitMargins")
        result["revenue_growth"] = info.get("revenueGrowth")

        # FCF margin
        fcf = info.get("freeCashflow")
        if fcf is not None and result["revenue"] and result["revenue"] > 0:
            result["fcf_margin"] = fcf / result["revenue"]

        # EV/Revenue
        if result["ev"] and result["revenue"] and result["revenue"] > 0:
            result["ev_revenue"] = result["ev"] / result["revenue"]

        # EV/EBITDA
        if result["ev"] and result["ebitda"] and result["ebitda"] > 0:
            result["ev_ebitda"] = result["ev"] / result["ebitda"]

        # Forward revenue estimate
        rev_growth = result["revenue_growth"]
        if rev_growth is not None and result["revenue"] and result["revenue"] > 0:
            result["forward_revenue"] = result["revenue"] * (1 + rev_growth)
            if result["ev"]:
                result["ev_forward_revenue"] = result["ev"] / result["forward_revenue"]

        result["data_source"] = "yfinance"
        time.sleep(sleep_sec)
        return result

    except Exception as yf_err:
        print(f"  [WARN] yfinance failed for {ticker}: {yf_err}, trying SEC EDGAR...")

    # --- Fallback: SEC EDGAR ---
    try:
        from dcf_builder import fetch_company_data, extract_all_financials, _series_from_tags, BASIC_SHARES_TAGS
        from dcf_utils import get_latest_price_stooq, infer_sector_from_facts

        _cik, facts = fetch_company_data(ticker)
        all_data = extract_all_financials(facts)

        # Latest annual values
        revenue_s = all_data["revenue"][0]
        total_debt_s = all_data["total_debt"][0]
        total_cash_s = all_data["total_cash"][0]
        ebitda_s = all_data["ebitda"][0]
        net_income_s = all_data["net_income"][0]
        gross_profit_s = all_data["gross_profit"][0]
        fcf_s = all_data["fcf"][0]

        # Basic shares for market cap
        basic_shares, _, _ = _series_from_tags(facts, BASIC_SHARES_TAGS, unit="shares")
        if basic_shares.empty:
            basic_shares = all_data["shares_outstanding"][0]

        def _latest(s):
            if s is not None and not s.empty:
                return float(s.iloc[-1])
            return None

        rev = _latest(revenue_s)
        debt = _latest(total_debt_s)
        cash = _latest(total_cash_s)
        shares = _latest(basic_shares)
        ebitda = _latest(ebitda_s)
        ni = _latest(net_income_s)
        gp = _latest(gross_profit_s)
        fcf = _latest(fcf_s)

        price = get_latest_price_stooq(ticker)

        result["name"] = facts.get("entityName")
        result["sector"] = infer_sector_from_facts(facts, ticker)
        result["revenue"] = rev
        result["debt"] = debt if debt else 0
        result["cash"] = cash if cash else 0
        result["price"] = price
        result["shares"] = shares
        result["ebitda"] = ebitda

        if shares and price:
            result["market_cap"] = price * shares
            result["ev"] = result["market_cap"] + (debt or 0) - (cash or 0)

        if rev and rev > 0:
            if result["ev"]:
                result["ev_revenue"] = result["ev"] / rev
            if ebitda and ebitda > 0 and result["ev"]:
                result["ev_ebitda"] = result["ev"] / ebitda
            if gp:
                result["gross_margin"] = gp / rev
            if ni:
                result["net_margin"] = ni / rev
            if fcf:
                result["fcf_margin"] = fcf / rev

        # Revenue growth (latest 2 years)
        if len(revenue_s) >= 2:
            prev_rev = float(revenue_s.iloc[-2])
            if prev_rev > 0 and rev:
                result["revenue_growth"] = (rev - prev_rev) / prev_rev

        result["data_source"] = "sec_edgar"
        time.sleep(sleep_sec)
        return result

    except Exception as sec_err:
        result["error"] = f"yfinance: {yf_err}; sec: {sec_err}"
        result["data_source"] = "failed"
        return result


# =======================================
#  隐含估值计算
# =======================================

def compute_implied_valuation(
    target_revenue: float,
    target_debt: float,
    target_cash: float,
    target_shares: float,
    peer_median_ev_revenue: float,
) -> dict:
    """从同行 EV/Revenue 中位数推算隐含价格。"""
    implied_ev = target_revenue * peer_median_ev_revenue
    implied_equity = implied_ev - target_debt + target_cash
    implied_price = implied_equity / target_shares if target_shares and target_shares > 0 else None
    return {
        "implied_ev": implied_ev,
        "implied_equity": implied_equity,
        "implied_price": implied_price,
    }


# =======================================
#  核心：构建对比表 + 估值
# =======================================

def build_ev_revenue_comparison(
    target: str,
    peers: List[str],
    include_forward: bool = False,
    sleep_sec: float = 0.3,
) -> dict:
    """获取所有公司数据，计算同行统计，推算隐含估值。"""
    all_tickers = [target] + peers
    all_metrics = {}
    errors = []

    for t in all_tickers:
        print(f"[INFO] Fetching data for {t}...")
        m = fetch_peer_metrics(t, sleep_sec=sleep_sec)
        all_metrics[t.upper()] = m
        if m["error"]:
            errors.append(f"{t}: {m['error']}")

    target_upper = target.upper()
    target_data = all_metrics[target_upper]

    # Filter valid peers (non-target, has valid EV/Revenue)
    valid_peers = []
    for p in peers:
        p_upper = p.upper()
        m = all_metrics.get(p_upper)
        if not m:
            continue
        if m["error"]:
            continue
        if m["ev_revenue"] is None or not np.isfinite(m["ev_revenue"]):
            errors.append(f"{p}: no valid EV/Revenue ratio")
            continue
        if m["revenue"] is None or m["revenue"] <= 0:
            errors.append(f"{p}: revenue is zero or negative")
            continue
        valid_peers.append(p_upper)

    if len(valid_peers) < 2:
        return {
            "target": target_data,
            "peers": all_metrics,
            "valid_peers": valid_peers,
            "stats": None,
            "valuation": None,
            "forward_valuation": None,
            "errors": errors + ["ERROR: Need at least 2 valid peers for comparison"],
        }

    # Compute peer statistics
    peer_ev_revs = [all_metrics[p]["ev_revenue"] for p in valid_peers]
    peer_ev_ebitdas = [all_metrics[p]["ev_ebitda"] for p in valid_peers if all_metrics[p]["ev_ebitda"] is not None]
    peer_gross_margins = [all_metrics[p]["gross_margin"] for p in valid_peers if all_metrics[p]["gross_margin"] is not None]
    peer_net_margins = [all_metrics[p]["net_margin"] for p in valid_peers if all_metrics[p]["net_margin"] is not None]
    peer_rev_growths = [all_metrics[p]["revenue_growth"] for p in valid_peers if all_metrics[p]["revenue_growth"] is not None]

    stats = {
        "ev_revenue_median": float(np.median(peer_ev_revs)),
        "ev_revenue_mean": float(np.mean(peer_ev_revs)),
        "ev_revenue_min": float(np.min(peer_ev_revs)),
        "ev_revenue_max": float(np.max(peer_ev_revs)),
        "ev_ebitda_median": float(np.median(peer_ev_ebitdas)) if peer_ev_ebitdas else None,
        "gross_margin_median": float(np.median(peer_gross_margins)) if peer_gross_margins else None,
        "net_margin_median": float(np.median(peer_net_margins)) if peer_net_margins else None,
        "revenue_growth_median": float(np.median(peer_rev_growths)) if peer_rev_growths else None,
        "num_valid_peers": len(valid_peers),
    }

    # Implied valuation (trailing revenue)
    valuation = None
    if (target_data["revenue"] and target_data["revenue"] > 0
            and target_data["shares"] and target_data["shares"] > 0):
        debt = target_data["debt"] or 0
        cash = target_data["cash"] or 0
        valuation = compute_implied_valuation(
            target_data["revenue"], debt, cash,
            target_data["shares"], stats["ev_revenue_median"],
        )
        valuation["current_price"] = target_data["price"]
        if valuation["implied_price"] and target_data["price"]:
            valuation["upside_pct"] = (
                (valuation["implied_price"] - target_data["price"])
                / target_data["price"] * 100
            )
        else:
            valuation["upside_pct"] = None

    # Forward valuation
    forward_valuation = None
    if include_forward and target_data["forward_revenue"] and target_data["forward_revenue"] > 0:
        peer_fwd = [all_metrics[p]["ev_forward_revenue"] for p in valid_peers
                     if all_metrics[p].get("ev_forward_revenue") is not None]
        if len(peer_fwd) >= 2:
            fwd_median = float(np.median(peer_fwd))
            debt = target_data["debt"] or 0
            cash = target_data["cash"] or 0
            forward_valuation = compute_implied_valuation(
                target_data["forward_revenue"], debt, cash,
                target_data["shares"], fwd_median,
            )
            forward_valuation["peer_fwd_ev_revenue_median"] = fwd_median
            forward_valuation["current_price"] = target_data["price"]
            if forward_valuation["implied_price"] and target_data["price"]:
                forward_valuation["upside_pct"] = (
                    (forward_valuation["implied_price"] - target_data["price"])
                    / target_data["price"] * 100
                )

    return {
        "target": target_data,
        "peers": {p: all_metrics[p] for p in valid_peers},
        "valid_peers": valid_peers,
        "all_metrics": all_metrics,
        "stats": stats,
        "valuation": valuation,
        "forward_valuation": forward_valuation,
        "errors": errors,
    }


# =======================================
#  输出：CSV
# =======================================

def _fmt(val, fmt_type="number"):
    """Format a value for display."""
    if val is None or (isinstance(val, float) and not np.isfinite(val)):
        return "N/A"
    if fmt_type == "billions":
        return f"{val / 1e9:.2f}"
    if fmt_type == "pct":
        return f"{val * 100:.1f}"
    if fmt_type == "ratio":
        return f"{val:.2f}"
    if fmt_type == "price":
        return f"{val:.2f}"
    return f"{val}"


def save_ev_revenue_csv(result: dict, output_path: str):
    """Save comparison table as CSV."""
    target = result["target"]
    valid_peers = result["valid_peers"]
    all_metrics = result.get("all_metrics", result.get("peers", {}))
    stats = result["stats"]
    valuation = result["valuation"]

    # Column order: Target first, then peers
    tickers = [target["ticker"]] + valid_peers
    labels = [f"{target['ticker']} (Target)"] + valid_peers

    # Build rows
    rows = []

    def _add_row(metric_name, key, fmt_type):
        row = {"Metric": metric_name}
        for i, t in enumerate(tickers):
            m = all_metrics.get(t, target if i == 0 else {})
            if isinstance(m, dict):
                val = m.get(key)
            else:
                val = None
            row[labels[i]] = _fmt(val, fmt_type)
        # Peer stats column
        if stats and key == "ev_revenue":
            row["Peer Stats"] = f"Median: {stats['ev_revenue_median']:.2f}"
        elif stats and key == "ev_ebitda" and stats.get("ev_ebitda_median"):
            row["Peer Stats"] = f"Median: {stats['ev_ebitda_median']:.2f}"
        elif stats and key == "gross_margin" and stats.get("gross_margin_median"):
            row["Peer Stats"] = f"Median: {stats['gross_margin_median'] * 100:.1f}%"
        elif stats and key == "net_margin" and stats.get("net_margin_median"):
            row["Peer Stats"] = f"Median: {stats['net_margin_median'] * 100:.1f}%"
        elif stats and key == "revenue_growth" and stats.get("revenue_growth_median"):
            row["Peer Stats"] = f"Median: {stats['revenue_growth_median'] * 100:.1f}%"
        else:
            row["Peer Stats"] = ""
        rows.append(row)

    _add_row("Company Name", "name", "number")
    _add_row("Data Source", "data_source", "number")
    _add_row("Sector", "sector", "number")
    _add_row("Revenue TTM ($B)", "revenue", "billions")
    _add_row("Enterprise Value ($B)", "ev", "billions")
    _add_row("Market Cap ($B)", "market_cap", "billions")
    _add_row("EV/Revenue", "ev_revenue", "ratio")
    _add_row("EV/EBITDA", "ev_ebitda", "ratio")
    _add_row("Gross Margin (%)", "gross_margin", "pct")
    _add_row("Net Margin (%)", "net_margin", "pct")
    _add_row("FCF Margin (%)", "fcf_margin", "pct")
    _add_row("Revenue Growth (%)", "revenue_growth", "pct")
    _add_row("Price ($)", "price", "price")

    df = pd.DataFrame(rows)
    df = df.set_index("Metric")

    # Add valuation summary rows
    val_rows = []
    val_rows.append("")  # separator
    val_rows.append("--- Implied Valuation ---")

    if valuation and stats:
        val_data = {
            "Peer Median EV/Revenue": f"{stats['ev_revenue_median']:.2f}",
            "Target Revenue ($B)": _fmt(target["revenue"], "billions"),
            "Implied EV ($B)": _fmt(valuation["implied_ev"], "billions"),
            "Implied Equity ($B)": _fmt(valuation["implied_equity"], "billions"),
            "Implied Price ($)": _fmt(valuation["implied_price"], "price"),
            "Current Price ($)": _fmt(valuation["current_price"], "price"),
            "Upside/Downside (%)": _fmt(valuation.get("upside_pct"), "ratio") + "%" if valuation.get("upside_pct") is not None else "N/A",
        }
        for k, v in val_data.items():
            row = {labels[0]: v}
            val_rows.append(row)

    # Write main table + valuation
    with open(output_path, "w") as f:
        df.to_csv(f)
        f.write("\n")
        f.write("Implied Valuation\n")
        if valuation and stats:
            f.write(f"Peer Median EV/Revenue,{stats['ev_revenue_median']:.2f}\n")
            f.write(f"Target Revenue ($B),{_fmt(target['revenue'], 'billions')}\n")
            f.write(f"Implied EV ($B),{_fmt(valuation['implied_ev'], 'billions')}\n")
            f.write(f"Implied Equity ($B),{_fmt(valuation['implied_equity'], 'billions')}\n")
            f.write(f"Implied Price ($),{_fmt(valuation['implied_price'], 'price')}\n")
            f.write(f"Current Price ($),{_fmt(valuation['current_price'], 'price')}\n")
            upside = valuation.get("upside_pct")
            f.write(f"Upside/Downside (%),{upside:.1f}%\n" if upside is not None else "Upside/Downside (%),N/A\n")
        else:
            f.write("Insufficient data for valuation\n")

        # Forward valuation
        fwd = result.get("forward_valuation")
        if fwd:
            f.write("\nForward Implied Valuation\n")
            f.write(f"Peer Median EV/Fwd Revenue,{fwd.get('peer_fwd_ev_revenue_median', 'N/A')}\n")
            f.write(f"Forward Revenue ($B),{_fmt(target.get('forward_revenue'), 'billions')}\n")
            f.write(f"Implied EV ($B),{_fmt(fwd['implied_ev'], 'billions')}\n")
            f.write(f"Implied Price ($),{_fmt(fwd['implied_price'], 'price')}\n")
            fwd_up = fwd.get("upside_pct")
            f.write(f"Upside/Downside (%),{fwd_up:.1f}%\n" if fwd_up is not None else "Upside/Downside (%),N/A\n")

        # Errors
        if result.get("errors"):
            f.write("\nWarnings/Errors\n")
            for e in result["errors"]:
                f.write(f",{e}\n")

    print(f"[Saved] {output_path}")


# =======================================
#  输出：JSON
# =======================================

def save_ev_revenue_json(result: dict, output_path: str):
    """Save metadata as JSON."""
    target = result["target"]
    stats = result["stats"]
    valuation = result["valuation"]
    fwd = result.get("forward_valuation")

    meta = {
        "target_ticker": target["ticker"],
        "target_name": target["name"],
        "peer_tickers": result["valid_peers"],
        "peer_ev_revenue_median": stats["ev_revenue_median"] if stats else None,
        "peer_ev_revenue_mean": stats["ev_revenue_mean"] if stats else None,
        "peer_ev_revenue_min": stats["ev_revenue_min"] if stats else None,
        "peer_ev_revenue_max": stats["ev_revenue_max"] if stats else None,
        "num_valid_peers": stats["num_valid_peers"] if stats else 0,
        "target_revenue": target["revenue"],
        "target_ev": target["ev"],
        "target_ev_revenue": target["ev_revenue"],
        "implied_ev": valuation["implied_ev"] if valuation else None,
        "implied_price": valuation["implied_price"] if valuation else None,
        "current_price": target["price"],
        "upside_pct": valuation.get("upside_pct") if valuation else None,
        "data_source": target["data_source"],
        "timestamp": datetime.now().isoformat(),
        "errors": result.get("errors", []),
    }

    if fwd:
        meta["forward_implied_price"] = fwd.get("implied_price")
        meta["forward_upside_pct"] = fwd.get("upside_pct")

    # Per-peer detail
    meta["peer_details"] = {}
    for p in result["valid_peers"]:
        pm = result["peers"][p]
        meta["peer_details"][p] = {
            "name": pm["name"],
            "ev_revenue": pm["ev_revenue"],
            "ev_ebitda": pm["ev_ebitda"],
            "gross_margin": pm["gross_margin"],
            "net_margin": pm["net_margin"],
            "revenue_growth": pm["revenue_growth"],
            "data_source": pm["data_source"],
        }

    def _json_safe(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(output_path, "w") as f:
        json.dump(meta, f, indent=2, default=_json_safe)
    print(f"[Saved] {output_path}")


# =======================================
#  入口函数
# =======================================

def run_ev_revenue(
    target: str,
    peers: List[str],
    include_forward: bool = False,
    sleep_sec: float = 0.3,
) -> dict:
    """程序入口：获取数据、计算估值、保存文件。"""
    target_upper = target.upper()
    curr_year = pd.Timestamp.now().year
    out_dir = os.path.join("output", target_upper)
    os.makedirs(out_dir, exist_ok=True)

    result = build_ev_revenue_comparison(
        target, peers,
        include_forward=include_forward,
        sleep_sec=sleep_sec,
    )

    base = os.path.join(out_dir, f"{curr_year}_ev_revenue_{target_upper}")
    save_ev_revenue_csv(result, base + ".csv")
    save_ev_revenue_json(result, base + "_meta.json")

    # Print summary
    print(f"\n{'='*50}")
    print(f"EV/Revenue Comparison: {target_upper}")
    print(f"{'='*50}")

    if result["stats"]:
        stats = result["stats"]
        print(f"Valid peers: {len(result['valid_peers'])} ({', '.join(result['valid_peers'])})")
        print(f"Peer EV/Revenue median: {stats['ev_revenue_median']:.2f}")
        print(f"Peer EV/Revenue range: {stats['ev_revenue_min']:.2f} - {stats['ev_revenue_max']:.2f}")

    if result["valuation"]:
        v = result["valuation"]
        print(f"\nTarget EV/Revenue: {result['target']['ev_revenue']:.2f}" if result["target"]["ev_revenue"] else "")
        print(f"Implied Price: ${v['implied_price']:.2f}" if v["implied_price"] else "Implied Price: N/A")
        print(f"Current Price: ${v['current_price']:.2f}" if v["current_price"] else "")
        if v.get("upside_pct") is not None:
            direction = "upside" if v["upside_pct"] > 0 else "downside"
            print(f"{direction.capitalize()}: {v['upside_pct']:.1f}%")

    if result.get("forward_valuation"):
        fwd = result["forward_valuation"]
        print(f"\nForward Implied Price: ${fwd['implied_price']:.2f}" if fwd["implied_price"] else "")

    if result.get("errors"):
        print(f"\nWarnings: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"  - {e}")

    print()
    return result


def main():
    """CLI 入口。"""
    ap = argparse.ArgumentParser(
        description="EV/Revenue 对比估值：用同行倍数推算隐含公允价值"
    )
    ap.add_argument("--ticker", required=True, help="目标公司 ticker")
    ap.add_argument("--peers", required=True, help="逗号分隔的同行股票列表")
    ap.add_argument("--forward", action="store_true",
                    help="额外计算 EV/预测收入（用分析师预测增长率）")
    ap.add_argument("--sleep", type=float, default=0.3,
                    help="API 调用间隔秒数 (默认 0.3)")
    args = ap.parse_args()

    peers = [p.strip().upper() for p in args.peers.split(",") if p.strip()]
    if len(peers) < 2:
        print("ERROR: 至少需要 2 个 peer 公司")
        sys.exit(1)

    run_ev_revenue(
        target=args.ticker,
        peers=peers,
        include_forward=args.forward,
        sleep_sec=args.sleep,
    )


if __name__ == "__main__":
    main()
