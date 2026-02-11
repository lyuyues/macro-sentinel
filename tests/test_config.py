"""Tests for BacktestConfig dataclass."""
import pytest
from quant.config import BacktestConfig


class TestBacktestConfig:
    def test_defaults_match_hardcoded_values(self):
        """Default config should match the original hardcoded parameters."""
        cfg = BacktestConfig()
        assert cfg.stop_loss_pct == 0.15
        assert cfg.max_position_weight == 0.20
        assert cfg.momentum_lookback == 126
        assert cfg.sma_window == 200
        assert cfg.factor_weights is None
        assert cfg.disable_trend_filter is False
        assert cfg.label == "default"

    def test_custom_values(self):
        cfg = BacktestConfig(
            stop_loss_pct=0.10,
            max_position_weight=0.30,
            momentum_lookback=63,
            sma_window=100,
            factor_weights={"value": 0.5, "momentum": 0.3, "cycle": 0.2},
            label="custom",
        )
        assert cfg.stop_loss_pct == 0.10
        assert cfg.max_position_weight == 0.30
        assert cfg.momentum_lookback == 63
        assert cfg.sma_window == 100
        assert cfg.factor_weights["value"] == 0.5
        assert cfg.label == "custom"

    def test_disable_trend_filter(self):
        cfg = BacktestConfig(disable_trend_filter=True)
        assert cfg.disable_trend_filter is True


class TestBacktesterWithConfig:
    """Test that Backtester correctly uses config parameters."""

    @pytest.fixture
    def synthetic_data(self):
        import numpy as np
        import pandas as pd

        dates = pd.bdate_range("2023-01-01", "2024-12-31")
        np.random.seed(42)
        prices = pd.DataFrame({
            "AAA": 100 * np.cumprod(1 + np.random.normal(0.0003, 0.02, len(dates))),
            "BBB": 50 * np.cumprod(1 + np.random.normal(0.0002, 0.015, len(dates))),
            "CCC": 200 * np.cumprod(1 + np.random.normal(0.0001, 0.025, len(dates))),
            "SPY": 400 * np.cumprod(1 + np.random.normal(0.0003, 0.01, len(dates))),
        }, index=dates)
        fair_values = {"AAA": 120.0, "BBB": 45.0, "CCC": 250.0}
        return prices, fair_values

    def test_default_config_backward_compatible(self, synthetic_data):
        """Backtester with default config should produce same results as no config."""
        from quant.backtest import Backtester

        prices, fair_values = synthetic_data
        universe = ["AAA", "BBB", "CCC"]

        # Run without config (default)
        bt1 = Backtester(
            prices=prices, universe=universe, fair_values=fair_values,
            benchmark="SPY", initial_cash=100000.0,
        )
        r1 = bt1.run()

        # Run with explicit default config
        bt2 = Backtester(
            prices=prices, universe=universe, fair_values=fair_values,
            benchmark="SPY", initial_cash=100000.0,
            config=BacktestConfig(),
        )
        r2 = bt2.run()

        assert r1["metrics"]["total_return"] == pytest.approx(
            r2["metrics"]["total_return"], rel=1e-6
        )
        assert r1["metrics"]["sharpe"] == pytest.approx(
            r2["metrics"]["sharpe"], rel=1e-6
        )

    def test_config_returned_in_result(self, synthetic_data):
        from quant.backtest import Backtester

        prices, fair_values = synthetic_data
        cfg = BacktestConfig(label="test_label")
        bt = Backtester(
            prices=prices, universe=["AAA", "BBB", "CCC"],
            fair_values=fair_values, benchmark="SPY",
            config=cfg,
        )
        result = bt.run()
        assert result["config"] is cfg
        assert result["config"].label == "test_label"

    def test_custom_factor_weights(self, synthetic_data):
        """Runs with custom factor weights should not crash."""
        from quant.backtest import Backtester

        prices, fair_values = synthetic_data
        cfg = BacktestConfig(
            factor_weights={"value": 1.0, "momentum": 0.0, "cycle": 0.0},
            label="value_only",
        )
        bt = Backtester(
            prices=prices, universe=["AAA", "BBB", "CCC"],
            fair_values=fair_values, benchmark="SPY",
            config=cfg,
        )
        result = bt.run()
        assert result["nav"].iloc[-1] > 0
