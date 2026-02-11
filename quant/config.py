"""Configuration dataclass for backtest parameters."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class BacktestConfig:
    """All tunable backtest parameters.

    When passed to Backtester, these override the hardcoded defaults.
    Setting factor_weights to None uses the regime-dependent defaults.
    """

    factor_weights: dict | None = None  # {"value": w, "momentum": w, "cycle": w}
    stop_loss_pct: float = 0.15
    max_position_weight: float = 0.20
    momentum_lookback: int = 126
    sma_window: int = 200
    disable_trend_filter: bool = False
    label: str = "default"
