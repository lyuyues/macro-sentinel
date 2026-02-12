#!/usr/bin/env python3
"""Portfolio Performance Analysis: Real account vs SPY vs optimized sell rules.

Reads Fidelity transaction history from two accounts, reconstructs daily positions,
computes TWR performance, and compares against SPY buy-hold and a rule-based
sell strategy (v70/m30 with 15% stop-loss).

Outputs: PDF report + charts to output/analysis/
"""

import os
import sys
import json
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quant.data_loader import load_price_data
from quant.metrics import (
    cagr, max_drawdown, annualized_volatility, sharpe_ratio,
    sortino_ratio, calmar_ratio, compute_alpha_beta,
)

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Constants ────────────────────────────────────────────────────────────────

OUTPUT_DIR = "output/analysis/portfolio"
PDF_PATH = "output/analysis/Portfolio_Performance_Report.pdf"
FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"

SKIP_SYMBOLS = {"SPAXX", "FDRXX", "QPISQ"}
TICKER_MAP = {
    "67901108": "GOLD",  # Barrick Gold (old CUSIP before rename)
    "B": "GOLD",         # Barrick Mining (renamed from Barrick Gold May 2025)
    "BRKB": "BRK-B",
}

# Initial positions from ~2021 Q4 Fidelity statement snapshot
# These are positions that existed BEFORE the transaction history starts
# NOTE: Shares and cost basis are SPLIT-ADJUSTED to match yfinance adjusted prices.
# - GOOGL: 20-for-1 split July 2022 (user gave 1 pre-split share -> 20 post-split)
# - GOLD: 2-for-1 split June 2022 (150.4 pre-split -> 300.8 post-split)
# - FTNT: 5-for-1 split June 2022 (20 pre-split -> 100 post-split)
INITIAL_POSITIONS = {
    "JETS": {"shares": 40, "cost_basis": 543.0},
    "ITA":  {"shares": 70.5, "cost_basis": 5923.0},
    "VDE":  {"shares": 103.7, "cost_basis": 4632.0},
    "GOOGL": {"shares": 20, "cost_basis": 1700.0},     # already post-split adjusted
    "GOLD": {"shares": 300.8, "cost_basis": 3979.0},   # 150.4 * 2 (2:1 split)
    "BA":   {"shares": 41, "cost_basis": 8374.0},
    "CCL":  {"shares": 650, "cost_basis": 11858.0},
    "DAL":  {"shares": 540, "cost_basis": 12865.0},
    "XOM":  {"shares": 125.2, "cost_basis": 5305.0},
    "FTNT": {"shares": 100, "cost_basis": 2575.0},     # 20 * 5 (5:1 split)
    "MSFT": {"shares": 265.8, "cost_basis": 48661.0},
    "WFC":  {"shares": 513.1, "cost_basis": 15245.0},
}
INITIAL_SNAPSHOT_DATE = pd.Timestamp("2021-10-01")  # approximate snapshot date


# ── Part 1: Data Parsing ─────────────────────────────────────────────────────

def parse_action(action_str: str) -> str:
    action_str = str(action_str).upper()
    if "YOU BOUGHT" in action_str or "ESPP" in action_str:
        return "buy"
    elif "YOU SOLD" in action_str:
        return "sell"
    elif "DIVIDEND RECEIVED" in action_str:
        return "dividend"
    elif "REINVESTMENT" in action_str:
        return "reinvestment"
    elif "ELECTRONIC FUNDS TRANSFER RECEIVED" in action_str:
        return "deposit"
    elif "ELECTRONIC FUNDS TRANSFER PAID" in action_str:
        return "withdrawal"
    elif "CONTRIBUTIONS" in action_str:
        return "contribution"
    elif "CO CONTR" in action_str:
        return "employer_contribution"
    elif "CONVERSION SHARES DEPOSITED" in action_str:
        return "transfer_in"
    elif "MARGIN INTEREST" in action_str:
        return "margin_interest"
    elif "REDEMPTION FROM CORE" in action_str or "PURCHASE INTO CORE" in action_str:
        return "money_market"
    elif "NAME CHANGED" in action_str:
        return "rename"
    elif "JOURNALED" in action_str:
        return "journal"
    else:
        return "other"


def load_trades(filepath: str, account_name: str, account_filter: str = None) -> pd.DataFrame:
    """Load Fidelity transaction export and return standardized trades."""
    df = pd.read_excel(filepath)
    df["date"] = pd.to_datetime(df["Run Date"], format="%m/%d/%Y")
    df["action_type"] = df["Action"].apply(parse_action)
    df["ticker"] = df["Symbol"].apply(
        lambda x: TICKER_MAP.get(str(x), str(x)) if pd.notna(x) else None
    )
    if account_filter and "Account" in df.columns:
        df = df[df["Account"] == account_filter].copy()

    # Build standardized trades list
    trades = []
    for _, row in df.iterrows():
        action = row["action_type"]
        ticker = row["ticker"]
        if ticker in SKIP_SYMBOLS or ticker is None:
            continue
        if action in ("money_market", "rename", "journal", "other",
                      "contribution", "employer_contribution", "deposit",
                      "withdrawal", "margin_interest", "dividend"):
            # For dividends, record them for cash flow but not as position changes
            if action == "dividend":
                amt = row.get("Amount", 0) or 0
                if amt != 0:
                    trades.append({
                        "date": row["date"],
                        "ticker": ticker,
                        "action": "dividend",
                        "shares": 0,
                        "price": 0,
                        "amount": float(amt),
                        "account": account_name,
                    })
            elif action == "deposit":
                amt = row.get("Amount", 0) or 0
                if amt != 0:
                    trades.append({
                        "date": row["date"],
                        "ticker": "CASH",
                        "action": "deposit",
                        "shares": 0,
                        "price": 0,
                        "amount": float(amt),
                        "account": account_name,
                    })
            continue

        qty = row.get("Quantity", 0)
        qty = float(qty) if pd.notna(qty) else 0.0
        price = row.get("Price", 0)
        price = float(price) if pd.notna(price) else 0.0
        amount = row.get("Amount", 0)
        amount = float(amount) if pd.notna(amount) else 0.0

        if action == "buy" and qty > 0:
            trades.append({
                "date": row["date"],
                "ticker": ticker,
                "action": "buy",
                "shares": qty,
                "price": price,
                "amount": abs(amount),
                "account": account_name,
            })
        elif action == "sell" and qty < 0:
            trades.append({
                "date": row["date"],
                "ticker": ticker,
                "action": "sell",
                "shares": abs(qty),
                "price": price,
                "amount": abs(amount),
                "account": account_name,
            })
        elif action == "reinvestment" and qty > 0:
            cost = abs(amount) if amount != 0 else abs(price * qty)
            trades.append({
                "date": row["date"],
                "ticker": ticker,
                "action": "reinvestment",
                "shares": qty,
                "price": price,
                "amount": cost,
                "account": account_name,
            })
        elif action == "transfer_in" and qty != 0:
            fmv = abs(amount) if amount != 0 else abs(price * qty)
            trades.append({
                "date": row["date"],
                "ticker": ticker,
                "action": "transfer_in",
                "shares": abs(qty),
                "price": price,
                "amount": fmv,
                "account": account_name,
            })

    return pd.DataFrame(trades)


def get_all_tickers(trades_df: pd.DataFrame) -> list:
    """Get all unique tickers from trades and initial positions."""
    tickers = set(trades_df[trades_df["ticker"] != "CASH"]["ticker"].unique())
    tickers.update(INITIAL_POSITIONS.keys())
    return sorted(tickers)


def load_all_prices(tickers: list, start: str = "2021-01-01",
                    end: str = "2026-02-15") -> pd.DataFrame:
    """Load price data for all tickers plus SPY."""
    all_tickers = list(set(tickers + ["SPY"]))
    prices = load_price_data(all_tickers, start=start, end=end, use_cache=True)
    prices = prices.ffill()
    return prices


# ── Part 2: Position Reconstruction & TWR ─────────────────────────────────────

def reconstruct_daily_positions(trades_df: pd.DataFrame,
                                 prices: pd.DataFrame,
                                 include_initial: bool = True) -> tuple:
    """Reconstruct daily share counts from trades.

    Returns:
        positions_df: DataFrame with (date, ticker) -> shares
        cash_flows: list of (date, amount) for TWR sub-periods
                    negative = money flowing INTO portfolio
        cost_basis: dict {ticker: total cost basis}
    """
    # Sort trades chronologically
    trades = trades_df.sort_values("date").reset_index(drop=True)

    # Determine date range
    if include_initial:
        start_date = INITIAL_SNAPSHOT_DATE
    else:
        trade_dates = trades["date"]
        start_date = trade_dates.min() if len(trade_dates) > 0 else prices.index[0]

    end_date = prices.index[-1]
    all_dates = prices.index[(prices.index >= start_date) & (prices.index <= end_date)]

    # Initialize positions from snapshot
    current_shares = {}
    cost_basis = {}
    if include_initial:
        for ticker, pos in INITIAL_POSITIONS.items():
            current_shares[ticker] = pos["shares"]
            cost_basis[ticker] = pos["cost_basis"]

    # Track external cash flows for TWR (date, amount)
    # Negative = money in, positive = money out
    cash_flows = []

    # Process trades day by day
    tickers_seen = set(current_shares.keys())
    daily_shares = {}

    trade_by_date = trades.groupby("date")

    for date in all_dates:
        # Process any trades on this date
        if date in trade_by_date.groups:
            day_trades = trade_by_date.get_group(date)
            for _, t in day_trades.iterrows():
                ticker = t["ticker"]
                if ticker == "CASH":
                    if t["action"] == "deposit":
                        cash_flows.append((date, -abs(t["amount"])))
                    continue

                tickers_seen.add(ticker)

                if t["action"] == "buy":
                    current_shares[ticker] = current_shares.get(ticker, 0) + t["shares"]
                    cost_basis[ticker] = cost_basis.get(ticker, 0) + t["amount"]
                    cash_flows.append((date, -t["amount"]))

                elif t["action"] == "sell":
                    old_shares = current_shares.get(ticker, 0)
                    sell_shares = min(t["shares"], old_shares)
                    if old_shares > 0:
                        frac = sell_shares / old_shares
                        cost_basis[ticker] = cost_basis.get(ticker, 0) * (1 - frac)
                    current_shares[ticker] = old_shares - sell_shares
                    cash_flows.append((date, t["amount"]))
                    if current_shares[ticker] < 0.01:
                        current_shares[ticker] = 0

                elif t["action"] == "reinvestment":
                    current_shares[ticker] = current_shares.get(ticker, 0) + t["shares"]
                    cost_basis[ticker] = cost_basis.get(ticker, 0) + t["amount"]
                    # DRIP is not external cash flow — it's internal reinvestment

                elif t["action"] == "transfer_in":
                    current_shares[ticker] = current_shares.get(ticker, 0) + t["shares"]
                    cost_basis[ticker] = cost_basis.get(ticker, 0) + t["amount"]
                    cash_flows.append((date, -t["amount"]))

        # Record end-of-day positions
        daily_shares[date] = dict(current_shares)

    # Convert to DataFrame
    positions_df = pd.DataFrame(daily_shares).T
    positions_df.index.name = "date"
    positions_df = positions_df.fillna(0)

    return positions_df, cash_flows, cost_basis


def compute_portfolio_nav(positions_df: pd.DataFrame,
                          prices: pd.DataFrame) -> pd.Series:
    """Compute daily portfolio NAV (market value of all positions)."""
    common_dates = positions_df.index.intersection(prices.index)
    nav = pd.Series(0.0, index=common_dates, name="NAV")

    for date in common_dates:
        total = 0.0
        for ticker in positions_df.columns:
            shares = positions_df.loc[date, ticker]
            if shares > 0 and ticker in prices.columns:
                price = prices.loc[date, ticker]
                if pd.notna(price):
                    total += shares * price
        nav[date] = total

    return nav


def compute_twr(nav: pd.Series, cash_flows: list) -> pd.Series:
    """Compute Time-Weighted Return series.

    Splits NAV at each cash flow point into sub-periods,
    computes holding-period return for each, and chains them.
    """
    if len(nav) < 2:
        return pd.Series(dtype=float)

    # Sort cash flows by date
    cf_dates = sorted(set(d for d, _ in cash_flows if d in nav.index))

    # Build sub-period returns
    twr = pd.Series(1.0, index=nav.index, name="TWR")

    # Simple approach: daily returns adjusted for cash flows
    # On cash flow days, adjust the beginning NAV
    prev_nav = nav.iloc[0]
    cumulative = 1.0

    for i in range(1, len(nav)):
        date = nav.index[i]
        prev_date = nav.index[i - 1]

        # Sum cash flows on this date
        day_cf = sum(amt for d, amt in cash_flows if d == date)

        # Adjusted beginning value = previous NAV + cash flow
        # (cash flow is negative for money in, so adding it increases beginning value)
        adjusted_begin = prev_nav - day_cf  # minus because cf is negative for inflows
        if adjusted_begin > 0:
            daily_return = nav[date] / adjusted_begin
        else:
            daily_return = 1.0

        cumulative *= daily_return
        twr[date] = cumulative
        prev_nav = nav[date]

    return twr


def compute_all_metrics(nav: pd.Series, benchmark_nav: pd.Series = None) -> dict:
    """Compute comprehensive performance metrics from a NAV series."""
    metrics = {
        "total_return": float(nav.iloc[-1] / nav.iloc[0] - 1),
        "cagr": cagr(nav),
        "max_drawdown": max_drawdown(nav),
        "volatility": annualized_volatility(nav),
        "sharpe": sharpe_ratio(nav),
        "sortino": sortino_ratio(nav),
        "calmar": calmar_ratio(nav),
    }
    if benchmark_nav is not None:
        alpha, beta = compute_alpha_beta(nav, benchmark_nav)
        metrics["alpha"] = alpha
        metrics["beta"] = beta
    return metrics


# ── Part 3: Three Scenarios ──────────────────────────────────────────────────

def scenario_actual(trades_df: pd.DataFrame, prices: pd.DataFrame,
                    include_initial: bool = True) -> tuple:
    """Scenario A: Actual portfolio performance."""
    positions, cash_flows, cost_basis = reconstruct_daily_positions(
        trades_df, prices, include_initial=include_initial
    )
    nav = compute_portfolio_nav(positions, prices)
    twr = compute_twr(nav, cash_flows)
    return nav, twr, cash_flows, cost_basis


def scenario_spy_buyhold(cash_flows: list, prices: pd.DataFrame,
                         initial_value: float = 0) -> tuple:
    """Scenario B: Same cash flows invested entirely in SPY.

    Every time money goes in (negative cash flow), buy SPY.
    Every time money goes out (positive cash flow), sell SPY proportionally.
    """
    spy = prices["SPY"].dropna()
    if spy.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    # Sort cash flows chronologically
    sorted_cf = sorted(cash_flows, key=lambda x: x[0])

    # Build SPY positions
    spy_shares = 0.0
    if initial_value > 0:
        # Convert initial portfolio value to SPY shares at start date
        start_date = spy.index[0]
        spy_shares = initial_value / spy[start_date]

    nav = pd.Series(0.0, index=spy.index, name="SPY_NAV")
    cf_dict = {}
    for d, amt in sorted_cf:
        cf_dict.setdefault(d, 0.0)
        cf_dict[d] += amt

    for date in spy.index:
        # Process cash flows for this date
        if date in cf_dict:
            flow = cf_dict[date]
            if flow < 0:
                # Money in — buy SPY
                buy_amount = abs(flow)
                spy_shares += buy_amount / spy[date]
            elif flow > 0:
                # Money out — sell SPY proportionally
                sell_amount = flow
                if spy_shares > 0 and spy[date] > 0:
                    sell_shares = sell_amount / spy[date]
                    spy_shares = max(0, spy_shares - sell_shares)

        nav[date] = spy_shares * spy[date]

    # TWR for SPY
    twr = compute_twr(nav, cash_flows)
    return nav, twr


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def scenario_with_sell_rules(trades_df: pd.DataFrame, prices: pd.DataFrame,
                             include_initial: bool = True,
                             stop_loss_pct: float = 0.15) -> tuple:
    """Scenario C: User's buys unchanged, but with systematic sell rules.

    Rules (v70/m30 optimized):
    1. Stop loss: sell if price drops 15% from cost basis (per-lot weighted avg)
    2. Trend break: sell if price < 200-day SMA AND RSI > 30
    3. Sold proceeds stay as cash (pure reduction strategy)

    Returns nav, twr, sell_log
    """
    trades = trades_df.sort_values("date").reset_index(drop=True)

    # Determine date range
    if include_initial:
        start_date = INITIAL_SNAPSHOT_DATE
    else:
        start_date = trades["date"].min() if len(trades) > 0 else prices.index[0]
    end_date = prices.index[-1]
    all_dates = prices.index[(prices.index >= start_date) & (prices.index <= end_date)]

    # Pre-compute technical indicators for all tickers
    sma200 = {}
    rsi14 = {}
    for ticker in prices.columns:
        sma200[ticker] = compute_sma(prices[ticker], 200)
        rsi14[ticker] = compute_rsi(prices[ticker], 14)

    # Initialize positions
    current_shares = {}
    cost_basis = {}
    cash = 0.0
    cash_flows = []
    sell_log = []

    if include_initial:
        for ticker, pos in INITIAL_POSITIONS.items():
            current_shares[ticker] = pos["shares"]
            cost_basis[ticker] = pos["cost_basis"]

    trade_by_date = trades.groupby("date")
    nav = pd.Series(0.0, index=all_dates, name="RuleSell_NAV")

    for date in all_dates:
        # Process buys from original trades (keep buys unchanged)
        if date in trade_by_date.groups:
            day_trades = trade_by_date.get_group(date)
            for _, t in day_trades.iterrows():
                ticker = t["ticker"]
                if ticker == "CASH":
                    continue

                if t["action"] in ("buy", "transfer_in"):
                    current_shares[ticker] = current_shares.get(ticker, 0) + t["shares"]
                    cost_basis[ticker] = cost_basis.get(ticker, 0) + t["amount"]
                    cash_flows.append((date, -t["amount"]))

                elif t["action"] == "reinvestment":
                    current_shares[ticker] = current_shares.get(ticker, 0) + t["shares"]
                    cost_basis[ticker] = cost_basis.get(ticker, 0) + t["amount"]

                # Skip original sells — we replace them with rule-based sells

        # Check sell rules for each position
        for ticker in list(current_shares.keys()):
            shares = current_shares.get(ticker, 0)
            if shares < 0.01 or ticker not in prices.columns:
                continue

            price = prices.loc[date, ticker] if date in prices.index else np.nan
            if pd.isna(price):
                continue

            avg_cost = cost_basis.get(ticker, 0) / shares if shares > 0 else 0
            should_sell = False
            reason = ""

            # Rule 1: Stop loss
            if avg_cost > 0 and (avg_cost - price) / avg_cost >= stop_loss_pct:
                should_sell = True
                reason = "stop_loss"

            # Rule 2: Trend break (below 200 SMA and RSI > 30)
            if not should_sell and ticker in sma200:
                sma_val = sma200[ticker].get(date, np.nan) if date in sma200[ticker].index else np.nan
                rsi_val = rsi14[ticker].get(date, np.nan) if date in rsi14[ticker].index else np.nan
                if pd.notna(sma_val) and pd.notna(rsi_val):
                    if price < sma_val and rsi_val > 30:
                        should_sell = True
                        reason = "trend_break"

            if should_sell:
                proceeds = shares * price
                sell_log.append({
                    "date": date,
                    "ticker": ticker,
                    "shares": shares,
                    "price": price,
                    "avg_cost": avg_cost,
                    "proceeds": proceeds,
                    "reason": reason,
                    "loss_pct": (price - avg_cost) / avg_cost if avg_cost > 0 else 0,
                })
                cash += proceeds
                cash_flows.append((date, proceeds))
                current_shares[ticker] = 0
                cost_basis[ticker] = 0

        # Compute daily NAV
        total = cash
        for ticker, shares in current_shares.items():
            if shares > 0 and ticker in prices.columns:
                p = prices.loc[date, ticker] if date in prices.index else np.nan
                if pd.notna(p):
                    total += shares * p
        nav[date] = total

    twr = compute_twr(nav, cash_flows)
    return nav, twr, sell_log


# ── Part 4: Per-Stock Analysis ───────────────────────────────────────────────

def per_stock_pnl(trades_df: pd.DataFrame, prices: pd.DataFrame,
                  include_initial: bool = True) -> pd.DataFrame:
    """Compute per-stock PnL summary."""
    # Reconstruct final positions
    positions, _, cost_basis = reconstruct_daily_positions(
        trades_df, prices, include_initial=include_initial
    )

    last_date = positions.index[-1]
    rows = []

    for ticker in positions.columns:
        shares = positions.loc[last_date, ticker]
        cb = cost_basis.get(ticker, 0)

        if shares < 0.01 and cb < 1:
            continue  # skip fully closed positions with no basis

        current_price = 0
        if ticker in prices.columns:
            valid = prices[ticker].dropna()
            if len(valid) > 0:
                current_price = float(valid.iloc[-1])

        market_value = shares * current_price
        gain = market_value - cb
        gain_pct = (gain / cb * 100) if cb > 0 else 0
        avg_cost = cb / shares if shares > 0 else 0

        # Calculate max drawdown for this stock
        if ticker in prices.columns:
            stock_prices = prices[ticker].dropna()
            if len(stock_prices) > 1:
                peak = stock_prices.cummax()
                dd = (peak - stock_prices) / peak
                stock_max_dd = float(dd.max())
            else:
                stock_max_dd = 0
        else:
            stock_max_dd = 0

        status = "HELD" if shares > 0.01 else "CLOSED"

        rows.append({
            "ticker": ticker,
            "shares": round(shares, 2),
            "avg_cost": round(avg_cost, 2),
            "current_price": round(current_price, 2),
            "cost_basis": round(cb, 2),
            "market_value": round(market_value, 2),
            "gain_loss": round(gain, 2),
            "gain_loss_pct": round(gain_pct, 1),
            "max_drawdown": round(stock_max_dd * 100, 1),
            "status": status,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("gain_loss", ascending=False).reset_index(drop=True)
    return df


def stop_loss_analysis(trades_df: pd.DataFrame, prices: pd.DataFrame,
                       include_initial: bool = True,
                       stop_loss_pct: float = 0.15) -> pd.DataFrame:
    """For each stock, determine when a 15% stop-loss would trigger
    and compare holding to current vs selling at trigger."""
    trades = trades_df.sort_values("date").reset_index(drop=True)

    # Build per-ticker cost basis history
    ticker_info = {}
    if include_initial:
        for ticker, pos in INITIAL_POSITIONS.items():
            ticker_info[ticker] = {
                "avg_cost": pos["cost_basis"] / pos["shares"],
                "shares": pos["shares"],
                "first_buy": INITIAL_SNAPSHOT_DATE,
            }

    for _, t in trades.iterrows():
        if t["action"] in ("buy", "transfer_in", "reinvestment") and t["shares"] > 0:
            ticker = t["ticker"]
            if ticker == "CASH":
                continue
            if ticker not in ticker_info:
                ticker_info[ticker] = {"avg_cost": 0, "shares": 0, "first_buy": t["date"]}
            info = ticker_info[ticker]
            total_cost = info["avg_cost"] * info["shares"] + t["amount"]
            info["shares"] += t["shares"]
            info["avg_cost"] = total_cost / info["shares"] if info["shares"] > 0 else 0

    results = []
    for ticker, info in ticker_info.items():
        if ticker not in prices.columns:
            continue
        avg_cost = info["avg_cost"]
        if avg_cost <= 0:
            continue

        # Find first date price drops below stop loss threshold
        stock_prices = prices[ticker].dropna()
        stop_price = avg_cost * (1 - stop_loss_pct)

        trigger_date = None
        trigger_price = None
        for date, price in stock_prices.items():
            if date < info["first_buy"]:
                continue
            if price <= stop_price:
                trigger_date = date
                trigger_price = price
                break

        current_price = float(stock_prices.iloc[-1])
        hold_return = (current_price - avg_cost) / avg_cost

        if trigger_date:
            # What if sold at trigger? Cash just sits.
            sell_return = (trigger_price - avg_cost) / avg_cost
            # Opportunity cost: if reinvested in SPY at trigger
            if "SPY" in prices.columns and trigger_date in prices.index:
                spy_at_trigger = prices.loc[trigger_date, "SPY"]
                spy_now = float(prices["SPY"].dropna().iloc[-1])
                spy_return = (spy_now / spy_at_trigger - 1) if spy_at_trigger > 0 else 0
                combined_return = (1 + sell_return) * (1 + spy_return) - 1
            else:
                spy_return = 0
                combined_return = sell_return
            better = "STOP" if sell_return > hold_return else "HOLD"
        else:
            trigger_price = None
            sell_return = None
            spy_return = None
            combined_return = None
            better = "HOLD (no trigger)"

        results.append({
            "ticker": ticker,
            "avg_cost": round(avg_cost, 2),
            "stop_price": round(stop_price, 2),
            "trigger_date": str(trigger_date.date()) if trigger_date else "Never",
            "trigger_price": round(trigger_price, 2) if trigger_price else None,
            "sell_return": f"{sell_return:.1%}" if sell_return is not None else "N/A",
            "hold_return": f"{hold_return:.1%}",
            "current_price": round(current_price, 2),
            "better_choice": better,
        })

    return pd.DataFrame(results)


# ── Part 5: Charts ───────────────────────────────────────────────────────────

def plot_nav_comparison(nav_actual, nav_spy, nav_rules, output_dir):
    """Plot 3-scenario NAV comparison."""
    fig, ax = plt.subplots(figsize=(14, 7))

    # Normalize all to 100 at start
    start_val_a = nav_actual.iloc[0] if nav_actual.iloc[0] > 0 else 1
    start_val_s = nav_spy.iloc[0] if nav_spy.iloc[0] > 0 else 1
    start_val_r = nav_rules.iloc[0] if nav_rules.iloc[0] > 0 else 1

    ax.plot(nav_actual.index, nav_actual / start_val_a * 100,
            label="Actual Portfolio", color="#2196F3", linewidth=2)
    ax.plot(nav_spy.index, nav_spy / start_val_s * 100,
            label="SPY Buy & Hold", color="#FF9800", linewidth=1.5, linestyle="--")
    ax.plot(nav_rules.index, nav_rules / start_val_r * 100,
            label="With Sell Rules (15% SL + 200MA)", color="#4CAF50",
            linewidth=1.5, linestyle="-.")

    ax.set_title("Portfolio Performance: Three Scenarios (Normalized to 100)", fontsize=14)
    ax.set_ylabel("Normalized Value")
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "nav_comparison.png"), dpi=150)
    plt.close(fig)


def plot_drawdown(nav: pd.Series, label: str, output_dir: str, filename: str):
    """Plot drawdown chart."""
    peak = nav.cummax()
    dd = (nav - peak) / peak * 100

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.fill_between(dd.index, dd.values, 0, color="red", alpha=0.3)
    ax.plot(dd.index, dd.values, color="red", linewidth=0.8)
    ax.set_title(f"Drawdown: {label}", fontsize=12)
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, filename), dpi=150)
    plt.close(fig)


def plot_per_stock_returns(pnl_df: pd.DataFrame, output_dir: str):
    """Bar chart of per-stock returns."""
    if pnl_df.empty:
        return
    df = pnl_df[pnl_df["status"] == "HELD"].copy()
    if df.empty:
        df = pnl_df.copy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # Dollar gain/loss
    colors1 = ["#4CAF50" if g >= 0 else "#F44336" for g in df["gain_loss"]]
    ax1.barh(df["ticker"], df["gain_loss"], color=colors1, alpha=0.8)
    ax1.set_xlabel("Gain/Loss ($)")
    ax1.set_title("Unrealized Gain/Loss by Position ($)")
    ax1.axvline(x=0, color="black", linewidth=0.5)
    ax1.grid(axis="x", alpha=0.3)

    # Percentage return
    colors2 = ["#4CAF50" if g >= 0 else "#F44336" for g in df["gain_loss_pct"]]
    ax2.barh(df["ticker"], df["gain_loss_pct"], color=colors2, alpha=0.8)
    ax2.set_xlabel("Return (%)")
    ax2.set_title("Return by Position (%)")
    ax2.axvline(x=0, color="black", linewidth=0.5)
    ax2.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "per_stock_returns.png"), dpi=150)
    plt.close(fig)


def plot_allocation_pie(pnl_df: pd.DataFrame, output_dir: str):
    """Pie chart of current allocation."""
    df = pnl_df[pnl_df["market_value"] > 0].copy()
    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 8))
    total = df["market_value"].sum()
    df["weight"] = df["market_value"] / total * 100

    # Group small positions
    threshold = 2.0  # 2% threshold
    major = df[df["weight"] >= threshold]
    minor = df[df["weight"] < threshold]

    labels = list(major["ticker"])
    sizes = list(major["market_value"])
    if not minor.empty:
        labels.append(f"Others ({len(minor)})")
        sizes.append(minor["market_value"].sum())

    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.1f%%", colors=colors, pctdistance=0.85
    )
    ax.set_title(f"Portfolio Allocation\nTotal: ${total:,.0f}", fontsize=14)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "allocation.png"), dpi=150)
    plt.close(fig)


# ── Part 6: PDF Generation ──────────────────────────────────────────────────

def generate_pdf(pnl_z, pnl_y, metrics_actual, metrics_spy, metrics_rules,
                 sl_analysis, sell_log, output_dir):
    """Generate comprehensive PDF report."""
    from fpdf import FPDF

    class ReportPDF(FPDF):
        def __init__(self):
            super().__init__()
            self.add_font("CJK", "", FONT_PATH)
            self.add_font("CJK", "B", FONT_PATH)
            self.add_font("CJK", "I", FONT_PATH)

        def header(self):
            if self.page_no() > 1:
                self.set_font("CJK", "I", 7)
                self.set_text_color(150, 150, 150)
                self.cell(95, 5, "Portfolio Performance Report", align="L")
                self.cell(95, 5, f"Page {self.page_no()}", align="R")
                self.ln(8)

        def chapter_title(self, title):
            self.set_font("CJK", "B", 16)
            self.set_text_color(20, 50, 100)
            self.multi_cell(0, 10, title)
            y = self.get_y()
            self.set_draw_color(20, 50, 100)
            self.set_line_width(0.8)
            self.line(10, y, 200, y)
            self.set_line_width(0.2)
            self.ln(5)

        def section_title(self, title):
            self.set_font("CJK", "B", 13)
            self.set_text_color(30, 70, 130)
            self.multi_cell(0, 8, title)
            self.ln(2)

        def sub_section(self, title):
            self.set_font("CJK", "B", 11)
            self.set_text_color(60, 60, 60)
            self.multi_cell(0, 7, title)
            self.ln(1)

        def body(self, text):
            self.set_font("CJK", "", 9.5)
            self.set_text_color(30, 30, 30)
            self.multi_cell(0, 5, text)
            self.ln(2)

        def bold_body(self, text):
            self.set_font("CJK", "B", 9.5)
            self.set_text_color(30, 30, 30)
            self.multi_cell(0, 5, text)
            self.ln(2)

        def bullet(self, text):
            self.set_font("CJK", "", 9.5)
            self.set_text_color(30, 30, 30)
            x = self.get_x()
            self.set_x(x + 4)
            self.multi_cell(0, 5, "- " + text)
            self.ln(0.5)

        def table(self, headers, rows, col_widths=None):
            if col_widths is None:
                col_widths = [190 / len(headers)] * len(headers)
            needed = 8 + len(rows) * 6 + 5
            if self.get_y() + needed > 270:
                self.add_page()
            self.set_font("CJK", "B", 7.5)
            self.set_fill_color(20, 50, 100)
            self.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
            self.ln()
            self.set_font("CJK", "", 7.5)
            self.set_text_color(30, 30, 30)
            alt = False
            for row in rows:
                if self.get_y() + 6 > 275:
                    self.add_page()
                    self.set_font("CJK", "B", 7.5)
                    self.set_fill_color(20, 50, 100)
                    self.set_text_color(255, 255, 255)
                    for i, h in enumerate(headers):
                        self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
                    self.ln()
                    self.set_font("CJK", "", 7.5)
                    self.set_text_color(30, 30, 30)
                    alt = False
                if alt:
                    self.set_fill_color(240, 243, 250)
                else:
                    self.set_fill_color(255, 255, 255)
                for i, cell in enumerate(row):
                    self.cell(col_widths[i], 6, str(cell), border=1, fill=True, align="C")
                self.ln()
                alt = not alt
            self.ln(3)

        def insight_box(self, label, text, color_rgb=(30, 100, 60)):
            r, g, b = color_rgb
            self.set_fill_color(min(r + 210, 255), min(g + 180, 255), min(b + 210, 255))
            self.set_draw_color(r, g, b)
            self.set_line_width(0.5)
            y = self.get_y()
            self.set_font("CJK", "B", 9)
            lines = len(text) / 45 + 2
            h = max(lines * 5 + 4, 14)
            if y + h > 270:
                self.add_page()
                y = self.get_y()
            self.rect(10, y, 190, h, style="DF")
            self.set_xy(14, y + 2)
            self.set_text_color(r, g, b)
            self.set_font("CJK", "B", 9)
            self.cell(30, 5, label)
            self.set_font("CJK", "", 9)
            self.multi_cell(146, 5, text)
            self.set_y(y + h + 3)
            self.set_line_width(0.2)

        def add_image_safe(self, path, w=190):
            if os.path.exists(path):
                if self.get_y() + 100 > 270:
                    self.add_page()
                self.image(path, x=10, w=w)
                self.ln(5)

    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(10, 10, 10)

    # ── Cover Page ──
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("CJK", "B", 26)
    pdf.set_text_color(20, 50, 100)
    pdf.multi_cell(0, 13, "Portfolio Performance\nAnalysis Report", align="C")
    pdf.ln(5)
    pdf.set_font("CJK", "B", 14)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, "Real Account vs SPY vs Optimized Sell Rules", align="C")
    pdf.ln(15)
    pdf.set_draw_color(20, 50, 100)
    pdf.set_line_width(1)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(15)
    pdf.set_font("CJK", "", 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 7, (
        "Accounts: Z Individual (TOD) + Y (Margin)\n"
        "Period: 2021 Q4 - 2026 Feb\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d')}"
    ), align="C")
    pdf.ln(25)
    pdf.set_font("CJK", "I", 9)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 5, (
        "Disclaimer: This report is for personal reference only. "
        "Past performance does not guarantee future results. "
        "All data sourced from Fidelity transaction history and Yahoo Finance."
    ), align="C")

    # ── Chapter 1: Account Overview ──
    pdf.add_page()
    pdf.chapter_title("Chapter 1: Account Overview")

    # Z Account positions
    pdf.section_title("1.1 Z Account (Individual TOD)")
    if not pnl_z.empty:
        headers = ["Ticker", "Shares", "Avg Cost", "Price", "Cost Basis",
                    "Mkt Value", "Gain/Loss", "G/L %", "Status"]
        rows = []
        for _, r in pnl_z.iterrows():
            rows.append([
                r["ticker"],
                f"{r['shares']:.1f}",
                f"${r['avg_cost']:.2f}",
                f"${r['current_price']:.2f}",
                f"${r['cost_basis']:,.0f}",
                f"${r['market_value']:,.0f}",
                f"${r['gain_loss']:+,.0f}",
                f"{r['gain_loss_pct']:+.1f}%",
                r["status"],
            ])
        cw = [18, 18, 22, 22, 25, 25, 25, 18, 17]
        pdf.table(headers, rows, cw)

        total_cost_z = pnl_z["cost_basis"].sum()
        total_val_z = pnl_z["market_value"].sum()
        total_gain_z = total_val_z - total_cost_z
        ret_z = (total_gain_z / total_cost_z * 100) if total_cost_z > 0 else 0
        pdf.bold_body(
            f"Z Account Total: Cost ${total_cost_z:,.0f} | Value ${total_val_z:,.0f} | "
            f"Gain ${total_gain_z:+,.0f} ({ret_z:+.1f}%)"
        )

    # Y Account positions
    pdf.section_title("1.2 Y Account (Margin)")
    if not pnl_y.empty:
        rows = []
        for _, r in pnl_y.iterrows():
            rows.append([
                r["ticker"],
                f"{r['shares']:.1f}",
                f"${r['avg_cost']:.2f}",
                f"${r['current_price']:.2f}",
                f"${r['cost_basis']:,.0f}",
                f"${r['market_value']:,.0f}",
                f"${r['gain_loss']:+,.0f}",
                f"{r['gain_loss_pct']:+.1f}%",
                r["status"],
            ])
        pdf.table(headers, rows, cw)

        total_cost_y = pnl_y["cost_basis"].sum()
        total_val_y = pnl_y["market_value"].sum()
        total_gain_y = total_val_y - total_cost_y
        ret_y = (total_gain_y / total_cost_y * 100) if total_cost_y > 0 else 0
        pdf.bold_body(
            f"Y Account Total: Cost ${total_cost_y:,.0f} | Value ${total_val_y:,.0f} | "
            f"Gain ${total_gain_y:+,.0f} ({ret_y:+.1f}%)"
        )

    # Combined
    if not pnl_z.empty and not pnl_y.empty:
        combined_cost = total_cost_z + total_cost_y
        combined_val = total_val_z + total_val_y
        combined_gain = combined_val - combined_cost
        combined_ret = (combined_gain / combined_cost * 100) if combined_cost > 0 else 0
        pdf.ln(3)
        pdf.insight_box(
            "Combined:",
            f"Cost ${combined_cost:,.0f} | Value ${combined_val:,.0f} | "
            f"Gain ${combined_gain:+,.0f} ({combined_ret:+.1f}%)",
            (20, 80, 40),
        )

    # ── Chapter 2: Performance Comparison ──
    pdf.add_page()
    pdf.chapter_title("Chapter 2: Three-Scenario Performance Comparison")

    pdf.section_title("2.1 Scenario Definitions")
    pdf.bullet("Scenario A (Actual): Your real trading history as executed")
    pdf.bullet("Scenario B (SPY Buy & Hold): Same cash flows invested entirely in SPY")
    pdf.bullet("Scenario C (With Sell Rules): Your buys unchanged, but with systematic sell rules: "
               "15% stop-loss from cost basis + sell below 200-day MA when RSI > 30")

    pdf.section_title("2.2 Performance Metrics")

    def fmt(v, pct=False):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "N/A"
        if pct:
            return f"{v:.1%}"
        return f"{v:.2f}"

    headers = ["Metric", "Actual", "SPY B&H", "Sell Rules"]
    rows = [
        ["Total Return", fmt(metrics_actual.get("total_return"), True),
         fmt(metrics_spy.get("total_return"), True),
         fmt(metrics_rules.get("total_return"), True)],
        ["CAGR", fmt(metrics_actual.get("cagr"), True),
         fmt(metrics_spy.get("cagr"), True),
         fmt(metrics_rules.get("cagr"), True)],
        ["Max Drawdown", fmt(metrics_actual.get("max_drawdown"), True),
         fmt(metrics_spy.get("max_drawdown"), True),
         fmt(metrics_rules.get("max_drawdown"), True)],
        ["Volatility", fmt(metrics_actual.get("volatility"), True),
         fmt(metrics_spy.get("volatility"), True),
         fmt(metrics_rules.get("volatility"), True)],
        ["Sharpe Ratio", fmt(metrics_actual.get("sharpe")),
         fmt(metrics_spy.get("sharpe")),
         fmt(metrics_rules.get("sharpe"))],
        ["Sortino Ratio", fmt(metrics_actual.get("sortino")),
         fmt(metrics_spy.get("sortino")),
         fmt(metrics_rules.get("sortino"))],
        ["Calmar Ratio", fmt(metrics_actual.get("calmar")),
         fmt(metrics_spy.get("calmar")),
         fmt(metrics_rules.get("calmar"))],
    ]
    pdf.table(headers, rows, [45, 48, 48, 49])

    # NAV comparison chart
    pdf.section_title("2.3 NAV Comparison Chart")
    pdf.add_image_safe(os.path.join(output_dir, "nav_comparison.png"))

    # Drawdown
    pdf.section_title("2.4 Drawdown")
    pdf.add_image_safe(os.path.join(output_dir, "drawdown_actual.png"))

    # ── Chapter 3: Per-Stock Analysis ──
    pdf.add_page()
    pdf.chapter_title("Chapter 3: Per-Stock Gain/Loss Analysis")

    pdf.add_image_safe(os.path.join(output_dir, "per_stock_returns.png"))
    pdf.add_image_safe(os.path.join(output_dir, "allocation.png"))

    # ── Chapter 4: Stop-Loss Analysis ──
    pdf.add_page()
    pdf.chapter_title("Chapter 4: Stop-Loss Simulation")

    pdf.body(
        "For each stock, we check when a 15% stop-loss (from cost basis) would have "
        "triggered, and whether selling at that point would have been better than holding to today."
    )

    if not sl_analysis.empty:
        headers = ["Ticker", "Avg Cost", "Stop @", "Trigger Date",
                    "Trigger $", "Sell Ret", "Hold Ret", "Better"]
        rows = []
        for _, r in sl_analysis.iterrows():
            rows.append([
                r["ticker"],
                f"${r['avg_cost']:.0f}",
                f"${r['stop_price']:.0f}",
                r["trigger_date"],
                f"${r['trigger_price']:.0f}" if r["trigger_price"] else "N/A",
                r["sell_return"],
                r["hold_return"],
                r["better_choice"],
            ])
        pdf.table(headers, rows, [20, 22, 22, 28, 22, 22, 22, 32])

    # ── Chapter 5: Sell Rule Execution Log ──
    if sell_log:
        pdf.add_page()
        pdf.chapter_title("Chapter 5: Sell Rule Execution Log")
        pdf.body(f"Total sell signals triggered: {len(sell_log)}")

        headers = ["Date", "Ticker", "Shares", "Price", "Avg Cost", "Proceeds", "Reason", "Loss %"]
        rows = []
        for s in sell_log[:50]:  # cap at 50 rows
            rows.append([
                str(s["date"].date()) if hasattr(s["date"], "date") else str(s["date"])[:10],
                s["ticker"],
                f"{s['shares']:.1f}",
                f"${s['price']:.2f}",
                f"${s['avg_cost']:.2f}",
                f"${s['proceeds']:,.0f}",
                s["reason"],
                f"{s['loss_pct']:.1%}",
            ])
        pdf.table(headers, rows, [24, 18, 18, 22, 22, 26, 30, 20])

    # ── Chapter 6: Key Findings ──
    pdf.add_page()
    pdf.chapter_title("Chapter 6: Key Findings & Recommendations")

    pdf.section_title("6.1 Portfolio Strengths")
    pdf.bullet("Heavy MSFT/NVDA weighting benefited from AI boom (2023-2025)")
    pdf.bullet("ESPP quarterly buying provided disciplined dollar-cost averaging")
    pdf.bullet("Diversification across tech (MSFT, GOOGL, AAPL), energy (XOM, VDE), "
               "financials (WFC, BRK-B), and aviation (DAL, JETS, ITA)")

    pdf.section_title("6.2 Portfolio Weaknesses")
    pdf.bullet("Pandemic-era positions (CCL, BA) created significant drag")
    pdf.bullet("No systematic sell discipline led to riding drawdowns")
    pdf.bullet("Aviation/travel sector overweight (DAL + JETS + ITA + BA) was high correlation risk")

    pdf.section_title("6.3 Aviation Sector Deep Dive (DAL)")
    pdf.body(
        "DAL (Delta Air Lines) was purchased at ~$23.82 average cost during pandemic lows. "
        "The aviation industry experienced unprecedented disruption from COVID-19:"
    )
    pdf.bullet("2020-2021: Passenger traffic -60%, airlines burned $5-10B/quarter cash")
    pdf.bullet("2021-2022: Gradual recovery, pent-up demand drove load factors back above 80%")
    pdf.bullet("2023-2024: Revenue exceeded pre-COVID levels, but rising fuel costs compressed margins")
    pdf.bullet("2025-2026: Strong profitability, DAL trading near all-time highs")
    pdf.body(
        "Combined with JETS (airline ETF) and ITA (aerospace/defense ETF), "
        "the aviation allocation was ~15-20% of the Z account at cost. "
        "This high-conviction bet on travel recovery paid off significantly."
    )

    pdf.section_title("6.4 Recommendations")
    pdf.bullet("Consider implementing trailing stop-losses (15-20%) for concentrated positions")
    pdf.bullet("The 200-day MA trend filter would have reduced drawdowns in 2022 bear market")
    pdf.bullet("DRIP (dividend reinvestment) in high-conviction names compounds well over time")
    pdf.bullet("Position sizing: MSFT concentration risk is high (~40%+ of Z account)")

    # Disclaimer
    pdf.ln(10)
    pdf.set_font("CJK", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4, (
        "This report is for personal reference only. Past performance does not guarantee "
        "future results. All calculations are based on available transaction data and may "
        "contain approximations."
    ), align="C")

    # Save
    os.makedirs(os.path.dirname(PDF_PATH), exist_ok=True)
    pdf.output(PDF_PATH)
    print(f"PDF saved to: {PDF_PATH} ({pdf.page_no()} pages)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("=" * 60)
    print("  Portfolio Performance Analysis")
    print("=" * 60)

    # ── Load trades ──
    print("\n[1/6] Loading transaction data...")
    z_trades = load_trades("input/Zccount.xlsx", "Z_Individual",
                           account_filter="Individual - TOD")
    y_trades = load_trades("input/Yccount.xlsx", "Y_Margin")

    print(f"  Z account: {len(z_trades)} trades")
    print(f"  Y account: {len(y_trades)} trades")

    # Combine for overall analysis
    all_trades = pd.concat([z_trades, y_trades], ignore_index=True)
    all_trades = all_trades.sort_values("date").reset_index(drop=True)

    # ── Load prices ──
    print("\n[2/6] Loading price data...")
    all_tickers = get_all_tickers(all_trades)
    print(f"  Tickers: {all_tickers}")
    prices = load_all_prices(all_tickers, start="2021-01-01", end="2026-02-15")
    print(f"  Price data: {prices.shape[0]} trading days, {prices.shape[1]} tickers")

    # ── Scenario A: Actual portfolio ──
    print("\n[3/6] Computing Scenario A (Actual)...")
    nav_actual, twr_actual, cf_actual, cb_actual = scenario_actual(
        all_trades, prices, include_initial=True
    )
    # Filter out zero-NAV dates at start
    nav_actual = nav_actual[nav_actual > 0]
    twr_actual = twr_actual[twr_actual.index.isin(nav_actual.index)]

    metrics_actual = compute_all_metrics(nav_actual, prices["SPY"])
    print(f"  NAV range: ${nav_actual.iloc[0]:,.0f} -> ${nav_actual.iloc[-1]:,.0f}")
    print(f"  CAGR: {metrics_actual['cagr']:.1%}")
    print(f"  Max DD: {metrics_actual['max_drawdown']:.1%}")
    print(f"  Sharpe: {metrics_actual['sharpe']:.2f}")

    # ── Scenario B: SPY buy & hold ──
    print("\n[4/6] Computing Scenario B (SPY Buy & Hold)...")
    initial_value = nav_actual.iloc[0]
    nav_spy, twr_spy = scenario_spy_buyhold(cf_actual, prices,
                                            initial_value=initial_value)
    # Align to same date range
    common_dates = nav_actual.index.intersection(nav_spy.index)
    nav_spy = nav_spy[common_dates]

    metrics_spy = compute_all_metrics(nav_spy, prices["SPY"])
    print(f"  NAV range: ${nav_spy.iloc[0]:,.0f} -> ${nav_spy.iloc[-1]:,.0f}")
    print(f"  CAGR: {metrics_spy['cagr']:.1%}")

    # ── Scenario C: With sell rules ──
    print("\n[5/6] Computing Scenario C (With Sell Rules)...")
    nav_rules, twr_rules, sell_log = scenario_with_sell_rules(
        all_trades, prices, include_initial=True
    )
    nav_rules = nav_rules[nav_rules > 0]

    metrics_rules = compute_all_metrics(nav_rules, prices["SPY"])
    print(f"  NAV range: ${nav_rules.iloc[0]:,.0f} -> ${nav_rules.iloc[-1]:,.0f}")
    print(f"  CAGR: {metrics_rules['cagr']:.1%}")
    print(f"  Sell signals triggered: {len(sell_log)}")
    for s in sell_log[:10]:
        print(f"    {s['date'].strftime('%Y-%m-%d') if hasattr(s['date'], 'strftime') else s['date']} "
              f"{s['ticker']:>6} {s['reason']:<16} @ ${s['price']:.2f} ({s['loss_pct']:+.1%})")

    # ── Per-stock analysis ──
    print("\n[6/6] Per-stock analysis & report generation...")

    pnl_z = per_stock_pnl(z_trades, prices, include_initial=True)
    pnl_y = per_stock_pnl(y_trades, prices, include_initial=False)

    sl_analysis = stop_loss_analysis(all_trades, prices, include_initial=True)

    # ── Generate charts ──
    print("  Generating charts...")
    plot_nav_comparison(nav_actual, nav_spy, nav_rules, OUTPUT_DIR)
    plot_drawdown(nav_actual, "Actual Portfolio", OUTPUT_DIR, "drawdown_actual.png")
    plot_per_stock_returns(
        pd.concat([pnl_z, pnl_y], ignore_index=True), OUTPUT_DIR
    )
    plot_allocation_pie(
        pd.concat([pnl_z, pnl_y], ignore_index=True), OUTPUT_DIR
    )

    # ── Generate PDF ──
    print("  Generating PDF...")
    generate_pdf(pnl_z, pnl_y, metrics_actual, metrics_spy, metrics_rules,
                 sl_analysis, sell_log, OUTPUT_DIR)

    # ── Save metrics JSON ──
    summary = {
        "generated": datetime.now().isoformat(),
        "scenarios": {
            "actual": {k: round(v, 4) if isinstance(v, float) and not np.isnan(v) else None
                       for k, v in metrics_actual.items()},
            "spy_buyhold": {k: round(v, 4) if isinstance(v, float) and not np.isnan(v) else None
                            for k, v in metrics_spy.items()},
            "sell_rules": {k: round(v, 4) if isinstance(v, float) and not np.isnan(v) else None
                           for k, v in metrics_rules.items()},
        },
        "sell_signals": len(sell_log),
    }
    with open(os.path.join(OUTPUT_DIR, "metrics.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Metrics saved to {OUTPUT_DIR}/metrics.json")

    print("\n" + "=" * 60)
    print("  Analysis complete!")
    print(f"  PDF: {PDF_PATH}")
    print(f"  Charts: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
