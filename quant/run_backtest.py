"""Entry point: run the multi-factor backtest and generate reports."""
import argparse
import os
import sys
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.data_loader import load_price_data, load_vix, load_yield_spread, load_fundamental_data
from quant.backtest import Backtester
from quant.screener import filter_universe


# Default universe (from existing output/)
UNIVERSE = [
    "AAPL", "AMZN", "AVGO", "CSGP", "EXLS", "FCX", "GOOGL",
    "LMT", "MSFT", "PLTR", "SNOW", "TSLA", "V", "ZG",
]

START_DATE = "2016-01-01"
END_DATE = "2026-02-01"
INITIAL_CASH = 100_000.0
OUTPUT_DIR = "output/backtest"


def load_fair_values(universe, output_dir="output"):
    """Load DCF fair values from meta.json files."""
    fair_values = {}
    for ticker in universe:
        data = load_fundamental_data(ticker, output_dir)
        meta = data.get("meta", {})
        fv_str = meta.get("Fair Value / Share ", "")
        try:
            fair_values[ticker] = float(str(fv_str).replace(",", ""))
        except (ValueError, TypeError):
            fair_values[ticker] = np.nan
    return fair_values


def create_universe_function(output_dir="output", screener_config=None):
    """Create a callable that returns (universe, fair_values) for a given date.

    The screener runs once at creation time (fair values are static DCF estimates).
    Returns a function: date -> (list[str], dict[str, float])
    """
    config = screener_config or {}
    result = filter_universe(
        output_dir=output_dir,
        skip_sectors=config.get("skip_sectors", ("BANK", "INSURANCE")),
        min_fair_value=config.get("min_fair_value", 1.0),
        require_usd=config.get("require_usd", True),
    )
    qualified = result["qualified"]
    universe = sorted(qualified.keys())
    fair_values = dict(qualified)

    def universe_func(date):
        return universe, fair_values

    return universe_func, universe, fair_values, result["rejected"]


def plot_results(result, output_dir):
    """Generate performance charts."""
    os.makedirs(output_dir, exist_ok=True)
    nav = result["nav"]
    bench = result["benchmark_nav"]

    # 1. NAV curve
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(nav.index, nav.values, label="Strategy", linewidth=1.5)
    ax.plot(bench.index, bench.values, label="SPY (Buy & Hold)", linewidth=1.5, alpha=0.7)
    ax.set_title("Portfolio NAV: Strategy vs SPY")
    ax.set_ylabel("Portfolio Value ($)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "nav_curve.png"), dpi=150)
    plt.close(fig)

    # 2. Drawdown curve
    peak = nav.cummax()
    dd = (peak - nav) / peak * 100
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(dd.index, dd.values, alpha=0.4, color="red")
    ax.set_title("Strategy Drawdown")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "drawdown.png"), dpi=150)
    plt.close(fig)

    # 3. Monthly returns heatmap
    _freq = "M"  # month-end frequency
    monthly_returns = nav.resample(_freq).last().pct_change().dropna()
    if len(monthly_returns) == 0:
        return
    monthly_df = pd.DataFrame({
        "year": monthly_returns.index.year,
        "month": monthly_returns.index.month,
        "return": monthly_returns.values * 100,
    })
    pivot = monthly_df.pivot_table(index="year", columns="month", values="return", aggfunc="first")
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto",
                   vmin=-10, vmax=10)
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


def print_report(result, mode="static"):
    """Print performance summary to console."""
    m = result["metrics"]
    print("\n" + "=" * 60)
    print(f"  BACKTEST RESULTS ({mode.upper()} mode)")
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

    trades = result["trades"]
    if not trades.empty:
        print(f"\n  Total Trades: {len(trades)}")
        print(f"  Buys:  {len(trades[trades['action'] == 'buy'])}")
        print(f"  Sells: {len(trades[trades['action'] == 'sell'])}")
        universe_exits = trades[trades["reason"] == "universe_exit"]
        if len(universe_exits) > 0:
            print(f"  Universe Exits: {len(universe_exits)}")
    print()


def save_results(result, output_dir):
    """Save metrics, trades, and NAV to output directory."""
    os.makedirs(output_dir, exist_ok=True)

    # Save metrics
    metrics_path = os.path.join(output_dir, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(
            {k: round(v, 4) if isinstance(v, float) and np.isfinite(v) else str(v)
             for k, v in result["metrics"].items()},
            f, indent=2,
        )

    # Save trades
    if not result["trades"].empty:
        trades_path = os.path.join(output_dir, "trades.csv")
        result["trades"].to_csv(trades_path, index=False)
        print(f"Trades saved to {trades_path}")

    # Save daily NAV
    nav_path = os.path.join(output_dir, "nav.csv")
    result["nav"].to_csv(nav_path)
    print(f"NAV saved to {nav_path}")

    print(f"\nAll outputs saved to {output_dir}/")


def run_static():
    """Run backtest with hardcoded static universe (Phase 1 behavior)."""
    output_dir = OUTPUT_DIR

    print("Loading price data...")
    all_tickers = UNIVERSE + ["SPY"]
    prices = load_price_data(all_tickers, start=START_DATE, end=END_DATE)

    valid_universe = [t for t in UNIVERSE if t in prices.columns and prices[t].dropna().shape[0] > 252]
    print(f"Valid universe: {len(valid_universe)} stocks: {valid_universe}")

    print("Loading macro data...")
    vix = load_vix(start=START_DATE, end=END_DATE)
    spread = load_yield_spread(start=START_DATE, end=END_DATE)

    print("Loading DCF fair values...")
    fair_values = load_fair_values(valid_universe)
    print("Fair values:", {k: f"${v:.2f}" if np.isfinite(v) else "N/A" for k, v in fair_values.items()})

    print("Running backtest...")
    bt = Backtester(
        prices=prices,
        universe=valid_universe,
        fair_values=fair_values,
        benchmark="SPY",
        initial_cash=INITIAL_CASH,
        vix=vix,
        yield_spread=spread,
    )
    result = bt.run()

    print_report(result, mode="static")
    plot_results(result, output_dir)
    save_results(result, output_dir)


def run_dynamic():
    """Run backtest with screener-driven dynamic universe."""
    output_dir = "output/backtest_dynamic"

    print("Running screener to discover qualified stocks...")
    universe_func, universe, fair_values, rejected = create_universe_function()
    print(f"Qualified: {len(universe)} stocks: {universe}")
    print(f"Rejected: {len(rejected)} stocks: {rejected}")

    print("Loading price data...")
    all_tickers = universe + ["SPY"]
    prices = load_price_data(all_tickers, start=START_DATE, end=END_DATE)

    valid_universe = [t for t in universe if t in prices.columns and prices[t].dropna().shape[0] > 252]
    print(f"Valid universe (after price filter): {len(valid_universe)} stocks: {valid_universe}")

    # Rebuild universe_func with only valid tickers
    valid_fv = {t: fair_values[t] for t in valid_universe}

    def valid_universe_func(date):
        return valid_universe, valid_fv

    print("Loading macro data...")
    vix = load_vix(start=START_DATE, end=END_DATE)
    spread = load_yield_spread(start=START_DATE, end=END_DATE)

    print("Running dynamic backtest...")
    bt = Backtester(
        prices=prices,
        universe=valid_universe,
        fair_values=valid_fv,
        benchmark="SPY",
        initial_cash=INITIAL_CASH,
        vix=vix,
        yield_spread=spread,
        universe_func=valid_universe_func,
    )
    result = bt.run()

    print_report(result, mode="dynamic")
    plot_results(result, output_dir)
    save_results(result, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Run multi-factor backtest")
    parser.add_argument(
        "--mode",
        choices=["static", "dynamic"],
        default="static",
        help="static: hardcoded 14-stock universe; dynamic: screener-driven universe",
    )
    args = parser.parse_args()

    if args.mode == "dynamic":
        run_dynamic()
    else:
        run_static()


if __name__ == "__main__":
    main()
