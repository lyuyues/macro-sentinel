"""BNF (小手川隆) 25-day MA deviation rate mean-reversion strategy."""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BNFConfig:
    """Configuration for BNF deviation rate strategy."""

    ma_window: int = 25
    entry_threshold: float = -10.0  # buy when deviation < -10%
    exit_threshold: float = 0.0  # sell when deviation reverts to 0%
    stop_loss_pct: float = 0.08  # 8% stop loss from entry price
    max_holding_days: int = 20  # force exit after 20 trading days
    max_positions: int = 5


def compute_ma_deviation(prices: pd.Series, window: int = 25) -> pd.Series:
    """Compute deviation rate from N-day simple moving average.

    deviation = (close - SMA) / SMA * 100 (percentage)

    Returns NaN for days where SMA is not yet available.
    """
    sma = prices.rolling(window=window, min_periods=window).mean()
    deviation = (prices - sma) / sma * 100.0
    return deviation


def check_entry_signal(deviation: float, config: BNFConfig) -> bool:
    """Check if deviation is below entry threshold (oversold)."""
    if np.isnan(deviation):
        return False
    return deviation < config.entry_threshold


def check_exit_signal(
    current_deviation: float,
    entry_price: float,
    current_price: float,
    holding_days: int,
    config: BNFConfig,
) -> tuple:
    """Check if a position should be exited.

    Returns:
        (should_exit: bool, reason: str)
        reason is one of: "mean_reversion", "stop_loss", "max_holding", ""
    """
    # Stop loss: price dropped too far from entry
    if current_price <= entry_price * (1 - config.stop_loss_pct):
        return True, "stop_loss"

    # Max holding period exceeded
    if holding_days >= config.max_holding_days:
        return True, "max_holding"

    # Mean reversion: deviation reverted to exit threshold
    if not np.isnan(current_deviation) and current_deviation >= config.exit_threshold:
        return True, "mean_reversion"

    return False, ""
