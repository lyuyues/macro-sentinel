"""Analyze actual portfolio performance from Fidelity transaction history."""
import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import brentq
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quant.data_loader import load_price_data


# ── Ticker mapping (handle renamed/special symbols) ─────────────────────────
TICKER_MAP = {
    "67901108": "GOLD",   # Barrick Gold (was Barrick Gold, now Barrick Mining)
    "BRKB": "BRK-B",     # Berkshire Hathaway class B
}

# Symbols to skip (money market, not real investments)
SKIP_SYMBOLS = {"SPAXX", "FDRXX", "QPISQ"}


def parse_action(action_str):
    """Extract action type from Fidelity action description."""
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
    elif "CHANGE ON MARKET VALUE" in action_str:
        return "market_value_change"
    elif "EXCHANGE" in action_str:
        return "exchange"
    elif "NAME CHANGED" in action_str:
        return "rename"
    else:
        return "other"


def load_account(filepath):
    """Load and parse a Fidelity transaction export."""
    df = pd.read_excel(filepath)
    df["date"] = pd.to_datetime(df["Run Date"], format="%m/%d/%Y")
    df["action_type"] = df["Action"].apply(parse_action)

    # Map symbols
    df["ticker"] = df["Symbol"].apply(
        lambda x: TICKER_MAP.get(str(x), str(x)) if pd.notna(x) else None
    )
    return df


def reconstruct_positions(df, account_filter=None):
    """Reconstruct daily positions from transaction history.

    Returns:
        positions: dict {ticker: {"shares": float, "cost_basis": float}}
        cash_flows: list of (date, amount) for XIRR — positive = money in
        total_invested: total cash deposited
    """
    if account_filter:
        df = df[df["Account"] == account_filter].copy()

    # Sort chronologically
    df = df.sort_values("date").reset_index(drop=True)

    positions = {}  # {ticker: {"shares": float, "cost_basis": float}}
    cash_flows = []  # (date, amount) — negative = money going IN to portfolio
    total_invested = 0.0

    for _, row in df.iterrows():
        action = row["action_type"]
        ticker = row["ticker"]
        qty = row.get("Quantity", 0) or 0
        amount = row.get("Amount", 0) or 0
        price = row.get("Price", 0) or 0
        date = row["date"]

        # Skip money market operations
        if ticker in SKIP_SYMBOLS:
            continue

        if action == "buy" and ticker and qty > 0:
            cost = abs(amount)
            if ticker not in positions:
                positions[ticker] = {"shares": 0.0, "cost_basis": 0.0}
            positions[ticker]["shares"] += qty
            positions[ticker]["cost_basis"] += cost
            # ESPP purchases use paycheck money — count as cash flow
            cash_flows.append((date, -cost))
            total_invested += cost

        elif action == "sell" and ticker and qty < 0:
            sell_shares = abs(qty)
            if ticker in positions and positions[ticker]["shares"] > 0:
                # Reduce cost basis proportionally
                frac = min(sell_shares / positions[ticker]["shares"], 1.0)
                positions[ticker]["cost_basis"] *= (1 - frac)
                positions[ticker]["shares"] -= sell_shares
                # Sell proceeds = cash out of portfolio
                proceeds = abs(amount) if amount > 0 else abs(sell_shares * price)
                cash_flows.append((date, proceeds))
                if positions[ticker]["shares"] < 0.01:
                    del positions[ticker]

        elif action == "reinvestment" and ticker and qty > 0:
            # Dividend reinvestment — adds shares
            reinvest_cost = abs(amount) if amount < 0 else abs(price * qty) if price else 0
            if ticker not in positions:
                positions[ticker] = {"shares": 0.0, "cost_basis": 0.0}
            positions[ticker]["shares"] += qty
            positions[ticker]["cost_basis"] += reinvest_cost

        elif action == "transfer_in" and ticker:
            # RSU vests (CONVERSION SHARES DEPOSITED)
            # Price is NaN but Amount = fair market value at vest
            if ticker not in positions:
                positions[ticker] = {"shares": 0.0, "cost_basis": 0.0}
            if qty > 0:
                positions[ticker]["shares"] += qty
                # Use Amount as cost basis (FMV at vest for RSUs)
                if amount and not np.isnan(amount):
                    fmv = abs(amount)
                    positions[ticker]["cost_basis"] += fmv
                    # RSU vesting = employer compensation, treat as cash flow
                    cash_flows.append((date, -fmv))
                    total_invested += fmv
                elif price and not np.isnan(price):
                    cost = abs(price * qty)
                    positions[ticker]["cost_basis"] += cost
                    cash_flows.append((date, -cost))
                    total_invested += cost

        elif action in ("contribution", "employer_contribution"):
            # 401K / HSA contributions (no associated stock buy in same row)
            cash_in = abs(amount) if amount > 0 else abs(amount)
            total_invested += cash_in
            cash_flows.append((date, -cash_in))

        elif action == "deposit":
            # Electronic fund transfer — just note it, the actual investment
            # is tracked when the buy happens
            pass

        elif action == "withdrawal":
            cash_out = abs(amount)
            total_invested -= cash_out
            cash_flows.append((date, cash_out))

    return positions, cash_flows, total_invested


def get_current_prices(tickers):
    """Get latest prices for a list of tickers."""
    # Use yfinance-compatible tickers
    price_tickers = list(set(tickers))
    try:
        prices = load_price_data(price_tickers, start="2026-01-01", end="2026-02-10")
        latest = {}
        for t in price_tickers:
            if t in prices.columns:
                valid = prices[t].dropna()
                if len(valid) > 0:
                    latest[t] = float(valid.iloc[-1])
        return latest
    except Exception as e:
        print(f"Error loading prices: {e}")
        return {}


def compute_xirr(cash_flows, final_value, final_date):
    """Compute annualized internal rate of return (XIRR).

    cash_flows: list of (date, amount) — negative = money in, positive = money out
    final_value: current portfolio value (treated as final cash out)
    """
    all_flows = list(cash_flows) + [(final_date, final_value)]
    if not all_flows:
        return 0.0

    dates = [cf[0] for cf in all_flows]
    amounts = [cf[1] for cf in all_flows]
    d0 = min(dates)

    def npv(rate):
        total = 0.0
        for d, a in zip(dates, amounts):
            years = (d - d0).days / 365.25
            total += a / (1 + rate) ** years
        return total

    try:
        return brentq(npv, -0.5, 10.0, maxiter=1000)
    except (ValueError, RuntimeError):
        # If brentq fails, try a narrower range
        try:
            return brentq(npv, -0.3, 5.0, maxiter=1000)
        except (ValueError, RuntimeError):
            return float("nan")


def analyze_account(name, df, account_filter=None):
    """Analyze a single account/sub-account."""
    positions, cash_flows, total_invested = reconstruct_positions(df, account_filter)

    if not positions:
        return None

    # Get current prices
    tickers = list(positions.keys())
    current_prices = get_current_prices(tickers)

    # Calculate current value per position
    holdings = []
    total_value = 0.0
    total_cost = 0.0

    for ticker, pos in sorted(positions.items(), key=lambda x: -x[1]["cost_basis"]):
        price = current_prices.get(ticker, 0)
        value = pos["shares"] * price
        cost = pos["cost_basis"]
        gain = value - cost
        gain_pct = (gain / cost * 100) if cost > 0 else 0

        holdings.append({
            "ticker": ticker,
            "shares": pos["shares"],
            "avg_cost": cost / pos["shares"] if pos["shares"] > 0 else 0,
            "current_price": price,
            "cost_basis": cost,
            "market_value": value,
            "gain_loss": gain,
            "gain_loss_pct": gain_pct,
        })
        total_value += value
        total_cost += cost

    # Allocation weights
    for h in holdings:
        h["weight"] = (h["market_value"] / total_value * 100) if total_value > 0 else 0

    # XIRR
    final_date = pd.Timestamp("2026-02-07")  # approximate current date
    xirr = compute_xirr(cash_flows, total_value, final_date) if cash_flows else float("nan")

    # Simple return
    simple_return = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

    return {
        "name": name,
        "holdings": holdings,
        "total_invested": total_invested,
        "total_cost_basis": total_cost,
        "total_market_value": total_value,
        "total_gain": total_value - total_cost,
        "simple_return_pct": simple_return,
        "xirr": xirr,
        "cash_flows": cash_flows,
    }


def format_currency(val):
    return f"${val:,.2f}" if val >= 0 else f"-${abs(val):,.2f}"


def print_account_report(result):
    """Print a formatted report for one account."""
    if result is None:
        return

    print(f"\n{'='*70}")
    print(f"  {result['name']}")
    print(f"{'='*70}")

    print(f"\n  {'Ticker':<8} {'Shares':>10} {'Avg Cost':>10} {'Price':>10} {'Cost Basis':>12} {'Mkt Value':>12} {'Gain/Loss':>12} {'G/L %':>8} {'Wt%':>6}")
    print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*8} {'-'*6}")

    for h in result["holdings"]:
        gl_str = f"{h['gain_loss_pct']:+.1f}%"
        print(f"  {h['ticker']:<8} {h['shares']:>10.2f} {h['avg_cost']:>10.2f} {h['current_price']:>10.2f} "
              f"{format_currency(h['cost_basis']):>12} {format_currency(h['market_value']):>12} "
              f"{format_currency(h['gain_loss']):>12} {gl_str:>8} {h['weight']:>5.1f}%")

    print(f"\n  {'─'*50}")
    print(f"  Total Cost Basis:    {format_currency(result['total_cost_basis'])}")
    print(f"  Total Market Value:  {format_currency(result['total_market_value'])}")
    print(f"  Total Gain/Loss:     {format_currency(result['total_gain'])} ({result['simple_return_pct']:+.1f}%)")
    if result["total_invested"] > 0:
        print(f"  Total Cash Invested: {format_currency(result['total_invested'])}")
    if not np.isnan(result["xirr"]):
        print(f"  XIRR (annualized):   {result['xirr']:.1%}")
    print()


def plot_combined_performance(results, output_dir):
    """Generate comparison charts."""
    os.makedirs(output_dir, exist_ok=True)

    # 1. Holdings breakdown per account
    fig, axes = plt.subplots(1, len(results), figsize=(7 * len(results), 6))
    if len(results) == 1:
        axes = [axes]

    for ax, result in zip(axes, results):
        tickers = [h["ticker"] for h in result["holdings"]]
        values = [h["market_value"] for h in result["holdings"]]
        colors = plt.cm.Set3(np.linspace(0, 1, len(tickers)))

        wedges, texts, autotexts = ax.pie(
            values, labels=tickers, autopct="%1.1f%%",
            colors=colors, pctdistance=0.85
        )
        ax.set_title(f"{result['name']}\n{format_currency(result['total_market_value'])}")

    fig.suptitle("Portfolio Allocation by Account", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "allocation.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # 2. Gain/loss by position (combined)
    all_holdings = []
    for r in results:
        for h in r["holdings"]:
            all_holdings.append(h)
    all_holdings.sort(key=lambda x: x["gain_loss"], reverse=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    tickers = [h["ticker"] for h in all_holdings]
    gains = [h["gain_loss"] for h in all_holdings]
    colors = ["green" if g >= 0 else "red" for g in gains]
    ax.barh(tickers, gains, color=colors, alpha=0.7)
    ax.set_xlabel("Gain/Loss ($)")
    ax.set_title("Unrealized Gain/Loss by Position (All Accounts)")
    ax.axvline(x=0, color="black", linewidth=0.5)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "gain_loss.png"), dpi=150)
    plt.close(fig)

    # 3. Summary comparison bar chart
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    names = [r["name"] for r in results]
    invested = [r["total_cost_basis"] for r in results]
    current = [r["total_market_value"] for r in results]

    x = np.arange(len(names))
    width = 0.35
    axes[0].bar(x - width/2, invested, width, label="Cost Basis", color="steelblue", alpha=0.8)
    axes[0].bar(x + width/2, current, width, label="Market Value", color="green", alpha=0.8)
    axes[0].set_ylabel("$")
    axes[0].set_title("Cost Basis vs Market Value")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(names, rotation=15)
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.3)

    returns = [r["simple_return_pct"] for r in results]
    colors = ["green" if r >= 0 else "red" for r in returns]
    axes[1].bar(names, returns, color=colors, alpha=0.7)
    axes[1].set_ylabel("Return (%)")
    axes[1].set_title("Simple Return by Account")
    axes[1].grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "summary.png"), dpi=150)
    plt.close(fig)


def main():
    output_dir = "output/portfolio_analysis"
    os.makedirs(output_dir, exist_ok=True)

    # Load accounts
    print("Loading Y account...")
    y_df = load_account("input/Yccount.xlsx")

    print("Loading Z account...")
    z_df = load_account("input/Zccount.xlsx")

    results = []

    # Y account (single brokerage)
    print("\nAnalyzing Y account (Fidelity Brokerage)...")
    y_result = analyze_account("Y Account (Brokerage)", y_df)
    if y_result:
        results.append(y_result)
        print_account_report(y_result)

    # Z account — Individual
    print("Analyzing Z account — Individual...")
    z_ind = analyze_account("Z Individual (TOD)", z_df, account_filter="Individual - TOD")
    if z_ind:
        results.append(z_ind)
        print_account_report(z_ind)

    # Z account — HSA
    print("Analyzing Z account — HSA...")
    z_hsa = analyze_account("Z HSA", z_df, account_filter="Health Savings Account")
    if z_hsa:
        results.append(z_hsa)
        print_account_report(z_hsa)

    # Z account — 401K (contributions only, no stock symbols)
    print("Analyzing Z account — 401K...")
    z_401k_df = z_df[z_df["Account"] == "MICROSOFT 401K PLAN"].copy()
    z_401k_contribs = z_401k_df[z_401k_df["action_type"].isin(["contribution", "employer_contribution"])]
    total_401k_contributed = z_401k_contribs["Amount"].abs().sum()

    # 401K: we can't track positions (no symbols), just summarize contributions
    print(f"\n{'='*70}")
    print(f"  Z 401K (Microsoft)")
    print(f"{'='*70}")
    print(f"  Total Contributions (data period): {format_currency(total_401k_contributed)}")
    # Check if contributions come in pairs (employee + employer)
    dates_with_contribs = z_401k_contribs.groupby("date").agg(
        count=("Amount", "count"),
        total=("Amount", lambda x: x.abs().sum())
    )
    print(f"  Contribution events: {len(dates_with_contribs)}")
    print(f"  Entries per event: {dates_with_contribs['count'].mode().iloc[0]} (pairs = employee + employer or 2 funds)")
    avg_per_event = dates_with_contribs["total"].mean()
    print(f"  Avg per event: {format_currency(avg_per_event)}")
    print(f"\n  NOTE: 401K has no ticker data — contributions go to index funds")
    print(f"  managed by Fidelity. Cannot track exact positions or returns.")
    print()

    # Combined summary
    print(f"\n{'='*70}")
    print(f"  COMBINED PORTFOLIO SUMMARY")
    print(f"{'='*70}")
    total_cost = sum(r["total_cost_basis"] for r in results)
    total_value = sum(r["total_market_value"] for r in results)
    total_gain = total_value - total_cost
    combined_return = (total_gain / total_cost * 100) if total_cost > 0 else 0

    print(f"  Total Cost Basis (excl 401K):    {format_currency(total_cost)}")
    print(f"  Total Market Value (excl 401K):  {format_currency(total_value)}")
    print(f"  Total Gain/Loss:                 {format_currency(total_gain)} ({combined_return:+.1f}%)")
    print(f"  401K Contributions:              {format_currency(total_401k_contributed)}")
    print()

    # Generate charts
    if results:
        print("Generating charts...")
        plot_combined_performance(results, output_dir)
        print(f"Charts saved to {output_dir}/")

    # Save summary JSON
    summary = {
        "generated": datetime.now().isoformat(),
        "accounts": [],
    }
    for r in results:
        summary["accounts"].append({
            "name": r["name"],
            "total_cost_basis": round(r["total_cost_basis"], 2),
            "total_market_value": round(r["total_market_value"], 2),
            "total_gain": round(r["total_gain"], 2),
            "simple_return_pct": round(r["simple_return_pct"], 2),
            "xirr": round(r["xirr"], 4) if not np.isnan(r["xirr"]) else None,
            "holdings": [{k: round(v, 2) if isinstance(v, float) else v
                          for k, v in h.items()} for h in r["holdings"]],
        })
    summary["combined"] = {
        "total_cost_basis": round(total_cost, 2),
        "total_market_value": round(total_value, 2),
        "total_gain": round(total_gain, 2),
        "simple_return_pct": round(combined_return, 2),
        "total_401k_contributions": round(total_401k_contributed, 2),
    }
    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Summary saved to {output_dir}/summary.json")


if __name__ == "__main__":
    main()
