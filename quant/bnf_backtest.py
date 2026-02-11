"""Daily backtester for BNF 25-day MA deviation rate strategy."""
import numpy as np
import pandas as pd

from quant.bnf_strategy import BNFConfig, compute_ma_deviation, check_entry_signal, check_exit_signal
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


class BNFBacktester:
    """Daily backtester for BNF mean-reversion strategy."""

    def __init__(
        self,
        prices: pd.DataFrame,
        universe: list,
        config: BNFConfig = None,
        benchmark: str = "SPY",
        initial_cash: float = 100_000.0,
    ):
        self.prices = prices
        self.universe = [t for t in universe if t in prices.columns]
        self.config = config or BNFConfig()
        self.benchmark = benchmark
        self.initial_cash = initial_cash

    def run(self) -> dict:
        """Execute the backtest and return results."""
        config = self.config

        # Pre-compute deviation series for all tickers (vectorized)
        deviations = {}
        for ticker in self.universe:
            deviations[ticker] = compute_ma_deviation(
                self.prices[ticker], window=config.ma_window
            )

        # State
        cash = self.initial_cash
        position_size = self.initial_cash / config.max_positions
        positions = {}  # {ticker: {"shares", "entry_price", "entry_date", "entry_idx"}}
        nav_series = []
        trade_log = []
        positions_over_time = []

        dates = self.prices.index

        for i, date in enumerate(dates):
            # --- Check exits first ---
            for ticker in list(positions.keys()):
                pos = positions[ticker]
                current_price = self.prices.loc[date, ticker]
                if not np.isfinite(current_price):
                    continue

                dev_val = deviations[ticker].iloc[i] if i < len(deviations[ticker]) else np.nan
                holding_days = i - pos["entry_idx"]

                should_exit, reason = check_exit_signal(
                    current_deviation=dev_val,
                    entry_price=pos["entry_price"],
                    current_price=current_price,
                    holding_days=holding_days,
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
                        "holding_days": holding_days,
                    })
                    del positions[ticker]

            # --- Scan for entries ---
            if len(positions) < config.max_positions:
                # Build candidate list sorted by most oversold
                candidates = []
                for ticker in self.universe:
                    if ticker in positions:
                        continue
                    dev_val = deviations[ticker].iloc[i] if i < len(deviations[ticker]) else np.nan
                    if check_entry_signal(dev_val, config):
                        candidates.append((ticker, dev_val))

                # Sort by most oversold first (most negative deviation)
                candidates.sort(key=lambda x: x[1])

                slots = config.max_positions - len(positions)
                for ticker, dev_val in candidates[:slots]:
                    current_price = self.prices.loc[date, ticker]
                    if not np.isfinite(current_price) or current_price <= 0:
                        continue

                    buy_dollars = min(position_size, cash) * (1 - COST_PER_SIDE)
                    if buy_dollars < 100:  # minimum trade size
                        break

                    buy_shares = buy_dollars / current_price
                    cash -= buy_dollars / (1 - COST_PER_SIDE)

                    positions[ticker] = {
                        "shares": buy_shares,
                        "entry_price": current_price,
                        "entry_date": date,
                        "entry_idx": i,
                    }
                    trade_log.append({
                        "date": date,
                        "ticker": ticker,
                        "action": "buy",
                        "shares": buy_shares,
                        "price": current_price,
                        "value": buy_dollars,
                        "reason": f"deviation={dev_val:.1f}%",
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

        # BNF-specific trade statistics
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
            # Exit reason breakdown
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
            "deviations": deviations,
            "positions_over_time": positions_over_time,
        }
