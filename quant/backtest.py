"""Monthly rebalancing backtest engine."""
import numpy as np
import pandas as pd
from quant.data_loader import get_monthly_rebalance_dates
from quant.factors import (
    factor_trend_confirmation,
    factor_momentum,
    factor_dcf_discount,
    factor_relative_valuation,
    factor_industry_cycle,
    compute_macro_regime,
    compute_composite_score,
    REGIME_WEIGHTS,
    REGIME_MAX_EXPOSURE,
)
from quant.portfolio import (
    compute_risk_parity_weights,
    apply_position_limits,
    COST_PER_SIDE,
)
from quant.strategy import generate_signals, check_sell_conditions
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


class Backtester:
    """Monthly rebalancing backtester with multi-factor signals."""

    def __init__(
        self,
        prices: pd.DataFrame,
        universe: list,
        fair_values: dict,
        benchmark: str = "SPY",
        initial_cash: float = 100_000.0,
        vix: pd.Series = None,
        yield_spread: pd.Series = None,
        fundamental_data: dict = None,
    ):
        self.prices = prices
        self.universe = universe
        self.fair_values = fair_values
        self.benchmark = benchmark
        self.initial_cash = initial_cash
        self.vix = vix
        self.yield_spread = yield_spread
        self.fundamental_data = fundamental_data or {}

    def run(self) -> dict:
        """Execute the backtest and return results."""
        rebal_dates = get_monthly_rebalance_dates(self.prices.index)
        rebal_set = set(rebal_dates)

        # State
        cash = self.initial_cash
        positions = {}    # {ticker: {"shares": float, "entry_price": float}}
        nav_series = []   # [(date, nav)]
        trade_log = []    # list of trade dicts

        # Track daily NAV
        for date in self.prices.index:
            port_value = cash
            for ticker, pos in positions.items():
                if ticker in self.prices.columns:
                    price = self.prices.loc[date, ticker]
                    if np.isfinite(price):
                        port_value += pos["shares"] * price
            nav_series.append((date, port_value))

            # Monthly rebalancing
            if date in rebal_set:
                cash, positions, new_trades = self._rebalance(
                    date, cash, positions
                )
                trade_log.extend(new_trades)

        # Build NAV series
        nav = pd.Series(
            [v for _, v in nav_series],
            index=pd.DatetimeIndex([d for d, _ in nav_series]),
            name="NAV",
        )

        # Benchmark NAV
        bench_col = self.benchmark if self.benchmark in self.prices.columns else self.prices.columns[-1]
        bench_prices = self.prices[bench_col].dropna()
        bench_nav = bench_prices / bench_prices.iloc[0] * self.initial_cash

        # Metrics
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

        return {
            "nav": nav,
            "benchmark_nav": bench_nav,
            "trades": pd.DataFrame(trade_log) if trade_log else pd.DataFrame(),
            "metrics": metrics,
        }

    def _rebalance(self, date, cash, positions):
        """Execute monthly rebalance logic."""
        new_trades = []

        # Price history up to this date
        hist = self.prices.loc[:date]

        # F5: Macro regime
        spy_col = self.benchmark if self.benchmark in hist.columns else hist.columns[-1]
        spy_hist = hist[spy_col].dropna()

        if self.vix is not None:
            vix_hist = self.vix.loc[:date].dropna()
            if len(vix_hist) == 0:
                vix_hist = pd.Series([20.0], index=[date])
        else:
            vix_hist = pd.Series([20.0], index=[date])

        if self.yield_spread is not None:
            spread_hist = self.yield_spread.loc[:date].dropna()
            if len(spread_hist) == 0:
                spread_hist = pd.Series([1.0], index=[date])
        else:
            spread_hist = pd.Series([1.0], index=[date])

        regime = compute_macro_regime(spy_hist, vix_hist, spread_hist)
        weights_config = REGIME_WEIGHTS[regime]
        max_exposure = REGIME_MAX_EXPOSURE[regime]

        # Per-stock factors
        composite_scores = {}
        trend_flags = {}
        volatilities = {}

        for ticker in self.universe:
            if ticker not in hist.columns:
                continue
            ticker_prices = hist[ticker].dropna()
            if len(ticker_prices) < 50:
                continue

            # F1: DCF discount
            current_price = ticker_prices.iloc[-1]
            fv = self.fair_values.get(ticker, np.nan)
            f1 = factor_dcf_discount(fv, current_price)

            # F2: Relative valuation (price percentile in 1-year history as proxy)
            one_year = ticker_prices.iloc[-252:] if len(ticker_prices) >= 252 else ticker_prices
            f2 = factor_relative_valuation(current_price, one_year)

            # F3: Trend confirmation
            f3_series = factor_trend_confirmation(ticker_prices)
            f3 = bool(f3_series.iloc[-1]) if len(f3_series) > 0 else False
            trend_flags[ticker] = f3

            # F4: Momentum
            f4 = factor_momentum(ticker_prices)

            # F6: Industry cycle (use price growth as proxy)
            if len(ticker_prices) >= 252:
                quarterly_returns = ticker_prices.resample("Q").last().pct_change().dropna()
                rev_growth = quarterly_returns.iloc[-4:] if len(quarterly_returns) >= 4 else quarterly_returns
                margin_proxy = rev_growth
                f6 = factor_industry_cycle(rev_growth, margin_proxy)
            else:
                f6 = 0.5

            # Normalize F1 and F4 to [0, 1] range
            f1_norm = max(0, min(1, (f1 + 0.5)))
            f4_norm = max(0, min(1, (f4 + 0.5)))

            value_score = (f1_norm + f2) / 2.0
            momentum_score = ((1.0 if f3 else 0.0) + f4_norm) / 2.0
            cycle_score = f6

            composite = compute_composite_score(
                {"value": value_score, "momentum": momentum_score, "cycle": cycle_score},
                weights_config,
            )
            composite_scores[ticker] = composite

            # Volatility for risk parity
            returns = ticker_prices.pct_change().dropna()
            vol = float(returns.iloc[-60:].std() * np.sqrt(252)) if len(returns) >= 60 else 0.20
            volatilities[ticker] = vol

        # Signal generation
        selected = generate_signals(
            composite_scores, trend_flags, regime, len(self.universe)
        )

        # Sell check for current positions
        for ticker in list(positions.keys()):
            if ticker not in hist.columns:
                continue
            current_price = hist[ticker].dropna().iloc[-1]
            pos = positions[ticker]
            fv = self.fair_values.get(ticker, np.nan)

            should_sell, reason = check_sell_conditions(
                entry_price=pos["entry_price"],
                current_price=current_price,
                fair_value=fv,
                in_top_n=(ticker in selected),
                trend_confirmed=trend_flags.get(ticker, False),
            )

            if should_sell:
                sell_value = pos["shares"] * current_price * (1 - COST_PER_SIDE)
                cash += sell_value
                new_trades.append({
                    "date": date,
                    "ticker": ticker,
                    "action": "sell",
                    "shares": pos["shares"],
                    "price": current_price,
                    "value": sell_value,
                    "reason": reason,
                })
                del positions[ticker]

        # Buy / rebalance
        if selected:
            sel_vols = {t: volatilities.get(t, 0.20) for t in selected}
            target_weights = compute_risk_parity_weights(sel_vols)
            target_weights = apply_position_limits(target_weights, max_weight=0.20)

            # Total portfolio value
            port_value = cash + sum(
                pos["shares"] * hist[t].dropna().iloc[-1]
                for t, pos in positions.items()
                if t in hist.columns
            )
            investable = port_value * max_exposure

            for ticker, weight in target_weights.items():
                if ticker not in hist.columns:
                    continue
                current_price = hist[ticker].dropna().iloc[-1]
                target_value = investable * weight
                current_value = (
                    positions[ticker]["shares"] * current_price
                    if ticker in positions else 0.0
                )
                diff = target_value - current_value

                if diff > port_value * 0.01 and cash > diff * 0.5:
                    buy_dollars = min(diff, cash) * (1 - COST_PER_SIDE)
                    buy_shares = buy_dollars / current_price
                    cash -= buy_dollars / (1 - COST_PER_SIDE)

                    if ticker in positions:
                        old = positions[ticker]
                        total_shares = old["shares"] + buy_shares
                        avg_price = (
                            (old["entry_price"] * old["shares"] + current_price * buy_shares)
                            / total_shares
                        )
                        positions[ticker] = {"shares": total_shares, "entry_price": avg_price}
                    else:
                        positions[ticker] = {"shares": buy_shares, "entry_price": current_price}

                    new_trades.append({
                        "date": date,
                        "ticker": ticker,
                        "action": "buy",
                        "shares": buy_shares,
                        "price": current_price,
                        "value": buy_dollars,
                        "reason": "signal",
                    })

        return cash, positions, new_trades
