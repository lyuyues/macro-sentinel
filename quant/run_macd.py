"""Entry point: run MACD triple divergence backtest and generate reports."""
import argparse
import os
import sys
import json

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yfinance as yf

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant.macd_strategy import MACDConfig
from quant.macd_backtest import MACDBacktester

# Same 14-stock universe as existing system
UNIVERSE = [
    "AAPL", "AMZN", "AVGO", "CSGP", "EXLS", "FCX", "GOOGL",
    "LMT", "MSFT", "PLTR", "SNOW", "TSLA", "V", "ZG",
]

START_DATE = "2016-01-01"
END_DATE = "2026-02-01"
INITIAL_CASH = 100_000.0
OUTPUT_DIR = "output/backtest_macd"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")


def load_ohlc_data(
    tickers: list,
    start: str = "2016-01-01",
    end: str = "2026-02-01",
    use_cache: bool = True,
) -> tuple:
    """Load daily OHLC data for tickers via yfinance.

    Returns (close_df, high_df, low_df) — each a DataFrame with
    DatetimeIndex and one column per ticker.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = "ohlc_{}_{}_{}.pkl".format(
        "_".join(sorted(tickers)), start, end
    )
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if use_cache and os.path.exists(cache_path):
        data = pd.read_pickle(cache_path)
        return data["close"], data["high"], data["low"]

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)

    if raw.empty:
        empty = pd.DataFrame()
        return empty, empty, empty

    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
        high = raw["High"]
        low = raw["Low"]
    else:
        close = raw[["Close"]].rename(columns={"Close": tickers[0]})
        high = raw[["High"]].rename(columns={"High": tickers[0]})
        low = raw[["Low"]].rename(columns={"Low": tickers[0]})

    for df in [close, high, low]:
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

    if use_cache:
        pd.to_pickle({"close": close, "high": high, "low": low}, cache_path)

    return close, high, low


def plot_results(result, config, prices, output_dir):
    """Generate 5 performance charts."""
    os.makedirs(output_dir, exist_ok=True)
    nav = result["nav"]
    bench = result["benchmark_nav"]

    # 1. NAV curve (strategy vs SPY)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(nav.index, nav.values, label="MACD Divergence", linewidth=1.5)
    ax.plot(bench.index, bench.values, label="SPY (Buy & Hold)", linewidth=1.5, alpha=0.7)
    ax.set_title("MACD Triple Divergence Strategy vs SPY")
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
    ax.set_title("MACD Strategy Drawdown")
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

    # 4. MACD histogram chart per ticker with divergence signal markers
    macd_data = result["macd_data"]
    trades = result["trades"]
    n_tickers = len(macd_data)
    if n_tickers > 0:
        cols = min(3, n_tickers)
        rows = (n_tickers + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 3.5 * rows), squeeze=False)
        for idx, (ticker, mdf) in enumerate(macd_data.items()):
            r, c = divmod(idx, cols)
            ax = axes[r][c]
            hist = mdf["histogram"]
            pos_mask = hist >= 0
            neg_mask = hist < 0
            ax.bar(hist.index[pos_mask], hist.values[pos_mask],
                   color="green", alpha=0.6, width=1)
            ax.bar(hist.index[neg_mask], hist.values[neg_mask],
                   color="red", alpha=0.6, width=1)
            ax.axhline(0, color="gray", linewidth=0.5)

            # Mark buy/sell signals
            buys = [t for t in trades if t["ticker"] == ticker and t["action"] == "buy"]
            sells = [t for t in trades if t["ticker"] == ticker and t["action"] == "sell"]
            if buys:
                ax.scatter([t["date"] for t in buys],
                          [0] * len(buys),
                          marker="^", color="blue", s=40, zorder=5, label="Buy")
            if sells:
                ax.scatter([t["date"] for t in sells],
                          [0] * len(sells),
                          marker="v", color="orange", s=40, zorder=5, label="Sell")

            ax.set_title(f"{ticker} MACD Histogram")
            if buys or sells:
                ax.legend(fontsize=6, loc="upper left")
            ax.grid(True, alpha=0.2)

        for idx in range(n_tickers, rows * cols):
            r, c = divmod(idx, cols)
            axes[r][c].set_visible(False)
        fig.suptitle("MACD Histogram by Ticker", fontsize=14)
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "macd_histograms.png"), dpi=150)
        plt.close(fig)

    # 5. Price chart with buy/sell markers
    plot_trade_markers(prices, trades, output_dir)


def plot_trade_markers(prices, trades, output_dir):
    """Plot price charts with buy/sell markers per ticker."""
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
    print("  MACD TRIPLE DIVERGENCE BACKTEST")
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

    if result["trades"]:
        trades_df = pd.DataFrame(result["trades"])
        trades_path = os.path.join(output_dir, "trades.csv")
        trades_df.to_csv(trades_path, index=False)
        print(f"Trades saved to {trades_path}")

    nav_path = os.path.join(output_dir, "nav.csv")
    result["nav"].to_csv(nav_path)
    print(f"NAV saved to {nav_path}")

    print(f"\nAll outputs saved to {output_dir}/")


def main():
    parser = argparse.ArgumentParser(description="Run MACD triple divergence backtest")
    parser.add_argument("--fast-period", type=int, default=12,
                        help="MACD fast EMA period (default: 12)")
    parser.add_argument("--slow-period", type=int, default=26,
                        help="MACD slow EMA period (default: 26)")
    parser.add_argument("--signal-period", type=int, default=9,
                        help="MACD signal EMA period (default: 9)")
    parser.add_argument("--noise-threshold", type=float, default=0.0,
                        help="Histogram noise threshold (default: 0.0)")
    parser.add_argument("--min-segment-bars", type=int, default=2,
                        help="Minimum bars per segment (default: 2)")
    parser.add_argument("--max-holding", type=int, default=30,
                        help="Max holding days (default: 30)")
    parser.add_argument("--max-positions", type=int, default=5,
                        help="Max concurrent positions (default: 5)")
    parser.add_argument("--no-confirm", action="store_true",
                        help="Disable next-bar histogram confirmation")
    parser.add_argument("--start", type=str, default=START_DATE,
                        help=f"Start date (default: {START_DATE})")
    parser.add_argument("--end", type=str, default=END_DATE,
                        help=f"End date (default: {END_DATE})")
    args = parser.parse_args()

    config = MACDConfig(
        fast_period=args.fast_period,
        slow_period=args.slow_period,
        signal_period=args.signal_period,
        noise_threshold=args.noise_threshold,
        min_segment_bars=args.min_segment_bars,
        max_holding_days=args.max_holding,
        max_positions=args.max_positions,
        confirm_next_bar=not args.no_confirm,
    )

    print("MACD Triple Divergence Config:")
    print(f"  Fast/Slow/Signal: {config.fast_period}/{config.slow_period}/{config.signal_period}")
    print(f"  Noise Threshold:  {config.noise_threshold}")
    print(f"  Min Segment Bars: {config.min_segment_bars}")
    print(f"  Max Holding:      {config.max_holding_days} days")
    print(f"  Max Positions:    {config.max_positions}")
    print(f"  Next-Bar Confirm: {config.confirm_next_bar}")

    print("\nLoading OHLC data...")
    all_tickers = UNIVERSE + ["SPY"]
    close, high, low = load_ohlc_data(all_tickers, start=args.start, end=args.end)

    if close.empty:
        print("ERROR: Failed to load price data.")
        sys.exit(1)

    valid_universe = [t for t in UNIVERSE if t in close.columns and close[t].dropna().shape[0] > 50]
    print(f"Valid universe: {len(valid_universe)} stocks: {valid_universe}")

    print("Running MACD divergence backtest...")
    bt = MACDBacktester(
        prices=close,
        prices_high=high,
        prices_low=low,
        universe=valid_universe,
        config=config,
        benchmark="SPY",
        initial_cash=INITIAL_CASH,
    )
    result = bt.run()

    print_report(result)

    print("Generating charts...")
    plot_results(result, config, close, OUTPUT_DIR)

    save_results(result, OUTPUT_DIR)


if __name__ == "__main__":
    main()
