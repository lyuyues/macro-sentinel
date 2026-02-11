"""Entry point: run BNF 25-day MA deviation rate backtest and generate reports."""
import argparse
import os
import sys
import json

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.data_loader import load_price_data
from quant.bnf_strategy import BNFConfig
from quant.bnf_backtest import BNFBacktester


# Same 14-stock universe as existing system
UNIVERSE = [
    "AAPL", "AMZN", "AVGO", "CSGP", "EXLS", "FCX", "GOOGL",
    "LMT", "MSFT", "PLTR", "SNOW", "TSLA", "V", "ZG",
]

START_DATE = "2016-01-01"
END_DATE = "2026-02-01"
INITIAL_CASH = 100_000.0
OUTPUT_DIR = "output/backtest_bnf"


def plot_results(result, config, output_dir):
    """Generate 5 performance charts."""
    os.makedirs(output_dir, exist_ok=True)
    nav = result["nav"]
    bench = result["benchmark_nav"]

    # 1. NAV curve (strategy vs SPY)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(nav.index, nav.values, label="BNF Strategy", linewidth=1.5)
    ax.plot(bench.index, bench.values, label="SPY (Buy & Hold)", linewidth=1.5, alpha=0.7)
    ax.set_title("BNF MA Deviation Strategy vs SPY")
    ax.set_ylabel("Portfolio Value ($)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "nav_curve.png"), dpi=150)
    plt.close(fig)

    # 2. Drawdown
    peak = nav.cummax()
    dd = (peak - nav) / peak * 100
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(dd.index, dd.values, alpha=0.4, color="red")
    ax.set_title("BNF Strategy Drawdown")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "drawdown.png"), dpi=150)
    plt.close(fig)

    # 3. Monthly returns heatmap
    monthly_returns = nav.resample("M").last().pct_change().dropna()
    if len(monthly_returns) > 0:
        monthly_df = pd.DataFrame({
            "year": monthly_returns.index.year,
            "month": monthly_returns.index.month,
            "return": monthly_returns.values * 100,
        })
        pivot = monthly_df.pivot_table(index="year", columns="month", values="return", aggfunc="first")
        fig, ax = plt.subplots(figsize=(12, 6))
        im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto", vmin=-10, vmax=10)
        ax.set_xticks(range(12))
        ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_title("Monthly Returns Heatmap (%)")
        plt.colorbar(im, ax=ax)
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "monthly_heatmap.png"), dpi=150)
        plt.close(fig)

    # 4. Deviation rate chart with threshold lines
    deviations = result["deviations"]
    n_tickers = len(deviations)
    if n_tickers > 0:
        cols = min(3, n_tickers)
        rows = (n_tickers + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 3 * rows), squeeze=False)
        for idx, (ticker, dev) in enumerate(deviations.items()):
            r, c = divmod(idx, cols)
            ax = axes[r][c]
            ax.plot(dev.index, dev.values, linewidth=0.8, color="steelblue")
            ax.axhline(config.entry_threshold, color="green", linestyle="--", alpha=0.7, label=f"Entry ({config.entry_threshold}%)")
            ax.axhline(config.exit_threshold, color="red", linestyle="--", alpha=0.7, label=f"Exit ({config.exit_threshold}%)")
            ax.axhline(0, color="gray", linestyle="-", alpha=0.3)
            ax.set_title(f"{ticker} Deviation Rate")
            ax.set_ylabel("Deviation (%)")
            ax.legend(fontsize=7)
            ax.grid(True, alpha=0.2)
        # Hide empty subplots
        for idx in range(n_tickers, rows * cols):
            r, c = divmod(idx, cols)
            axes[r][c].set_visible(False)
        fig.suptitle("25-Day MA Deviation Rate by Ticker", fontsize=14)
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "deviation_rates.png"), dpi=150)
        plt.close(fig)

    # 5. Price chart with buy/sell markers — handled by plot_trade_markers()


def plot_trade_markers(prices, trades, output_dir):
    """Plot price charts with buy/sell markers per ticker (needs raw prices)."""
    traded_tickers = sorted(set(t["ticker"] for t in trades)) if trades else []
    if not traded_tickers:
        return

    cols = min(3, len(traded_tickers))
    rows = (len(traded_tickers) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 3.5 * rows), squeeze=False)

    for idx, ticker in enumerate(traded_tickers):
        r, c = divmod(idx, cols)
        ax = axes[r][c]

        if ticker in prices.columns:
            ax.plot(prices.index, prices[ticker].values, linewidth=0.8, color="steelblue")

        buys = [t for t in trades if t["ticker"] == ticker and t["action"] == "buy"]
        sells = [t for t in trades if t["ticker"] == ticker and t["action"] == "sell"]
        if buys:
            ax.scatter([t["date"] for t in buys], [t["price"] for t in buys],
                      marker="^", color="green", s=60, zorder=5, label="Buy")
        if sells:
            ax.scatter([t["date"] for t in sells], [t["price"] for t in sells],
                      marker="v", color="red", s=60, zorder=5, label="Sell")
        ax.set_title(f"{ticker} Price & Trades")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.2)

    for idx in range(len(traded_tickers), rows * cols):
        r, c = divmod(idx, cols)
        axes[r][c].set_visible(False)

    fig.suptitle("Price Charts with Buy/Sell Markers", fontsize=14)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "trade_markers.png"), dpi=150)
    plt.close(fig)


def print_report(result):
    """Print performance summary to console."""
    m = result["metrics"]
    print("\n" + "=" * 60)
    print("  BNF 25-DAY MA DEVIATION RATE BACKTEST")
    print("=" * 60)
    print(f"  Total Return:       {m['total_return']:.1%}")
    print(f"  CAGR:               {m['cagr']:.1%}")
    print(f"  Max Drawdown:       {m['max_drawdown']:.1%}")
    print(f"  Volatility:         {m['volatility']:.1%}")
    print(f"  Sharpe Ratio:       {m['sharpe']:.2f}")
    print(f"  Sortino Ratio:      {m['sortino']:.2f}")
    print(f"  Calmar Ratio:       {m['calmar']:.2f}")
    print(f"  Alpha:              {m['alpha']:.2%}")
    print(f"  Beta:               {m['beta']:.2f}")
    print("-" * 60)
    print(f"  Benchmark Return:   {m['benchmark_return']:.1%}")
    print(f"  Benchmark CAGR:     {m['benchmark_cagr']:.1%}")
    print(f"  Excess Return:      {m['total_return'] - m['benchmark_return']:.1%}")
    print("=" * 60)

    # BNF trade statistics
    print("\n  TRADE STATISTICS")
    print("-" * 60)
    print(f"  Total Trades:       {m['total_trades']}")
    print(f"  Win Rate:           {m['win_rate']:.1%}")
    print(f"  Avg Holding Days:   {m['avg_holding_days']:.1f}")
    print(f"  Profit Factor:      {m['profit_factor']:.2f}")

    reasons = m.get("exit_reasons", {})
    if reasons:
        print("\n  Exit Reasons:")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason:<20s} {count:>5d}")
    print()


def save_results(result, output_dir):
    """Save metrics, trades, and NAV to output directory."""
    os.makedirs(output_dir, exist_ok=True)

    # Save metrics (exclude non-serializable exit_reasons nested dict)
    metrics_out = {}
    for k, v in result["metrics"].items():
        if k == "exit_reasons":
            metrics_out[k] = v
        elif isinstance(v, float) and np.isfinite(v):
            metrics_out[k] = round(v, 4)
        else:
            metrics_out[k] = str(v)

    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics_out, f, indent=2)

    # Save trades
    if result["trades"]:
        trades_df = pd.DataFrame(result["trades"])
        trades_path = os.path.join(output_dir, "trades.csv")
        trades_df.to_csv(trades_path, index=False)
        print(f"Trades saved to {trades_path}")

    # Save daily NAV
    nav_path = os.path.join(output_dir, "nav.csv")
    result["nav"].to_csv(nav_path)
    print(f"NAV saved to {nav_path}")

    print(f"\nAll outputs saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Run BNF 25-day MA deviation rate backtest")
    parser.add_argument("--entry-threshold", type=float, default=-10.0,
                        help="Entry deviation threshold %% (default: -10)")
    parser.add_argument("--exit-threshold", type=float, default=0.0,
                        help="Exit deviation threshold %% (default: 0)")
    parser.add_argument("--stop-loss", type=float, default=0.08,
                        help="Stop loss percentage (default: 0.08)")
    parser.add_argument("--max-holding", type=int, default=20,
                        help="Max holding days (default: 20)")
    parser.add_argument("--max-positions", type=int, default=5,
                        help="Max concurrent positions (default: 5)")
    parser.add_argument("--start", type=str, default=START_DATE,
                        help=f"Start date (default: {START_DATE})")
    parser.add_argument("--end", type=str, default=END_DATE,
                        help=f"End date (default: {END_DATE})")
    args = parser.parse_args()

    config = BNFConfig(
        entry_threshold=args.entry_threshold,
        exit_threshold=args.exit_threshold,
        stop_loss_pct=args.stop_loss,
        max_holding_days=args.max_holding,
        max_positions=args.max_positions,
    )

    print(f"BNF Strategy Config:")
    print(f"  MA Window:        {config.ma_window}")
    print(f"  Entry Threshold:  {config.entry_threshold}%")
    print(f"  Exit Threshold:   {config.exit_threshold}%")
    print(f"  Stop Loss:        {config.stop_loss_pct:.0%}")
    print(f"  Max Holding:      {config.max_holding_days} days")
    print(f"  Max Positions:    {config.max_positions}")

    print("\nLoading price data...")
    all_tickers = UNIVERSE + ["SPY"]
    prices = load_price_data(all_tickers, start=args.start, end=args.end)

    valid_universe = [t for t in UNIVERSE if t in prices.columns and prices[t].dropna().shape[0] > 50]
    print(f"Valid universe: {len(valid_universe)} stocks: {valid_universe}")

    print("Running BNF backtest...")
    bt = BNFBacktester(
        prices=prices,
        universe=valid_universe,
        config=config,
        benchmark="SPY",
        initial_cash=INITIAL_CASH,
    )
    result = bt.run()

    print_report(result)

    print("Generating charts...")
    plot_results(result, config, OUTPUT_DIR)
    plot_trade_markers(prices, result["trades"], OUTPUT_DIR)

    save_results(result, OUTPUT_DIR)


if __name__ == "__main__":
    main()
