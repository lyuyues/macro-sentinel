"""Daily backtester for MACD triple divergence strategy."""
import numpy as np
import pandas as pd

from quant.macd_strategy import (
    MACDConfig,
    compute_macd,
    build_histogram_segments,
    detect_triple_divergence,
    check_exit_signal,
)
from quant.portfolio import COST_PER_SIDE
from quant.metrics import (
    total_return,
    cagr,
    max_drawdown,
    annualized_volatility,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    compute_alpha_beta,
)


class MACDBacktester:
    """Daily backtester for MACD triple divergence reversal strategy."""

    def __init__(
        self,
        prices: pd.DataFrame,
        prices_high: pd.DataFrame,
        prices_low: pd.DataFrame,
        universe: list,
        config: MACDConfig = None,
        benchmark: str = "SPY",
        initial_cash: float = 100_000.0,
    ):
        self.prices = prices
        self.prices_high = prices_high
        self.prices_low = prices_low
        self.universe = [t for t in universe if t in prices.columns]
        self.config = config or MACDConfig()
        self.benchmark = benchmark
        self.initial_cash = initial_cash

    def run(self) -> dict:
        """Execute the backtest and return results."""
        config = self.config
        dates = self.prices.index

        # Pre-compute MACD data for all tickers
        macd_data = {}
        all_segments = {}
        for ticker in self.universe:
            macd_df = compute_macd(
                self.prices[ticker],
                fast=config.fast_period,
                slow=config.slow_period,
                signal=config.signal_period,
            )
            macd_data[ticker] = macd_df

        # State
        cash = self.initial_cash
        position_size = self.initial_cash / config.max_positions
        positions = {}  # {ticker: {shares, entry_price, entry_date, entry_idx, stop_loss_price, entry_histogram}}
        nav_series = []
        trade_log = []
        positions_over_time = []

        for i, date in enumerate(dates):
            # Build segments up to current bar for each ticker
            for ticker in self.universe:
                hist_vals = macd_data[ticker]["histogram"].values[:i + 1]
                high_vals = self.prices_high[ticker].values[:i + 1]
                low_vals = self.prices_low[ticker].values[:i + 1]
                all_segments[ticker] = build_histogram_segments(
                    hist_vals, high_vals, low_vals,
                    noise_threshold=config.noise_threshold,
                    min_segment_bars=config.min_segment_bars,
                )

            # --- Check exits first ---
            for ticker in list(positions.keys()):
                pos = positions[ticker]
                current_price = self.prices.loc[date, ticker]
                if not np.isfinite(current_price):
                    continue

                hist_series = macd_data[ticker]["histogram"]
                current_hist = hist_series.iloc[i] if i < len(hist_series) else np.nan
                prev_hist = hist_series.iloc[i - 1] if i > 0 else np.nan

                # Check for bearish divergence (exit signal for longs)
                bearish_signal = None
                segments = all_segments.get(ticker, [])
                div_signal = detect_triple_divergence(segments, current_idx=i)
                if div_signal and div_signal.signal_type == "bearish":
                    bearish_signal = div_signal

                should_exit, reason = check_exit_signal(
                    entry_price=pos["entry_price"],
                    stop_loss_price=pos["stop_loss_price"],
                    entry_bar_idx=pos["entry_idx"],
                    current_bar_idx=i,
                    current_price=current_price,
                    current_histogram=current_hist,
                    prev_histogram=prev_hist,
                    bearish_signal=bearish_signal,
                    config=config,
                )

                if should_exit:
                    sell_value = pos["shares"] * current_price * (1 - COST_PER_SIDE)
                    cash += sell_value
                    trade_log.append({
                        "date": date,
                        "ticker": ticker,
                        "action": "sell",
                        "shares": pos["shares"],
                        "price": current_price,
                        "value": sell_value,
                        "reason": reason,
                        "pnl": (current_price - pos["entry_price"]) * pos["shares"],
                        "holding_days": i - pos["entry_idx"],
                    })
                    del positions[ticker]

            # --- Scan for entries ---
            if len(positions) < config.max_positions:
                candidates = []
                for ticker in self.universe:
                    if ticker in positions:
                        continue

                    segments = all_segments.get(ticker, [])
                    div_signal = detect_triple_divergence(segments, current_idx=i)
                    if div_signal and div_signal.signal_type == "bullish":
                        # Signal freshness: only valid within 2 bars of detection
                        if div_signal.bar_idx >= i - 2:
                            # Divergence strength: ratio of first to third peak
                            strength = div_signal.histogram_peaks[0] / div_signal.histogram_peaks[2] if div_signal.histogram_peaks[2] > 0 else 0
                            candidates.append((ticker, div_signal, strength))

                # Sort by divergence strength (strongest first)
                candidates.sort(key=lambda x: -x[2])

                slots = config.max_positions - len(positions)
                for ticker, signal, _ in candidates[:slots]:
                    current_price = self.prices.loc[date, ticker]
                    if not np.isfinite(current_price) or current_price <= 0:
                        continue

                    buy_dollars = min(position_size, cash) * (1 - COST_PER_SIDE)
                    if buy_dollars < 100:
                        break

                    buy_shares = buy_dollars / current_price
                    cash -= buy_dollars / (1 - COST_PER_SIDE)

                    hist_val = macd_data[ticker]["histogram"].iloc[i] if i < len(macd_data[ticker]) else np.nan

                    positions[ticker] = {
                        "shares": buy_shares,
                        "entry_price": current_price,
                        "entry_date": date,
                        "entry_idx": i,
                        "stop_loss_price": signal.stop_loss_price,
                        "entry_histogram": hist_val,
                    }
                    trade_log.append({
                        "date": date,
                        "ticker": ticker,
                        "action": "buy",
                        "shares": buy_shares,
                        "price": current_price,
                        "value": buy_dollars,
                        "reason": f"bullish_divergence",
                        "pnl": 0.0,
                        "holding_days": 0,
                    })

            # --- Record NAV ---
            port_value = cash
            for ticker, pos in positions.items():
                price = self.prices.loc[date, ticker]
                if np.isfinite(price):
                    port_value += pos["shares"] * price
            nav_series.append(port_value)
            positions_over_time.append(len(positions))

        # Build NAV series
        nav = pd.Series(nav_series, index=dates, name="NAV")

        # Benchmark NAV
        bench_col = self.benchmark if self.benchmark in self.prices.columns else self.prices.columns[-1]
        bench_prices = self.prices[bench_col].dropna()
        bench_nav = bench_prices / bench_prices.iloc[0] * self.initial_cash

        # Standard metrics
        alpha, beta = compute_alpha_beta(nav, bench_nav)
        metrics = {
            "total_return": total_return(nav),
            "cagr": cagr(nav),
            "max_drawdown": max_drawdown(nav),
            "volatility": annualized_volatility(nav),
            "sharpe": sharpe_ratio(nav),
            "sortino": sortino_ratio(nav),
            "calmar": calmar_ratio(nav),
            "alpha": alpha,
            "beta": beta,
            "benchmark_return": total_return(bench_nav),
            "benchmark_cagr": cagr(bench_nav),
        }

        # Trade statistics
        sell_trades = [t for t in trade_log if t["action"] == "sell"]
        if sell_trades:
            wins = [t for t in sell_trades if t["pnl"] > 0]
            losses = [t for t in sell_trades if t["pnl"] <= 0]
            metrics["total_trades"] = len(sell_trades)
            metrics["win_rate"] = len(wins) / len(sell_trades)
            metrics["avg_holding_days"] = np.mean([t["holding_days"] for t in sell_trades])
            gross_profit = sum(t["pnl"] for t in wins) if wins else 0
            gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 1
            metrics["profit_factor"] = gross_profit / gross_loss if gross_loss > 0 else float("inf")
            reasons = {}
            for t in sell_trades:
                reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
            metrics["exit_reasons"] = reasons
        else:
            metrics["total_trades"] = 0
            metrics["win_rate"] = 0.0
            metrics["avg_holding_days"] = 0.0
            metrics["profit_factor"] = 0.0
            metrics["exit_reasons"] = {}

        return {
            "nav": nav,
            "benchmark_nav": bench_nav,
            "trades": trade_log,
            "metrics": metrics,
            "macd_data": macd_data,
            "positions_over_time": positions_over_time,
        }
